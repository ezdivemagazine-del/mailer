FROM python:3.11-slim-bullseye

WORKDIR /app

COPY app/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /app/data

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
