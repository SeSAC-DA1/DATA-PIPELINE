FROM apache/airflow:3.1.0

# root로 OS/Chrome 설치
USER root
ENV DEBIAN_FRONTEND=noninteractive

# Chrome 설치를 위한 패키지 설치
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
    apt-get autoremove -yqq --purge && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# airflow 유저로 돌아와 Python 패키지 설치 (+constraints)
USER airflow
ARG AIRFLOW_VERSION=3.1.0
ENV PIP_NO_CACHE_DIR=1
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir \
    -r /requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"

# 런타임 힌트
ENV CHROME_BIN=/usr/bin/google-chrome \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
