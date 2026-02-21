from .models import Notification

def notifications_processor(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        notifications = Notification.objects.filter(
            recipient=request.user
        ).order_by('-created_at')[:10]

        unread_notifications_count = notifications.filter(is_read=False).count()
    else:
        notifications = []
        unread_notifications_count = 0

    return {
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
    }