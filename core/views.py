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



from .models import Client, Application, ApplicationDocument
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
        return render(request, 'login.html', {"message": "✔ Email verified successfully! You can now log in."})

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
        return redirect('landing')

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

    # ---------------- Dashboard Stats ----------------
    per_program = (
        Application.objects.values('program')
        .annotate(total=Count('id'))
        .order_by('program')
    )
    programs = [p['program'] for p in per_program]
    program_counts = [p['total'] for p in per_program]

    per_status = (
        Application.objects.values('status')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    statuses = [p['status'] for p in per_status]
    status_counts = [p['total'] for p in per_status]

    # Active clients per month
    year = timezone.now().year
    monthly = (
        Client.objects.filter(created_at__year=year)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )

    month_labels = [e['month'].strftime('%b') for e in monthly if e.get('month')]
    month_counts = [e['total'] for e in monthly if e.get('month')]

    if not month_labels:
        month_labels = [calendar.month_abbr[i] for i in range(1, 13)]
        month_counts = [0] * 12

    latest_clients = Client.objects.order_by('-created_at')[:6]

    # ---------------- ML Prediction ----------------
    prediction = None
    probability = None
    inputs_used = None

    if request.method == "POST":
        try:
            inputs_used = {
                "Age": int(request.POST.get("Age") or 0),
                "Income_Monthly": float(request.POST.get("Income_Monthly") or 0),
                "Family_Size": int(request.POST.get("Family_Size") or 0),
                "Sex": request.POST.get("Sex") or "",
                "Region": request.POST.get("Region") or "",
                "Employment_Status": request.POST.get("Employment_Status") or "",
                "Has_Disability": 1 if request.POST.get("Has_Disability") == "Yes" else 0,
                "Previous_Aid": request.POST.get("Previous_Aid") or "",
                "Aid_Type_Applied": request.POST.get("Aid_Type_Applied") or "",
            }

            # MODEL PREDICT
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

            # ---------------- FIX: Clamp probability ----------------
            prob = max(0, min(prob, 100))

            # ---------------- FIX: Use confidence ranges ONLY ----------------
            if prob < 70:
                prediction = "Not Eligible"
            else:
                prediction = "Eligible"

            probability = prob

        except Exception as e:
            print("ML prediction error:", e)
            prediction = "Unavailable"
            probability = None

    # ---------------- Context ----------------
    context = {
        "program_labels": programs,
        "program_values": program_counts,
        "status_labels": statuses,
        "status_values": status_counts,
        "month_labels": month_labels,
        "month_values": month_counts,
        "latest_clients": latest_clients,
        "prediction": prediction,
        "probability": probability,
        "inputs_used": inputs_used,
    }

    return render(request, "dashboard.html", context)

@login_required
def add_client(request):
    # Allow STAFF, ADMIN, SUPERUSER
    if not (
        getattr(request.user, 'role', None) in ['staff', 'admin']
        or request.user.is_superuser
    ):
        return redirect('dashboard')

    if request.method == 'POST':
        form = ClientForm(request.POST)
        app_form = ApplicationForm(request.POST)

        if form.is_valid() and app_form.is_valid():
            client = form.save()
            app = app_form.save(commit=False)
            app.client = client

            # ML PREDICTION
            try:
                from ml.predictor import predict_eligibility

                ml_input = {
                    "age": client.age,
                    "income": client.income,
                    "family_size": client.family_size,
                    "is_pwd": 1 if client.is_pwd else 0,
                }

                prediction = predict_eligibility(ml_input)

                app.status = "eligible" if prediction == 1 else "not eligible"

            except Exception as e:
                print("ML prediction error:", e)
                app.status = "pending"  # fallback

            app.save()

            messages.success(
                request,
                f"Client created. ML Eligibility: {app.status}"
            )
            return redirect('dashboard')

    else:
        form = ClientForm()
        app_form = ApplicationForm()

    return render(request, 'add_client.html', {
        'form': form,
        'app_form': app_form
    })

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
@login_required
def assistance_program(request, program='SEA'):
    if not (getattr(request.user, 'role', None) == 'admin' or request.user.is_staff or request.user.is_superuser):
        return redirect('landing')

    program = request.GET.get('program', program).upper()
    form = AssistanceFilterForm(request.GET or None)
    qs = Application.objects.filter(program__iexact=program).select_related('client').order_by('-created_at')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(client__first_name__icontains=q) |
                       Q(client__last_name__icontains=q) |
                       Q(client__email__icontains=q))

    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status__iexact=status)

    view_pending = request.GET.get('view', '') == 'pending'
    if view_pending:
        qs = qs.filter(status__iexact='pending')

    if request.GET.get('export') == 'csv':
        return assistance_export_csv(qs, program)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'program': program,
        'form': form,
        'applications': page_obj,
        'paginator': paginator,
        'view_pending': view_pending,
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
        barangay = getattr(app, 'barangay', '') or ''
        livelihood = getattr(app, 'livelihood', '') or ''
        amount = f"₱{float(app.amount or 0):,.2f}"
        status = app.status
        date = app.created_at.strftime('%Y-%m-%d %H:%M')
        writer.writerow([idx, smart_str(name), smart_str(email), smart_str(barangay),
                         smart_str(livelihood), amount, status, date])
    return response


