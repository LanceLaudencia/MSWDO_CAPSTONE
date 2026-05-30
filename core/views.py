import json
import calendar
import os
import csv
import requests

import joblib
import pandas as pd
from django.shortcuts import render

from django.db.models import Count
from django.utils import timezone
from ml.model_loader import predict_input
from django.db.models.functions import TruncMonth

from django.utils.timezone import now

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils.encoding import smart_str
from django.shortcuts import render

from django.db.models import Sum

from .models import Client,  ApplicationDocument
from .models import Assistance
from .forms import (
    ClientForm,
    ApplicationForm,
    LoginForm,
    SignupForm,
    DocumentUploadForm,
    AssistanceFilterForm
)

from django.contrib.auth import get_user_model
User = get_user_model()



# In-memory verification codes (development only)
verification_codes = {}


# --- Public Views ---
def landing(request):
    return render(request, 'landing.html')


def select_account(request):
    return render(request, "select_account.html")

def verify_email(request):
    return HttpResponse("Verify Email Page")


def resend_verification(request):
    return HttpResponse("Resend Verification Page")

def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.email = form.cleaned_data.get('email')
        user.is_active = False
        if hasattr(user, 'is_verified'):
            user.is_verified = False
        user.save()

        code = get_random_string(32)
        verification_codes[user.email] = code
        verify_url = request.build_absolute_uri(
            reverse('verify') + f'?email={user.email}&code={code}'
        )
        print("Verification link:", verify_url)

        try:
            send_mail(
                'Verify Your Account',
                f'Click the link to verify your account:\n\n{verify_url}',
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False
            )
        except Exception as e:
            messages.warning(request, f"Could not send email: {e}")

        return render(request, 'signup.html', {
            'form': form,
            'message': 'Verification sent! Check your email or server console.'
        })
    return render(request, 'signup.html', {'form': form})


def verify(request):
    email = request.GET.get('email')
    code = request.GET.get('code')

    if email and code and email in verification_codes and verification_codes[email] == code:
        user = User.objects.filter(email=email).first()
        if not user:
            return render(request, 'login.html', {"message": "User not found."})

        user.is_active = True
        if hasattr(user, 'is_verified'):
            user.is_verified = True
        user.save()
        del verification_codes[email]
        return render(request, 'verify_message.html', {"message": "✔ Email verified successfully! You can now log in."})

    return render(request, 'login.html', {"message": "Invalid verification link or code."})


def login_view(request):
    form = LoginForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()

        if not user.is_active:
            return render(
                request, 
                'login.html', 
                {'form': form, 'message': 'Account inactive.'}
            )

        login(request, user)

        # --- Role Based Redirects ---
        if getattr(user, 'role', None) == 'admin' or user.is_superuser:
            return redirect('admin_account')

        elif getattr(user, 'role', None) == 'staff':
            return redirect('staff_account')

        # Default fallback
        return redirect('dashboard')

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('landing')


# --- Admin View ---
@login_required
def admin_account(request):
    # Only ADMIN can open admin account page
    if getattr(request.user, 'role', None) != 'admin' and not request.user.is_superuser:
        return redirect('dashboard')

    staff_members = User.objects.filter(role='staff')

    return render(request, 'admin_account.html', {
        'admin': request.user,       # 👈 needed by your template
        'staffs': staff_members,     # 👈 rename to match template
    })



@login_required
def update_staff(request, staff_id):
    # Only ADMIN can access this
    if getattr(request.user, 'role', None) != 'admin' and not request.user.is_superuser:
        return redirect('landing')

    staff = get_object_or_404(User, id=staff_id)

    if request.method == 'POST':
        staff.first_name = request.POST.get('first_name')
        staff.last_name = request.POST.get('last_name')
        staff.email = request.POST.get('email')
        staff.role = request.POST.get('role')
        staff.save()
        return redirect('admin_account')

    return render(request, 'update_staff.html', {'staff': staff})


# --- Dashboard & Stats ---
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.utils import timezone
import json
import calendar

from .models import Client, Application

@login_required
def dashboard(request):

    # =============================
    # TIME SETUP
    # =============================
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # =============================
    # BASIC COUNTS
    # =============================
    total_beneficiaries = Client.objects.count()

    pending_applications = Application.objects.filter(
        status='PENDING'
    ).count()

    monthly_disbursements = Application.objects.filter(
        status='RELEASED',
        created_at__gte=start_of_month,
        created_at__lte=now
    ).aggregate(
        total=Sum('released_amount')
    )['total'] or 0

    # =============================
    # PIPELINE COUNTS
    # =============================
    pipeline_counts = {
        'pending':    Application.objects.filter(status='PENDING').count(),
        'assessment': Application.objects.filter(status='ASSESSMENT').count(),
        'approval':   Application.objects.filter(status='APPROVAL').count(),
        'release':    Application.objects.filter(status='RELEASE').count(),
        'released':   Application.objects.filter(status='RELEASED').count(),
        'rejected':   Application.objects.filter(status='REJECTED').count(),
    }

    # =============================
    # BENEFICIARIES PER PROGRAM
    # =============================
    program_data = (
        Application.objects
        .values('aid_type')
        .annotate(count=Count('id'))
        .order_by('aid_type')
    )
    program_labels = [p['aid_type'] for p in program_data]
    program_values = [p['count'] for p in program_data]

    # =============================
    # STATUS DISTRIBUTION
    # =============================
    status_data = (
        Application.objects
        .values('status')
        .annotate(count=Count('id'))
    )
    status_labels = [s['status'].capitalize() for s in status_data]
    status_values = [s['count'] for s in status_data]

    # =============================
    # ELIGIBILITY
    # =============================
    eligibility_labels = ['Eligible', 'Not Eligible']
    eligibility_values = [
        Application.objects.filter(eligibility_result='Eligible').count(),
        Application.objects.filter(eligibility_result='Not Eligible').count(),
    ]

    # =============================
    # CLIENTS OVER TIME (6 MONTHS)
    # =============================
    six_months_ago = now - timedelta(days=180)

    monthly_clients = (
        Client.objects
        .filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    month_labels = [m['month'].strftime('%b %Y') for m in monthly_clients]
    month_values = [m['count'] for m in monthly_clients]

    # =============================
    # SEX DISTRIBUTION
    # =============================
    sex_data = (
        Client.objects
        .values('sex')
        .annotate(count=Count('id'))
        .order_by('sex')
    )
    sex_labels = [s['sex'] or 'Unknown' for s in sex_data]
    sex_values = [s['count'] for s in sex_data]

    # =============================
    # SECTORS DISTRIBUTION
    # =============================
    from collections import Counter
    sector_counter = Counter()
    for client in Client.objects.only('sectors'):
        sectors = client.sectors or []
        if isinstance(sectors, list):
            sector_counter.update(sectors)

    sector_labels = list(sector_counter.keys())
    sector_values = list(sector_counter.values())

    # =============================
    # LATEST APPLICATIONS
    # ✅ Shows every submission from both staff (add_client)
    #    and self-apply (client_apply_program).
    #    Program & Status are always populated since we
    #    query Application directly instead of Client.
    # =============================
    latest_applications = (
        Application.objects
        .select_related('client')
        .order_by('-created_at')[:10]
    )

    # =============================
    # RENDER
    # =============================
    return render(request, 'dashboard.html', {
        'total_beneficiaries':   total_beneficiaries,
        'pending_applications':  pending_applications,
        'monthly_disbursements': monthly_disbursements,
        'pipeline_counts':       pipeline_counts,

        'program_labels': program_labels,
        'program_values': program_values,

        'status_labels': status_labels,
        'status_values': status_values,

        'eligibility_labels': eligibility_labels,
        'eligibility_values': eligibility_values,

        'month_labels': month_labels,
        'month_values': month_values,

        'sex_labels': sex_labels,
        'sex_values': sex_values,

        'sector_labels': sector_labels,
        'sector_values': sector_values,

        'latest_applications': latest_applications,
    })

from datetime import datetime
from decimal import Decimal
from ml.model_loader import predict_input


from .models import (
    AICSDetail,
    SEADetail,
    REDCARDDetail,
    EducationalAssistanceDetail,
)

from .models import FamilyMember
# ==============================
# 👤 ADD CLIENT VIEW
# ==============================

from .ml_predictor import predict_input, compute_score, generate_reason

SECTOR_KEYS = [
    'WEDC','SC','PWD','SP','IP','OFW','TP','PDL',
    'PWUD','IFW','4PS','CNSP','CAR','CICL','OSCY','FR','KASAMBAHAY'
]
 
def add_client(request):
    if not (getattr(request.user, "role", None) in ["staff", "admin"] or request.user.is_superuser):
        return redirect("dashboard")
 
    if request.method == "POST":
        try:
            # ── Collect selected sectors ──────────────────────────
            selected_sectors = [k for k in SECTOR_KEYS if request.POST.get(f"sector_{k}")]
 
            # ── Derive ML flags from sectors ──────────────────────
            has_disability  = "Yes" if "PWD"  in selected_sectors else "No"
            is_senior       = "Yes" if "SC"   in selected_sectors else "No"
            is_solo_parent  = "Yes" if "SP"   in selected_sectors else "No"
            is_indigenous   = "Yes" if "IP"   in selected_sectors else "No"
 
            client = Client.objects.create(
                first_name=request.POST.get("first_name"),
                middle_name=request.POST.get("middle_name") or None,
                last_name=request.POST.get("last_name"),
                sex=request.POST.get("sex"),
                birth_date=datetime.strptime(request.POST.get("birth_date"), "%Y-%m-%d").date(),
                civil_status=request.POST.get("civil_status"),
                nationality=request.POST.get("nationality"),
                address=request.POST.get("address"),
                barangay=request.POST.get("barangay"),
                municipality=request.POST.get("municipality"),
                email=request.POST.get("email") or None,
                contact_no=request.POST.get("contact_no"),
                livelihood=request.POST.get("livelihood"),
                monthly_income=Decimal(request.POST.get("monthly_income") or 0),
                household_size=int(request.POST.get("household_size") or 0),
                # ML-compatible single flags (derived from sectors)
                has_disability=has_disability,
                is_senior=is_senior,
                is_solo_parent=is_solo_parent,
                is_indigenous=is_indigenous,
                previous_aid=request.POST.get("previous_aid", "No"),
                # 4Ps
                is_4ps=request.POST.get("is_4ps", "No"),
                fourps_id=request.POST.get("fourps_id") or None,
                # Full sector list (JSON field)
                sectors=selected_sectors,
            )
 
            # ── Family Members ─────────────────────────────────────
            for index in range(51):
                name = request.POST.get(f"family_name_{index}", "").strip()
                if not name:
                    continue
                civil_status = request.POST.get(f"family_cs_{index}") or None
                education = (
                    "Elem"     if request.POST.get(f"family_edu_elem_{index}") else
                    "HS"       if request.POST.get(f"family_edu_hs_{index}")   else
                    "Coll/Voc" if request.POST.get(f"family_edu_coll_{index}") else
                    "Illit"    if request.POST.get(f"family_edu_illit_{index}") else None
                )
                raw_age    = request.POST.get(f"family_age_{index}", "").strip()
                raw_income = request.POST.get(f"family_inc_{index}", "").strip()
                # Collect multiple sectors for this family member
                SECTOR_KEYS_LOCAL = [
                    'WEDC','SC','PWD','SP','IP','OFW','TP','PDL',
                    'PWUD','IFW','4PS','CNSP','CAR','CICL','OSCY','FR','KASAMBAHAY'
                ]
                member_sectors = [
                    k for k in SECTOR_KEYS_LOCAL
                    if request.POST.get(f"family_sector_{index}_{k}")
                ]
 
                FamilyMember.objects.create(
                    client=client,
                    name=name,
                    age=int(raw_age) if raw_age else None,
                    sex=request.POST.get(f"family_sex_{index}") or None,
                    civil_status=civil_status,
                    relationship=request.POST.get(f"family_rel_{index}") or None,
                    educational_attainment=education,
                    occupation=request.POST.get(f"family_occ_{index}") or None,
                    income=Decimal(raw_income) if raw_income else None,
                    sectors=member_sectors,   # JSONField list
                )
 
            # ── Application ────────────────────────────────────────
            aid_type = request.POST.get("program")
            application = Application.objects.create(
                client=client, aid_type=aid_type, status="PENDING",
            )
 
            # ── ML Prediction ──────────────────────────────────────
            try:
                income = float(client.monthly_income)
                hh     = int(client.household_size) or 1
                ml_input = {
                    "monthly_income":    income,
                    "household_size":    hh,
                    "income_per_person": income / hh,
                    "has_disability":    1 if has_disability  == "Yes" else 0,
                    "is_senior":         1 if is_senior       == "Yes" else 0,
                    "previous_aid":      1 if client.previous_aid == "Yes" else 0,
                    "is_solo_parent":    1 if is_solo_parent  == "Yes" else 0,
                    "is_indigenous":     1 if is_indigenous   == "Yes" else 0,
                    "is_4ps":            1 if client.is_4ps   == "Yes" else 0,
                }
                prediction = predict_input(ml_input, aid_type)
                score      = compute_score(ml_input)
                reason     = generate_reason(ml_input, prediction, aid_type)
                application.eligibility_result = "Eligible" if prediction == 1 else "Not Eligible"
                application.eligibility_score  = score
                application.eligibility_reason = reason
            except Exception as ml_err:
                import traceback; traceback.print_exc()
                application.eligibility_result = "Not Eligible"
                application.eligibility_score  = 0
                application.eligibility_reason = "Eligibility could not be determined automatically. Please assess manually."
 
            application.save()
 
            # ── Program Details & Documents ────────────────────────
            docs = {}
            if aid_type == "AICS":
                AICSDetail.objects.create(application=application, crisis_type=request.POST.get("aics_crisis_type"))
                docs = {"AICS Barangay Cert": request.FILES.get("aics_barangay_cert"), "Medical/Death Cert": request.FILES.get("aics_medical_death_cert"), "Official Receipt": request.FILES.get("aics_receipt")}
            elif aid_type == "SEA":
                SEADetail.objects.create(application=application)
                docs = {"Barangay Clearance": request.FILES.get("sea_barangay_clearance"), "Cedula": request.FILES.get("sea_cedula"), "Project Proposal": request.FILES.get("sea_project_proposal"), "Project Picture": request.FILES.get("sea_project_picture")}
            elif aid_type == "REDCARD":
                REDCARDDetail.objects.create(application=application, emergency_type=request.POST.get("redcard_emergency_type"), reason=request.POST.get("redcard_reason"), usage_count=request.POST.get("redcard_usage") or 1)
                docs = {"Birth Certificate": request.FILES.get("redcard_birth_cert"), "Valid ID Picture": request.FILES.get("redcard_valid_id"), "Certificate of Indigency": request.FILES.get("redcard_indigency")}
            elif aid_type == "EDUCATIONAL":
                EducationalAssistanceDetail.objects.create(application=application, school_name=request.POST.get("school_name"), course_or_grade=request.POST.get("course_level"))
                docs = {"Letter of Appeal": request.FILES.get("edu_letter"), "Certificate of Indigency": request.FILES.get("edu_indigency"), "Grades": request.FILES.get("edu_grades"), "Certificate of Enrollment": request.FILES.get("edu_enrollment"), "Billing Statement": request.FILES.get("edu_billing"), "Official Receipt": request.FILES.get("edu_receipt")}
 
            for doc_name, file in docs.items():
                if file:
                    ApplicationDocument.objects.create(application=application, name=doc_name, file=file)
 
            messages.success(request, "Application submitted successfully!")
            return redirect("application_detail", application.id)
 
        except Exception as e:
            import traceback; traceback.print_exc()
            messages.error(request, f"Submission failed: {e}")
 
    return render(request, "add_client.html")
 
 

    
# --- Simple APIs ---
@login_required
def api_program_counts(request):
    data = list(Application.objects.values('program').annotate(total=Count('id')))
    return JsonResponse(data, safe=False)


@login_required
def api_status_counts(request):
    data = list(Application.objects.values('status').annotate(total=Count('id')))
    return JsonResponse(data, safe=False)


# --- Assistance Program ---
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.db.models import Q

def assistance_program(request, program='SEA'):
    user = request.user

    if not (
        user.is_superuser
        or getattr(user, 'role', None) in ['admin', 'staff']
    ):
        return redirect('landing')

    program = request.GET.get('program', program).upper()

    if program not in ['SEA', 'AICS', 'REDCARD', 'EA', 'EDUCATIONAL']:
        program = 'SEA'

    # Map display code 'EA' → 'EDUCATIONAL' for the DB query
    db_aid_type = 'EDUCATIONAL' if program == 'EA' else program

    qs = (
        Application.objects
        .filter(aid_type=db_aid_type)
        .select_related('client')
        .prefetch_related('documents')
        .order_by('-created_at')
    )

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(client__first_name__icontains=q) |
            Q(client__last_name__icontains=q) |
            Q(client__email__icontains=q)
        )

    # Uppercase to match model STATUS_CHOICES
    status = request.GET.get('status', '').strip().upper()
    if status:
        qs = qs.filter(status=status)

    if request.GET.get('view') == 'pending':
        qs = qs.filter(status='PENDING')

    if request.GET.get('export') == 'csv':
        return assistance_export_csv(qs, program)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'assistance_program.html', {
        'applications': page_obj,
        'program': program,
    })

