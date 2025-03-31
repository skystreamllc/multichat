FROM python:3.9-slim

WORKDIR /app

COPY app.py .
COPY templates/ ./templates/
COPY .env .

RUN pip install --no-cache-dir flask flask-socketio openai python-dotenv gunicorn eventlet

EXPOSE 5000

# По умолчанию запускаем Gunicorn для продакшена
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"]