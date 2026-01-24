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
    total_beneficiaries = Client.objects.count()

    pending_applications = Application.objects.filter(
        status='pending'
    ).count()

    monthly_disbursements = Application.objects.filter(
        status='approved',
        created_at__month=now().month
    ).aggregate(total=Sum('requested_amount'))['total'] or 0

    # ❌ REMOVE ACTIVE EMERGENCIES
    # active_emergencies → DELETE COMPLETELY

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
    # 🆕 BAR CHART: ELIGIBLE VS NOT ELIGIBLE
    # =============================
    eligible_count = Application.objects.filter(status='approved').count()
    not_eligible_count = Application.objects.filter(status='rejected').count()

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
        'total_beneficiaries': total_beneficiaries,
        'pending_applications': pending_applications,
        'monthly_disbursements': monthly_disbursements,

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

@login_required
def add_client(request):
    if not (
        getattr(request.user, 'role', None) in ['staff', 'admin']
        or request.user.is_superuser
    ):
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            # ===============================
            # I. CREATE CLIENT
            # ===============================
            client = Client.objects.create(
                first_name=request.POST.get('first_name', '').strip(),
                middle_name=request.POST.get('middle_name') or None,
                last_name=request.POST.get('last_name', '').strip(),

                sex=request.POST.get('sex') or None,
                birth_date=datetime.strptime(
                    request.POST.get('birth_date'), "%Y-%m-%d"
                ).date() if request.POST.get('birth_date') else None,

                civil_status=request.POST.get('civil_status') or None,
                nationality=request.POST.get('nationality') or None,

                address=request.POST.get('address') or None,
                barangay=request.POST.get('barangay') or None,
                municipality=request.POST.get('municipality') or None,

                email=request.POST.get('email') or None,
                contact_no=request.POST.get('contact_no') or None,

                livelihood=request.POST.get('livelihood') or None,
                monthly_income=Decimal(request.POST.get('monthly_income') or 0),
                household_size=int(request.POST.get('household_size') or 1),

                has_disability=request.POST.get('has_disability'),
                is_senior=request.POST.get('is_senior'),
                previous_aid=request.POST.get('previous_aid'),
            )

            # ===============================
            # II. CREATE APPLICATION
            # ===============================
            application = Application.objects.create(
                client=client,
                aid_type=request.POST.get('aid_type'),
                requested_amount=Decimal(request.POST.get('requested_amount') or 0),
                reason=request.POST.get('reason') or None,
                status='pending'
            )

            # ===============================
            # III. ML ELIGIBILITY PREDICTION
            # ===============================
            ml_input = {
                "monthly_income": float(client.monthly_income),
                "household_size": client.household_size,
                "has_disability": 1 if client.has_disability == 'Yes' else 0,
                "is_senior": 1 if client.is_senior == 'Yes' else 0,
                "previous_aid": 1 if client.previous_aid == 'Yes' else 0,
            }

            prediction = predict_input(ml_input)

            application.eligibility_result = (
                "Eligible" if prediction == 1 else "Not Eligible"
            )
            application.status = (
                "approved" if prediction == 1 else "pending"
            )
            application.save()

            # ===============================
            # IV. UPLOAD DOCUMENTS
            # ===============================
            files = {
                'Valid Government ID': request.FILES.get('valid_id'),
                'Barangay Certificate': request.FILES.get('barangay_certificate'),
                'Supporting Document': request.FILES.get('other_document'),
            }

            for name, file in files.items():
                if file:
                    ApplicationDocument.objects.create(
                        application=application,
                        name=name,
                        file=file
                    )
                    application.status = 'draft'
                    application.program = 'AICS'
                    application.save()


            messages.success(request, "Application submitted & evaluated successfully.")
            return redirect('application_detail', application.id)

        except Exception as e:
            print("Submission Error:", e)
            messages.error(request, "Submission failed.")

    return render(request, 'add_client.html')

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

    # ✅ ALLOW: admin role OR staff OR superuser
    if not (
        user.is_superuser
        or user.is_staff
        or getattr(user, 'role', None) in ['admin', 'staff']
    ):
        return redirect('landing')

    program = request.GET.get('program', program).upper()

    # ✅ FILTER APPLICATIONS BY PROGRAM
    qs = Application.objects.filter(
        aid_type__iexact=program
    ).select_related('client').order_by('-created_at')

    # 🔍 SEARCH
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
        qs = qs.filter(status__iexact=status)

    # ⏳ PENDING SHORTCUT
    if request.GET.get('view') == 'pending':
        qs = qs.filter(status='pending')

    # 📤 EXPORT CSV
    if request.GET.get('export') == 'csv':
        return assistance_export_csv(qs, program)

    # 📄 PAGINATION
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'program': program,
        'applications': page_obj,
    }

    return render(request, 'assistance_program.html', context)

def assistance_export_csv(qs, program):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{program}_applications.csv"'
    writer = csv.writer(response)
    writer.writerow(['#', 'Full Name', 'Email', 'Barangay', 'Livelihood', 'Amount (₱)', 'Status', 'Date'])

    for idx, app in enumerate(qs, start=1):
        name = f"{app.client.first_name} {app.client.last_name}"
        email = app.client.email or ''
        barangay = app.barangay or ''
        livelihood = app.livelihood or ''
        amount = f"₱{float(app.amount or 0):,.2f}"
        status = app.status
        date = app.created_at.strftime('%Y-%m-%d %H:%M')
        writer.writerow([idx, smart_str(name), smart_str(email), smart_str(barangay),
                         smart_str(livelihood), amount, status, date])
    return response