def assistance_export_csv(qs, program):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{program}_applications.csv"'

    writer = csv.writer(response)
    writer.writerow([
        '#',
        'Full Name',
        'Contact No.',
        'Email',
        'Barangay',
        'Municipality',
        'Livelihood',
        'Monthly Income (₱)',
        'Eligibility',
        'Approved Amount (₱)',
        'Status',
        'Date Submitted',
    ])

    for idx, app in enumerate(qs, start=1):
        client = app.client

        writer.writerow([
            idx,
            smart_str(f"{client.first_name} {client.last_name}"),
            smart_str(client.contact_no or ''),
            smart_str(client.email or ''),
            smart_str(client.barangay or ''),
            smart_str(client.municipality or ''),
            smart_str(client.livelihood or ''),
            f"₱{float(client.monthly_income or 0):,.2f}",
            app.eligibility_result or 'Not evaluated',
            f"₱{float(app.approved_amount or 0):,.2f}",  # ✅ was requested_amount
            app.get_status_display(),
            app.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response



@login_required
def application_detail(request, pk):
    application = get_object_or_404(
        Application.objects.select_related('client').prefetch_related('documents'),
        pk=pk
    )
    client = application.client

    context = {
        'application': application,
        'client': client,
        'documents': application.documents.all(),
        'aid_type': application.aid_type,
        'status': application.status,
        'eligibility_result': application.eligibility_result,
        'family_members': client.family_members.all(),
        'aics':    getattr(application, 'aics_detail', None),
        'sea':     getattr(application, 'sea_detail', None),
        'redcard': getattr(application, 'redcard_detail', None),
        'edu':     getattr(application, 'educational_detail', None),
    }

    return render(request, 'application_detail.html', context)


@login_required
def application_advance(request, pk):
    """
    Advances application through the pipeline:
    PENDING → ASSESSMENT → APPROVAL → RELEASE → RELEASED

    When moving RELEASE → RELEASED the POST body must contain
    'approved_amount' (the amount input in the template form).
    """
    application = get_object_or_404(Application, pk=pk)

    # ── Permission Check ───────────────────────────────────────────────
    if not (getattr(request.user, 'role', None) in ['admin', 'staff']
            or request.user.is_superuser):
        messages.error(request, "You do not have permission to update applications.")
        return redirect('dashboard')

    pipeline = ['PENDING', 'ASSESSMENT', 'APPROVAL', 'RELEASE', 'RELEASED']

    if application.status not in pipeline:
        messages.error(request, "Cannot advance a rejected application.")
        return redirect('application_detail', pk=pk)

    current_index = pipeline.index(application.status)

    if current_index >= len(pipeline) - 1:
        messages.info(request, "Application is already at the final stage.")
        return redirect('application_detail', pk=pk)

    next_status = pipeline[current_index + 1]
    application.status = next_status

    # ── Track Workflow Stages ──────────────────────────────────────────
    if next_status == 'ASSESSMENT':
        application.assessed_by = request.user
        application.assessed_at = timezone.now()

    elif next_status == 'APPROVAL':
        application.approved_by = request.user
        application.approved_at = timezone.now()

    elif next_status == 'RELEASED':
        application.released_at = timezone.now()

        # ✅ Capture amount entered in the RELEASE → RELEASED form
        raw_amount = request.POST.get('approved_amount', '').strip()
        if raw_amount:
            try:
                from decimal import Decimal
                amount = Decimal(raw_amount)
                application.approved_amount = amount
                application.released_amount = amount   # ← drives dashboard Sum
            except Exception:
                messages.warning(
                    request,
                    "Invalid amount entered — amount was not saved. Please edit manually."
                )
        else:
            # Fallback: if approved_amount was already set earlier, copy it
            if application.approved_amount:
                application.released_amount = application.approved_amount

    application.save()

    # ── Notifications & Comms on RELEASED ─────────────────────────────
    if next_status == 'RELEASED':
        client = application.client

        # ---------- EMAIL ----------
        if client.email:
            subject = "Your Assistance Has Been Released — MSWDO"
            message = f"""
Good day {client.full_name},

We are pleased to inform you that your {application.get_aid_type_display()} assistance
application has been RELEASED and is now ready for claiming.

Application Details:
  Program      : {application.get_aid_type_display()}
  Status       : Released
  Date Released: {timezone.now().strftime('%B %d, %Y')}
  {"Released Amount: ₱" + str(application.released_amount) if application.released_amount else ""}

Please visit the MSWDO office to claim your assistance. Bring a valid ID.

Thank you,
MSWDO Office
"""
            try:
                send_mail(
                    subject,
                    message.strip(),
                    None,
                    [client.email],
                    fail_silently=False,
                )
                print("===================================")
                print("EMAIL SENT SUCCESSFULLY")
                print("Recipient:", client.email)
                print("===================================")
            except Exception as e:
                print("===================================")
                print("EMAIL FAILED:", e)
                print("===================================")

        # ---------- SMS ----------
        if client.contact_no:
            sms_message = (
                f"Good day {client.full_name}! "
                f"Your {application.get_aid_type_display()} assistance has been RELEASED. "
                f"Please visit the MSWDO office to claim it. Bring a valid ID."
            )
            try:
                sms_response = send_sms(client.contact_no, sms_message)
                if sms_response.get("success"):
                    print("===================================")
                    print("SMS SENT SUCCESSFULLY")
                    print("Client:", client.full_name)
                    print("Number:", client.contact_no)
                    print("===================================")
                else:
                    print("===================================")
                    print("SMS FAILED:", sms_response.get("error"))
                    print("===================================")
            except Exception as e:
                print("===================================")
                print("SMS ERROR:", e)
                print("===================================")
        else:
            print("No contact number found for this client.")

    messages.success(
        request,
        f"Application moved to: {application.get_status_display()}"
    )
    return redirect('application_detail', pk=pk)

@login_required
def application_delete(request, pk):
    app = get_object_or_404(Application, pk=pk)
    if not (getattr(request.user, 'role', None) == 'admin' or request.user.is_staff or request.user.is_superuser):
        return redirect('assistance_program')
    if request.method == 'POST':
        app.delete()
        messages.success(request, 'Application deleted.')
        return redirect('assistance_program')
    return render(request, 'application_confirm_delete.html', {'application': app})


@login_required
def document_download(request, doc_id):
    doc = get_object_or_404(ApplicationDocument, id=doc_id)
    file_path = doc.file.path
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/octet-stream")
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
    raise Http404




@login_required
def staff_account(request):

    # Allow only STAFF or SUPERUSER
    if not (
        getattr(request.user, 'role', None) == 'staff'
        or request.user.is_superuser
    ):
        return redirect('landing')

    return render(request, 'staff_account.html', {
        'staff': request.user,
        'now': timezone.now(),
    })

    
    


# ---------------- ML Predict API (Optional View) ----------------
@login_required
def ml_predict_view(request):
    # Dashboard stats
    programs = Assistance.objects.annotate(total=Count('application'))
    program_labels = [p.name for p in programs]
    program_values = [p.total for p in programs]

    statuses = Application.objects.values('status').annotate(total=Count('id'))
    status_labels = [s['status'] for s in statuses]
    status_values = [s['total'] for s in statuses]

    # Last 6 months
    now = timezone.now()
    month_labels = []
    month_values = []
    for i in range(6):
        month = (now - timezone.timedelta(days=30 * i)).strftime("%B")
        month_labels.append(month)
        month_values.append(Client.objects.filter(created_at__month=(now.month - i)).count())

    month_labels.reverse()
    month_values.reverse()
    latest_clients = Client.objects.order_by('-created_at')[:5]

    # ---------------- ML Prediction ----------------
    prediction = None
    probability = None
    inputs_used = None

    if request.method == 'POST':
        try:
            inputs_used = {
                "Age": int(request.POST.get("age", 0)),
                "Income_Monthly": float(request.POST.get("income", 0)),
                "Family_Size": int(request.POST.get("family_size", 0)),
                "Sex": request.POST.get("sex", ""),
                "Region": request.POST.get("region", ""),
                "Employment_Status": request.POST.get("employment", ""),
                "Has_Disability": 1 if request.POST.get("disability", "No") == "Yes" else 0,
                "Previous_Aid": request.POST.get("previous_aid", ""),
                "Aid_Type_Applied": request.POST.get("aid_type", ""),
            }

            pred, prob = predict_input(
                inputs_used["Age"],
                inputs_used["Income_Monthly"],
                inputs_used["Family_Size"],
                inputs_used["Sex"],
                inputs_used["Region"],
                inputs_used["Employment_Status"],
                inputs_used["Has_Disability"],
                inputs_used["Previous_Aid"],
                inputs_used["Aid_Type_Applied"],
            )

            prediction = "Eligible" if pred == 1 else "Not Eligible"
            probability = prob

        except Exception as e:
            print("ML prediction error:", e)
            prediction = "Unavailable"
            probability = None

    return render(request, "dashboard.html", {
        "program_labels": program_labels,
        "program_values": program_values,
        "status_labels": status_labels,
        "status_values": status_values,
        "month_labels": month_labels,
        "month_values": month_values,
        "latest_clients": latest_clients,
        "prediction": prediction,
        "probability": probability,
        "inputs_used": inputs_used,
    })
    

@login_required
def pending_applications(request):

    if not (
        getattr(request.user, 'role', None) in ['staff', 'admin']
        or request.user.is_superuser
    ):
        return redirect('landing')

    allowed_programs = ["AICS", "SEA", "REDCARD", "EDUCATIONAL"]

    # Accept both ?aid_type= (template) and ?program= (some links)
    program = (
        request.GET.get("aid_type", "")
        or request.GET.get("program", "")
    ).upper()

    qs = (
        Application.objects
        .select_related("client")
        .order_by("-created_at")
    )

    if program in allowed_programs:
        qs = qs.filter(aid_type=program)
    else:
        program = "ALL"

    status_filter = request.GET.get("status", "").strip().upper()
    if status_filter:
        qs = qs.filter(status=status_filter)
    else:
        qs = qs.filter(status="PENDING")

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search) |
            Q(client__email__icontains=search)
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "applications": page_obj,
        "program": program,
        "allowed_programs": allowed_programs,
        "search": search,
        "status_filter": status_filter,
    }

    return render(request, "pending_applications.html", context)


