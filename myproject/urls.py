"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os

import django
from django.contrib import admin
from django.urls import include, path
from django.views import generic as django_views
from django.contrib.auth import views as auth_views
from django.conf import settings

handler404 = 'core.views.handler404'
handler500 = 'core.views.handler500'


def admin_honeypot(request):
    """Deception page at the scannable /admin/ path: always a fake login that
    never authenticates, and every probe is recorded in the audit log."""
    from django import forms as dj_forms

    class _FakeForm(dj_forms.Form):
        username = dj_forms.CharField(max_length=150)
        password = dj_forms.CharField(widget=dj_forms.PasswordInput)

    from core.models import AdminActionLog
    if request.method == 'POST':
        form = _FakeForm(request.POST)
        form.add_error(None, 'Invalid username or password. Please try again.')
        try:
            AdminActionLog.objects.create(
                actor=None,
                action='honeypot_probe',
                target_model='AdminHoneypot',
                target_id='/',
                target_repr=(request.POST.get('username') or '')[:64],
            )
        except Exception:
            pass
    else:
        form = _FakeForm()
    from django.shortcuts import render
    return render(request, 'core/admin_honeypot.html', {'form': form}, status=200)


urlpatterns = [
    path('', include('core.urls')),
    # Browsers request /favicon.ico by default even when a favicon <link>
    # is declared; redirect to the real icon instead of logging a 404.
    path('favicon.ico', django.views.generic.RedirectView.as_view(
        url='/static/core/images/bhims-icon.png', permanent=True)),
    path('admin/', admin_honeypot),
    path(settings.ADMIN_URL + '/', admin.site.urls),
    # Password reset URLs
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='core/password_reset.html'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='core/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='core/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='core/password_reset_complete.html'
    ), name='password_reset_complete'),
]

# Serve user-uploaded media and static files from Django.
# NOTE: In production behind nginx/Apache, let the web server serve these
# directories instead and remove this block.
# We call the serve views directly because django.conf.urls.static.static()
# silently serves nothing when DEBUG=False.
from django.contrib.staticfiles import finders
from django.http import Http404
from django.urls import re_path
from django.views.static import serve as _serve_file


def serve_static(request, path):
    # Resolve via the staticfiles finders so app-level static dirs work
    # even before `collectstatic` has been run.
    absolute_path = finders.find(path)
    if not absolute_path:
        raise Http404(f'{path!r} could not be found')
    document_root, relative_path = os.path.split(absolute_path)
    return _serve_file(request, relative_path, document_root=document_root)


urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', _serve_file,
            {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve_static),
]