@login_required
def application_detail(request, pk):
    application = get_object_or_404(
        Application.objects.select_related('client').prefetch_related('documents'),
        pk=pk
    )

    context = {
        'application': application,
        'client': application.client,
        'documents': application.documents.all(),
        'aid_type': application.aid_type,
        'requested_amount': application.requested_amount,
        'reason': application.reason,
        'status': application.status,
        'eligibility_result': application.eligibility_result,
    }

    return render(request, 'application_detail.html', context)


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
    # ✅ Allow staff, admin, superuser
    if not (
        getattr(request.user, 'role', None) in ['staff', 'admin']
        or request.user.is_superuser
    ):
        return redirect('landing')

    # ✅ Valid programs (must match Application.PROGRAM_CHOICES)
    allowed_programs = ["AICS", "SEA", "REDCARD", "EA"]

    # ✅ Selected program (optional)
    program = request.GET.get("program", "").upper()

    # ✅ Base queryset: PENDING applications
    qs = (
        Application.objects
        .filter(status="pending")
        .select_related("client")
        .order_by("-created_at")
    )

    # ✅ Filter by program (CORRECT FIELD: aid_type)
    if program in allowed_programs:
        qs = qs.filter(aid_type__iexact=program)
    else:
        program = "ALL"

    # ✅ Search (client fields)
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search) |
            Q(client__email__icontains=search)
        )

    # ✅ Pagination
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


@login_required
def application_approve(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if not (
        getattr(request.user, 'role', None) in ['admin', 'staff']
        or request.user.is_superuser
    ):
        return redirect('dashboard')

    application.status = 'approved'
    application.eligibility_result = 'Eligible'
    application.save()

    messages.success(request, "Application approved.")
    return redirect('application_detail', pk=pk)


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
def add_aics_case(request):
    if request.method == "POST":

        # -------------------------------
        # 1️⃣ SAVE CLIENT
        # -------------------------------
        client = Client.objects.create(
            first_name=request.POST.get("first_name"),
            middle_name=request.POST.get("middle_name") or None,
            last_name=request.POST.get("last_name"),

            sex=request.POST.get("sex") or None,
            birth_date=request.POST.get("birth_date") or None,
            civil_status=request.POST.get("civil_status") or None,

            address=request.POST.get("address") or None,
            barangay=request.POST.get("barangay"),
            municipality=request.POST.get("municipality") or None,

            contact_no=request.POST.get("contact_no") or None,
            email=request.POST.get("email") or None,

            livelihood=request.POST.get("livelihood") or None,
            monthly_income=request.POST.get("monthly_income") or None,
            household_size=request.POST.get("household_size") or None,

            has_disability=request.POST.get("has_disability") or None,
            is_senior=request.POST.get("is_senior") or None,
        )

        # -------------------------------
        # 2️⃣ SAVE APPLICATION (AICS)
        # -------------------------------
        application = Application.objects.create(
            client=client,
            aid_type="AICS",
            reason=request.POST.get("reason"),
            status="pending",
            eligibility_result="Not yet evaluated"
        )

        return redirect("aics/aics_assessment", application.id)

    return render(request, "aics/add_aics_case.html")


@login_required
def aics_assessment(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        application.reason = request.POST.get("assessment")
        application.crisis_type = request.POST.get("crisis_type")
        application.requested_amount = request.POST.get("requested_amount")

        application.status = "assessed"
        application.save()

        return redirect("upload_aics_documents", application.id)

    return render(request, "aics/aics_assessment.html", {
        "application": application
    })


@login_required
def upload_aics_documents(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        for f in request.FILES.getlist("documents"):
            ApplicationDocument.objects.create(
                application=application,
                file=f
            )

        application.status = "pending"
        application.save()

        return redirect("pending_applications")

    return render(request, "aics/upload_documents.html", {
        "application": application
    })

@login_required
def approve_aics(request, pk):
    application = get_object_or_404(Application, pk=pk)
    application.status = "approved"
    application.save()
    return redirect("pending_applications")


@login_required
def reject_aics(request, pk):
    application = get_object_or_404(Application, pk=pk)
    application.status = "rejected"
    application.save()
    return redirect("pending_applications")

@login_required
def aics_history(request):
    applications = Application.objects.filter(
        aid_type="AICS",
        status="released"
    ).select_related("client")

    return render(request, "aics/aics_history.html", {
        "applications": applications
    })

@login_required
def release_aics(request, pk):
    application = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        application.released_amount = request.POST.get("released_amount")
        application.status = "released"
        application.save()
        return redirect("assistance_program")

    return render(request, "aics/release_aid.html", {
        "application": application
    })

@login_required
def approve_aics(request, pk):
    application = get_object_or_404(
        Application,
        pk=pk,
        aid_type="AICS"
    )

    # Only admin or staff
    if not (
        getattr(request.user, "role", None) in ["admin", "staff"]
        or request.user.is_superuser
    ):
        return redirect("pending_applications")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            application.status = "approved"
            application.eligibility_result = "Eligible"
        elif action == "reject":
            application.status = "rejected"
            application.eligibility_result = "Not Eligible"

        application.save()
        return redirect("pending_applications")

    return render(request, "aics/approve.html", {
        "application": application
    })
