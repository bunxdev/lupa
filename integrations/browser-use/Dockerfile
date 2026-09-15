FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ENV ANONYMIZED_TELEMETRY=false BROWSER_USE_CLOUD_SYNC=false BROWSER_USE_LOGGING_LEVEL=error PYTHONUNBUFFERED=1
WORKDIR /client
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY client.py demo.html cursor.js leads.py lead_data.py export_leads.py ./
ENTRYPOINT ["python", "/client/client.py", "--token-stdin"]
