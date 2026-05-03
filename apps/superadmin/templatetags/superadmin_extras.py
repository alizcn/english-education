from datetime import date, datetime
from decimal import Decimal

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='sa_truncate')
def sa_truncate(value, n=80):
    if value is None:
        return ''
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return value
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    s = str(value)
    if len(s) > n:
        return s[:n] + '…'
    return s


@register.filter(name='sa_cell')
def sa_cell(value):
    """Render a cell value as HTML, picking sensible widgets based on type."""
    if value is None or value == '':
        return mark_safe('<span class="sa-bool-null">—</span>')
    if value is True:
        return mark_safe('<span class="sa-bool-true">✓</span>')
    if value is False:
        return mark_safe('<span class="sa-bool-false">✗</span>')
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, (int, float, Decimal)):
        return value
    s = str(value)
    if len(s) > 80:
        s = s[:80] + '…'
    return escape(s)


@register.filter(name='sa_status')
def sa_status(value):
    """Map common status strings to colored badges."""
    if not value:
        return ''
    v = str(value).lower()
    cls = 'sa-badge'
    if v in ('active', 'success', 'aktif', 'başarılı', 'completed'):
        cls += ' sa-badge-success'
    elif v in ('pending', 'initialized', 'beklemede', 'başlatıldı'):
        cls += ' sa-badge-warning'
    elif v in ('failed', 'expired', 'cancelled', 'başarısız', 'iptal edildi', 'süresi doldu'):
        cls += ' sa-badge-danger'
    else:
        cls += ' sa-badge-info'
    return mark_safe(f'<span class="{cls}">{escape(value)}</span>')


@register.simple_tag(takes_context=True)
def sa_querystring(context, **kwargs):
    """Build a querystring preserving existing GET params, overriding with kwargs."""
    request = context.get('request')
    params = request.GET.copy() if request else {}
    for k, v in kwargs.items():
        if v in (None, ''):
            params.pop(k, None)
        else:
            params[k] = v
    return params.urlencode()
