FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py /app/main.py
COPY app_shared.py /app/app_shared.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8092"]
