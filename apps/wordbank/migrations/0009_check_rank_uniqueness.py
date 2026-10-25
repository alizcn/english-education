"""0010'daki `(language, level, rank)` kısıtının ön koşulunu doğrular.

Mevcut veride bu üçlü tekil olmak zorunda; değilse kısıt eklenirken Django
anlaşılmaz bir IntegrityError veriyor. Burada erken ve açıklayıcı düşüyoruz.

Repodaki JSON dosyalarında `rank` her seviyede tekil (test ile de sabitlendi),
bu yüzden normal akışta bu migration no-op.
"""

from collections import Counter

from django.db import migrations


def check(apps, schema_editor):
    BankWord = apps.get_model('wordbank', 'BankWord')
    counts = Counter(
        BankWord.objects.values_list('language', 'level', 'rank')
    )
    clashes = {key: n for key, n in counts.items() if n > 1}
    if not clashes:
        return

    sample = list(clashes.items())[:10]
    detail = ', '.join(f'{lang}/{level}/rank={rank} ×{n}'
                       for (lang, level, rank), n in sample)
    raise RuntimeError(
        f'{len(clashes)} adet (language, level, rank) çakışması var, '
        f'unique kısıtı eklenemez. Örnekler: {detail}. '
        'Çakışan satırların rank değerlerini düzeltip tekrar deneyin.'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0008_move_turkish_to_translation'),
    ]

    operations = [
        migrations.RunPython(check, migrations.RunPython.noop),
    ]
