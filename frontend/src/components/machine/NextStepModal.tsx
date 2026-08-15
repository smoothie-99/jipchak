import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useToolStore } from '@/store/toolStore';
import { useAudio } from '@/hooks/useAudio';
import { SOUND_ASSETS } from '@/constants/soundConfig';

const AUTO_RESET_SECONDS = 30;

/**
 * NextStepModal
 * 크레파스 테마와 컨벤션을 준수하는 적응형 세션 확인창.
 */
const NextStepModal = () => {
  const { isAskingNextStep, setAskingNextStep, handleQRConsent, records, resetSession } = useToolStore();
  const [countdown, setCountdown] = useState(AUTO_RESET_SECONDS);
  const { playSfx } = useAudio();

  useEffect(() => {
    if (!isAskingNextStep) {
      setCountdown(AUTO_RESET_SECONDS);
      return;
    }

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          resetSession();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isAskingNextStep, resetSession]);

  const handleEndSession = async () => {
    setAskingNextStep(false);
    await handleQRConsent(true);
  };

  const handleContinue = () => {
    playSfx(SOUND_ASSETS.SFX.BUTTON_CLICK);
    setAskingNextStep(false);
  };

  return (
    <AnimatePresence>
      {isAskingNextStep && (
        <div className="absolute inset-0 z-modal flex items-center justify-center p-[5%] pointer-events-none font-crayon">
          {/* 배경 오버레이 제거됨 (다른 영역 조작 허용) */}

          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="relative w-full max-w-[440px] bg-crayon-bg rounded-[2.5vw] shadow-2xl p-[clamp(24px,6vw,48px)] border-[clamp(4px,0.8vw,8px)] border-crayon-line flex flex-col items-center pointer-events-auto"
          >
            <div className="text-center mb-[clamp(20px,4vw,32px)] w-full">
              <h2 className="text-[clamp(28px,4.5vw,40px)] font-black text-crayon-line mb-[clamp(10px,1.8vw,14px)] whitespace-nowrap tracking-tighter break-keep">
                한 판 더 하시겠어요?
              </h2>
              <p className="text-[clamp(18px,2.6vw,24px)] text-gray-700 font-bold mb-[clamp(4px,0.8vw,8px)] break-keep">
                지금까지 <span className="text-yellow-500">{records.length}개</span>의 영상이 저장되었습니다.
              </p>
              <p className="text-[clamp(14px,1.8vw,18px)] text-gray-400 font-medium break-keep">
                스타트 버튼을 눌러도 계속할 수 있어요!
              </p>
            </div>

            <div className="flex flex-col w-full gap-[clamp(8px,1.5vw,16px)]">
              <button
                onClick={handleContinue}
                className="w-full py-[clamp(12px,2.2vw,20px)] bg-yellow-400 text-gray-800 rounded-[1.2vw] font-black text-[clamp(22px,2.8vw,28px)] shadow-lg border-b-[clamp(3px,0.4vw,6px)] border-yellow-600 active:border-b-0 active:translate-y-[2px] transition-all"
              >
                네! 더 할래요
              </button>

              <button
                onClick={handleEndSession}
                className="w-full py-[clamp(10px,1.8vw,16px)] bg-white/50 text-gray-400 rounded-[1vw] font-bold text-[clamp(16px,2vw,22px)] hover:bg-white/80 transition-colors border border-gray-200"
              >
                그만하고 영상 받기
              </button>
            </div>

            {/* 자동 종료 안내 게이지 (크레파스 테마 적용) */}
            <div className="mt-[clamp(20px,4vw,32px)] flex flex-col items-center gap-[clamp(4px,0.8vw,8px)] w-full">
              <div className="w-full h-[clamp(6px,1vw,10px)] bg-white/40 rounded-full overflow-hidden max-w-[240px] border border-crayon-line/10">
                <motion.div 
                  className="h-full bg-red-400"
                  initial={{ width: '100%' }}
                  animate={{ width: `${(countdown / AUTO_RESET_SECONDS) * 100}%` }}
                  transition={{ duration: 1, ease: 'linear' }}
                />
              </div>
              <p className="text-[clamp(12px,1.5vw,15px)] text-red-400 font-black uppercase tracking-widest break-keep text-center w-full">
                {countdown}초 후 세션이 자동 종료됩니다
              </p>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default NextStepModal;
