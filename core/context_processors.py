from .models import Notification

def notifications_processor(request):
    if request.user.is_authenticated:
        user_role = getattr(request.user, "role", None)
        if user_role in ["staff", "admin"] or request.user.is_superuser:
            # Get all notifications for this user (no slice yet)
            notifications_all = Notification.objects.filter(
                recipient=request.user
            ).order_by('-created_at')
            
            # Count unread BEFORE slicing
            unread_notifications_count = notifications_all.filter(is_read=False).count()
            
            # NOW slice to get only 10 for display
            notifications = notifications_all[:10]
        else:
            notifications = []
            unread_notifications_count = 0
    else:
        notifications = []
        unread_notifications_count = 0

    return {
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
    }