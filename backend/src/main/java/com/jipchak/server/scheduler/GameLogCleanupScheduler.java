package com.jipchak.server.scheduler;

import com.jipchak.server.entity.GameLog;
import com.jipchak.server.repository.GameLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class GameLogCleanupScheduler {

    private static final long RETENTION_MINUTES = 3L;
    private final GameLogRepository gameLogRepository;

    @Scheduled(fixedDelayString = "${jipchak.video.cleanup-interval-ms:30000}")
    @Transactional
    public void cleanupExpiredLogs() {
        LocalDateTime cutoff = LocalDateTime.now().minusMinutes(RETENTION_MINUTES);
        List<GameLog> expiredLogs = gameLogRepository.findByCreatedAtBefore(cutoff);
        if (expiredLogs.isEmpty()) {
            return;
        }

        int cleanedFileCount = 0;
        for (GameLog logEntity : expiredLogs) {
            String videoPath = logEntity.getVideoPath();
            if (videoPath != null && !videoPath.isBlank()) {
                File file = new File(videoPath);
                if (file.exists() && !file.delete()) {
                    log.warn("Failed to delete expired video file: {}", videoPath);
                } else {
                    cleanedFileCount += 1;
                }
            }
            // 게임 결과(isSuccess, createdAt, sessionId)는 남기고 videoPath 만 비운다.
            logEntity.clearVideoPath();
        }
        log.info(
                "Expired cleanup done: rows touched={}, files deleted={}, retention={} min",
                expiredLogs.size(),
                cleanedFileCount,
                RETENTION_MINUTES
        );
    }
}
