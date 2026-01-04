from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Client, Application, ApplicationDocument


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'contact_no', 'barangay', 'livelihood']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (optional)'}),
            'contact_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact number'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Barangay'}),
            'livelihood': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Livelihood'}),
        }



class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['aid_type', 'status', 'requested_amount']  # <-- use requested_amount
        widgets = {
            'aid_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'requested_amount': forms.NumberInput(attrs={'class': 'form-control'}),  # <-- updated
        }

class SignupForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLES)

    class Meta:
        model = User
        fields = ['email', 'username', 'role', 'password1', 'password2']


class LoginForm(AuthenticationForm):
    pass


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = ApplicationDocument
        fields = ['name', 'file']


# FIXED — properly defined OUTSIDE the Meta class
class AssistanceFilterForm(forms.Form):
    PROGRAM_CHOICES = [
        ('SEA', 'SEA'),
        ('AICS', 'AICS'),
        ('REDCARD', 'RED CARD'),
        ('EA', 'Educational Assistance (EA)'),
    ]

    STATUS_CHOICES = [
        ('', 'All Status'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('referral', 'Referral'),
        ('other', 'Others'),
    ]

    program = forms.ChoiceField(
        choices=PROGRAM_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search name/email'})
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']
