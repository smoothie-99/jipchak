package com.jipchak.server.service;

import com.jipchak.server.dto.GameLogResponse;
import com.jipchak.server.entity.GameLog;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.jipchak.server.dto.SessionVideoDto;
import com.jipchak.server.repository.GameLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.springframework.data.redis.core.StringRedisTemplate;

/**
 * 게임 로그 저장 + 영상 파일 관리.
 *
 * 호출 흐름:
 * 1. AI 서버가 멀티파트(sessionId, isSuccess, video) 로 호출
 * 2. 디스크에 영상 저장 → DB에 메타 저장
 * 3. 보관 한도 초과 시 가장 오래된 영상부터 삭제
 * 4. 응답 DTO(GameLogResponse) 반환
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional
public class GameLogService {

    private final GameLogRepository gameLogRepository;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    /** 보관 영상 최대 개수. application.yml 의 jipchak.video.max-count 와 매핑. */
    @Value("${jipchak.video.max-count:50}")
    private int maxVideoCount;

    /** 영상 저장 베이스 디렉토리. 절대 경로 또는 상대 경로 가능. */
    @Value("${jipchak.video.base-dir:videos}")
    private String videoBaseDir;

    public Long saveGameLog(String sessionId, Boolean isSuccess, MultipartFile video) throws IOException {
        // 1. 영상 저장 폴더 보장
        String uploadPath = resolveUploadPath();
        File folder = new File(uploadPath);
        if (!folder.exists() && !folder.mkdirs()) {
            throw new IOException("영상 저장 폴더 생성 실패: " + uploadPath);
        }

        // 2. 보관 한도 정리 (디스크 누적 방지)
        enforceVideoRetention();

        // 3. 파일명 결정 (중복 방지: sessionId + UUID 단편)
        String fileName = buildFileName(sessionId);
        String fullPath = Paths.get(uploadPath, fileName).toString();

        // 4. 디스크 쓰기
        video.transferTo(new File(fullPath));

        // 5. DB 메타 저장
        GameLog gameLogEntity = GameLog.builder()
                .sessionId(sessionId)
                .isSuccess(isSuccess)
                .videoPath(fullPath)
                // QR 다운로드용 short key (8자리)
                .qrCodeKey(UUID.randomUUID().toString().substring(0, 8))
                .build();
        GameLog saved = gameLogRepository.save(gameLogEntity);

        // 6. 응답 DTO 빌드 (Nginx /videos/<fileName> 로 외부 접근)
        String videoUrl = "/videos/" + fileName;

        // 7. Redis session update (TTL 3 minutes per sessionId key)
        if (sessionId != null && !sessionId.isBlank()) {
            try {
                SessionVideoDto dto = SessionVideoDto.builder()
                        .id(saved.getId().toString())
                        .url(videoUrl)
                        .thumb("/logo.png") // 클라이언트가 처리할 수 있게 기본 로고 경로 지정
                        .isSuccess(isSuccess)
                        .build();
                String jsonString = objectMapper.writeValueAsString(dto);
                String redisKey = "session:" + sessionId;
                redisTemplate.opsForList().rightPush(redisKey, jsonString);
                redisTemplate.expire(redisKey, 3, TimeUnit.MINUTES);
            } catch (Exception e) {
                log.error("Redis 세션 정보 업데이트 실패: {}", e.getMessage());
            }
        }

        return saved.getId();
    }

    /**
     * videoBaseDir 가 절대 경로면 그대로, 아니면 작업 디렉토리 기준 상대경로로 해석.
     */
    private String resolveUploadPath() {
        File base = new File(videoBaseDir);
        if (base.isAbsolute()) {
            return base.getAbsolutePath();
        }
        return Paths.get(System.getProperty("user.dir"), videoBaseDir).toString();
    }

    /**
     * 보관 한도 초과 시 가장 오래된 영상부터 삭제.
     * (DB row 는 남기되 videoPath 만 비워서 다운로드 시 404 가 나도록.)
     */
    private void enforceVideoRetention() {
        List<GameLog> logs = gameLogRepository.findByVideoPathIsNotNullOrderByCreatedAtAsc();
        int excess = logs.size() - (maxVideoCount - 1); // 새로 1개 추가될 자리 확보
        if (excess <= 0) {
            return;
        }
        for (int i = 0; i < excess; i++) {
            GameLog oldest = logs.get(i);
            File file = new File(oldest.getVideoPath());
            if (file.exists() && !file.delete()) {
                log.warn("오래된 영상 파일 삭제 실패: {}", oldest.getVideoPath());
            }
            oldest.clearVideoPath();
        }
    }

    /** 파일명 규칙: "yyMMdd_HHmmss.mp4" — 같은 초 동시 종료는 거의 없으므로 초 단위로 충분. */
    private static final DateTimeFormatter FILE_NAME_FORMAT = DateTimeFormatter.ofPattern("yyMMdd_HHmmss");
    /** 파일명 timestamp 는 항상 KST 로 — JVM default timezone (UTC) 영향 받지 않도록 명시. */
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    private String buildFileName(String sessionId) {
        return LocalDateTime.now(KST).format(FILE_NAME_FORMAT) + ".mp4";
    }
}
