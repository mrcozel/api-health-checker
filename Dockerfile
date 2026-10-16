FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 monitor \
    && useradd --uid 10001 --gid monitor --no-create-home monitor \
    && mkdir /data && chown monitor:monitor /data

COPY health_checker.py email_alerts.py health_stats.py incident_history.py dashboard.py metrics.py ./
COPY dashboard/ ./dashboard/
USER 10001:10001
WORKDIR /data
CMD ["python", "/app/health_checker.py"]
