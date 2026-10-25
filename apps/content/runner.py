"""Devam edebilir paralel üretim koşucusu.

`claude_client.parallel_map`in üstüne oturuyor ve onun SÖZLEŞMESİNE uyuyor:
iş parçacıkları yalnızca Claude çağırır, veritabanına dokunmaz. Sonuçlar
generator ile ana parçacığa dönüyor ve DB yazımı orada yapılıyor — Django
thread başına ayrı bağlantı açtığı için SQLite'ta aksi hâlde
`database table is locked` alınıyor.

Oturum limiti davranışı özel: parça `failed` DEĞİL `pending` kalıyor ve
`attempts` artmıyor. Limit bir kalite hatası değil, kota olayı; denemeyi
harcamak parçayı haksız yere "üç kez denendi" durumuna düşürürdü.

Çıkış kodu 75 (`EX_TEMPFAIL`): dış sarmalayıcı "sonra tekrar dene"yi
böyle anlıyor.

    until manage.py enrich_wordbank --target de --native tr; do
      [ $? -eq 75 ] && sleep 1800 || break
    done
"""

import logging
import time

from django.utils import timezone

from services import claude_client as claude

from .models import GenerationBatch

logger = logging.getLogger(__name__)

#: `EX_TEMPFAIL` — geçici başarısızlık, sonra tekrar denenebilir.
EXIT_TEMPFAIL = 75


class SessionLimitReached(Exception):
    """CLI oturum limiti doldu; kalan plan iptal edilmeli."""


class BatchValidationError(Exception):
    """Üretilen parça kalite kapısından geçmedi."""


def pending_batches(queryset):
    """Yapılacak parçalar: hiç denenmemiş ya da hakkı tükenmemiş başarısızlar."""
    return queryset.filter(
        status__in=[GenerationBatch.PENDING, GenerationBatch.RUNNING,
                    GenerationBatch.FAILED],
        attempts__lt=GenerationBatch.MAX_ATTEMPTS,
    ).order_by('level', 'topic_slug', 'chunk_index')


def run_batches(queryset, produce, *, validate=None, workers=None,
                max_runtime=None, stdout=None):
    """Parçaları paralel üretir, bitenleri hemen kaydeder.

    `produce(batch) -> dict`  bir parçayı üretir (yalnızca Claude çağırır).
    `validate(batch, output)` çıktıyı denetler; `BatchValidationError` fırlatabilir.

    Dönen: `(done, failed, left, stopped_reason)`.
    """
    plan = list(pending_batches(queryset))
    if not plan:
        return 0, 0, 0, None

    write = stdout.write if stdout else (lambda *_a, **_k: None)
    started = time.monotonic()
    done = failed = 0
    stopped = None

    GenerationBatch.objects.filter(pk__in=[b.pk for b in plan]).update(
        status=GenerationBatch.RUNNING, started_at=timezone.now(),
    )

    for index, output, error in claude.parallel_map(produce, plan, workers=workers):
        batch = plan[index]

        if error is not None:
            reason = getattr(error, 'reason', '')
            if reason == 'session_limit':
                # Kota olayı: deneme hakkı harcanmıyor, parça yeniden
                # denenmek üzere bekliyor.
                GenerationBatch.objects.filter(pk=batch.pk).update(
                    status=GenerationBatch.PENDING,
                    last_error=str(error)[:2000],
                )
                stopped = 'session_limit'
                write(f'  oturum limiti — parça {batch} bekliyor bırakıldı')
                break
            failed += 1
            GenerationBatch.objects.filter(pk=batch.pk).update(
                status=GenerationBatch.FAILED,
                attempts=batch.attempts + 1,
                last_error=str(error)[:2000],
                finished_at=timezone.now(),
            )
            write(f'  BAŞARISIZ {batch}: {str(error)[:120]}')
            continue

        try:
            if validate is not None:
                validate(batch, output)
        except BatchValidationError as e:
            failed += 1
            GenerationBatch.objects.filter(pk=batch.pk).update(
                status=GenerationBatch.FAILED,
                attempts=batch.attempts + 1,
                last_error=f'doğrulama: {e}'[:2000],
                finished_at=timezone.now(),
            )
            write(f'  DOĞRULAMA {batch}: {e}')
            continue

        done += 1
        GenerationBatch.objects.filter(pk=batch.pk).update(
            status=GenerationBatch.DONE,
            attempts=batch.attempts + 1,
            output=output,
            last_error='',
            model_used=claude._setting('CLAUDE_MODEL'),
            finished_at=timezone.now(),
        )
        # `.update()` bellekteki nesneyi tazelemiyor; `__str__` durumu
        # yazdırdığı için güncellemezsek log satırı "bitti … [pending]" diyor
        # ve izleme sırasında yanlış alarm veriyor.
        batch.status = GenerationBatch.DONE
        write(f'  bitti {batch} ({done}/{len(plan)})')

        if max_runtime and (time.monotonic() - started) > max_runtime:
            stopped = 'max_runtime'
            write(f'  süre sınırı ({max_runtime}s) aşıldı, temiz çıkılıyor')
            break

    # Başlatıldı ama sıra gelmemiş parçaları geri bekleme durumuna al.
    GenerationBatch.objects.filter(
        pk__in=[b.pk for b in plan], status=GenerationBatch.RUNNING,
    ).update(status=GenerationBatch.PENDING, started_at=None)

    left = pending_batches(queryset).count()
    return done, failed, left, stopped


def plan_chunks(items, batch_size):
    """`items`i `batch_size`lik parçalara böler, `(index, parça)` verir.

    Parça indeksi listenin SIRASINA bağlı; bu yüzden kaynak liste
    deterministik olmak zorunda (rank sırası). Aksi halde `--resume` yanlış
    parçayı atlar.
    """
    for index in range(0, len(items), batch_size):
        yield index // batch_size, items[index:index + batch_size]
