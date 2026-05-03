from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def superuser_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Bu sayfa yalnızca süper kullanıcılar içindir.')
        return view(request, *args, **kwargs)
    return wrapper
