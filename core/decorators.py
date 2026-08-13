from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def access_code_required(view_func):
    """
    Blocks access to a view until the visitor has entered the correct
    access code via access_code_view, which sets
    request.session['access_granted'] = True on success.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get('access_granted'):
            messages.error(request, "Please enter the access code first.")
            return redirect('access_code')  # must match your urls.py name
        return view_func(request, *args, **kwargs)
    return _wrapped