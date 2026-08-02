FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY zhangwen_cloud_auth ./zhangwen_cloud_auth

ENV PYTHONUNBUFFERED=1
EXPOSE 8200
CMD ["uvicorn", "zhangwen_cloud_auth.main:app", "--host", "0.0.0.0", "--port", "8200"]
