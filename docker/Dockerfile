# ARGOS Dockerfile - Public version (generic)
FROM python:3.13-slim

WORKDIR /home/argos/argos-core

RUN apt-get update && apt-get install -y curl git rsync openssh-client && rm -rf /var/lib/apt/lists/*

COPY argos-core/ ./
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
