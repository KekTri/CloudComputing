FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /usr/local/lib/python3.11/site-packages/pyspark/jars/
COPY analytics_job.py .
COPY spark-server.pem .

CMD ["python", "analytics_job.py"]
