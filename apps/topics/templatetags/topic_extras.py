"""Konu şablonları için yardımcı filtreler."""

from django import template

register = template.Library()


@register.filter
def dict_get(value, key):
    """Sözlükten anahtarla okur — Django şablon dili değişken anahtarı desteklemiyor.

    `TopicExample.translations` bir JSON sözlüğü ve anahtarı çalışma anında
    belirleniyor (kursun ana dili). `{{ e.translations.tr }}` sabit anahtar
    gerektirdiği için işe yaramıyor.
    """
    if not isinstance(value, dict) or not key:
        return ''
    return value.get(key) or ''
