package com.jipchak.server.controller;

import com.jipchak.server.dto.GameLogResponse;
import com.jipchak.server.service.GameLogService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

/**
 * 게임 로그 REST 엔드포인트.
 *
 * 호출자: AI 서버(FastAPI). 한 게임 종료 시 영상과 함께 결과를 POST.
 * 응답: 항상 JSON (GameLogResponse). 에러는 GlobalExceptionHandler 가 일괄 처리.
 */
@RestController
@RequestMapping("/api/game")
@RequiredArgsConstructor
public class GameLogController {

    private final GameLogService gameLogService;

    @PostMapping("/log")
    public ResponseEntity<Long> createGameLog(
            // sessionId 는 AI 서버가 발급한 세션 식별자. 없으면 anon 으로 처리.
            @RequestParam(value = "sessionId", required = false) String sessionId,
            @RequestParam("isSuccess") Boolean isSuccess,
            @RequestParam("video") MultipartFile video) throws IOException {
        Long savedId = gameLogService.saveGameLog(sessionId, isSuccess, video);
        return ResponseEntity.status(HttpStatus.CREATED).body(savedId);
    }
}
