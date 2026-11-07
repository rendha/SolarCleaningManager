from django import template

register = template.Library()


@register.simple_tag
def pending_requests():
    """How many "to be scheduled" items are waiting (shown on the menu)."""
    from cleaning.models import ScheduleRequest
    try:
        return ScheduleRequest.objects.filter(done=False).count()
    except Exception:
        return 0


@register.simple_tag
def pending_requests_of(kind):
    """How many waiting items there are for the Cleaning ('cleaning') or the Services ('services') calendar."""
    from django.db.models import Q
    from cleaning.models import ScheduleRequest
    try:
        only_cleaning = Q(service_type__isnull=True) | Q(service_type__name__iexact='cleaning')
        waiting = ScheduleRequest.objects.filter(done=False)
        return (waiting.exclude(only_cleaning) if kind == 'services' else waiting.filter(only_cleaning)).count()
    except Exception:
        return 0


@register.simple_tag
def field_team(user):
    """True for the people who go out to site (they keep My Jobs); everybody else gets the Service Desk menu."""
    from cleaning.permissions import is_field_team
    return is_field_team(user)


@register.simple_tag
def scheduler_user(user):
    """True for the scheduler (Fidha): some owner-menu items are hidden for her."""
    from cleaning.permissions import is_scheduler
    return is_scheduler(user) or bool(user.is_superuser)
