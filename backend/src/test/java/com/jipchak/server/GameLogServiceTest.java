package com.jipchak.server;

import com.jipchak.server.service.GameLogService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@Transactional
class GameLogServiceTest {

    @Autowired
    private GameLogService gameLogService;

    @Test
    @DisplayName("게임 로그와 영상이 성공적으로 저장되어야 한다")
    void saveGameLogTest() throws Exception {
        // 1. Given: 테스트에 필요한 가짜 영상 파일 준비 (더미 데이터)
        MockMultipartFile mockVideo = new MockMultipartFile(
                "video",
                "test_video.mp4",
                "video/mp4",
                "dummy video content".getBytes());

        // 2. When: 서비스를 실행해서 로그를 저장
        Long response = gameLogService.saveGameLog("test-session", true, mockVideo);

        // 3. Then: 결과가 완벽한지 검증!
        assertThat(response).isNotNull();
        System.out.println("✅ 테스트 성공! 생성된 로그 ID: " + response);
    }
}
