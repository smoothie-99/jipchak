import { useState, useEffect } from 'react';
import { useToolStore } from '@/store/toolStore';
import CrayonWrapper from '../common/CrayonWrapper';
import { useAudio } from '@/hooks/useAudio';
import { SOUND_ASSETS } from '@/constants/soundConfig';

const AUTO_RESET_SECONDS = 30;

/**
 * QRConsent 컴포넌트
 * 게임 5회 종료 후 사용자의 동영상 다운로드 QR 생성 동의를 구합니다.
 */
const QRConsent = () => {
  const { handleQRConsent, records, resetSession } = useToolStore();
  const [countdown, setCountdown] = useState(AUTO_RESET_SECONDS);
  const { playVoice } = useAudio();

  // 안내 음성 재생 및 자동 종료 타이머
  useEffect(() => {
    // playVoice 는 cleanup 함수를 반환한다. 컴포넌트 언마운트 시 음성도 같이 정지.
    const stopVoice = playVoice(SOUND_ASSETS.VOICE.QR_AGREE);

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          resetSession(); // 시간 만료 시 세션 파기
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      clearInterval(timer);
      stopVoice();
    };
  }, [resetSession, playVoice]);

  return (
    <CrayonWrapper showCharacter={false} className="justify-around items-center gap-[4%]">
      <div className="flex flex-col items-center w-full">
        <h3 className="text-[clamp(18px,2.6vw,26px)] font-bold text-gray-800 text-center leading-tight break-keep">
          총 <span className="text-yellow-500">{records.length}개</span>의 영상이 저장되었습니다.<br />
          영상을 받으러 가시겠습니까?
        </h3>
        <p className="text-[clamp(13px,1.5vw,16px)] text-gray-600 text-center mt-2 break-keep">
          거절 시 현재 세션의 영상들은 삭제됩니다.
        </p>
      </div>

      <div className="flex w-full px-[5%] gap-[5%]">
        {/* 아니오 버튼 (거절 -> 삭제 및 초기화) */}
        <button
          onClick={() => handleQRConsent(false)}
          className="flex-1 py-[clamp(10px,1.2vw,18px)] bg-gray-200 text-gray-600 rounded-[255px_15px_225px_15px/15px_225px_15px_255px] font-bold shadow-md border-[clamp(1px,0.2vw,2px)] border-gray-400 active:scale-95 transition-transform text-[clamp(14px,1.8vw,18px)]"
        >
          아니오
        </button>

        {/* 네! 버튼 (수락 -> QR 생성) */}
        <button
          onClick={() => handleQRConsent(true)}
          className="flex-1 py-[clamp(10px,1.2vw,18px)] bg-yellow-400 text-gray-800 rounded-[15px_225px_15px_255px/255px_15px_225px_15px] font-bold shadow-lg border-[clamp(1px,0.2vw,2px)] border-yellow-600 active:scale-95 transition-transform text-[clamp(14px,1.8vw,18px)]"
        >
          네!
        </button>
      </div>

      {/* 카운트다운 표시 */}
      <p className="text-[clamp(11px,1.3vw,14px)] text-red-400 font-bold break-keep text-center w-full">
        <span className="animate-pulse">{countdown}</span>초 후 자동으로 종료됩니다.
      </p>
    </CrayonWrapper>
  );
};

export default QRConsent;
