# 1단계: 빌드 환경 (Build stage)
FROM eclipse-temurin:21-jdk-jammy AS build

# 작업 디렉토리 설정
WORKDIR /app

# Gradle 래퍼 및 설정 파일 복사 (캐시 활용을 위해 먼저 복사)
COPY gradle gradle
COPY gradlew .
RUN chmod +x gradlew
COPY build.gradle .
COPY settings.gradle .

# 종속성 미리 다운로드
RUN ./gradlew dependencies --no-daemon

# 소스 코드 복사 및 빌드
COPY src src
RUN ./gradlew bootJar --no-daemon

# 2단계: 실행 환경 (Run stage)
FROM eclipse-temurin:21-jre-jammy

WORKDIR /app

# 빌드 단계에서 생성된 jar 파일만 복사
COPY --from=build /app/build/libs/*.jar app.jar

# 실행 권한 부여
RUN useradd -m jipchak
USER jipchak

# 실행 명령어
ENTRYPOINT ["java", "-jar", "app.jar"]
