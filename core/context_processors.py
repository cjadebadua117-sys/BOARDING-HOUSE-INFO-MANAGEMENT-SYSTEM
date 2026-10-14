from django.db.models import Q, F
from django.utils import timezone


def inquiry_notifications(request):
    """Inject the unread-inquiry count for the sidebar NEW badge.

    Both roles get a badge: a landlord sees students whose inquiries/replies
    they have not opened, and a student sees landlord replies they have not
    read. The per-thread timestamps (Inquiry.last_viewed_by_*) decide what is
    unread; one correlated subquery covers the whole list.
    """
    ctx = {}
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return ctx
    role = getattr(user, 'role', None)
    if role not in ('landlord', 'student'):
        return ctx

    from core.models import Inquiry
    from core.views import _inquiry_has_new_message, _with_latest_message

    if role == 'landlord':
        qs = Inquiry.objects.filter(room__boarding_house__owner=user).exclude(
            status__in=[Inquiry.Status.CLOSED, Inquiry.Status.REJECTED]
        )
        viewed_field = 'last_viewed_by_landlord'
    else:
        qs = Inquiry.objects.filter(student=user)
        viewed_field = 'last_viewed_by_student'

    ctx['pending_inquiries_count'] = sum(
        1 for inq in _with_latest_message(qs)
        if _inquiry_has_new_message(inq, viewed_field)
    )
    return ctx
