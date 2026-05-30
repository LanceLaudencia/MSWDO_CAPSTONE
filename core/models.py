from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User


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
    first_name   = models.CharField(max_length=120)
    middle_name  = models.CharField(max_length=120, blank=True, null=True)
    last_name    = models.CharField(max_length=120)
 
    sex          = models.CharField(max_length=10, blank=True, null=True)
    birth_date   = models.DateField(blank=True, null=True)
    civil_status = models.CharField(max_length=30, blank=True, null=True)
    nationality  = models.CharField(max_length=50, blank=True, null=True)
 
    address      = models.TextField(blank=True, null=True)
    barangay     = models.CharField(max_length=100, blank=True, null=True)
    municipality = models.CharField(max_length=100, blank=True, null=True)
 
    email        = models.EmailField(blank=True, null=True)
    contact_no   = models.CharField(max_length=20, blank=True, null=True)
 
    livelihood      = models.CharField(max_length=100, blank=True, null=True)
    monthly_income  = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    household_size  = models.IntegerField(blank=True, null=True)
 
    has_disability  = models.CharField(max_length=10, blank=True, null=True)
    is_senior       = models.CharField(max_length=10, blank=True, null=True)
    previous_aid    = models.CharField(max_length=10, blank=True, null=True)
 
    # ── NEW ──────────────────────────────────────────────────────
    is_solo_parent  = models.CharField(max_length=3, default='No', blank=True, null=True)
    is_indigenous   = models.CharField(max_length=3, default='No', blank=True, null=True)
    # ─────────────────────────────────────────────────────────────
    sectors = models.JSONField(default=list, blank=True)
    is_4ps          = models.CharField(max_length=3, default='No', blank=True, null=True)
    fourps_id       = models.CharField(max_length=50, blank=True, null=True)
 
    created_at      = models.DateTimeField(auto_now_add=True)
 
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
 
    def __str__(self):
        return self.full_name

# ========================
# FAMILY MEMBER
# ========================
class FamilyMember(models.Model):
    CIVIL_STATUS_CHOICES = [
        ('S', 'Single'),
        ('M', 'Married'),
        ('W', 'Widowed'),
    ]
    EDUCATION_CHOICES = [
        ('Elem',     'Elementary'),
        ('HS',       'High School'),
        ('Coll/Voc', 'College / Vocational'),
        ('Illit',    'Illiterate'),
    ]
    SEX_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    client       = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='family_members')
    name         = models.CharField(max_length=200)
    age          = models.PositiveIntegerField(blank=True, null=True)
    sex          = models.CharField(max_length=1, choices=SEX_CHOICES, blank=True, null=True)
    civil_status = models.CharField(max_length=1, choices=CIVIL_STATUS_CHOICES, blank=True, null=True)
    relationship = models.CharField(max_length=100, blank=True, null=True)
    educational_attainment = models.CharField(max_length=20, choices=EDUCATION_CHOICES, blank=True, null=True)
    occupation   = models.CharField(max_length=150, blank=True, null=True)
    income       = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    sectors = models.JSONField(default=list, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.client.full_name})"


# ========================
# APPLICATION
# ========================
class Application(models.Model):
    PROGRAM_CHOICES = [
        ('AICS',        'AICS'),
        ('SEA',         'Sustainable Livelihood (SEA)'),
        ('REDCARD',     'Red Card'),
        ('EDUCATIONAL', 'Educational Assistance'),
    ]
    STATUS_CHOICES = [
        ('PENDING',    'Pending Review'),
        ('ASSESSMENT', 'Under Assessment'),
        ('APPROVAL',   'For Approval'),
        ('RELEASE',    'For Release'),
        ('RELEASED',   'Released'),
        ('REJECTED',   'Rejected'),
    ]

    client   = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='applications')
    aid_type = models.CharField(max_length=20, choices=PROGRAM_CHOICES)

    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    released_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    eligibility_result = models.CharField(max_length=50, blank=True, null=True)
    eligibility_reason = models.TextField(null=True, blank=True)
    eligibility_score = models.IntegerField(null=True, blank=True)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessed_applications')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_applications')

    assessed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)   # ✅ removed duplicate
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client.full_name} - {self.get_aid_type_display()} ({self.status})"


# ========================
# APPLICATION DOCUMENTS
# ========================
class ApplicationDocument(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    name        = models.CharField(max_length=200)          # ✅ removed duplicate document_name field
    description = models.TextField(blank=True)
    file        = models.FileField(upload_to='application_documents/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.file.name


# ========================
# ASSISTANCE RECORD
# ========================
class Assistance(models.Model):
    PROGRAM_CHOICES = [
        ('SEA',     'SEA'),
        ('AICS',    'AICS'),
        ('REDCARD', 'REDCARD'),
        ('EA',      'Educational Assistance'),
    ]

    client     = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='assistances')
    program    = models.CharField(max_length=20, choices=PROGRAM_CHOICES)
    barangay   = models.CharField(max_length=255, blank=True, null=True)
    livelihood = models.CharField(max_length=255, blank=True, null=True)
    amount     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status     = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.full_name} - {self.program}"


