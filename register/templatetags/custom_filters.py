from django import template

register = template.Library()


@register.filter
def divide_by_1000(value):
    try:
        return float(value) / 1000
    except (ValueError, TypeError):
        return value
