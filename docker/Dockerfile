FROM python:3.13-slim

WORKDIR /home/darkangel/.argos/argos-core

# Dependente sistem
RUN apt-get update && apt-get install -y \
    curl git openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Python packages
COPY argos-core/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# User non-root
RUN useradd -m -u 1000 argos
USER argos
WORKDIR /home/darkangel/.argos/argos-core

# --limit-max-request-size 10485760 → reject request bodies > 10 MB (audit H3)
CMD ["python3", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--limit-max-request-size", "10485760"]
