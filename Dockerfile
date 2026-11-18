# syntax=docker/dockerfile:1.4
FROM python:3.12-slim

WORKDIR /app

# gthread-Worker: glibc legt sonst je Thread eine 64-MB-Arena an, die nie
# zurueckgegeben wird (Coding-Standards, "Limit the glibc malloc arenas").
ENV MALLOC_ARENA_MAX=2 \
    MALLOC_TRIM_THRESHOLD_=131072

# msh-base ist VENDORED (lokales Verzeichnis `msh-base/`, via
# `msh-base @ file:///app/msh-base` in requirements.txt) — das kanonische
# Muster realer MSH-Services (claude-overview, gehaltsmatrix). Kein git+http-
# Clone von msh/base, kein `git`-Build-Tool und kein `gitea_credentials`-Secret
# noetig (der git-clone-Pfad schlug im BuildKit-Build reproduzierbar fehl).
# `COPY msh-base/` vor dem Source-COPY haelt den pip-Layer gecached, solange
# sich requirements + msh-base nicht aendern.
# Schrift mit Umlauten/Sonderzeichen fuer die PDF-Downloads (app/services/doc_export.py)
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY msh-base/ ./msh-base/
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -r -u 1000 -s /bin/false appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "-k", "gthread", \
     "--threads", "4", "--access-logfile", "-", "wsgi:app"]
