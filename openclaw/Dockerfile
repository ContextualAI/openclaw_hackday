FROM python:3.12-slim

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scrape.py .
COPY telegram_sec_bot.py .
COPY telegram_bot.py .

CMD ["python", "scrape.py"]
