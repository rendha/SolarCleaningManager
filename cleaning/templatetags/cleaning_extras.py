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
