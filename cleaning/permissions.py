from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect

def owner_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            if request.headers.get('x-request-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Not allowed'}, status=403)
            return redirect('home')      # not an owner: back to your own page instead of a 403 error
        return view(request, *args, **kwargs)
    return wrapper


# The people who go out to site: they keep their own "My Jobs" dashboard.  Everybody else who is not an owner sees the Service Desk.
# Add more by putting a person in the group "Field team" in Admin.
FIELD_TEAM = {'aswanth', 'ziyad', 'junaid'}


def is_field_team(user):
    if not user.is_authenticated:
        return False
    if user.get_username().lower() in FIELD_TEAM:
        return True
    return user.groups.filter(name__iexact='Field team').exists()


# The person who schedules (Fidha): her menu is kept short - no "To Be Scheduled" page and no "Record Finished Job".
SCHEDULER_NAMES = {'fidha'}


def is_scheduler(user):
    return user.is_authenticated and user.get_username().lower() in SCHEDULER_NAMES
