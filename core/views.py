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
    # BASIC COUNTS
    # =============================
    total_beneficiaries  = Client.objects.count()
    pending_applications = Application.objects.filter(status='PENDING').count()

    monthly_disbursements = Application.objects.filter(
        status='RELEASED',
        created_at__month=now().month,
        created_at__year=now().year,
    ).aggregate(total=Sum('approved_amount'))['total'] or 0

    # =============================
    # PIPELINE STAGE COUNTS
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
    # BAR CHART: BENEFICIARIES PER PROGRAM
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
    # DOUGHNUT: STATUS DISTRIBUTION
    # =============================
    status_data = (
        Application.objects
        .values('status')
        .annotate(count=Count('id'))
    )

    status_labels = [s['status'].capitalize() for s in status_data]
    status_values = [s['count'] for s in status_data]

    # =============================
    # BAR CHART: ELIGIBLE VS NOT ELIGIBLE
    # =============================
    eligible_count     = Application.objects.filter(eligibility_result='Eligible').count()
    not_eligible_count = Application.objects.filter(eligibility_result='Not Eligible').count()

    eligibility_labels = ['Eligible', 'Not Eligible']
    eligibility_values = [eligible_count, not_eligible_count]

    # =============================
    # LINE CHART: CLIENTS OVER TIME
    # =============================
    six_months_ago = now() - timedelta(days=180)

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
    # LATEST CLIENTS
    # =============================
    latest_clients = Client.objects.order_by('-created_at')[:5]

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

        'latest_clients': latest_clients,
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
@login_required
def add_client(request):

    if not (getattr(request.user, "role", None) in ["staff", "admin"] or request.user.is_superuser):
        return redirect("dashboard")

    if request.method == "POST":
        try:
            # ================= CLIENT =================
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
                has_disability=request.POST.get("has_disability", "No"),
                is_senior=request.POST.get("is_senior", "No"),
                previous_aid=request.POST.get("previous_aid", "No"),
                is_4ps=request.POST.get("is_4ps", "No"),
                fourps_id=request.POST.get("fourps_id") or None,
            )

            # ================= FAMILY MEMBERS =================
            index = 0
            while index <= 50:
                name = request.POST.get(f"family_name_{index}", "").strip()
                if name:
                    cs_s  = request.POST.get(f"family_cs_s_{index}")
                    cs_m  = request.POST.get(f"family_cs_m_{index}")
                    cs_w  = request.POST.get(f"family_cs_w_{index}")
                    civil_status = "S" if cs_s else "M" if cs_m else "W" if cs_w else None

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

            # ================= APPLICATION =================
            aid_type = request.POST.get("program")

            application = Application.objects.create(
                client=client,
                aid_type=aid_type,
                status="PENDING",
            )

            # ================= ML PREDICTION =================
            try:
                ml_input = {
                    "monthly_income": float(client.monthly_income),
                    "household_size": client.household_size,
                    "has_disability": 1 if client.has_disability == "Yes" else 0,
                    "is_senior":      1 if client.is_senior      == "Yes" else 0,
                    "previous_aid":   1 if client.previous_aid   == "Yes" else 0,
                }
                prediction = predict_input(ml_input)
                application.eligibility_result = "Eligible" if prediction == 1 else "Not Eligible"
            except Exception as ml_error:
                print("ML ERROR:", ml_error)
                application.eligibility_result = "Not Eligible"

            application.save()

            # ================= PROGRAM-SPECIFIC DETAILS =================
            docs = {}

            if aid_type == "AICS":
                AICSDetail.objects.create(
                    application=application,
                    crisis_type=request.POST.get("aics_crisis_type"),
                )
                docs = {
                    "AICS Barangay Cert": request.FILES.get("aics_barangay_cert"),
                    "Medical/Death Cert": request.FILES.get("aics_medical_death_cert"),
                    "Official Receipt":   request.FILES.get("aics_receipt"),
                }

            elif aid_type == "SEA":
                SEADetail.objects.create(application=application)
                docs = {
                    "Barangay Clearance": request.FILES.get("sea_barangay_clearance"),
                    "Cedula":             request.FILES.get("sea_cedula"),
                    "Project Proposal":   request.FILES.get("sea_project_proposal"),
                    "Project Picture":    request.FILES.get("sea_project_picture"),
                }

            elif aid_type == "REDCARD":
                REDCARDDetail.objects.create(
                    application=application,
                    emergency_type=request.POST.get("redcard_emergency_type"),
                    reason=request.POST.get("redcard_reason"),
                    usage_count=request.POST.get("redcard_usage") or 1,
                )
                docs = {
                    "Birth Certificate":         request.FILES.get("redcard_birth_cert"),
                    "Valid ID Picture":           request.FILES.get("redcard_valid_id"),
                    "Certificate of Indigency":  request.FILES.get("redcard_indigency"),
                }

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

            # ================= SAVE DOCUMENTS =================
            for doc_name, file in docs.items():
                if file:
                    ApplicationDocument.objects.create(
                        application=application,
                        name=doc_name,
                        file=file,
                    )

            messages.success(request, "Application submitted successfully!")
            return redirect("application_detail", application.id)

        except Exception as e:
            import traceback
            traceback.print_exc()
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

