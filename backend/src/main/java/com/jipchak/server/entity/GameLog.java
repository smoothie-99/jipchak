package com.jipchak.server.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

/**
 * 게임 한 판의 결과(성공/실패) 및 영상 메타데이터.
 *
 * sessionId 는 한 사용자의 키오스크 세션(여러 판)을 묶기 위한 식별자이며
 * AI 서버(FastAPI)가 송신하는 값을 그대로 보관한다. 같은 sessionId 끼리
 * 묶어서 QR 다운로드 시 모아서 제공할 수 있다.
 */
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(
        name = "game_logs",
        indexes = {
                // 같은 세션의 영상 묶음 조회를 위한 인덱스
                @Index(name = "idx_game_logs_session_id", columnList = "sessionId"),
                // 오래된 영상 정리(createdAt 오름차순) 시 사용
                @Index(name = "idx_game_logs_created_at", columnList = "createdAt")
        }
)
public class GameLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** AI 서버가 송신하는 세션 ID (예: "mock-2846ea48"). */
    @Column(length = 64)
    private String sessionId;

    @Column(nullable = false)
    private Boolean isSuccess;

    /** 영상 파일의 절대 경로. 파일이 삭제된 후에는 null. */
    private String videoPath;

    /** QR 다운로드용 short key (UUID 앞 8자리). */
    @Column(unique = true, length = 8)
    private String qrCodeKey;

    private LocalDateTime createdAt;

    @PrePersist
    public void prePersist() {
        this.createdAt = LocalDateTime.now();
    }

    /** 파일이 디스크에서 삭제되었을 때 경로만 비운다. */
    public void clearVideoPath() {
        this.videoPath = null;
    }

    // 기존 호환을 위해 남겨둠 (deprecated)
    public void updateVideoPath(String videoPath) {
        this.videoPath = videoPath;
    }
}
