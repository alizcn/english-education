FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gettext \
        libmagic1 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI — CLAUDE_AUTH_MODE=cli bu binary'yi subprocess olarak çağırır,
# kimlik doğrulamayı compose'da mount edilen ~/.claude oturumundan alır.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/data

# Çeviriler BUILD aşamasında derleniyor. Eskiden CMD içindeydi: .po dosyası
# bayat kalırsa canlıya da bayat yansıyordu ve her container açılışı gereksiz
# iş yapıyordu. .mo artefaktı artık imajın parçası, repoda tutulmuyor.
RUN python manage.py compilemessages

RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Seed komutları CMD'den çıkarıldı ve entrypoint'e taşındı: dört dil × altı
# seviye × ~6k satır + çeviriler her açılışta dakikalar sürüyordu, ayrıca
# seed_topics örnekleri silip yeniden yaratıyordu. Entrypoint kaynak
# dosyaların parmak izini tutup değişmemişse adımı atlıyor.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "900", "--access-logfile", "-", "--error-logfile", "-"]