@login_required
def client_detail(request, pk):
    # Only staff/admin/superuser can access
    if not (getattr(request.user, 'role', None) in ['staff', 'admin'] or request.user.is_superuser):
        return redirect('landing')

    # Get the client
    client = get_object_or_404(Client, pk=pk)

    # Get all applications for this client
    applications = Application.objects.filter(client=client).order_by('-created_at')

    # Render template
    return render(request, "client_detail.html", {
        "client": client,
        "applications": applications,
    })


from django.contrib import messages

@login_required
def client_delete(request, pk):
    # Only staff/admin/superuser can access
    if not (getattr(request.user, 'role', None) in ['staff', 'admin'] or request.user.is_superuser):
        return redirect('landing')

    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        client.delete()
        messages.success(request, f'Client {client.first_name} {client.last_name} deleted.')
        return redirect('pending_applications')  # go back to pending list

    return render(request, "client_confirm_delete.html", {"client": client})


@login_required
def toggle_staff_status(request, staff_id):
    # Only ADMIN can access this
    if getattr(request.user, 'role', None) != 'admin' and not request.user.is_superuser:
        return redirect('landing')

    staff = get_object_or_404(User, id=staff_id)
    staff.is_active = not staff.is_active
    staff.save()

    return redirect('admin_account')


from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def test_api(request):
    return Response({"message": "Django connected to React successfully!"})

from rest_framework.decorators import api_view
from rest_framework.response import Response

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from .models import Client, Application


