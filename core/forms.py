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
        fields = ['program', 'status', 'amount']
        widgets = {
            'program': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
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
    program = forms.ChoiceField(
        choices=[
            ('SEA', 'SEA'),
            ('AICS', 'AICS'),
            ('REDCARD', 'REDCARD'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search name or email'})
    )

    status = forms.ChoiceField(
        choices=[
            ('', 'All Status'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('referral', 'Referral'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']
