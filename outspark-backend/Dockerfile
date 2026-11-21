FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY outspark ./outspark
USER 65532:65532
CMD ["sh", "-c", "exec uvicorn outspark.cloud_run:application --factory --host 0.0.0.0 --port \"${PORT:-8080}\" --no-access-log"]