@api_view(["GET"])
def dashboard_api(request):
    program_data = (
        Application.objects
        .values("program")
        .annotate(count=Count("id"))
    )

    status_data = (
        Application.objects
        .values("status")
        .annotate(count=Count("id"))
    )

    monthly_data = (
        Client.objects
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    latest_clients = Client.objects.order_by("-created_at")[:5]

    return Response({
        "programs": {
            "labels": [p["program"] for p in program_data],
            "values": [p["count"] for p in program_data],
        },
        "statuses": {
            "labels": [s["status"] for s in status_data],
            "values": [s["count"] for s in status_data],
        },
        "months": {
            "labels": [m["month"].strftime("%Y-%m") for m in monthly_data],
            "values": [m["count"] for m in monthly_data],
        },
        "latest_clients": [
            {
                "name": f"{c.first_name} {c.last_name}",
                "email": c.email,
                "created": c.created_at.strftime("%Y-%m-%d"),
            }
            for c in latest_clients
        ]
    })

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def dashboard_data(request):
    program_counts = (
        Application.objects.values("program")
        .annotate(total=Count("id"))
    )

    status_counts = (
        Application.objects.values("status")
        .annotate(total=Count("id"))
    )

    program_labels = [p["program"] for p in program_counts]
    program_values = [p["total"] for p in program_counts]

    status_labels = [s["status"] for s in status_counts]
    status_values = [s["total"] for s in status_counts]

    latest_clients = list(
        Client.objects.order_by("-id")
        .values("id", "full_name", "barangay")[:5]
    )

    return JsonResponse({
        "program_chart": {
            "labels": program_labels,
            "data": program_values
        },
        "status_chart": {
            "labels": status_labels,
            "data": status_values
        },
        "latest_clients": latest_clients
    })


from .utils import send_sms  # 👈 IMPORT THIS

@login_required
def application_approve(request, pk):
    application = get_object_or_404(Application, pk=pk)

    # ── Permission Check ───────────────────────────────────────────────
    if not (getattr(request.user, 'role', None) in ['admin', 'staff'] or request.user.is_superuser):
        messages.error(request, "You do not have permission to approve applications.")
        return redirect('dashboard')

    # ── Update Application ─────────────────────────────────────────────
    application.status = 'APPROVAL'
    application.eligibility_result = 'Eligible'
    application.approved_by = request.user
    application.approved_at = timezone.now()
    application.save()

    client = application.client

    # ── Email ──────────────────────────────────────────────────────────
    if client.email:
        subject = "Your Assistance Application Has Been Approved"
        message = f"""
Good day {client.full_name},

Your application for {application.get_aid_type_display()} assistance has been APPROVED
and is now being processed for release.

Application Details:
  Program : {application.get_aid_type_display()}
  Status  : For Approval

Our office will contact you regarding the release schedule.

Thank you,
MSWDO Office
"""
        try:
            send_mail(
                subject,
                message,
                from_email=None,
                recipient_list=[client.email],
                fail_silently=False
            )

            print("===================================")
            print("EMAIL SENT SUCCESSFULLY")
            print(f"Recipient: {client.email}")
            print("===================================")

        except Exception as e:
            print("===================================")
            print("EMAIL ERROR")
            print(str(e))
            print("===================================")

    # ── SMS (PhilSMS) ─────────────────────────────────────────────────
    if client.contact_no:
        sms_message = (
            f"Good day {client.full_name}! "
            f"Your {application.get_aid_type_display()} assistance application has been APPROVED "
            f"and is now for release processing. MSWDO Office."
        )

        try:
            sms_response = send_sms(client.contact_no, sms_message)

            if sms_response.get("success"):
                print("===================================")
                print("SMS SENT SUCCESSFULLY")
                print(f"Recipient: {client.contact_no}")
                print("===================================")
            else:
                print("===================================")
                print("SMS FAILED")
                print(sms_response.get("error"))
                print("===================================")

        except Exception as e:
            print("===================================")
            print("SMS ERROR")
            print(str(e))
            print("===================================")
    else:
        print("No contact number found for this client.")

    # ── Final Message ─────────────────────────────────────────────────
    messages.success(request, "Application approved. Client notified via email and SMS.")
    return redirect('application_detail', pk=pk)


@login_required
def application_reject(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if not (getattr(request.user, 'role', None) in ['admin', 'staff'] or request.user.is_superuser):
        messages.error(request, "You do not have permission to reject applications.")
        return redirect('dashboard')

    application.status = 'REJECTED'
    application.eligibility_result = 'Not Eligible'
    application.save()

    client = application.client

    # ── Email ──────────────────────────────────────────────────────────
    if client.email:
        subject = "Update on Your Assistance Application"
        message = f"""
Good day {client.full_name},

We regret to inform you that your application for {application.get_aid_type_display()} assistance
has been reviewed and could not be approved at this time.

Application Details:
  Program : {application.get_aid_type_display()}
  Status  : Rejected

If you have questions, please visit or contact the MSWDO office.

Thank you,
MSWDO Office
"""
        try:
            send_mail(subject, message, from_email=None, recipient_list=[client.email], fail_silently=False)
        except Exception as e:
            print("Email sending failed:", e)

    # ── SMS ────────────────────────────────────────────────────────────
    if client.contact_no:
        sms_message = (
            f"Good day {client.full_name}. "
            f"Your {application.get_aid_type_display()} assistance application was not approved. "
            f"Please visit the MSWDO office for more information."
        )
        try:
            sms_response = send_sms(client.contact_no, sms_message)
            print("SMS Response:", sms_response)
        except Exception as e:
            print("SMS sending failed:", e)

    messages.success(request, "Application rejected. Client has been notified.")
    return redirect('application_detail', pk=pk)


def send_sms(phone_number, message):
    # Auto-convert PH number format
    if phone_number.startswith("09"):
        phone_number = "63" + phone_number[1:]

    url = "https://dashboard.philsms.com/api/v3/sms/send"

    payload = {
        "recipient": phone_number,
        "sender_id": getattr(settings, "PHILSMS_SENDER_ID", ""),
        "type": "plain",
        "message": message,
    }

    headers = {
        "Authorization": f"Bearer {settings.PHILSMS_API_TOKEN}",  # ✅ FIXED
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        print("===== SMS DEBUG (PhilSMS FINAL) =====")
        print("Number Sent To:", phone_number)
        print("Status Code:   ", response.status_code)
        print("Response:      ", response.text)
        print("====================================")

        response.raise_for_status()
        data = response.json()

        return {
            "success": True,
            "data": data
        }

    except requests.exceptions.RequestException as e:
        print("SMS ERROR (PhilSMS):", str(e))
        return {
            "success": False,
            "error": str(e)
        }
    

@login_required
def application_reject(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if not (
        getattr(request.user, 'role', None) in ['admin', 'staff']
        or request.user.is_superuser
    ):
        return redirect('dashboard')

    application.status = 'rejected'
    application.eligibility_result = 'Not Eligible'
    application.save()

    messages.warning(request, "Application rejected.")
    return redirect('application_detail', pk=pk)


@login_required
def application_edit(request, pk):
    application = get_object_or_404(Application, pk=pk)
    client = application.client

    if not (
        getattr(request.user, 'role', None) in ['admin', 'staff']
        or request.user.is_superuser
    ):
        return redirect('dashboard')

    if request.method == 'POST':
        # ── Personal ─────────────────────────────────────
        client.first_name   = request.POST.get('first_name')
        client.middle_name  = request.POST.get('middle_name') or None
        client.last_name    = request.POST.get('last_name')
        client.sex          = request.POST.get('sex')
        client.birth_date   = request.POST.get('birth_date') or None
        client.civil_status = request.POST.get('civil_status')
        client.nationality  = request.POST.get('nationality') or 'Filipino'

        # ── Address & Contact ────────────────────────────
        client.address      = request.POST.get('address')
        client.barangay     = request.POST.get('barangay')
        client.municipality = request.POST.get('municipality')
        client.contact_no   = request.POST.get('contact_no')
        client.email        = request.POST.get('email') or None

        # ── Socio-Economic ───────────────────────────────
        client.livelihood     = request.POST.get('livelihood')
        client.monthly_income = request.POST.get('monthly_income') or 0
        client.household_size = request.POST.get('household_size') or 1
        SECTOR_KEYS = ['WEDC','SC','PWD','SP','IP','OFW','TP','PDL',
                       'PWUD','IFW','4PS','CNSP','CAR','CICL','OSCY','FR','KASAMBAHAY']
        selected_sectors   = [k for k in SECTOR_KEYS if request.POST.get(f'sector_{k}')]
        client.sectors     = selected_sectors
        client.has_disability  = 'Yes' if 'PWD' in selected_sectors else 'No'
        client.is_senior       = 'Yes' if 'SC'  in selected_sectors else 'No'
        client.is_solo_parent  = 'Yes' if 'SP'  in selected_sectors else 'No'
        client.is_indigenous   = 'Yes' if 'IP'  in selected_sectors else 'No'
        client.previous_aid    = request.POST.get('previous_aid', 'No')

        # ── 4Ps ─────────────────────────────────────────
        client.is_4ps    = request.POST.get('is_4ps', 'No')
        client.fourps_id = request.POST.get('fourps_id') or None

        client.save()

        # ── Family Members — replace all existing ────────
        client.family_members.all().delete()

        index = 0
        while index <= 50:
            name = request.POST.get(f"family_name_{index}", "").strip()
            if name:
                civil_status = request.POST.get(f"family_cs_{index}") or None

                edu_elem  = request.POST.get(f"family_edu_elem_{index}")
                edu_hs    = request.POST.get(f"family_edu_hs_{index}")
                edu_coll  = request.POST.get(f"family_edu_coll_{index}")
                edu_illit = request.POST.get(f"family_edu_illit_{index}")
                education = (
                    "Elem"     if edu_elem  else
                    "HS"       if edu_hs    else
                    "Coll/Voc" if edu_coll  else
                    "Illit"    if edu_illit else None
                )

                raw_age    = request.POST.get(f"family_age_{index}", "").strip()
                raw_income = request.POST.get(f"family_inc_{index}", "").strip()

                FamilyMember.objects.create(
                    client=client,
                    name=name,
                    age=int(raw_age) if raw_age else None,
                    sex=request.POST.get(f"family_sex_{index}") or None,
                    civil_status=civil_status,
                    relationship=request.POST.get(f"family_rel_{index}") or None,
                    educational_attainment=education,
                    occupation=request.POST.get(f"family_occ_{index}") or None,
                    income=Decimal(raw_income) if raw_income else None,
                )
            index += 1

        # ── Application ──────────────────────────────────
        application.aid_type           = request.POST.get('aid_type')
        application.approved_amount    = request.POST.get('approved_amount') or None
        application.eligibility_result = request.POST.get('eligibility_result') or None
        application.status             = request.POST.get('status', application.status)
        application.save()

        messages.success(request, "Application updated successfully.")
        return redirect('application_detail', pk=pk)

    family_members = client.family_members.all()
    SECTOR_CHOICES_AE = [
        ('WEDC','Women in Especially Difficult Circumstances (WEDC)'),('SC','Senior Citizen (SC)'),
        ('PWD','Person with Disability (PWD)'),('SP','Solo Parent (SP)'),('IP','Indigenous People (IP)'),
        ('OFW','Overseas Filipino Worker (OFW)'),('TP','Trafficked Person (TP)'),
        ('PDL','Person Deprived of Liberty (PDL)'),('PWUD','Person Who Uses Drugs (PWUD)'),
        ('IFW','Informal Filipino Workers (IFW)'),('4PS','4Ps Beneficiary (4Ps)'),
        ('CNSP','Children in Need of Special Protection (CNSP)'),('CAR','Child at Risk (CAR)'),
        ('CICL','Child in Conflict with the Law (CICL)'),('OSCY','Out of School Children/Youth (OSCY)'),
        ('FR','Former Rebel (FR)'),('KASAMBAHAY','Domestic Helper (Kasambahay)'),
    ]
    return render(request, 'application_edit.html', {
        'application': application,
        'client': client,
        'family_members': family_members,
        'sector_choices': SECTOR_CHOICES_AE,
    })




@login_required
def approve_application(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.user.role not in ['admin'] and not request.user.is_superuser:
        messages.error(request, "Unauthorized action.")
        return redirect('client_detail', application.client.id)

    application.status = 'approved'
    application.approved_by = request.user
    application.approved_at = timezone.now()
    application.save()

    messages.success(request, "Application approved.")
    return redirect('client_detail', application.client.id)


@login_required
def reject_application(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.user.role not in ['admin'] and not request.user.is_superuser:
        messages.error(request, "Unauthorized action.")
        return redirect('client_detail', application.client.id)

    application.status = 'rejected'
    application.save()

    messages.warning(request, "Application disapproved.")
    return redirect('client_detail', application.client.id)


@login_required
def release_application(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        amount = Decimal(request.POST.get('released_amount', 0))

        application.released_amount = amount
        application.status = 'released'
        application.released_at = timezone.now()
        application.save()

        messages.success(request, "Aid released successfully.")

    return redirect('client_detail', application.client.id)

@login_required
def approve_application(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.user.role not in ['admin'] and not request.user.is_superuser:
        messages.error(request, "Unauthorized action.")
        return redirect('client_detail', application.client.id)

    application.status = 'approved'
    application.approved_by = request.user
    application.approved_at = timezone.now()
    application.save()

    messages.success(request, "Application approved.")
    return redirect('client_detail', application.client.id)


@login_required
def reject_application(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.user.role not in ['admin'] and not request.user.is_superuser:
        messages.error(request, "Unauthorized action.")
        return redirect('client_detail', application.client.id)

    application.status = 'rejected'
    application.save()

    messages.warning(request, "Application disapproved.")
    return redirect('client_detail', application.client.id)


@login_required
def release_application(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        amount = Decimal(request.POST.get('released_amount', 0))

        application.released_amount = amount
        application.status = 'released'
        application.released_at = timezone.now()
        application.save()

        messages.success(request, "Aid released successfully.")

    return redirect('client_detail', application.client.id)

from django.contrib.auth.hashers import make_password

def toggle_staff(request, staff_id):
    staff = get_object_or_404(User, id=staff_id)
    staff.is_active = not staff.is_active
    staff.save()
    messages.success(request, f"{staff.get_full_name()} is now {'active' if staff.is_active else 'inactive'}.")
    return redirect('admin_account')


def reset_staff_password(request, staff_id):
    staff = get_object_or_404(User, id=staff_id)
    # Simple password reset to 'password123' for demo; replace with proper workflow
    staff.set_password('password123')
    staff.save()
    messages.success(request, f"Password for {staff.get_full_name()} has been reset.")
    return redirect('admin_account')


def edit_staff_role(request, staff_id):
    staff = get_object_or_404(User, id=staff_id)
    if request.method == "POST":
        role = request.POST.get('role')
        staff.role = role
        staff.save()
        messages.success(request, f"{staff.get_full_name()}'s role has been updated to {role}.")
        return redirect('admin_account')
    return render(request, 'edit_staff_role.html', {'staff': staff})


def staff_activity_logs(request, staff_id):
    staff = get_object_or_404(User, id=staff_id)
    activity_logs = [
        {"action": "Account Created", "date": staff.date_joined},
        {"action": "Last Login", "date": staff.last_login or "Never"}
    ]
    return render(request, 'staff_activity_logs.html', {'staff': staff, 'activity_logs': activity_logs})




from .models import ClientAccount
from django.contrib import messages

def client_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            account = ClientAccount.objects.select_related("client").get(email=email)

            if account.check_password(password):
                request.session["client_account_id"] = account.id
                request.session["client_id"] = account.client.id
                request.session["client_name"] = account.client.full_name

                messages.success(request, "Login successful!")
                return redirect("client_dashboard")
            else:
                messages.error(request, "Invalid password.")

        except ClientAccount.DoesNotExist:
            messages.error(request, "No account found with that email.")

    return render(request, "client_login.html")



from urllib.parse import quote   # add this import near the top of views.py if not present
 
 
def client_register(request):
    if request.method == "POST":
        password  = request.POST.get('password')
        password2 = request.POST.get('confirm_password')
 
        if password != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'client_register.html')
 
        email = (request.POST.get('email') or '').strip().lower()
 
        if not email:
            messages.error(request, "Email address is required.")
            return render(request, 'client_register.html')
 
        # Duplicate check
        if Client.objects.filter(email__iexact=email).exists() or \
           ClientAccount.objects.filter(email__iexact=email).exists():
            messages.error(request, "This email is already registered.")
            return render(request, 'client_register.html')
 
        try:
            selected_sectors  = request.POST.getlist("selected_sectors")
            has_disability    = request.POST.get("has_disability") == "on"
            is_senior         = request.POST.get("is_senior") == "on"
            previous_aid      = request.POST.get("previous_aid")
            is_solo_parent    = request.POST.get("is_solo_parent") == "on"
            is_indigenous     = request.POST.get("is_indigenous") == "on"
 
            client = Client.objects.create(
                first_name    = request.POST.get('first_name'),
                middle_name   = request.POST.get('middle_name') or None,
                last_name     = request.POST.get('last_name'),
                sex           = request.POST.get('sex'),
                birth_date    = request.POST.get('birth_date'),
                civil_status  = request.POST.get('civil_status'),
                nationality   = request.POST.get('nationality') or 'Filipino',
                address       = request.POST.get('address'),
                barangay      = request.POST.get('barangay'),
                municipality  = request.POST.get('municipality'),
                contact_no    = request.POST.get('contact_no'),
                email         = email,
                livelihood    = request.POST.get('livelihood'),
                monthly_income  = request.POST.get('monthly_income') or 0,
                household_size  = request.POST.get('household_size') or 1,
                sectors         = selected_sectors,
                has_disability  = has_disability,
                is_senior       = is_senior,
                previous_aid    = previous_aid,
                is_solo_parent  = is_solo_parent,
                is_indigenous   = is_indigenous,
                is_4ps          = request.POST.get('is_4ps', 'No'),
                fourps_id       = request.POST.get('fourps_id') or None,
            )
 
            # Family Members
            index = 0
            while index <= 50:
                name = request.POST.get(f"family_name_{index}", "").strip()
                if name:
                    civil_status_fm = request.POST.get(f"family_cs_{index}") or None
                    edu_elem   = request.POST.get(f"family_edu_elem_{index}")
                    edu_hs     = request.POST.get(f"family_edu_hs_{index}")
                    edu_coll   = request.POST.get(f"family_edu_coll_{index}")
                    edu_illit  = request.POST.get(f"family_edu_illit_{index}")
                    education  = (
                        "Elem"     if edu_elem  else
                        "HS"       if edu_hs    else
                        "Coll/Voc" if edu_coll  else
                        "Illit"    if edu_illit else None
                    )
                    raw_age    = request.POST.get(f"family_age_{index}", "").strip()
                    raw_income = request.POST.get(f"family_inc_{index}", "").strip()
 
                    FamilyMember.objects.create(
                        client                 = client,
                        name                   = name,
                        age                    = int(raw_age) if raw_age else None,
                        sex                    = request.POST.get(f"family_sex_{index}") or None,
                        civil_status           = civil_status_fm,
                        relationship           = request.POST.get(f"family_rel_{index}") or None,
                        educational_attainment = education,
                        occupation             = request.POST.get(f"family_occ_{index}") or None,
                        income                 = Decimal(raw_income) if raw_income else None,
                    )
                index += 1
 
            # Create account — inactive until verified
            account = ClientAccount.objects.create(
                client    = client,
                email     = email,
                is_active = False,
            )
            account.set_password(password)
 
            # Store token IN THE DATABASE — survives server reloads
            token = get_random_string(48)
            account.verification_token = token
            account.save()
 
            # Build verify URL — use quote() so special chars in email are safe
            verify_url = request.build_absolute_uri(
                reverse('client_verify') + '?email=' + quote(email, safe='') + '&token=' + token
            )
 
            # Send verification email
            try:
                send_mail(
                    subject='Verify Your MSWDO Account',
                    message=(
                        f"Hello {client.first_name},\n\n"
                        f"Thank you for registering with MSWDO.\n\n"
                        f"Please click the link below to verify your email address:\n\n"
                        f"{verify_url}\n\n"
                        f"If you did not register, please ignore this email.\n\n"
                        f"— MSWDO Team"
                    ),
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[email],
                    fail_silently=False,
                )
                email_sent = True
            except Exception as mail_err:
                print(f"[EMAIL] ❌ FAILED: {mail_err}")
                email_sent = False
                messages.warning(request, f"Registration saved but email could not be sent: {mail_err}")
 
            return render(request, 'client_register.html', {
                'registration_done': True,
                'reg_email': email,
                'email_sent': email_sent,
            })
 
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f"Registration failed: {e}")
 
    return render(request, 'client_register.html')
 
 
def client_verify(request):
    """
    Called when the user clicks the verification link in their email.
    Activates the ClientAccount and shows a success page.
    """
    from urllib.parse import unquote
    email = unquote(request.GET.get('email', '').strip())
    token = request.GET.get('token', '').strip()
 
    error = None
 
    if not email or not token:
        error = "Invalid verification link. Please register again."
    else:
        try:
            account = ClientAccount.objects.get(email__iexact=email)
 
            if account.is_active:
                # Already verified — just send them to login
                return render(request, 'client_verify_success.html', {
                    'already_verified': True,
                    'email': email,
                })
 
            if not account.verification_token or account.verification_token != token:
                error = "This verification link is invalid or has already been used."
            else:
                account.is_active           = True
                account.verification_token  = ''   # consume the token
                account.save()
                return render(request, 'client_verify_success.html', {
                    'already_verified': False,
                    'email': email,
                })
 
        except ClientAccount.DoesNotExist:
            error = "No account found for this email address."
 
    return render(request, 'client_verify_success.html', {
        'error': error,
        'email': email,
    })
 
 
def resend_client_verification(request):
    """
    Lets a client request a fresh verification email if the original expired
    or was never received.
    """
    from urllib.parse import quote
 
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        try:
            account = ClientAccount.objects.get(email__iexact=email)
 
            if account.is_active:
                messages.info(request, "This account is already verified. Please log in.")
                return redirect('client_login')
 
            # Generate fresh token
            token = get_random_string(48)
            account.verification_token = token
            account.save()
 
            verify_url = request.build_absolute_uri(
                reverse('client_verify') + '?email=' + quote(email, safe='') + '&token=' + token
            )
 
            try:
                send_mail(
                    subject='Verify Your MSWDO Account (Resent)',
                    message=(
                        f"Hello,\n\n"
                        f"Here is your new verification link:\n\n"
                        f"{verify_url}\n\n"
                        f"— MSWDO Team"
                    ),
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[email],
                    fail_silently=False,
                )
                messages.success(request, "Verification email resent! Check your inbox.")
            except Exception as e:
                messages.error(request, f"Could not send email: {e}")
 
        except ClientAccount.DoesNotExist:
            messages.error(request, "No account found with that email.")
 
    return redirect('client_login')
 




def client_dashboard(request):
    client_id = request.session.get("client_id")

    if not client_id:
        return redirect("client_login")

    client = Client.objects.get(id=client_id)

    return render(request, "client_dashboard.html", {
        "client": client
    })



def client_edit_profile(request):
    client_id = request.session.get('client_id')
    if not client_id:
        return redirect('client_login')

    client = get_object_or_404(Client, id=client_id)

    if request.method == "POST":
        client.first_name   = request.POST.get('first_name')
        client.middle_name  = request.POST.get('middle_name') or None
        client.last_name    = request.POST.get('last_name')
        client.sex          = request.POST.get('sex')
        client.birth_date   = request.POST.get('birth_date')
        client.civil_status = request.POST.get('civil_status')
        client.nationality  = request.POST.get('nationality') or 'Filipino'
        client.address      = request.POST.get('address')
        client.barangay     = request.POST.get('barangay')
        client.municipality = request.POST.get('municipality')
        client.contact_no   = request.POST.get('contact_no')
        client.email        = request.POST.get('email') or None
        client.livelihood     = request.POST.get('livelihood')
        client.monthly_income = request.POST.get('monthly_income') or 0
        client.household_size = request.POST.get('household_size') or 1
        # Socio-economic checkboxes
        SECTOR_KEYS = ['WEDC','SC','PWD','SP','IP','OFW','TP','PDL',
                       'PWUD','IFW','4PS','CNSP','CAR','CICL','OSCY','FR','KASAMBAHAY']
        selected_sectors   = [k for k in SECTOR_KEYS if request.POST.get(f'sector_{k}')]
        client.sectors     = selected_sectors
        client.has_disability  = 'Yes' if 'PWD' in selected_sectors else 'No'
        client.is_senior       = 'Yes' if 'SC'  in selected_sectors else 'No'
        client.is_solo_parent  = 'Yes' if 'SP'  in selected_sectors else 'No'
        client.is_indigenous   = 'Yes' if 'IP'  in selected_sectors else 'No'
        client.previous_aid    = request.POST.get('previous_aid', 'No')
        # 4Ps
        client.is_4ps    = request.POST.get('is_4ps', 'No')
        client.fourps_id = request.POST.get('fourps_id') or None
        client.save()

        # Replace family members
        client.family_members.all().delete()
        index = 0
        while index <= 50:
            name = request.POST.get(f"family_name_{index}", "").strip()
            if name:
                civil_status = request.POST.get(f"family_cs_{index}") or None
                edu_elem  = request.POST.get(f"family_edu_elem_{index}")
                edu_hs    = request.POST.get(f"family_edu_hs_{index}")
                edu_coll  = request.POST.get(f"family_edu_coll_{index}")
                edu_illit = request.POST.get(f"family_edu_illit_{index}")
                education = (
                    "Elem"     if edu_elem  else
                    "HS"       if edu_hs    else
                    "Coll/Voc" if edu_coll  else
                    "Illit"    if edu_illit else None
                )
                raw_age    = request.POST.get(f"family_age_{index}", "").strip()
                raw_income = request.POST.get(f"family_inc_{index}", "").strip()
                FamilyMember.objects.create(
                    client=client, name=name,
                    age=int(raw_age) if raw_age else None,
                    sex=request.POST.get(f"family_sex_{index}") or None,
                    civil_status=civil_status,
                    relationship=request.POST.get(f"family_rel_{index}") or None,
                    educational_attainment=education,
                    occupation=request.POST.get(f"family_occ_{index}") or None,
                    income=Decimal(raw_income) if raw_income else None,
                )
            index += 1

        messages.success(request, "Profile updated successfully.")
        return redirect('client_edit_profile')

    family_members = client.family_members.all()
    SECTOR_CHOICES = [
        ('WEDC','Women in Especially Difficult Circumstances (WEDC)'),('SC','Senior Citizen (SC)'),
        ('PWD','Person with Disability (PWD)'),('SP','Solo Parent (SP)'),('IP','Indigenous People (IP)'),
        ('OFW','Overseas Filipino Worker (OFW)'),('TP','Trafficked Person (TP)'),
        ('PDL','Person Deprived of Liberty (PDL)'),('PWUD','Person Who Uses Drugs (PWUD)'),
        ('IFW','Informal Filipino Workers (IFW)'),('4PS','4Ps Beneficiary (4Ps)'),
        ('CNSP','Children in Need of Special Protection (CNSP)'),('CAR','Child at Risk (CAR)'),
        ('CICL','Child in Conflict with the Law (CICL)'),('OSCY','Out of School Children/Youth (OSCY)'),
        ('FR','Former Rebel (FR)'),('KASAMBAHAY','Domestic Helper (Kasambahay)'),
    ]
    return render(request, 'client_edit_profile.html', {
        'client': client,
        'family_members': family_members,
        'sector_choices': SECTOR_CHOICES,
    })
 


def client_applications(request):
    client_id = request.session.get('client_id')

    if not client_id:
        return redirect('client_login')

    client = Client.objects.get(id=client_id)

    applications = Application.objects.filter(client=client).order_by('-created_at')

    return render(request, 'client_applications.html', {
        'client': client,
        'applications': applications
    })

from django.db import transaction
from .models import Notification
def client_apply_program(request):
    client_id = request.session.get("client_id")
    if not client_id:
        return redirect("client_login")

    client = get_object_or_404(Client, id=client_id)

    if request.method == "POST":
        aid_type = request.POST.get("aid_type")

        if not aid_type:
            messages.error(request, "Please select a program.")
            return redirect("client_apply_program")

        try:
            with transaction.atomic():

                # ── ML Prediction (SAME AS add_client) ───────────────
                try:
                    income = float(client.monthly_income)
                    hh     = int(client.household_size) or 1

                    ml_input = {
                        "monthly_income":    income,
                        "household_size":    hh,
                        "income_per_person": income / hh,
                        "has_disability":    1 if client.has_disability == "Yes" else 0,
                        "is_senior":         1 if client.is_senior      == "Yes" else 0,
                        "previous_aid":      1 if client.previous_aid   == "Yes" else 0,
                        "is_solo_parent":    1 if getattr(client, "is_solo_parent", "No") == "Yes" else 0,
                        "is_indigenous":     1 if getattr(client, "is_indigenous", "No") == "Yes" else 0,
                        "is_4ps":            1 if getattr(client, "is_4ps", "No") == "Yes" else 0,
                    }

                    prediction = predict_input(ml_input, aid_type)
                    score      = compute_score(ml_input)
                    reason     = generate_reason(ml_input, prediction, aid_type)

                    eligibility = "Eligible" if prediction == 1 else "Not Eligible"

                except Exception as ml_err:
                    import traceback
                    traceback.print_exc()
                    eligibility = "Not Eligible"
                    score = 0
                    reason = "Eligibility could not be determined automatically. Please assess manually."

                # ── Create Application ───────────────────────────────
                application = Application.objects.create(
                    client=client,
                    aid_type=aid_type,
                    status="PENDING",
                    eligibility_result=eligibility,
                    eligibility_score=score,
                    eligibility_reason=reason,
                )

                print(f"📋 Application {application.id} created for {client.full_name}")

                docs = {}

                # ── AICS ─────────────────────────────────────────────
                if aid_type == "AICS":
                    AICSDetail.objects.create(
                        application=application,
                        crisis_type=request.POST.get("aics_crisis_type"),
                    )
                    docs = {
                        "AICS Barangay Certificate":  request.FILES.get("aics_barangay_cert"),
                        "Medical / Death Certificate": request.FILES.get("aics_medical_death_cert"),
                        "Official Receipt":            request.FILES.get("aics_receipt"),
                    }

                # ── SEA ──────────────────────────────────────────────
                elif aid_type == "SEA":
                    SEADetail.objects.create(application=application)
                    docs = {
                        "Barangay Clearance": request.FILES.get("sea_barangay_clearance"),
                        "Cedula":             request.FILES.get("sea_cedula"),
                        "Project Proposal":   request.FILES.get("sea_project_proposal"),
                        "Project Picture":    request.FILES.get("sea_project_picture"),
                    }

                # ── REDCARD ──────────────────────────────────────────
                elif aid_type == "REDCARD":
                    REDCARDDetail.objects.create(
                        application=application,
                        emergency_type=request.POST.get("redcard_emergency_type"),
                        reason=request.POST.get("redcard_reason"),
                        usage_count=request.POST.get("redcard_usage") or 1,
                    )
                    docs = {
                        "Birth Certificate":        request.FILES.get("redcard_birth_cert"),
                        "Valid ID Picture":         request.FILES.get("redcard_valid_id"),
                        "Certificate of Indigency": request.FILES.get("redcard_indigency"),
                    }

                # ── EDUCATIONAL ──────────────────────────────────────
                elif aid_type == "EDUCATIONAL":
                    EducationalAssistanceDetail.objects.create(
                        application=application,
                        school_name=request.POST.get("school_name"),
                        course_or_grade=request.POST.get("course_level"),
                    )
                    docs = {
                        "Letter of Appeal":          request.FILES.get("edu_letter"),
                        "Certificate of Indigency":  request.FILES.get("edu_indigency"),
                        "Grades":                    request.FILES.get("edu_grades"),
                        "Certificate of Enrollment": request.FILES.get("edu_enrollment"),
                        "Billing Statement":         request.FILES.get("edu_billing"),
                        "Official Receipt":          request.FILES.get("edu_receipt"),
                    }

                # ── Save Documents ───────────────────────────────────
                for doc_name, file in docs.items():
                    if file:
                        ApplicationDocument.objects.create(
                            application=application,
                            name=doc_name,
                            file=file,
                        )

                # ── Notify Staff/Admin ───────────────────────────────
                staff_admins = User.objects.filter(role__in=["staff", "admin"]) | User.objects.filter(is_superuser=True)

                for user in staff_admins.distinct():
                    Notification.objects.create(
                        recipient=user,
                        message=f"New {aid_type} application from {client.full_name}",
                        link=f"/application/{application.id}/",
                    )

                print("🎉 Application + ML + Notifications completed!")

            messages.success(request, "Application submitted successfully!")
            return redirect("client_applications")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f"Submission failed: {e}")

    return render(request, "client_apply_program.html", {"client": client})

from django.views.decorators.http import require_POST
@login_required
@require_POST
def mark_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk)
    if notif.recipient == request.user:
        notif.is_read = True
        notif.save()

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(next_url)


ACCESS_CODE = "357246"

def access_code_view(request):
    if request.method == "POST":
        entered_code = request.POST.get("access_code")

        if entered_code == ACCESS_CODE:
            request.session['access_granted'] = True
            return redirect('select_account')
        else:
            messages.error(request, "Invalid access code.")

    return render(request, "access_code.html")


from django.http import JsonResponse

@login_required
def get_notifications_json(request):
    user_role = getattr(request.user, "role", None)
    if not (user_role in ["staff", "admin"] or request.user.is_superuser):
        return JsonResponse({'notifications': [], 'unread_count': 0})

    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]

    data = []
    for n in notifications:
        data.append({
            'id':         n.pk,
            'message':    n.message,
            'is_read':    n.is_read,
            'link':       n.link or '',
            'created_at': n.created_at.strftime('%b %d, %Y %I:%M %p'),
        })

    unread_count = notifications.filter(is_read=False).count()

    return JsonResponse({'notifications': data, 'unread_count': unread_count})




from .models import Report, User
 
# ─────────────────────────────────────────────
# STAFF: Submit a Report
# ─────────────────────────────────────────────
@login_required
def report_submit(request):
    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        content     = request.POST.get('content', '').strip()
        report_type = request.POST.get('report_type', '').strip()
        attachment  = request.FILES.get('attachment')
 
        if not title or not content:
            messages.error(request, "Title and content are required.")
            return render(request, 'report_submit.html')
 
        report = Report.objects.create(
            submitted_by=request.user,
            title=title,
            content=content,
            report_type=report_type or None,
            attachment=attachment,
        )
 
        # ── Email all admins ──────────────────────────────────
        admins = User.objects.filter(role='admin') | User.objects.filter(is_superuser=True)
        admin_emails = list(admins.distinct().values_list('email', flat=True))
        admin_emails = [e for e in admin_emails if e]
 
        if admin_emails:
            try:
                send_mail(
                    subject=f"[MSWDO] New Report Submitted: {title}",
                    message=(
                        f"A new report has been submitted and is awaiting your review.\n\n"
                        f"Title: {title}\n"
                        f"Type: {report_type or 'General'}\n"
                        f"Submitted by: {request.user.get_full_name() or request.user.username}\n"
                        f"Date: {report.created_at.strftime('%B %d, %Y %I:%M %p')}\n\n"
                        f"Preview:\n{content[:300]}{'...' if len(content) > 300 else ''}\n\n"
                        f"Log in to the MSWDO Admin Portal to review and approve or decline this report."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Email error: {e}")
 
        messages.success(request, "Report submitted successfully. The admin has been notified.")
        return redirect('report_submit')
 
    return render(request, 'report_submit.html')
 
 
# ─────────────────────────────────────────────
# ADMIN: Reports Dashboard (view all reports)
# ─────────────────────────────────────────────
@login_required
def reports_dashboard(request):
    # Admin only
    if not (getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser):
        messages.error(request, "Access denied. Admins only.")
        return redirect('dashboard')
 
    status_filter = request.GET.get('status', '')
    reports = Report.objects.all()
    if status_filter:
        reports = reports.filter(status=status_filter)
 
    counts = {
        'total':    Report.objects.count(),
        'pending':  Report.objects.filter(status='PENDING').count(),
        'approved': Report.objects.filter(status='APPROVED').count(),
        'declined': Report.objects.filter(status='DECLINED').count(),
    }
 
    return render(request, 'reports_dashboard.html', {
        'reports':       reports,
        'status_filter': status_filter,
        'counts':        counts,
    })
 
 
# ─────────────────────────────────────────────
# ADMIN: View single report
# ─────────────────────────────────────────────
@login_required
def report_detail(request, pk):
    if not (getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser):
        return redirect('dashboard')
 
    report = get_object_or_404(Report, pk=pk)
    return render(request, 'report_detail.html', {'report': report})
 
 
# ─────────────────────────────────────────────
# ADMIN: Approve a report
# ─────────────────────────────────────────────
@login_required
def report_approve(request, pk):
    if not (getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser):
        return redirect('dashboard')
 
    report = get_object_or_404(Report, pk=pk)
 
    if request.method == 'POST':
        admin_note   = request.POST.get('admin_note', '').strip()
        publish      = request.POST.get('publish') == '1'
 
        report.status      = 'APPROVED'
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.admin_note  = admin_note or None
        report.is_published = publish
        report.save()
 
        # ── Notify submitter by email ─────────────────────────
        if report.submitted_by.email:
            try:
                send_mail(
                    subject=f"[MSWDO] Your Report Has Been Approved: {report.title}",
                    message=(
                        f"Good news! Your report has been approved by the administrator.\n\n"
                        f"Title: {report.title}\n"
                        f"Reviewed by: {request.user.get_full_name() or request.user.username}\n"
                        f"Date: {report.reviewed_at.strftime('%B %d, %Y %I:%M %p')}\n"
                        + (f"\nAdmin Note:\n{admin_note}\n" if admin_note else "")
                        + (f"\nThis report has been published to the public portal." if publish else "")
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[report.submitted_by.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Email error: {e}")
 
        messages.success(request, f"Report approved{'and published' if publish else ''}.")
    return redirect('report_detail', pk=pk)
 
 
# ─────────────────────────────────────────────
# ADMIN: Decline a report
# ─────────────────────────────────────────────
@login_required
def report_decline(request, pk):
    if not (getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser):
        return redirect('dashboard')
 
    report = get_object_or_404(Report, pk=pk)
 
    if request.method == 'POST':
        admin_note = request.POST.get('admin_note', '').strip()
 
        report.status      = 'DECLINED'
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.admin_note  = admin_note or None
        report.is_published = False
        report.save()
 
        # ── Notify submitter ──────────────────────────────────
        if report.submitted_by.email:
            try:
                send_mail(
                    subject=f"[MSWDO] Your Report Was Declined: {report.title}",
                    message=(
                        f"Your report has been reviewed and declined by the administrator.\n\n"
                        f"Title: {report.title}\n"
                        f"Reviewed by: {request.user.get_full_name() or request.user.username}\n"
                        f"Date: {report.reviewed_at.strftime('%B %d, %Y %I:%M %p')}\n"
                        + (f"\nReason:\n{admin_note}" if admin_note else "")
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[report.submitted_by.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Email error: {e}")
 
        messages.error(request, "Report declined.")
    return redirect('report_detail', pk=pk)
 
 
# ─────────────────────────────────────────────
# STAFF: My Submitted Reports
# ─────────────────────────────────────────────
@login_required
def my_reports(request):
    reports = Report.objects.filter(submitted_by=request.user)
 
    status_filter = request.GET.get('status', '')
    if status_filter:
        reports = reports.filter(status=status_filter)
 
    counts = {
        'total':    Report.objects.filter(submitted_by=request.user).count(),
        'pending':  Report.objects.filter(submitted_by=request.user, status='PENDING').count(),
        'approved': Report.objects.filter(submitted_by=request.user, status='APPROVED').count(),
        'declined': Report.objects.filter(submitted_by=request.user, status='DECLINED').count(),
    }
 
    return render(request, 'my_reports.html', {
        'reports':       reports,
        'status_filter': status_filter,
        'counts':        counts,
    })
 
 
# ─────────────────────────────────────────────
# STAFF: View their own report detail
# ─────────────────────────────────────────────
@login_required
def my_report_detail(request, pk):
    # Staff can only see their own reports; admins can see all
    if getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser:
        report = get_object_or_404(Report, pk=pk)
    else:
        report = get_object_or_404(Report, pk=pk, submitted_by=request.user)
 
    return render(request, 'my_report_detail.html', {'report': report})
 


 
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from collections import Counter
from decimal import Decimal


@login_required
def generate_report(request):
    """
    Auto-generates a PDF report from dashboard data.
    """
    if not (getattr(request.user, 'role', None) in ['admin', 'staff']
            or request.user.is_superuser):
        messages.error(request, "You do not have permission to generate reports.")
        return redirect('dashboard')

    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Gather all dashboard data ──────────────────────────────────────
    total_beneficiaries  = Client.objects.count()
    pending_applications = Application.objects.filter(status='PENDING').count()

    monthly_disbursements = Application.objects.filter(
        status='RELEASED',
        created_at__gte=start_of_month,
        created_at__lte=now,
    ).aggregate(total=Sum('released_amount'))['total'] or Decimal('0')

    pipeline_counts = {
        'Pending':    Application.objects.filter(status='PENDING').count(),
        'Assessment': Application.objects.filter(status='ASSESSMENT').count(),
        'For Approval': Application.objects.filter(status='APPROVAL').count(),
        'For Release':  Application.objects.filter(status='RELEASE').count(),
        'Released':   Application.objects.filter(status='RELEASED').count(),
        'Rejected':   Application.objects.filter(status='REJECTED').count(),
    }

    program_data = (
        Application.objects.values('aid_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    status_data = (
        Application.objects.values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    eligibility_eligible     = Application.objects.filter(eligibility_result='Eligible').count()
    eligibility_not_eligible = Application.objects.filter(eligibility_result='Not Eligible').count()
    total_applications       = Application.objects.count()

    sex_data = (
        Client.objects.values('sex')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    sector_counter = Counter()
    for client in Client.objects.only('sectors'):
        s = client.sectors or []
        if isinstance(s, list):
            sector_counter.update(s)

    latest_clients = (
        Client.objects
        .prefetch_related('applications')
        .order_by('-created_at')[:10]
    )

    total_released = Application.objects.filter(status='RELEASED').count()
    total_rejected = Application.objects.filter(status='REJECTED').count()
    release_rate   = round((total_released / total_applications * 100), 1) if total_applications else 0
    rejection_rate = round((total_rejected / total_applications * 100), 1) if total_applications else 0

    # ── Build PDF ──────────────────────────────────────────────────────
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=20*mm,   bottomMargin=20*mm,
    )

    W = A4[0] - 40*mm  # usable width

    # Colours
    BLUE      = colors.HexColor('#0038A8')
    BLUE_DARK = colors.HexColor('#002882')
    RED       = colors.HexColor('#CE1126')
    YELLOW    = colors.HexColor('#FCD116')
    GREEN     = colors.HexColor('#27ae60')
    LIGHT_BG  = colors.HexColor('#f0f2f7')
    BORDER    = colors.HexColor('#dde3ef')
    WHITE     = colors.white
    GREY_TEXT = colors.HexColor('#5a6a8a')

    styles = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, **kw)

    s_title    = style('Title',    fontName='Helvetica-Bold',   fontSize=20, textColor=WHITE,     alignment=TA_CENTER, spaceAfter=2)
    s_subtitle = style('Sub',      fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#d0d8f0'), alignment=TA_CENTER)
    s_sec      = style('Section',  fontName='Helvetica-Bold',   fontSize=11, textColor=BLUE_DARK, spaceBefore=14, spaceAfter=6)
    s_normal   = style('Normal2',  fontName='Helvetica',        fontSize=8.5, textColor=colors.HexColor('#0f1f4b'), leading=13)
    s_small    = style('Small',    fontName='Helvetica',        fontSize=7.5, textColor=GREY_TEXT)
    s_footer   = style('Footer',   fontName='Helvetica-Oblique',fontSize=7.5, textColor=GREY_TEXT, alignment=TA_CENTER)
    s_key      = style('Key',      fontName='Helvetica-Bold',   fontSize=18, textColor=BLUE_DARK, alignment=TA_CENTER)
    s_keylabel = style('KeyLabel', fontName='Helvetica',        fontSize=7.5, textColor=GREY_TEXT, alignment=TA_CENTER)

    story = []

    # ── HEADER BANNER ────────────────────────────────────────────────
    header_data = [[
        Paragraph("MSWDO PORTAL", style('H1', fontName='Helvetica-Bold', fontSize=7, textColor=colors.HexColor('#d0d8f0'), alignment=TA_CENTER, spaceAfter=2)),
        Paragraph("Dashboard Analytics Report", s_title),
        Paragraph(f"Generated: {now.strftime('%B %d, %Y  %I:%M %p')}", s_subtitle),
    ]]
    header_table = Table([[Paragraph("MSWDO PORTAL — Dashboard Analytics Report", s_title),
                           Paragraph(f"Generated: {now.strftime('%B %d, %Y  %I:%M %p')} &nbsp;·&nbsp; {now.strftime('%A')}", s_subtitle)]],
                         colWidths=[W])
    # Simpler single-cell header
    banner = Table(
        [[Paragraph("MSWDO PORTAL", style('BH', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#aabbdd'), alignment=TA_CENTER)),
          Paragraph("Dashboard Analytics Report", style('BT', fontName='Helvetica-Bold', fontSize=18, textColor=WHITE, alignment=TA_CENTER)),
          Paragraph(f"Generated on {now.strftime('%B %d, %Y')}  ·  {now.strftime('%I:%M %p')}", s_subtitle)]],
        colWidths=[W],
        rowHeights=[None],
    )

    # Clean single-column banner
    banner = Table([
        [Paragraph("<b>MSWDO PORTAL &nbsp;·&nbsp; DASHBOARD ANALYTICS REPORT</b>",
                   style('BannerTitle', fontName='Helvetica-Bold', fontSize=14,
                         textColor=WHITE, alignment=TA_CENTER))],
        [Paragraph(f"Period: {start_of_month.strftime('%B 1, %Y')} – {now.strftime('%B %d, %Y')}  &nbsp;|&nbsp;  Generated: {now.strftime('%B %d, %Y %I:%M %p')}",
                   style('BannerSub', fontName='Helvetica', fontSize=8,
                         textColor=colors.HexColor('#c0cce8'), alignment=TA_CENTER))],
    ], colWidths=[W])
    banner.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), BLUE_DARK),
        ('TOPPADDING',   (0,0), (-1, 0), 14),
        ('BOTTOMPADDING',(0,0), (-1, 0), 4),
        ('TOPPADDING',   (0,1), (-1, 1), 2),
        ('BOTTOMPADDING',(0,1), (-1,-1), 14),
        ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(banner)

    # Yellow accent line
    story.append(HRFlowable(width=W, thickness=3, color=YELLOW, spaceAfter=16))

    # ── KPI CARDS ────────────────────────────────────────────────────
    story.append(Paragraph("● Key Performance Indicators", s_sec))

    def kpi_cell(value, label, color=BLUE):
        return [
            Paragraph(str(value), style(f'KV{label}', fontName='Helvetica-Bold',
                                        fontSize=22, textColor=color, alignment=TA_CENTER)),
            Paragraph(label,       style(f'KL{label}', fontName='Helvetica',
                                        fontSize=7.5, textColor=GREY_TEXT, alignment=TA_CENTER)),
        ]

    kpi_data = [[
        kpi_cell(total_beneficiaries, "Total Beneficiaries"),
        kpi_cell(pending_applications, "Pending Applications", RED if pending_applications > 10 else BLUE),
        kpi_cell(f"₱{monthly_disbursements:,.2f}", "Monthly Disbursements", GREEN),
        kpi_cell(total_applications, "Total Applications"),
    ]]

    # Flatten: each kpi_cell returns 2 rows → use nested table
    def kpi_box(value, label, bg=colors.HexColor('#f8fafc'), accent=BLUE):
        inner = Table([
            [Paragraph(str(value), style(f'kv', fontName='Helvetica-Bold', fontSize=20, textColor=accent, alignment=TA_CENTER))],
            [Paragraph(label,      style(f'kl', fontName='Helvetica',       fontSize=7,  textColor=GREY_TEXT, alignment=TA_CENTER))],
        ], colWidths=[(W-6*3)/4])
        inner.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,-1), bg),
            ('BOX',          (0,0), (-1,-1), 1, BORDER),
            ('TOPPADDING',   (0,0), (-1,-1), 10),
            ('BOTTOMPADDING',(0,0), (-1,-1), 10),
            ('ROUNDEDCORNERS', [8]),
        ]))
        return inner

    kpi_row = Table([[
        kpi_box(total_beneficiaries,        "Total Beneficiaries"),
        kpi_box(pending_applications,        "Pending Applications",  accent=RED if pending_applications > 10 else BLUE),
        kpi_box(f"₱{monthly_disbursements:,.0f}", "Monthly Disbursements", accent=GREEN),
        kpi_box(total_applications,          "Total Applications"),
    ]], colWidths=[(W-6*3)/4]*4, hAlign='LEFT')
    kpi_row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),3), ('RIGHTPADDING',(0,0),(-1,-1),3)]))
    story.append(kpi_row)
    story.append(Spacer(1, 6))

    # Release & rejection rate pills
    rate_data = [[
        Paragraph(f"<b>Release Rate:</b>  {release_rate}%  ({total_released} released out of {total_applications})",
                  style('Rate', fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#1a7a45'))),
        Paragraph(f"<b>Rejection Rate:</b>  {rejection_rate}%  ({total_rejected} rejected out of {total_applications})",
                  style('Rate2', fontName='Helvetica', fontSize=8, textColor=RED)),
    ]]
    rate_table = Table(rate_data, colWidths=[W/2, W/2])
    rate_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#edfaf3')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#fdf0f2')),
        ('BOX',        (0,0), (0,0), 1, colors.HexColor('#b7ebd1')),
        ('BOX',        (1,0), (1,0), 1, colors.HexColor('#f5c0c8')),
        ('TOPPADDING',   (0,0),(-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('LEFTPADDING',  (0,0),(-1,-1), 12),
        ('RIGHTPADDING', (0,0),(-1,-1), 12),
        ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(rate_table)
    story.append(Spacer(1, 14))

    # ── PIPELINE TABLE ────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph("● Application Pipeline", s_sec))

    pipe_header = ['Stage', 'Count', 'Share']
    pipe_rows   = []
    total_pipe  = sum(pipeline_counts.values())
    stage_colors = {
        'Pending': colors.HexColor('#fff7e6'),
        'Assessment': colors.HexColor('#e6f7ff'),
        'For Approval': colors.HexColor('#f3eeff'),
        'For Release': colors.HexColor('#fff3e6'),
        'Released': colors.HexColor('#edfaf3'),
        'Rejected': colors.HexColor('#fdf0f2'),
    }
    stage_accent = {
        'Pending': colors.HexColor('#f59e0b'),
        'Assessment': colors.HexColor('#17a2b8'),
        'For Approval': colors.HexColor('#6f42c1'),
        'For Release': colors.HexColor('#fd7e14'),
        'Released': GREEN,
        'Rejected': RED,
    }
    for stage, count in pipeline_counts.items():
        share = f"{round(count/total_pipe*100,1)}%" if total_pipe else "0%"
        pipe_rows.append([
            Paragraph(f"<b>{stage}</b>", style(f'PS{stage}', fontName='Helvetica-Bold', fontSize=8.5,
                                                textColor=stage_accent.get(stage, BLUE))),
            Paragraph(str(count), style(f'PC{stage}', fontName='Helvetica-Bold', fontSize=8.5,
                                        textColor=stage_accent.get(stage, BLUE), alignment=TA_CENTER)),
            Paragraph(share, style(f'PP{stage}', fontName='Helvetica', fontSize=8, textColor=GREY_TEXT, alignment=TA_CENTER)),
        ])

    pipe_table = Table(
        [[ Paragraph(h, style(f'PH{h}', fontName='Helvetica-Bold', fontSize=8.5,
                              textColor=WHITE, alignment=TA_CENTER))
           for h in pipe_header ]] + pipe_rows,
        colWidths=[W*0.5, W*0.25, W*0.25],
    )
    pipe_table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), BLUE),
        ('TOPPADDING',   (0,0), (-1,-1), 7),
        ('BOTTOMPADDING',(0,0), (-1,-1), 7),
        ('LEFTPADDING',  (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, LIGHT_BG]),
        ('GRID',         (0,0), (-1,-1), 0.5, BORDER),
        ('LINEBELOW',    (0,0), (-1,0),  1,   BLUE_DARK),
    ]))
    story.append(pipe_table)
    story.append(Spacer(1, 14))

    # ── TWO-COLUMN: Program Distribution + Status Distribution ───────
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    def mini_table(title, rows_data, col_widths, header_row):
        """Helper to build a compact titled table."""
        tbl_rows = [[Paragraph(h, style(f'MH{h}', fontName='Helvetica-Bold', fontSize=8,
                                        textColor=WHITE, alignment=TA_CENTER))
                     for h in header_row]]
        for row in rows_data:
            tbl_rows.append(row)
        t = Table(tbl_rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0), BLUE),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, LIGHT_BG]),
            ('GRID',         (0,0), (-1,-1), 0.5, BORDER),
        ]))
        title_cell = Table([[Paragraph(f"<b>{title}</b>",
                                       style(f'MT{title}', fontName='Helvetica-Bold', fontSize=9,
                                             textColor=BLUE_DARK))]],
                           colWidths=[sum(col_widths)])
        title_cell.setStyle(TableStyle([
            ('TOPPADDING',   (0,0),(-1,-1), 0),
            ('BOTTOMPADDING',(0,0),(-1,-1), 5),
        ]))
        wrapper = Table([[title_cell], [t]], colWidths=[sum(col_widths)])
        wrapper.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        return wrapper

    # Program rows
    prog_rows = []
    total_prog = sum(p['count'] for p in program_data)
    for p in program_data:
        pct = round(p['count']/total_prog*100, 1) if total_prog else 0
        prog_rows.append([
            Paragraph(p['aid_type'], style('pr', fontName='Helvetica-Bold', fontSize=8, textColor=BLUE)),
            Paragraph(str(p['count']), style('pc', fontName='Helvetica', fontSize=8, alignment=TA_CENTER)),
            Paragraph(f"{pct}%", style('pp', fontName='Helvetica', fontSize=8, textColor=GREY_TEXT, alignment=TA_CENTER)),
        ])

    # Status rows
    stat_rows = []
    for s in status_data:
        pct = round(s['count']/total_applications*100, 1) if total_applications else 0
        stat_rows.append([
            Paragraph(s['status'].capitalize(), style('sr', fontName='Helvetica-Bold', fontSize=8, textColor=BLUE)),
            Paragraph(str(s['count']), style('sc', fontName='Helvetica', fontSize=8, alignment=TA_CENTER)),
            Paragraph(f"{pct}%", style('sp', fontName='Helvetica', fontSize=8, textColor=GREY_TEXT, alignment=TA_CENTER)),
        ])

    half = (W - 8) / 2
    prog_tbl   = mini_table("Beneficiaries per Program",      prog_rows, [half*0.5, half*0.25, half*0.25], ['Program', 'Count', '%'])
    status_tbl = mini_table("Application Status Distribution", stat_rows, [half*0.5, half*0.25, half*0.25], ['Status',  'Count', '%'])

    two_col = Table([[prog_tbl, status_tbl]], colWidths=[half, half])
    two_col.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                  ('VALIGN',(0,0),(-1,-1),'TOP'), ('RIGHTPADDING',(0,0),(0,-1),8)]))
    story.append(Paragraph("● Program & Status Breakdown", s_sec))
    story.append(two_col)
    story.append(Spacer(1, 14))

    # ── ELIGIBILITY SUMMARY ───────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph("● ML Eligibility Assessment Summary", s_sec))

    elig_pct_yes = round(eligibility_eligible / total_applications * 100, 1) if total_applications else 0
    elig_pct_no  = round(eligibility_not_eligible / total_applications * 100, 1) if total_applications else 0

    elig_table = Table([
        [Paragraph('<b>Result</b>',   style('eh', fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
         Paragraph('<b>Count</b>',    style('ec', fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
         Paragraph('<b>Share</b>',    style('es', fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
         Paragraph('<b>Indicator</b>',style('ei', fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_CENTER))],
        [Paragraph('<b>✔ Eligible</b>',     style('eyr', fontName='Helvetica-Bold', fontSize=8.5, textColor=GREEN)),
         Paragraph(str(eligibility_eligible), style('eyc', fontName='Helvetica-Bold', fontSize=8.5, textColor=GREEN, alignment=TA_CENTER)),
         Paragraph(f"{elig_pct_yes}%",        style('eyp', fontName='Helvetica', fontSize=8, textColor=GREY_TEXT, alignment=TA_CENTER)),
         Paragraph("●" * min(int(elig_pct_yes // 5), 20),
                   style('eyb', fontName='Helvetica', fontSize=8, textColor=GREEN))],
        [Paragraph('<b>✘ Not Eligible</b>', style('enr', fontName='Helvetica-Bold', fontSize=8.5, textColor=RED)),
         Paragraph(str(eligibility_not_eligible), style('enc', fontName='Helvetica-Bold', fontSize=8.5, textColor=RED, alignment=TA_CENTER)),
         Paragraph(f"{elig_pct_no}%",        style('enp', fontName='Helvetica', fontSize=8, textColor=GREY_TEXT, alignment=TA_CENTER)),
         Paragraph("●" * min(int(elig_pct_no // 5), 20),
                   style('enb', fontName='Helvetica', fontSize=8, textColor=RED))],
    ], colWidths=[W*0.35, W*0.15, W*0.15, W*0.35])
    elig_table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), BLUE),
        ('BACKGROUND',   (0,1), (-1,1), colors.HexColor('#edfaf3')),
        ('BACKGROUND',   (0,2), (-1,2), colors.HexColor('#fdf0f2')),
        ('TOPPADDING',   (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 8),
        ('LEFTPADDING',  (0,0), (-1,-1), 10),
        ('GRID',         (0,0), (-1,-1), 0.5, BORDER),
    ]))
    story.append(elig_table)
    story.append(Spacer(1, 14))

    # ── SEX DISTRIBUTION ─────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph("● Client Sex Distribution", s_sec))

    sex_rows = []
    total_sex = sum(s['count'] for s in sex_data)
    for s in sex_data:
        pct = round(s['count']/total_sex*100, 1) if total_sex else 0
        bar = "█" * min(int(pct // 3), 30)
        sex_rows.append([
            Paragraph(s['sex'] or 'Unknown', style('sxr', fontName='Helvetica-Bold', fontSize=8.5, textColor=BLUE)),
            Paragraph(str(s['count']),         style('sxc', fontName='Helvetica-Bold', fontSize=8.5, textColor=BLUE, alignment=TA_CENTER)),
            Paragraph(f"{pct}%",               style('sxp', fontName='Helvetica', fontSize=8, textColor=GREY_TEXT, alignment=TA_CENTER)),
            Paragraph(f"<font color='#3b82f6'>{bar}</font> {pct}%",
                      style('sxb', fontName='Helvetica', fontSize=7.5)),
        ])

    sex_table = Table(
        [[Paragraph(h, style(f'SH{h}', fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_CENTER))
          for h in ['Sex', 'Count', '%', 'Distribution']]] + sex_rows,
        colWidths=[W*0.2, W*0.15, W*0.15, W*0.5],
    )
    sex_table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), BLUE),
        ('TOPPADDING',   (0,0), (-1,-1), 7),
        ('BOTTOMPADDING',(0,0), (-1,-1), 7),
        ('LEFTPADDING',  (0,0), (-1,-1), 10),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, LIGHT_BG]),
        ('GRID',         (0,0), (-1,-1), 0.5, BORDER),
    ]))
    story.append(sex_table)
    story.append(Spacer(1, 14))

    # ── SECTOR DISTRIBUTION ───────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph("● Client Sector Distribution", s_sec))

    sector_rows = []
    total_sectors = sum(sector_counter.values())
    for sector, count in sector_counter.most_common():
        pct = round(count / total_sectors * 100, 1) if total_sectors else 0
        bar = "█" * min(int(pct // 2), 40)
        sector_rows.append([
            Paragraph(sector, style('scr', fontName='Helvetica-Bold', fontSize=8, textColor=BLUE)),
            Paragraph(str(count), style('scc', fontName='Helvetica-Bold', fontSize=8, textColor=BLUE, alignment=TA_CENTER)),
            Paragraph(f"{pct}%", style('scp', fontName='Helvetica', fontSize=8, textColor=GREY_TEXT, alignment=TA_CENTER)),
            Paragraph(f"<font color='#6366f1'>{bar}</font>",
                      style('scb', fontName='Helvetica', fontSize=7.5)),
        ])

    if sector_rows:
        sector_table = Table(
            [[Paragraph(h, style(f'SCH{h}', fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_CENTER))
              for h in ['Sector', 'Count', '%', 'Distribution']]] + sector_rows,
            colWidths=[W*0.25, W*0.15, W*0.15, W*0.45],
        )
        sector_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0), BLUE),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 10),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, LIGHT_BG]),
            ('GRID',         (0,0), (-1,-1), 0.5, BORDER),
        ]))
        story.append(sector_table)
    else:
        story.append(Paragraph("No sector data available.", s_small))
    story.append(Spacer(1, 14))

    # ── LATEST CLIENTS TABLE ──────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph("● Latest 10 Clients", s_sec))

    client_header = ['#', 'Name', 'Barangay', 'Program', 'Status', 'Date Registered']
    client_rows   = []
    for i, c in enumerate(latest_clients, 1):
        latest_app = c.applications.first()
        client_rows.append([
            Paragraph(str(i), style(f'cn{i}', fontName='Helvetica', fontSize=7.5, textColor=GREY_TEXT, alignment=TA_CENTER)),
            Paragraph(f"{c.first_name} {c.last_name}", style(f'cname{i}', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0f1f4b'))),
            Paragraph(c.barangay or '—', style(f'cbgy{i}', fontName='Helvetica', fontSize=7.5, textColor=GREY_TEXT)),
            Paragraph(latest_app.aid_type if latest_app else '—', style(f'cprog{i}', fontName='Helvetica-Bold', fontSize=7.5, textColor=BLUE)),
            Paragraph(latest_app.status.capitalize() if latest_app else '—', style(f'cstat{i}', fontName='Helvetica', fontSize=7.5, textColor=GREY_TEXT)),
            Paragraph(c.created_at.strftime('%b %d, %Y'), style(f'cdate{i}', fontName='Helvetica', fontSize=7.5, textColor=GREY_TEXT)),
        ])

    client_table = Table(
        [[Paragraph(h, style(f'CH{h}', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_CENTER))
          for h in client_header]] + client_rows,
        colWidths=[W*0.05, W*0.25, W*0.18, W*0.14, W*0.15, W*0.23],
    )
    client_table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), BLUE),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, LIGHT_BG]),
        ('GRID',         (0,0), (-1,-1), 0.5, BORDER),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 20))

    # ── FOOTER ───────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=1, color=YELLOW, spaceAfter=6))
    story.append(Paragraph(
        f"MSWDO Portal  ·  Auto-generated Report  ·  {now.strftime('%B %d, %Y at %I:%M %p')}  ·  Confidential",
        s_footer
    ))
    story.append(Paragraph(
        "This report was automatically generated from live dashboard data. For official use only.",
        s_footer
    ))

    # ── Build & Return ─────────────────────────────────────────────────
    doc.build(story)
    buffer.seek(0)

    filename = f"MSWDO_Dashboard_Report_{now.strftime('%Y%m%d_%H%M')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def program_rate_prediction(request):
    """
    3-Year application rate prediction for every MSWDO program.
    Uses simple least-squares linear regression on monthly application counts.
    """
    import datetime
    from collections import defaultdict
 
    # Guard: staff/admin only
    if not (
        getattr(request.user, 'role', None) in ['admin', 'staff']
        or request.user.is_superuser
    ):
        return redirect('landing')
 
    PROGRAMS = {
        'AICS':        'AICS (Aid to Individuals in Crisis Situation)',
        'SEA':         'Sustainable Livelihood (SEA)',
        'REDCARD':     'Red Card',
        'EDUCATIONAL': 'Educational Assistance',
    }
 
    # ── 1. Fetch all historical monthly counts per program ───────────────────
    qs = (
        Application.objects
        .annotate(month=TruncMonth('created_at'))
        .values('aid_type', 'month')
        .annotate(count=Count('id'))
        .order_by('aid_type', 'month')
    )
 
    raw = defaultdict(list)   # { 'AICS': [(date, count), ...], ... }
    for row in qs:
        if row['aid_type'] in PROGRAMS and row['month'] is not None:
            # TruncMonth may return datetime or date depending on DB
            d = row['month']
            if hasattr(d, 'date'):
                d = d.date()
            raw[row['aid_type']].append((d, row['count']))
 
    # ── 2. Determine epoch (earliest month ever seen, or 2 years ago) ────────
    all_dates = [d for entries in raw.values() for (d, _) in entries]
    today     = timezone.now().date()
 
    if all_dates:
        epoch = min(all_dates).replace(day=1)
    else:
        epoch = today.replace(day=1, month=1, year=today.year - 2)
 
    def month_idx(d):
        """0-based integer index relative to epoch."""
        d = d.replace(day=1)
        return (d.year - epoch.year) * 12 + (d.month - epoch.month)
 
    def idx_to_label(idx):
        """Convert a month index back to 'YYYY-MM' string."""
        total_months = epoch.month + idx - 1   # 0-based offset from epoch month
        yr = epoch.year + total_months // 12
        mo = total_months % 12 + 1
        return f"{yr}-{mo:02d}"
 
    # ── 3. Linear regression ─────────────────────────────────────────────────
    def linear_regression(xy_pairs):
        n = len(xy_pairs)
        if n == 0:
            return 0.0, 0.0
        if n == 1:
            return 0.0, float(xy_pairs[0][1])
        sx  = sum(x for x, _ in xy_pairs)
        sy  = sum(y for _, y in xy_pairs)
        sxy = sum(x * y for x, y in xy_pairs)
        sx2 = sum(x * x for x, _ in xy_pairs)
        denom = n * sx2 - sx * sx
        if denom == 0:
            return 0.0, sy / n
        slope     = (n * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        return slope, intercept
 
    # ── 4. Build per-program data ────────────────────────────────────────────
    cur_idx      = month_idx(today.replace(day=1))
    programs_data = {}
    summary_rows  = []
 
    for code, prog_label in PROGRAMS.items():
        entries = raw.get(code, [])
 
        # Convert to (x, y) pairs for regression
        xy = [(month_idx(d), c) for d, c in entries]
        slope, intercept = linear_regression(xy)
 
        # ── Historical: last 24 months (fill 0 for months with no applications)
        hist_labels = []
        hist_values = []
        hist_map    = {month_idx(d): c for d, c in entries}
        start_idx   = max(cur_idx - 23, 0)
 
        for i in range(start_idx, cur_idx + 1):
            hist_labels.append(idx_to_label(i))
            hist_values.append(hist_map.get(i, 0))
 
        # ── Forecast: next 36 months ─────────────────────────────────────────
        forecast_labels = []
        forecast_values = []
        yearly_totals   = [0, 0, 0]    # Year1, Year2, Year3
 
        for offset in range(1, 37):
            fi  = cur_idx + offset
            val = max(0, round(intercept + slope * fi))
            forecast_labels.append(idx_to_label(fi))
            forecast_values.append(val)
            yearly_totals[(offset - 1) // 12] += val
 
        year_labels = [
            str(today.year + 1),
            str(today.year + 2),
            str(today.year + 3),
        ]
 
        # Trend label
        if slope > 0.5:
            trend = "📈 Increasing"
            trend_class = "text-success"
        elif slope < -0.5:
            trend = "📉 Decreasing"
            trend_class = "text-danger"
        else:
            trend = "➡️ Stable"
            trend_class = "text-warning"
 
        avg_monthly_y1 = round(yearly_totals[0] / 12) if yearly_totals[0] else 0
 
        programs_data[code] = {
            'label':            prog_label,
            'hist_labels':      hist_labels,
            'hist_values':      hist_values,
            'forecast_labels':  forecast_labels,
            'forecast_values':  forecast_values,
            'yearly_forecast':  yearly_totals,
            'year_labels':      year_labels,
            'slope':            round(slope, 4),
            'trend':            trend,
            'trend_class':      trend_class,
            'avg_monthly_y1':   avg_monthly_y1,
            'total_historical': sum(c for _, c in entries),
        }
 
        summary_rows.append({
            'code':          code,
            'label':         prog_label,
            'trend':         trend,
            'trend_class':   trend_class,
            'y1':            yearly_totals[0],
            'y2':            yearly_totals[1],
            'y3':            yearly_totals[2],
            'avg_monthly_y1': avg_monthly_y1,
        })
 
    context = {
        'programs_data_json': json.dumps(programs_data),
        'summary_rows':       summary_rows,
        'current_year':       today.year,
    }
    return render(request, 'program_rate_prediction.html', context)


@login_required
def barangay_analytics(request):
    from collections import Counter
    from django.db.models.functions import TruncMonth
 
    if not (
        getattr(request.user, 'role', None) in ['admin', 'staff']
        or request.user.is_superuser
    ):
        return redirect('landing')
 
    all_barangays = (
        Client.objects
        .filter(barangay__isnull=False)
        .exclude(barangay='')
        .values_list('barangay', flat=True)
        .distinct()
        .order_by('barangay')
    )
 
    selected_brgy = request.GET.get('barangay', '').strip()
    analytics = None
 
    if selected_brgy:
        clients    = Client.objects.filter(barangay__iexact=selected_brgy)
        client_ids = list(clients.values_list('id', flat=True))
 
        # ── Prefetched queryset for Python-side processing only ───────────────
        apps = (
            Application.objects
            .filter(client_id__in=client_ids)
            .select_related('client')
            .prefetch_related('aics_detail', 'redcard_detail', 'educational_detail')
            .order_by('-created_at')
        )
 
        # ── Clean queryset for all DB aggregations (no prefetch/select_related)
        base_qs = Application.objects.filter(client_id__in=client_ids)
 
        total_apps    = base_qs.count()
        total_clients = clients.count()
 
        # ── Programs ─────────────────────────────────────────────────────────
        PROGRAM_LABELS = {
            'AICS':        'AICS',
            'SEA':         'Livelihood (SEA)',
            'REDCARD':     'Red Card',
            'EDUCATIONAL': 'Educational Assistance',
        }
        raw_prog = dict(
            base_qs.values('aid_type').annotate(n=Count('id')).values_list('aid_type', 'n')
        )
        program_data = [
            {'code': code, 'label': lbl, 'count': int(raw_prog.get(code, 0))}
            for code, lbl in PROGRAM_LABELS.items()
        ]
 
        # ── Reason extractor (Python-side, uses prefetched data) ──────────────
        def top_reasons(app_list, limit=5):
            counter = Counter()
            for app in app_list:
                found = False
                try:
                    ct = app.aics_detail.crisis_type
                    if ct:
                        counter[ct] += 1
                        found = True
                except Exception:
                    pass
                if not found:
                    try:
                        et = app.redcard_detail.emergency_type
                        if et:
                            counter[et] += 1
                            found = True
                    except Exception:
                        pass
                if not found:
                    try:
                        cg = app.educational_detail.course_or_grade
                        if cg:
                            counter['Education: ' + str(cg)] += 1
                            found = True
                    except Exception:
                        pass
                if not found:
                    try:
                        secs = app.client.sectors
                        if isinstance(secs, list) and secs:
                            for s in secs:
                                if s:
                                    counter[str(s)] += 1
                            found = True
                    except Exception:
                        pass
                if not found:
                    if getattr(app, 'eligibility_reason', None):
                        snippet = app.eligibility_reason[:60].split('.')[0].strip()
                        if snippet:
                            counter[snippet] += 1
                            found = True
                if not found:
                    counter['Unspecified'] += 1
            return [{'label': lbl, 'count': int(cnt)} for lbl, cnt in counter.most_common(limit)]
 
        app_list = list(apps)
        reasons_by_program = {
            code: top_reasons([a for a in app_list if a.aid_type == code])
            for code in PROGRAM_LABELS
        }
        overall_reasons = top_reasons(app_list, limit=8)
 
        # ── Monthly trend — use base_qs (clean, no prefetch conflicts) ────────
        monthly_qs = (
            base_qs
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(n=Count('id'))
            .order_by('month')
        )
        month_map = {}
        for row in monthly_qs:
            d = row['month']
            if d is None:
                continue
            if hasattr(d, 'date'):
                d = d.date()
            month_map[d.strftime('%Y-%m')] = int(row['n'])
 
        today = timezone.now().date()
        trend_labels, trend_values = [], []
        for i in range(11, -1, -1):
            mo = today.month - i
            yr = today.year
            while mo <= 0:
                mo += 12
                yr -= 1
            key = '{}-{:02d}'.format(yr, mo)
            trend_labels.append(key)
            trend_values.append(month_map.get(key, 0))
 
        # ── Status counts — use base_qs ────────────────────────────────────
        status_counts = {
            str(k): int(v)
            for k, v in (
                base_qs
                .values('status')
                .annotate(n=Count('id'))
                .values_list('status', 'n')
            )
        }
 
        # ── Sector profile ────────────────────────────────────────────────
        sector_counter = Counter()
        for c in clients:
            if isinstance(getattr(c, 'sectors', None), list):
                for s in c.sectors:
                    if s:
                        sector_counter[str(s)] += 1
        top_sectors = [
            {'label': s, 'count': int(cnt)}
            for s, cnt in sector_counter.most_common(6)
        ]
 
        top_prog   = max(program_data, key=lambda x: x['count'])['label'] if total_apps else '-'
        top_reason = overall_reasons[0]['label'] if overall_reasons else '-'
 
        analytics = {
            'barangay':           selected_brgy,
            'total_apps':         int(total_apps),
            'total_clients':      int(total_clients),
            'program_data':       program_data,
            'reasons_by_program': reasons_by_program,
            'overall_reasons':    overall_reasons,
            'trend_labels':       trend_labels,
            'trend_values':       trend_values,
            'status_counts':      status_counts,
            'top_sectors':        top_sectors,
            'top_program':        top_prog,
            'top_reason':         top_reason,
        }
 
    context = {
        'all_barangays':  list(all_barangays),
        'selected_brgy':  selected_brgy,
        'analytics':      analytics,
        'analytics_json': json.dumps(analytics, ensure_ascii=False) if analytics else 'null',
    }
    return render(request, 'barangay_analytics.html', context)