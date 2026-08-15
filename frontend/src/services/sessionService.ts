import axios from 'axios';

/**
 * sessionService.ts
 * 세션 관리 및 QR 생성, 영상 조회 관련 API 서비스
 */

// 로컬 환경(localhost)에서는 8108 포트로 직접 요청하고, 운영 서버에서는 nginx 라우팅을 위해 상대 경로 사용
const API_BASE = import.meta.env.VITE_API_BASE_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8108' : '');

export const sessionService = {
  /**
   * 사용자가 QR 생성을 거부했을 때 세션 삭제 (추후 백엔드 API 필요 시 구현)
   */
  deleteSessionVideos: async (): Promise<void> => {
    // 백엔드 구현에 따라 실제 API 호출로 변경 가능
    console.log('[API] 세션 삭제 요청됨');
  },

  /**
   * QR 생성을 요청하여 모바일 페이지 URL을 반환
   */
  generateSessionQr: async (sessionId: string): Promise<string> => {
    try {
      const response = await axios.post(`${API_BASE}/api/session/qr`, { sessionId });
      return response.data.qrUrl;
    } catch (error) {
      console.error('QR 생성 실패:', error);
      throw error;
    }
  },

  /**
   * 특정 세션의 영상 목록 조회
   */
  getSessionVideos: async (sessionId: string): Promise<any> => {
    try {
      const response = await axios.get(`${API_BASE}/api/session/${sessionId}/videos`);
      return response.data;
    } catch (error) {
      console.error('영상 목록 조회 실패:', error);
      throw error;
    }
  }
};