@login_required
def application_detail(request, pk):
    app = get_object_or_404(Application, pk=pk)
    form = DocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        doc = form.save(commit=False)
        doc.application = app
        doc.save()
        messages.success(request, "Document uploaded.")
        return redirect('application_detail', pk=pk)
    return render(request, 'application_detail.html', {'application': app, 'form': form})


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
def assistance_program(request):

    # Allow only staff/admin
    if not (
        getattr(request.user, 'role', None) in ['staff', 'admin']
        or request.user.is_superuser
    ):
        return redirect('landing')

    # ----------------------
    # Program (default to AICS)
    # ----------------------
    program = request.GET.get("program", "AICS").upper()

    # Base queryset
    qs = Application.objects.filter(program__iexact=program)\
                            .select_related("client")\
                            .order_by("-created_at")

    # ----------------------
    # Search
    # ----------------------
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search) |
            Q(client__email__icontains=search)
        )

    # ----------------------
    # Status Filter
    # ----------------------
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status__iexact=status)

    # ----------------------
    # View Pending Only
    # ----------------------
    view_pending = request.GET.get("view") == "pending"
    if view_pending:
        qs = qs.filter(status__iexact="pending")

    # ----------------------
    # CSV Export
    # ----------------------
    if request.GET.get("export") == "csv":
        return assistance_export_csv(qs, program)

    # ----------------------
    # Pagination
    # ----------------------
    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ----------------------
    # Render
    # ----------------------
    context = {
        "applications": page_obj,
        "paginator": paginator,
        "program": program,
        "view_pending": view_pending,
        "search": search,
        "status": status,
    }

    return render(request, "assistance_program.html", context)

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
    # Allow only staff/admin/superuser
    if not (getattr(request.user, 'role', None) in ['staff', 'admin'] 
            or request.user.is_superuser):
        return redirect('landing')

    # Allowed programs
    allowed_programs = ["AICS", "SEA", "REDCARD", "EA"]

    # Get selected program: If none -> show ALL
    program = request.GET.get("program", "").upper()

    # Base queryset: pending applications
    qs = Application.objects.filter(status__iexact="pending")\
                            .select_related("client")\
                            .order_by("-created_at")

    # Apply filtering only if program is valid
    if program in allowed_programs:
        qs = qs.filter(program__iexact=program)
    else:
        program = "ALL"   # For context display

    # Optional search
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search) |
            Q(client__email__icontains=search)
        )

    # Pagination
    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "applications": page_obj,
        "paginator": paginator,
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