@login_required
def assistance_program(request, program='SEA'):
    user = request.user

    # ✅ ROLE CHECK (your custom role system)
    if not (
        user.is_superuser
        or getattr(user, 'role', None) in ['admin', 'staff']
    ):
        return redirect('landing')

    # ✅ GET PROGRAM (from URL OR dropdown)
    program = request.GET.get('program', program).upper()

    # 🛑 SAFETY: ensure valid program
    if program not in ['SEA', 'AICS', 'REDCARD', 'EA']:
        program = 'SEA'

    # ✅ MAIN QUERY (THIS is your assistance records)
    qs = (
        Application.objects
        .filter(aid_type=program)
        .select_related('client')
        .prefetch_related('documents')  # 🚀 avoids N+1 query for files
        .order_by('-created_at')
    )

    # 🔍 SEARCH FILTER
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(client__first_name__icontains=q) |
            Q(client__last_name__icontains=q) |
            Q(client__email__icontains=q)
        )

    # 📌 STATUS FILTER
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    # ⏳ PENDING SHORTCUT
    if request.GET.get('view') == 'pending':
        qs = qs.filter(status='pending')

    # 📤 CSV EXPORT
    if request.GET.get('export') == 'csv':
        return assistance_export_csv(qs, program)

    # 📄 PAGINATION
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

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
        'Email',
        'Barangay',
        'Livelihood',
        'Requested Amount (₱)',
        'Status',
        'Date',
    ])

    for idx, app in enumerate(qs, start=1):
        client = app.client

        name = f"{client.first_name} {client.last_name}"
        email = client.email or ''
        barangay = client.barangay or ''
        livelihood = client.livelihood or ''
        amount = f"₱{float(app.requested_amount or 0):,.2f}"  # ✅ FIXED
        status = app.status
        date = app.created_at.strftime('%Y-%m-%d %H:%M')

        writer.writerow([
            idx,
            smart_str(name),
            smart_str(email),
            smart_str(barangay),
            smart_str(livelihood),
            amount,
            status,
            date,
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
    """Advances application through the pipeline: PENDING→ASSESSMENT→APPROVAL→RELEASE→RELEASED"""
    application = get_object_or_404(Application, pk=pk)

    if not (getattr(request.user, 'role', None) in ['admin', 'staff'] or request.user.is_superuser):
        messages.error(request, "You do not have permission to update applications.")
        return redirect('dashboard')

    pipeline = ['PENDING', 'ASSESSMENT', 'APPROVAL', 'RELEASE', 'RELEASED']

    if application.status in pipeline:
        current_index = pipeline.index(application.status)
        if current_index < len(pipeline) - 1:
            next_status = pipeline[current_index + 1]
            application.status = next_status

            # Track who did what at each stage
            if next_status == 'ASSESSMENT':
                application.assessed_by = request.user
                application.assessed_at = timezone.now()
            elif next_status == 'APPROVAL':
                application.approved_by = request.user
                application.approved_at = timezone.now()
            elif next_status == 'RELEASED':
                application.released_at = timezone.now()

            application.save()

            # ── Notify client when assistance is released ──────────────
            if next_status == 'RELEASED':
                client = application.client

                # Email
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
  {"Approved Amount: ₱" + str(application.approved_amount) if application.approved_amount else ""}

Please visit the MSWDO office to claim your assistance. Bring a valid ID.

For inquiries, please contact our office directly.

Thank you,
MSWDO Office
Municipal Social Welfare and Development Office
"""
                    try:
                        send_mail(
                            subject,
                            message.strip(),
                            from_email=None,
                            recipient_list=[client.email],
                            fail_silently=False,
                        )
                        print(f"Release email sent to {client.email}")
                    except Exception as e:
                        print(f"Release email failed: {e}")

                # SMS
                if client.contact_no:
                    sms_message = (
                        f"Good day {client.full_name}! "
                        f"Your {application.get_aid_type_display()} assistance has been RELEASED. "
                        f"Please visit the MSWDO office to claim it. Bring a valid ID. "
                        f"Thank you!"
                    )
                    try:
                        sms_response = send_sms(client.contact_no, sms_message)
                        print("SMS Response:", sms_response)
                    except Exception as e:
                        print(f"Release SMS failed: {e}")

            messages.success(request, f"Application moved to: {application.get_status_display()}")
        else:
            messages.info(request, "Application is already at the final stage.")
    else:
        messages.error(request, "Cannot advance a rejected application.")

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

    # 🔐 Allow only staff/admin/superuser
    if not (
        getattr(request.user, 'role', None) in ['staff', 'admin']
        or request.user.is_superuser
    ):
        return redirect('landing')

    # ✅ Must match PROGRAM_CHOICES
    allowed_programs = ["AICS", "SEA", "REDCARD", "EDUCATIONAL"]

    program = request.GET.get("program", "").upper()

    # 🔹 Base queryset (PENDING only)
    qs = (
        Application.objects
        .filter(status="PENDING")
        .select_related("client")
        .order_by("-created_at")
    )

    # 🔹 Filter by program
    if program in allowed_programs:
        qs = qs.filter(aid_type=program)
    else:
        program = "ALL"

    # 🔹 Search client
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search) |
            Q(client__email__icontains=search)
        )

    # 🔹 Pagination
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "applications": page_obj,
        "program": program,
        "allowed_programs": allowed_programs,
        "search": search,
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

    if not (getattr(request.user, 'role', None) in ['admin', 'staff'] or request.user.is_superuser):
        messages.error(request, "You do not have permission to approve applications.")
        return redirect('dashboard')

    application.status = 'APPROVAL'   # moves to "For Approval" stage in the pipeline
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
            send_mail(subject, message, from_email=None, recipient_list=[client.email], fail_silently=False)
        except Exception as e:
            print("Email sending failed:", e)

    # ── SMS ────────────────────────────────────────────────────────────
    if client.contact_no:
        sms_message = (
            f"Good day {client.full_name}! "
            f"Your {application.get_aid_type_display()} assistance application has been APPROVED "
            f"and is now for release processing. MSWDO Office."
        )
        try:
            sms_response = send_sms(client.contact_no, sms_message)
            print("SMS Response:", sms_response)
            if sms_response.get("status") != 200:
                print(f"SMS may not have delivered to {client.contact_no}.")
        except Exception as e:
            print("SMS sending failed:", e)
    else:
        print("No contact number found for this client.")

    messages.success(request, "Application approved. Client notified by email and SMS (Globe only).")
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
    # Auto-convert PH number format (09XXXXXXXXX → 639XXXXXXXXX)
    if phone_number.startswith("09"):
        phone_number = "63" + phone_number[1:]

    payload = {
        "apikey": settings.IPROG_API_KEY,
        "number": phone_number,
        "message": message,
    }

    try:
        response = requests.post(settings.IPROG_URL, data=payload, timeout=10)

        print("===== SMS DEBUG =====")
        print("Number Sent To:", phone_number)
        print("Status Code:   ", response.status_code)
        print("Response:      ", response.text)
        print("=====================")

        return response.json()

    except Exception as e:
        print("SMS ERROR:", str(e))
        return {"error": str(e)}


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
        # Update client
        client.first_name = request.POST.get('first_name')
        client.last_name = request.POST.get('last_name')
        client.contact_no = request.POST.get('contact_no')
        client.email = request.POST.get('email')
        client.save()

        # Update application
        application.aid_type = request.POST.get('aid_type')
        application.requested_amount = request.POST.get('requested_amount')
        application.reason = request.POST.get('reason')
        application.save()

        messages.success(request, "Application updated.")
        return redirect('application_detail', pk=pk)

    return render(request, 'application_edit.html', {
        'application': application,
        'client': client
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



def client_register(request):
    if request.method == "POST":
        password  = request.POST.get('password')
        password2 = request.POST.get('confirm_password')

        if password != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'client_register.html')

        email = request.POST.get('email') or None

        try:
            client = Client.objects.create(
                # I. Personal
                first_name=request.POST.get('first_name'),
                middle_name=request.POST.get('middle_name') or None,
                last_name=request.POST.get('last_name'),
                sex=request.POST.get('sex'),
                birth_date=request.POST.get('birth_date'),
                civil_status=request.POST.get('civil_status'),
                nationality=request.POST.get('nationality') or 'Filipino',

                # II. Address & Contact
                address=request.POST.get('address'),
                barangay=request.POST.get('barangay'),
                municipality=request.POST.get('municipality'),
                contact_no=request.POST.get('contact_no'),
                email=email,

                # III. Socio-Economic
                livelihood=request.POST.get('livelihood'),
                monthly_income=request.POST.get('monthly_income') or 0,
                household_size=request.POST.get('household_size') or 1,
                has_disability=request.POST.get('has_disability', 'No'),
                is_senior=request.POST.get('is_senior', 'No'),
                previous_aid=request.POST.get('previous_aid', 'No'),
            )

            # ── Family Members ──────────────────────────────────
            index = 0
            while index <= 50:
                name = request.POST.get(f"family_name_{index}", "").strip()
                if name:
                    cs_s  = request.POST.get(f"family_cs_s_{index}")
                    cs_m  = request.POST.get(f"family_cs_m_{index}")
                    cs_w  = request.POST.get(f"family_cs_w_{index}")
                    civil_status = "S" if cs_s else "M" if cs_m else "W" if cs_w else None

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

            # ── Account ─────────────────────────────────────────
            account = ClientAccount.objects.create(
                client=client,
                email=request.POST.get('email'),
            )
            account.set_password(password)
            account.save()

            messages.success(request, "Registration successful. You can now log in.")
            return redirect('client_login')

        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f"Registration failed: {e}")

    return render(request, 'client_register.html')

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
        # ── Personal ─────────────────────────────────────
        client.first_name  = request.POST.get('first_name')
        client.middle_name = request.POST.get('middle_name') or None
        client.last_name   = request.POST.get('last_name')
        client.sex         = request.POST.get('sex')
        client.birth_date  = request.POST.get('birth_date')       # ✅ was 'dob'
        client.civil_status= request.POST.get('civil_status')
        client.nationality = request.POST.get('nationality') or 'Filipino'

        # ── Address & Contact ────────────────────────────
        client.address      = request.POST.get('address')
        client.barangay     = request.POST.get('barangay')
        client.municipality = request.POST.get('municipality')
        client.contact_no   = request.POST.get('contact_no')       # ✅ was 'contact_number'
        client.email        = request.POST.get('email') or None

        # ── Socio-Economic ───────────────────────────────
        client.livelihood     = request.POST.get('livelihood')
        client.monthly_income = request.POST.get('monthly_income') or 0
        client.household_size = request.POST.get('household_size') or 1
        client.has_disability = request.POST.get('has_disability', 'No')  # ✅ was 'pwd'
        client.is_senior      = request.POST.get('is_senior', 'No')       # ✅ was 'senior'
        client.previous_aid   = request.POST.get('previous_aid', 'No')    # ✅ was 'previous_dswd'

        client.save()

        # ── Family Members — replace all existing ────────
        client.family_members.all().delete()

        index = 0
        while index <= 50:
            name = request.POST.get(f"family_name_{index}", "").strip()
            if name:
                cs_s  = request.POST.get(f"family_cs_s_{index}")
                cs_m  = request.POST.get(f"family_cs_m_{index}")
                cs_w  = request.POST.get(f"family_cs_w_{index}")
                civil_status = "S" if cs_s else "M" if cs_m else "W" if cs_w else None

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

        messages.success(request, "Profile updated successfully.")
        return redirect('client_edit_profile')

    family_members = client.family_members.all()
    return render(request, 'client_edit_profile.html', {
        'client': client,
        'family_members': family_members,
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
            return redirect("client_apply_program")

        with transaction.atomic():

            # ================= CREATE MAIN APPLICATION =================
            application = Application.objects.create(
                client=client,
                aid_type=aid_type,
                status="PENDING"
            )

            docs = {}

            # ================= AICS =================
            if aid_type == "AICS":
                AICSDetail.objects.create(
                    application=application,
                    crisis_type=request.POST.get("aics_crisis_type"),
                    assessment_findings=request.POST.get("aics_assessment"),
                    approved_amount=Decimal(request.POST.get("aics_approved_amount") or 0),
                )

                docs = {
                    "AICS Barangay Certificate": request.FILES.get("aics_barangay_cert"),
                    "Medical / Death Certificate": request.FILES.get("aics_medical_death_cert"),
                    "Official Receipt": request.FILES.get("aics_receipt"),
                }

            # ================= SEA =================
            elif aid_type == "SEA":
                SEADetail.objects.create(
                    application=application,
                    business_type=request.POST.get("sea_business_type"),
                    capital_requested=Decimal(request.POST.get("sea_capital") or 0),
                    training_completed=request.POST.get("sea_training") == "Yes",
                    monitoring_notes=request.POST.get("sea_monitoring"),
                )

                docs = {
                    "Barangay Clearance": request.FILES.get("sea_barangay_clearance"),
                    "Cedula": request.FILES.get("sea_cedula"),
                    "Project Proposal": request.FILES.get("sea_project_proposal"),
                    "Project Picture": request.FILES.get("sea_project_picture"),
                }

            # ================= RED CARD =================
            elif aid_type == "REDCARD":
                REDCARDDetail.objects.create(
                    application=application,
                    emergency_type=request.POST.get("redcard_emergency_type"),
                    usage_count=int(request.POST.get("redcard_usage") or 0),
                )

                docs = {
                    "Birth Certificate": request.FILES.get("redcard_birth_cert"),
                    "Valid ID Picture": request.FILES.get("redcard_valid_id"),
                    "Certificate of Indigency": request.FILES.get("redcard_indigency"),
                }

            # ================= EDUCATIONAL ASSISTANCE =================
            elif aid_type == "EA":
                EducationalAssistanceDetail.objects.create(
                    application=application,
                    school_name=request.POST.get("school_name"),
                    course_or_grade=request.POST.get("course_level"),
                )

                docs = {
                    "Letter of Appeal": request.FILES.get("edu_letter"),
                    "Certificate of Indigency": request.FILES.get("edu_indigency"),
                    "Grades": request.FILES.get("edu_grades"),
                    "Certificate of Enrollment": request.FILES.get("edu_enrollment"),
                    "Billing Statement": request.FILES.get("edu_billing"),
                    "Official Receipt": request.FILES.get("edu_receipt"),
                }

            # ================= SAVE DOCUMENTS =================
            for name, file in docs.items():
                if file:
                    ApplicationDocument.objects.create(
                        application=application,
                        document_name=name,
                        file=file
                    )

            # ================= 🔔 CREATE NOTIFICATIONS =================
            staff_admins = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)

            for user in staff_admins.distinct():
                Notification.objects.create(
                    recipient=user,
                    message=f"New application from {client.full_name} for {aid_type}",
                    link=f"/application/{application.id}/"
                )

        return redirect("client_applications")

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
    if not (request.user.is_staff or request.user.is_superuser):
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