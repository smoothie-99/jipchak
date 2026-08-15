package com.jipchak.server.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.jipchak.server.dto.SessionVideoDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

@Slf4j
@RestController
@RequestMapping("/api/session")
@RequiredArgsConstructor
public class SessionController {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    @GetMapping("/{sessionId}/videos")
    public ResponseEntity<Map<String, Object>> getSessionVideos(@PathVariable String sessionId) {
        String redisKey = "session:" + sessionId;
        Boolean exists = redisTemplate.hasKey(redisKey);
        if (exists == null || !exists) {
            return ResponseEntity.notFound().build();
        }

        Long ttl = redisTemplate.getExpire(redisKey, TimeUnit.SECONDS);
        if (ttl == null || ttl < 0) {
            ttl = 0L;
        }

        List<String> jsonStrings = redisTemplate.opsForList().range(redisKey, 0, -1);
        List<SessionVideoDto> videos = new ArrayList<>();

        if (jsonStrings != null) {
            for (String json : jsonStrings) {
                try {
                    SessionVideoDto dto = objectMapper.readValue(json, SessionVideoDto.class);
                    videos.add(dto);
                } catch (JsonProcessingException e) {
                    log.error("Failed to parse SessionVideoDto from Redis: {}", e.getMessage());
                }
            }
        }

        return ResponseEntity.ok(Map.of(
            "timeLeft", ttl,
            "videos", videos
        ));
    }

    @PostMapping("/qr")
    public ResponseEntity<Map<String, String>> generateSessionQr(@RequestBody Map<String, String> request) {
        String sessionId = request.get("sessionId");

        // HashRouter를 사용하므로 /#/m/{sessionId} 형태로 URL 생성
        String qrUrl = "https://k14d108.p.ssafy.io/#/m/" + sessionId;

        return ResponseEntity.ok(Map.of("qrUrl", qrUrl));
    }
}
