# Сервер MCP для Petzy: HTTP на порту 8000, путь /mcp, проверка здоровья на /healthz.
# Собирать из этой папки: docker build -t petzy-mcp mcp
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin petzy

COPY petzy_mcp ./petzy_mcp

# Не root, как и веб-приложение. Сервер ничего не пишет на диск, а код принадлежит root и открыт только на чтение.
USER petzy

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"]

CMD ["python", "-m", "petzy_mcp", "--host", "0.0.0.0", "--port", "8000"]
