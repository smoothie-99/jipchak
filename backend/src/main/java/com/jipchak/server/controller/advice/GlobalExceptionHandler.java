package com.jipchak.server.controller.advice;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.MultipartException;

import java.io.IOException;
import java.time.Instant;
import java.util.Map;

/**
 * 전역 예외 처리.
 *
 * 기존에는 GameLogController 가 try/catch (Exception e) 로 모든 에러를
 * 500 + 한국어 평문으로 돌려주었다. 이제 모든 응답을 JSON 으로 통일하고
 * 에러 종류에 따라 적절한 상태 코드를 분리한다.
 *
 * 응답 포맷:
 * { "timestamp": "...", "status": 400, "error": "Bad Request", "message": "..." }
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /** 필수 파라미터 누락 → 400 */
    @ExceptionHandler(MissingServletRequestParameterException.class)
    public ResponseEntity<Map<String, Object>> handleMissingParam(MissingServletRequestParameterException e) {
        return build(HttpStatus.BAD_REQUEST, "필수 파라미터 누락: " + e.getParameterName());
    }

    /** 멀티파트 업로드 크기 초과 → 413 */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<Map<String, Object>> handleUploadSize(MaxUploadSizeExceededException e) {
        return build(HttpStatus.PAYLOAD_TOO_LARGE, "업로드 크기 초과");
    }

    /** 멀티파트 일반 오류 (boundary 누락 등) → 400 */
    @ExceptionHandler(MultipartException.class)
    public ResponseEntity<Map<String, Object>> handleMultipart(MultipartException e) {
        log.warn("멀티파트 처리 실패", e);
        return build(HttpStatus.BAD_REQUEST, "멀티파트 요청 처리 실패: " + e.getMessage());
    }

    /** 디스크 IO 실패 → 500 */
    @ExceptionHandler(IOException.class)
    public ResponseEntity<Map<String, Object>> handleIO(IOException e) {
        log.error("IO 오류", e);
        return build(HttpStatus.INTERNAL_SERVER_ERROR, "파일 입출력 실패");
    }

    /** 잘못된 인자 → 400 */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArg(IllegalArgumentException e) {
        return build(HttpStatus.BAD_REQUEST, e.getMessage());
    }

    /** 그 외 예상치 못한 예외 → 500 (스택 로그는 남기고 응답엔 노출 X) */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGeneric(Exception e) {
        log.error("처리되지 않은 예외", e);
        return build(HttpStatus.INTERNAL_SERVER_ERROR, "서버 내부 오류");
    }

    private ResponseEntity<Map<String, Object>> build(HttpStatus status, String message) {
        Map<String, Object> body = Map.of(
                "timestamp", Instant.now().toString(),
                "status", status.value(),
                "error", status.getReasonPhrase(),
                "message", message
        );
        return ResponseEntity.status(status).body(body);
    }
}
