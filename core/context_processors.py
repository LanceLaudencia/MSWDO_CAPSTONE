from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        notifs = Notification.objects.filter(recipient=request.user)[:5]
        unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {
            'notifications': notifs,
            'unread_notifications_count': unread
        }
    return {}
