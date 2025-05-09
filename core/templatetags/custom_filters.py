from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    return value - arg

@register.filter
def keyvalue(dictionary, key):
    if not dictionary or not isinstance(dictionary, dict):
        return {}
    return dictionary.get(str(key), {})