#!/bin/sh
# Container açılış akışı.
#
# Eskiden bu iş Dockerfile'ın CMD satırındaydı ve her açılışta migrate +
# compilemessages + üç seed komutu koşuyordu. Seed'ler dil sayısıyla
# çarpıldığı için (dört hedef dil × altı seviye × ~6k kelime + çeviri satırları)
# açılış dakikalara çıkıyordu; `seed_topics` ayrıca her seferinde örnekleri
# silip yeniden yaratıyordu.
#
# Artık: migrate her zaman koşar (şema geriye dönük uyumlu tutuluyor), seed'ler
# yalnızca kaynak dosyalar değiştiğinde. Parmak izi `data/` altında tutuluyor,
# yani imajdan bağımsız ve volume ile kalıcı.
set -e

# Yalnızca web container'ı şema ve içerik kurar. Celery worker/beat aynı
# ENTRYPOINT'ten geçtiği için bu guard olmadan üç container birlikte migrate
# koşar: SQLite'ta bu kilit çekişmesi, seed'lerde ise aynı işin üç kez
# yapılması demek. compose dosyasında celery servisleri SKIP_BOOTSTRAP=1 veriyor.
if [ "${SKIP_BOOTSTRAP:-0}" = "1" ]; then
    echo "[entrypoint] SKIP_BOOTSTRAP=1 — migrate ve seed atlandı"
    exec "$@"
fi

FINGERPRINT_DIR="${FINGERPRINT_DIR:-/app/data/.seed-fingerprints}"
mkdir -p "$FINGERPRINT_DIR"

# Kaynak dosyaların SHA'sını alır; dizin yoksa boş döner.
fingerprint() {
    # shellcheck disable=SC2039
    find "$@" -type f \( -name '*.json' -o -name '*.md' -o -name '*.py' \) 2>/dev/null \
        | LC_ALL=C sort \
        | xargs -r sha256sum 2>/dev/null \
        | sha256sum \
        | cut -d' ' -f1
}

# seed_if_changed <ad> <kaynak dizin...> -- <komut...>
seed_if_changed() {
    name="$1"; shift
    sources=""
    while [ "$1" != "--" ]; do
        sources="$sources $1"
        shift
    done
    shift  # '--' atla

    # shellcheck disable=SC2086
    current="$(fingerprint $sources)"
    stamp="$FINGERPRINT_DIR/$name"

    if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$current" ] && [ -n "$current" ]; then
        echo "[entrypoint] $name: kaynak değişmemiş, atlandı"
        return 0
    fi

    echo "[entrypoint] $name: çalıştırılıyor"
    if "$@"; then
        printf '%s' "$current" > "$stamp"
    else
        # Başarısız seed'in parmak izini YAZMIYORUZ: sonraki açılış tekrar denesin.
        echo "[entrypoint] $name: BAŞARISIZ — parmak izi yazılmadı" >&2
        return 1
    fi
}

echo "[entrypoint] migrate"
python manage.py migrate --noinput

seed_if_changed topics  /app/apps/topics/management/commands /app/apps/topics/data \
    -- python manage.py seed_topics
seed_if_changed wordbank /app/apps/wordbank/data \
    -- python manage.py load_wordbank
seed_if_changed quizzes /app/apps/quizzes/seeds \
    -- python manage.py seed_quizzes

exec "$@"
