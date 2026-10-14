FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /relay
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
USER 65534:65534
CMD ["uvicorn", "app:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "4", "--no-access-log", "--no-proxy-headers"]
