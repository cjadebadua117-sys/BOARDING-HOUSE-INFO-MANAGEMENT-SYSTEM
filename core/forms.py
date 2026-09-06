from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.core.validators import MinValueValidator, RegexValidator

from .models import BoardingHouse, User, Inquiry, Room, Barangay, SiteSetting, UserReport, LandlordRating
from .models import BACNOTAN_BARANGAYS, BARANGAY_DISTANCES


class StudentRegistrationForm(UserCreationForm):
    username = forms.CharField(label='Username', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'username'}))
    email = forms.EmailField(label='Email', max_length=254, widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}))
    full_name = forms.CharField(label='Full Name', max_length=255, widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'name'}))
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
    program_custom = forms.CharField(
        label='Enter Your Grade Level',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Grade 11 - STEM'
        })
    )
    # password1/password2 are inherited from UserCreationForm, which already
    # sets autocomplete="new-password" and wires password validation.

    class Meta:
        model = User
        fields = ['username', 'email', 'full_name', 'student_id', 'program', 'program_custom', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django's UserCreationForm injects autofocus on the username widget;
        # it keeps the field stuck in its focused border state on page load.
        self.fields['username'].widget.attrs.pop('autofocus', None)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and not email.lower().endswith('@gmail.com'):
            raise forms.ValidationError('Please register with a valid Gmail address that ends in @gmail.com.')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('A student account with this Gmail address already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        program = cleaned_data.get('program')
        program_custom = cleaned_data.get('program_custom')
        if program == User.Program.K12 and not (program_custom or '').strip():
            self.add_error('program_custom', 'Please specify your grade level.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.student_id = self.cleaned_data['student_id']
        user.program = self.cleaned_data['program']
        user.program_custom = self.cleaned_data.get('program_custom', '').strip()
        if commit:
            user.save()
        return user


class LandlordRegistrationForm(UserCreationForm):
    username = forms.CharField(label='Username', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Email', max_length=254, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    full_name = forms.CharField(label='Full Name', max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(label='Contact Number', max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

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
    current_password = forms.CharField(label='Current Password', widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'current-password'}), required=False)
    new_password1 = forms.CharField(label='New Password', widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}), required=False)
    new_password2 = forms.CharField(label='Confirm New Password', widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}), required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'program', 'program_custom', 'phone_number', 'bio']
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

        program = cleaned_data.get('program')
        program_custom = cleaned_data.get('program_custom')
        if program == User.Program.K12 and not (program_custom or '').strip():
            self.add_error('program_custom', 'Please specify your grade level.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('new_password1'):
            user.set_password(self.cleaned_data['new_password1'])
        # Keep the display name in sync with the editable first/last names
        user.full_name = f"{user.first_name} {user.last_name}".strip()
        if commit:
            user.save()
        return user


class BoardingHouseForm(forms.ModelForm):
    class Meta:
        model = BoardingHouse
        # NOTE: is_active is deliberately excluded — only admins control
        # whether a listing is hidden/visible (see admin approve/reject views).
        fields = ['name', 'address', 'barangay', 'price', 'gender_allowed', 'description', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Sunrise Dormitory'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street, Purok, etc.'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2500', 'min': '1', 'step': '0.01'}),
            'gender_allowed': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': 'Tell students about your boarding house (optional, up to 500 words)...'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].required = True
        choices = []
        try:
            choices = [(b.name, b.display_name) for b in Barangay.objects.all()]
        except Exception:
            pass
        if not choices:
            choices = [
                (n, f'{n} ({BARANGAY_DISTANCES[n]})' if n in BARANGAY_DISTANCES else n)
                for n in BACNOTAN_BARANGAYS
            ]
        current = self.instance.barangay if self.instance and self.instance.pk else ''
        if current and current not in [c[0] for c in choices]:
            choices.append((current, current))
        self.fields['barangay'] = forms.ChoiceField(
            label='Barangay',
            choices=choices,
            widget=forms.Select(attrs={'class': 'form-select'}),
        )

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise forms.ValidationError('Price must be greater than ₱0.')
        return price

    def clean_description(self):
        description = self.cleaned_data.get('description', '')
        if description:
            word_count = len(description.split())
            if word_count > 500:
                raise forms.ValidationError(
                    f'Description must be at most 500 words. You entered {word_count}.'
                )
        return description


class RoomForm(forms.ModelForm):
    photo = forms.ImageField(
        label='Room Photo',
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        help_text='Upload a photo of the room.',
    )

    class Meta:
        model = Room
        fields = ['room_type', 'monthly_rate', 'capacity', 'is_available', 'amenities']
        widgets = {
            'room_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Studio with private balcony'}),
            'monthly_rate': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '0.01'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'amenities': forms.CheckboxSelectMultiple,
        }

    def clean_monthly_rate(self):
        rate = self.cleaned_data.get('monthly_rate')
        if rate is not None and rate <= 0:
            raise forms.ValidationError('Monthly rate must be greater than ₱0.')
        return rate

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity is not None and capacity < 1:
            raise forms.ValidationError('Capacity must be at least 1 occupant.')
        return capacity

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo and not self.instance.pk:
            raise forms.ValidationError('Please upload a room photo before saving. A photo is required so students can see the room.')
        return photo


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ['subject', 'message_text']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Subject (optional)',
            }),
            'message_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Write your inquiry here...'}),
        }


