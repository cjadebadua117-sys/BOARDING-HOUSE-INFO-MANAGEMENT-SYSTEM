from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.core.validators import RegexValidator

from .models import BoardingHouse, User, Inquiry, InquiryMessage, Room


class StudentRegistrationForm(UserCreationForm):
    username = forms.CharField(label='Username', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Email', max_length=254, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    full_name = forms.CharField(label='Full Name', max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))
    student_id = forms.CharField(
        label='Student ID',
        max_length=20,
        validators=[RegexValidator(regex=r'^\d{3}-\d{4}-\d{1}$', message='Student ID must be in the format 241-0273-1.')],
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    program = forms.ChoiceField(
        label='Program',
        choices=User.Program.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'full_name', 'student_id', 'program', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and not email.lower().endswith('@gmail.com'):
            raise forms.ValidationError('Please register with a valid Gmail address that ends in @gmail.com.')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('A student account with this Gmail address already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.student_id = self.cleaned_data['student_id']
        user.program = self.cleaned_data['program']
        if commit:
            user.save()
        return user


class LandlordRegistrationForm(UserCreationForm):
    username = forms.CharField(label='Username', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Email', max_length=254, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    full_name = forms.CharField(label='Full Name', max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(label='Contact Number', max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'full_name', 'phone_number', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.phone_number = self.cleaned_data['phone_number']
        if commit:
            user.save()
        return user


class StudentProfileEditForm(forms.ModelForm):
    current_password = forms.CharField(label='Current Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False)
    new_password1 = forms.CharField(label='New Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False)
    new_password2 = forms.CharField(label='Confirm New Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False)

    class Meta:
        model = User
        fields = ['full_name', 'program', 'phone_number', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get('current_password')
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if new_password1 or new_password2 or current_password:
            if not current_password:
                self.add_error('current_password', 'Please enter your current password to change it.')
            elif not self.instance.check_password(current_password):
                self.add_error('current_password', 'Current password is incorrect.')
            if new_password1 != new_password2:
                self.add_error('new_password2', 'New passwords do not match.')
            elif new_password1 and len(new_password1) < 8:
                self.add_error('new_password1', 'New password must be at least 8 characters long.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('new_password1'):
            user.set_password(self.cleaned_data['new_password1'])
        if commit:
            user.save()
        return user


class BoardingHouseForm(forms.ModelForm):
    class Meta:
        model = BoardingHouse
        fields = ['name', 'address', 'barangay', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ['message_text']
        widgets = {
            'message_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Write your inquiry here...'}),
        }


class InquiryMessageForm(forms.ModelForm):
    class Meta:
        model = InquiryMessage
        fields = ['message_text']
        widgets = {
            'message_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Type your reply here...'}),
        }


class BHIMSPasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'bhims-input'})


# Additional lightweight forms expected by views
class LandlordCreateForm(LandlordRegistrationForm):
    pass


class LandlordEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'phone_number', 'bio']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ListingFilterForm(forms.Form):
    room_type = forms.ChoiceField(required=False)
    price_min = forms.DecimalField(required=False, decimal_places=2, max_digits=10)
    price_max = forms.DecimalField(required=False, decimal_places=2, max_digits=10)
    amenities = forms.CharField(required=False)
    barangay = forms.ChoiceField(required=False)
    sort = forms.ChoiceField(required=False, choices=[('', 'Default'), ('lowest_price', 'Lowest price'), ('newest', 'Newest')])


class StudentProfileUpdateForm(StudentProfileEditForm):
    pass


class LandlordProfilePictureForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['profile_picture']
