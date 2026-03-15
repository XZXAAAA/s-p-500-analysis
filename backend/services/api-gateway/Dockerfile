FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY backend/services/api-gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/backend/services/api-gateway

EXPOSE 5000

CMD ["python", "gateway.py"]