class LandlordRatingForm(forms.ModelForm):
    class Meta:
        model = LandlordRating
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(5, '5 stars'), (4, '4 stars'), (3, '3 stars'), (2, '2 stars'), (1, '1 star')],
                attrs={'class': 'form-select'},
            ),
            'comment': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'maxlength': 500,
                    'placeholder': 'Share a short, respectful experience (optional)',
                },
            ),
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
    room_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Single, Studio, Bedspace...',
        }),
    )
    price_min = forms.DecimalField(required=False, decimal_places=2, max_digits=10)
    price_max = forms.DecimalField(required=False, decimal_places=2, max_digits=10)
    amenities = forms.CharField(required=False)
    barangay = forms.ChoiceField(required=False)
    sort = forms.ChoiceField(required=False, choices=[('', 'Default'), ('lowest_price', 'Lowest price'), ('newest', 'Newest')])


class StudentProfileUpdateForm(StudentProfileEditForm):
    pass


class LandlordProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number']

    def save(self, commit=True):
        user = super().save(commit=False)
        # Keep the display name in sync with the editable first/last names.
        user.full_name = f"{user.first_name} {user.last_name}".strip()
        if commit:
            user.save()
        return user


class LandlordProfilePictureForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['profile_picture']


class BarangayForm(forms.ModelForm):
    class Meta:
        model = Barangay
        fields = ['name', 'distance_from_campus']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Poblacion'}),
            'distance_from_campus': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3.5 km'}),
        }


class SystemSettingsForm(forms.Form):
    site_name = forms.CharField(label='System Name', max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    tagline = forms.CharField(label='Tagline', max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    support_email = forms.EmailField(label='Support Email', max_length=254, required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    student_registration_enabled = forms.BooleanField(
        label='Allow student registration',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def save(self):
        for key in ['site_name', 'tagline', 'support_email']:
            SiteSetting.objects.update_or_create(key=key, defaults={'value': self.cleaned_data.get(key, '')})
        enabled = '1' if self.cleaned_data.get('student_registration_enabled') else '0'
        SiteSetting.objects.update_or_create(key='student_registration_enabled', defaults={'value': enabled})


class UserReportForm(forms.ModelForm):
    class Meta:
        model = UserReport
        fields = ['reason', 'details']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'maxlength': 1000,
                'placeholder': 'Describe what happened (optional, up to 1000 characters).',
            }),
        }
        labels = {
            'reason': 'Reason for reporting',
            'details': 'Additional details',
        }
