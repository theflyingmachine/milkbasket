from django import template

register = template.Library()


@register.simple_tag()
def entry_quantity(day, register_entry, default=None):
    default_quantity = '___' if not default else default

    for entry in register_entry:
        if entry.log_date.day == day:
            if entry.schedule.endswith("yes"):
                default_quantity = entry.quantity
            else:
                default_quantity = 'Absent' if not default else default
    try:
        return round(default_quantity)
    except:
        return default_quantity
