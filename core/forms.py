from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Client, Application, ApplicationDocument


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'contact_no', 'barangay', 'livelihood']
        widgets = {
            'first_name':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email':       forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (optional)'}),
            'contact_no':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact number'}),
            'barangay':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Barangay'}),
            'livelihood':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Livelihood'}),
        }


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['aid_type', 'status']
        widgets = {
            'aid_type': forms.Select(attrs={'class': 'form-control'}),
            'status':   forms.Select(attrs={'class': 'form-control'}),
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


class AssistanceFilterForm(forms.Form):
    PROGRAM_CHOICES = [
        ('SEA',         'SEA'),
        ('AICS',        'AICS'),
        ('REDCARD',     'RED CARD'),
        ('EA',          'Educational Assistance (EA)'),
    ]

    STATUS_CHOICES = [
        ('',         'All Status'),
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('referral', 'Referral'),
        ('other',    'Others'),
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


        from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class MyRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class LoginForm(AuthenticationForm):
    pass

    class ClientForm(forms.ModelForm):
     class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'contact_no', 'barangay', 'livelihood']
        widgets = {
            'first_name':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email':       forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (optional)'}),
            'contact_no':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact number'}),
            'barangay':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Barangay'}),
            'livelihood':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Livelihood'}),
        }
 
 
class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['aid_type', 'status']
        widgets = {
            'aid_type': forms.Select(attrs={'class': 'form-control'}),
            'status':   forms.Select(attrs={'class': 'form-control'}),
        }
 
 
class SignupForm(UserCreationForm):
    role  = forms.ChoiceField(choices=User.ROLES)
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'e.g. juan.delacruz@mswdo.gov.ph',
            'autocomplete': 'email',
        })
    )
 
    class Meta:
        model  = User
        fields = ['email', 'username', 'role', 'password1', 'password2']
 
    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        # Allow re-registration if previous account was unverified (inactive)
        from .models import User as U
        if U.objects.filter(email=email, is_active=True).exists():
            raise forms.ValidationError("An active account already uses this email address.")
        return email
 
 

 
 
class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = ApplicationDocument
        fields = ['name', 'file']
 
 
class AssistanceFilterForm(forms.Form):
    PROGRAM_CHOICES = [
        ('SEA',         'SEA'),
        ('AICS',        'AICS'),
        ('REDCARD',     'RED CARD'),
        ('EA',          'Educational Assistance (EA)'),
    ]
 
    STATUS_CHOICES = [
        ('',         'All Status'),
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('referral', 'Referral'),
        ('other',    'Others'),
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