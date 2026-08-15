package com.jipchak.server.dto;

import com.jipchak.server.entity.GameLog;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

/**
 * 게임 로그 저장 응답 DTO.
 *
 * 클라이언트(AI 서버, 프론트엔드)는 이 JSON 을 그대로 파싱하여
 * - id: DB 식별자 (디버그/추적용)
 * - sessionId: 같은 세션 묶음 식별
 * - qrCodeKey: 즉시 QR 발급에 사용
 * - videoUrl: 영상 다운로드 경로 (Nginx /videos 매핑)
 * 등을 활용한다.
 */
@Getter
@Builder
public class GameLogResponse {

    private Long id;
    private String sessionId;
    private Boolean isSuccess;
    private String qrCodeKey;
    private String videoUrl;
    private LocalDateTime createdAt;

    /** 엔티티 + 다운로드 URL 로 응답 객체를 빌드하는 헬퍼. */
    public static GameLogResponse from(GameLog log, String videoUrl) {
        return GameLogResponse.builder()
                .id(log.getId())
                .sessionId(log.getSessionId())
                .isSuccess(log.getIsSuccess())
                .qrCodeKey(log.getQrCodeKey())
                .videoUrl(videoUrl)
                .createdAt(log.getCreatedAt())
                .build();
    }
}
