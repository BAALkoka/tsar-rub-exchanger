FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY src/bot/requirements.txt src/bot/requirements.txt
COPY src/api/payouts/requirements.txt src/api/payouts/requirements.txt
RUN pip install --no-cache-dir -q \
    aiogram==3.13.1 \
    httpx==0.27.0 \
    fastapi==0.115.0 \
    uvicorn==0.32.0 \
    pydantic==2.9.0 \
    python-dotenv==1.0.0

COPY src/ src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

CMD ["python3", "-m", "bot.main"]