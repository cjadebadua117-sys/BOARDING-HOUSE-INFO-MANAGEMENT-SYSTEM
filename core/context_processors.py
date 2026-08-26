from django.db.models import Q, F
from django.utils import timezone


def landlord_notifications(request):
    """Inject notification counts for the sidebar badge."""
    ctx = {}
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.role != 'landlord':
        return ctx
    from core.models import Inquiry, InquiryMessage
    
    # Get all active inquiries for this landlord
    inquiries = Inquiry.objects.filter(
        room__boarding_house__owner=user
    ).exclude(status__in=[Inquiry.Status.CLOSED, Inquiry.Status.REJECTED])
    
    # Count inquiries with new messages since landlord last viewed
    count = 0
    for inq in inquiries:
        latest_msg = inq.messages.order_by('-sent_at').first()
        if latest_msg and (inq.last_viewed_by_landlord is None or latest_msg.sent_at > inq.last_viewed_by_landlord):
            count += 1
    
    ctx['pending_inquiries_count'] = count
    return ctx
