FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY api.py /app/api.py

EXPOSE 8002
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8002"]
