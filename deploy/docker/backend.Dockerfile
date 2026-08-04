FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH=/opt/at-flow/src
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
      /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates xz-utils && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://npmmirror.com/mirrors/node/v20.19.0/node-v20.19.0-linux-x64.tar.xz \
    | tar -xJ -C /usr/local --strip-components=1

RUN npm install --registry=https://registry.npmmirror.com -g @openai/codex opencode-ai

WORKDIR /opt/at-flow

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY at.py at.config.json AGENTS.md ./
COPY src ./src
COPY deploy/docker/entrypoint.sh /usr/local/bin/at-entrypoint
RUN chmod +x /usr/local/bin/at-entrypoint

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/at-entrypoint"]
