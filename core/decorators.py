from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def access_code_required(view_func):
    """
    Blocks direct access to select_account, signup, and login_view
    unless this browser session has already passed the access-code
    gate (session key 'access_granted', set in access_code_view when
    the correct code is entered, cleared again in logout_view).

    Typing one of those URLs directly, or bookmarking one, now
    redirects to the access code page instead of the page that was
    actually requested — the code has to be entered first, every time,
    unless this session already passed the gate.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('access_granted'):
            messages.info(request, "Please enter the access code to continue.")
            return redirect('access_code')
        return view_func(request, *args, **kwargs)
    return wrapper