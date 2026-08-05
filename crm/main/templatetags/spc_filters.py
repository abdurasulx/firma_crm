from django import template
from django.template.defaultfilters import floatformat

from ..functions import add_spctoint

register = template.Library()


@register.filter(name='spc')
def spc(value, decimals=0):
    """Sonni har 3 xonadan keyin probel bilan ajratadi (1250000 -> "1 250 000").
    `decimals` — verguldan keyin nechta raqam qoldirilishi (standart 0)."""
    if value in (None, ''):
        return ''
    formatted = floatformat(value, decimals)
    return add_spctoint(formatted)
