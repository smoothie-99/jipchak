FROM python:3.11-slim

# stdout/stderr 를 즉시 flush — print 로그가 docker logs 에 즉시 보이게
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# OpenCV가 필요로 하는 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 영상 저장용 디렉토리
RUN mkdir -p /data/recordings

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
