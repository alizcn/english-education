"""`UserLevel` tablosunu siler — dual-read penceresi kapandı.

Veri `0006_migrate_userlevel_to_usercourse` ile `UserCourse`a taşındı ve model
bir faz boyunca kodda okunmadan bırakıldı: o pencerede geri alma yalnızca kod
revert'i demekti, veri geri yüklemesi gerekmiyordu. Pencere kapandığı için
tablo kaldırılıyor.

`DeleteModel` şema olarak geri alınabilir: Django model durumunu
migration zincirinden türettiği için tabloyu `0002`deki hâliyle yeniden
kuruyor, `models.py`de karşılığı kalmasa da. Ama **geri alma veriyi
getirmez** — tablo boş doğar ve `0006` yeniden koşturulamaz, çünkü kaynak
satırlar artık yok. Gerçek kurtarma yolu `db.sqlite3` yedeği.
"""

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0006_migrate_userlevel_to_usercourse'),
    ]

    operations = [
        migrations.DeleteModel(name='UserLevel'),
    ]
