FROM python:3.11-alpine

WORKDIR /app

# 安装极简依赖 (aiohttp, pyyaml)
RUN pip install --no-cache-dir aiohttp pyyaml

COPY solar.py model.py ha_client.py main.py ./
COPY config.yaml ./

CMD ["python", "main.py"]
