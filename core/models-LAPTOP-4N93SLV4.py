from django.db import models
from django.contrib.auth.models import AbstractUser

# ========================
# USER MODEL
# ========================
class User(AbstractUser):
    ROLES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    )
    role = models.CharField(max_length=20, choices=ROLES, default='staff')
    is_verified = models.BooleanField(default=False)
    last_login_time = models.DateTimeField(null=True, blank=True)

# ========================
# CLIENT / BENEFICIARY
# ========================
class Client(models.Model):
    first_name = models.CharField(max_length=120)
    middle_name = models.CharField(max_length=120, blank=True, null=True)
    last_name = models.CharField(max_length=120)

    sex = models.CharField(max_length=10, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    civil_status = models.CharField(max_length=30, blank=True, null=True)
    nationality = models.CharField(max_length=50, blank=True, null=True)

    address = models.TextField(blank=True, null=True)
    barangay = models.CharField(max_length=100, blank=True, null=True)
    municipality = models.CharField(max_length=100, blank=True, null=True)

    email = models.EmailField(blank=True, null=True)
    contact_no = models.CharField(max_length=20, blank=True, null=True)

    livelihood = models.CharField(max_length=100, blank=True, null=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    household_size = models.IntegerField(blank=True, null=True)

    has_disability = models.CharField(max_length=10, blank=True, null=True)
    is_senior = models.CharField(max_length=10, blank=True, null=True)
    previous_aid = models.CharField(max_length=10, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name

# ========================
# ASSISTANCE APPLICATION
# ========================
class Application(models.Model):
    PROGRAM_CHOICES = [
        ('SEA', 'SEA'),
        ('AICS', 'AICS'),
        ('REDCARD', 'REDCARD'),
        ('EA', 'Educational Assistance'),
    ]

    STATUS_CHOICES = [
            ('draft', 'Draft'),
    ('assessed', 'Assessed'),
    ('pending', 'For Approval'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('released', 'Released'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='applications')
    aid_type = models.CharField(max_length=20, choices=PROGRAM_CHOICES)
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    eligibility_result = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.full_name} - {self.aid_type}"

# ========================
# DOCUMENTS FOR APPLICATION
# ========================
class ApplicationDocument(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='documents'  # unique, avoids clashes
    )
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='application_documents/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.file.name

# ========================
# ADDITIONAL ASSISTANCE RECORD
# ========================
class Assistance(models.Model):
    PROGRAM_CHOICES = [
        ('SEA', 'SEA'),
        ('AICS', 'AICS'),
        ('REDCARD', 'REDCARD'),
        ('EA', 'Educational Assistance'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='assistances')
    program = models.CharField(max_length=20, choices=PROGRAM_CHOICES)
    barangay = models.CharField(max_length=255, blank=True, null=True)
    livelihood = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.full_name} - {self.program}"
