from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLES = (('admin', 'Admin'), ('staff', 'Staff'))
    role = models.CharField(max_length=20, choices=ROLES, default='staff')
    is_verified = models.BooleanField(default=False)
    last_login_time = models.DateTimeField(null=True, blank=True)

class Client(models.Model):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, null=True)
    contact_no = models.CharField(max_length=20, blank=True, null=True)
    barangay = models.CharField(max_length=100, blank=True, null=True)
    livelihood = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name
    
class Application(models.Model):
    PROGRAM_CHOICES = [
        ('SEA', 'SEA'),
        ('AICS', 'AICS'),
        ('REDCARD', 'REDCARD'),
        ('EA', 'Educational Assistance'),   # <-- Added EA
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('referral', 'Referrals'),
        ('other', 'Others'),
        ('organic', 'Organic Search')
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='applications')
    program = models.CharField(max_length=20, choices=PROGRAM_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.full_name} - {self.program} ({self.status})"


class ApplicationDocument(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)  # <-- add this
    file = models.FileField(upload_to='application_documents/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.file.name

class Assistance(models.Model):
    PROGRAM_CHOICES = [
        ('SEA', 'SEA'),
        ('AICS', 'AICS'),
        ('REDCARD', 'REDCARD'),
        ('EA', 'Educational Assistance'),  # <-- Added EA
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='assistances')
    program = models.CharField(max_length=20, choices=PROGRAM_CHOICES)
    barangay = models.CharField(max_length=255, blank=True, null=True)
    livelihood = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.first_name} {self.client.last_name} - {self.program}"

