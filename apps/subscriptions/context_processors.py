from . import access


def subscription_status(request):
    if not request.user.is_authenticated:
        return {'user_access': None}
    state = access.get_state(request.user)
    return {'user_access': state}
