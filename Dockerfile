FROM python:3.11-alpine

WORKDIR /app

# Install minimal dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY config.example.yaml ./config.example.yaml
COPY config.example.en.yaml ./config.example.en.yaml

EXPOSE 8787

CMD ["python", "main.py"]
