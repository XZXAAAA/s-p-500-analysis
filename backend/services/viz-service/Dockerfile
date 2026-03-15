FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY backend/services/viz-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/backend/services/viz-service

EXPOSE 5003

CMD ["python", "app.py"]

