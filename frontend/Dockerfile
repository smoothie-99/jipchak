# 1. 빌드 단계 (Build Stage)
FROM node:24-alpine AS build

WORKDIR /app

# 빌드 타임 환경변수 (Vite 가 import.meta.env.* 로 번들에 정적 삽입)
# - 클라이언트 번들에 그대로 박히므로 진짜 비밀은 여기에 넣지 말 것
# - 운영 진짜 보안은 백엔드 인증으로 이전 예정 (2단계)
ARG VITE_ADMIN_PASSWORD=
ENV VITE_ADMIN_PASSWORD=${VITE_ADMIN_PASSWORD}

# WebSocket stream endpoint — 절대 URL 이면 외부 도메인 (예: RunPod), 상대 경로 ('/ws/stream') 이면 nginx proxy 경유.
ARG VITE_WS_STREAM_PATH=/ws/stream
ENV VITE_WS_STREAM_PATH=${VITE_WS_STREAM_PATH}

# npm 버전을 특정 버전으로 고정
RUN npm install -g npm@11.6.2

# 의존성 파일 복사 및 설치
COPY package*.json ./
RUN npm install

# 소스 코드 복사 및 빌드
COPY . .
RUN npm run build

# 2. 실행 단계 (Production Stage)
FROM nginx:stable-alpine

# Nginx 설정 파일 복사 (필요한 경우)
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# 빌드 결과물을 Nginx 기본 경로로 복사
COPY --from=build /app/dist /usr/share/nginx/html

# 컨테이너 내부 포트
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
