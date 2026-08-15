pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timeout(time: 15, unit: 'MINUTES')
    }

    environment {
        DOCKER_COMPOSE_DIR = 'infra'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                dir("${DOCKER_COMPOSE_DIR}") {
                    sh "touch .env"
                }
            }
        }

        stage('Backend Build & Test') {
            when {
                changeset "backend/**"
            }
            steps {
                echo 'Building & Testing Backend...'
                dir("backend") {
                    sh "docker run --rm -w /app -v \$(pwd):/app eclipse-temurin:21-jdk-jammy sh -c 'chmod +x gradlew && ./gradlew build --no-daemon'"
                }
            }
        }

        // [REMOVED] AI Build / AI Test / AI Deploy stages
        //   AI 서버는 RunPod (GPU pod) 으로 분리됨.
        //   EC2 에서 ai-jipchak 빌드/배포하지 않음 — 코드 변경은 RunPod 에서 git pull + uvicorn 재시작으로 적용.
        //   docker-compose.yml 에서도 ai-jipchak service 제거.

        stage('Frontend CI') {
            when {
                changeset "frontend/**"
            }
            steps {
                echo 'Frontend typecheck & test...'
                dir("frontend") {
                    sh "docker run --rm -w /app -v \$(pwd):/app node:24-alpine sh -c '(npm ci || npm install) && npm run typecheck && npm run test:ci'"
                }
            }
        }

        stage('Backend Deploy') {
            when {
                changeset "backend/**"
            }
            steps {
                echo 'Deploying Backend...'
                dir("${DOCKER_COMPOSE_DIR}") {
                    // --force-recreate 로 compose 의 변경 감지 오판으로 컨테이너가
                    // Created 상태에 멈추는 사고를 방지한다.
                    sh "docker compose up -d --force-recreate --build app-jipchak"
                }
            }
        }

        // [REMOVED] AI Deploy — AI 는 RunPod 에서 별도 운영.

        stage('Frontend Deploy') {
            when {
                changeset "frontend/**"
            }
            steps {
                echo 'Deploying Frontend...'
                dir("${DOCKER_COMPOSE_DIR}") {
                    // --force-recreate 로 빌드 후 컨테이너가 Created 상태에 멈추는
                    // 과거 사고 (Phase 1 / Phase 2 머지 직후 frontend 다운) 재발 방지.
                    sh "docker compose up -d --force-recreate --build frontend-jipchak"
                }
            }
        }

        stage('Infra Deploy') {
            when {
                changeset "infra/**"
            }
            steps {
                echo 'Infra changed, rebuilding all services (jenkins excluded)...'
                dir("${DOCKER_COMPOSE_DIR}") {
                    // ⚠️ jenkins 는 명시적으로 제외.
                    //    Jenkins 가 자기 자신 컨테이너를 docker compose 로 재생성하면
                    //    Jenkins JVM 이 죽는 순간 현재 빌드 프로세스도 같이 종료되어
                    //    새 컨테이너가 Created 상태에 멈춘다 (실제 사고 발생함).
                    //    Jenkins 자체 업데이트는 호스트에서 수동으로:
                    //      docker compose up -d --force-recreate jenkins
                    //
                    // --force-recreate 로 정의 변경 감지 오판에 의한 컨테이너 stuck 방지.
                    sh "docker compose up -d --force-recreate --build db-jipchak redis-jipchak app-jipchak frontend-jipchak nginx"
                    // nginx conf 가 바인드 마운트라 컨테이너 recreate 만으로는 conf 갱신이 안 될 수도 있어
                    // 명시적으로 reload 호출. 실패 시 컨테이너 restart 로 fallback.
                    sh "docker compose exec -T nginx nginx -s reload || docker compose restart nginx"
                }
            }
        }

        stage('Cleanup') {
            steps {
                sh "docker image prune -f"
            }
        }
    }

    post {
        success {
            echo 'CI/CD Finished Successfully!'
        }
        failure {
            echo 'CI/CD Failed. Please check the logs.'
        }
    }
}
