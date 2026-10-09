from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

def owner_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            if request.headers.get('x-request-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Not allowed'}, status=403)
            raise PermissionsDenied
        return view(request, *args, **kwargs)
    return wrapper            