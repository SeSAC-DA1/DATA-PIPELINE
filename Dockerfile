FROM apache/airflow:3.1.0-python3.13

USER root
ENV DEBIAN_FRONTEND=noninteractive

# 필수 OS 패키지 + Chrome
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl gnupg ca-certificates unzip \
      libnss3 libxss1 libasound2 libx11-xcb1 libxcomposite1 libxdamage1 \
      libgbm1 libgtk-3-0 fonts-noto-cjk && \
    mkdir -p /usr/share/keyrings && \
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | gpg --dearmor -o /usr/share/keyrings/google-linux.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

USER airflow

# 추가 패키지 설치 (공식 방식: constraints 없이)
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 런타임 힌트
ENV CHROME_BIN=/usr/bin/google-chrome \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