# ========================
# AICS DETAIL
# ========================
class AICSDetail(models.Model):
    CRISIS_CHOICES = [
        ('Medical',        'Medical'),
        ('Death',          'Death'),
        ('Fire Victim',    'Fire Victim'),
        ('Calamity',       'Calamity'),
        ('Other',          'Other'),
    ]

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='aics_detail')
    crisis_type = models.CharField(max_length=50, choices=CRISIS_CHOICES, blank=True, null=True)
    # ✅ removed: assessment_findings, approved_amount (columns don't exist in DB)

    def __str__(self):
        return f"AICS - {self.application.client.full_name}"


# ========================
# SEA DETAIL
# ========================
class SEADetail(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='sea_detail')
    # ✅ removed: business_type, capital_requested, training_completed, monitoring_notes

    def __str__(self):
        return f"SEA - {self.application.client.full_name}"


# ========================
# REDCARD DETAIL
# ========================
class REDCARDDetail(models.Model):
    application     = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='redcard_detail')
    emergency_type  = models.CharField(max_length=255, blank=True, null=True)
    reason          = models.TextField(blank=True, null=True)
    usage_count     = models.PositiveIntegerField(default=1)
    allowable_limit = models.PositiveIntegerField(default=3)
    released_at     = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"REDCARD - {self.application.client.full_name}"


# ========================
# EDUCATIONAL ASSISTANCE DETAIL
# ========================
class EducationalAssistanceDetail(models.Model):
    application     = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='educational_detail')
    school_name     = models.CharField(max_length=255, blank=True, null=True)
    course_or_grade = models.CharField(max_length=255, blank=True, null=True)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    released_at     = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Educational - {self.application.client.full_name}"


# ========================
# CLIENT LOGIN ACCOUNT
# ========================
class ClientAccount(models.Model):
    client     = models.OneToOneField("Client", on_delete=models.CASCADE, related_name="account")
    email      = models.EmailField(unique=True)
    password   = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True) 
    verification_token = models.CharField(max_length=64, blank=True, default='')

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"Account: {self.client.full_name}"


# ========================
# NOTIFICATION
# ========================
class Notification(models.Model):
    recipient  = models.ForeignKey(User, on_delete=models.CASCADE)
    message    = models.TextField()
    link       = models.CharField(max_length=255, blank=True, null=True)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ========================
# REPORT model — replace in models.py
# ========================
class Report(models.Model):
    STATUS_CHOICES = [
        ('PENDING',  'Pending Review'),
        ('APPROVED', 'Approved'),
        ('DECLINED', 'Declined'),
    ]

    REPORT_TYPE_CHOICES = [
        ('Social Protection & Development Report (SPDR)',
         'Social Protection & Development Report (SPDR)'),
        ('Local Council for the Protection of Children (LCPC) Report',
         'Local Council for the Protection of Children (LCPC) Report'),
        ('Local Council Against Trafficking & Violence Against Women & their Children (LCAT VAWC) Report',
         'Local Council Against Trafficking & VAWC Report'),
        ('Persons with Disability Report (PWD)',
         'Persons with Disability Report (PWD)'),
        ('Report of the Office of Senior Citizen Affairs (OSCA)',
         'Report of the Office of Senior Citizen Affairs (OSCA)'),
        ('CICL / CAR Report',
         'CICL / CAR Report'),
        ('CNSP Report',
         'CNSP Report'),
        ('Migrant Workers Report',
         'Migrant Workers Report'),
        ('Indigenous People Progress Updates (IP)',
         'Indigenous People Progress Updates (IP)'),
        ('Report on Former Rebels (FR)',
         'Report on Former Rebels (FR)'),
        ('Persons Who Use Drugs Report (PWUD)',
         'Persons Who Use Drugs Report (PWUD)'),
        ('Other Reports', 'Other Reports'),
    ]

    submitted_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='submitted_reports'
    )
    title       = models.CharField(max_length=255)
    content     = models.TextField()
    report_type = models.CharField(
        max_length=200,
        choices=REPORT_TYPE_CHOICES,
        blank=True, null=True
    )
    attachment   = models.FileField(upload_to='reports/%Y/%m/', blank=True, null=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_reports'
    )
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    admin_note   = models.TextField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.submitted_by.username} ({self.status})"

    def get_type_abbr(self):
        """Returns short abbreviation for display badges."""
        abbr_map = {
            'Social Protection & Development Report (SPDR)': 'SPDR',
            'Local Council for the Protection of Children (LCPC) Report': 'LCPC',
            'Local Council Against Trafficking & Violence Against Women & their Children (LCAT VAWC) Report': 'LCAT VAWC',
            'Persons with Disability Report (PWD)': 'PWD',
            'Report of the Office of Senior Citizen Affairs (OSCA)': 'OSCA',
            'CICL / CAR Report': 'CICL/CAR',
            'CNSP Report': 'CNSP',
            'Migrant Workers Report': 'MIGRANT',
            'Indigenous People Progress Updates (IP)': 'IP',
            'Report on Former Rebels (FR)': 'FR',
            'Persons Who Use Drugs Report (PWUD)': 'PWUD',
            'Other Reports': 'Others',
        }
        return abbr_map.get(self.report_type, self.report_type or 'General')