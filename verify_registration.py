import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()
from core.forms import StudentRegistrationForm

data = {
    'email': 'tester@gmail.com',
    'full_name': 'Test Student',
    'student_id': '241-0273-1',
    'program': 'CE',
    'password1': 'StrongPass123',
    'password2': 'StrongPass123',
}
form = StudentRegistrationForm(data=data)
print('valid', form.is_valid())
print(form.errors)
if form.is_valid():
    user = form.save()
    print('saved', user.email, user.student_id, user.program, user.role)
