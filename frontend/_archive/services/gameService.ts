import axiosInstance from '@/utils/axios';

export interface GameLogRequest {
  isSuccess: boolean;
  video: File;
}

const gameService = {
  /**
   * 게임 로그 및 비디오 업로드
   * @param data { isSuccess, video }
   */
  createGameLog: async (data: GameLogRequest) => {
    const formData = new FormData();
    formData.append('isSuccess', String(data.isSuccess));
    formData.append('video', data.video);

    const response = await axiosInstance.post('/api/game/log', formData);
    return response.data;
  },

  /**
   * 홈 화면 환영 메시지 확인
   */
  getHomeMessage: async () => {
    const response = await axiosInstance.get('/api/home');
    return response.data;
  },
};

export default gameService;
