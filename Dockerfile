FROM python:3.12-slim

WORKDIR /app

COPY src/api/payouts/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt aiogram==3.13.1 httpx==0.27.0

COPY src/ /app/src/

ENV PYTHONPATH=/app/src
ENV PORT=8080

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "api.payouts.api:app", "--host", "0.0.0.0", "--port", "8080"]