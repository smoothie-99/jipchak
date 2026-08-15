import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStreamStore, StreamState } from '@/store/streamStore';
import { useToolStore } from '@/store/toolStore';

/**
 * GameCountModal
 *
 * /play 진입 직후 표시. 사용자가 한 세션에서 진행할 판수 (1 / 3 / 5) 선택.
 *
 * 입력 방식:
 *   - 마우스 클릭: 옵션 직접 선택
 *   - 아두이노 조이스틱 좌/우: 옵션 순환 (lastUiEvent.type === 'JOY_LEFT'|'JOY_RIGHT')
 *   - 아두이노 파랑(MAIN): 선택 확정 → Arduino 가 READY → PLAYING 진입 → SESSION_START 도착 시 모달 닫음
 *   - 아두이노 빨강(SUB): 'BACK_TO_HOME' 이벤트 → 메인 페이지로 navigate (Home/PlayGround 가드에서 처리)
 *
 * 마우스 클릭으로 옵션 선택 후엔 "파랑 버튼 또는 클릭으로 시작" 안내 표시.
 * 선택만으로 시작 안 함 — Arduino state 전이 (READY→PLAYING) 가 일어나야 SESSION_START 가 도착하고 게임 진행.
 */
const OPTIONS = [1, 3, 5] as const;

interface GameCountModalProps {
  isOpen: boolean;
  onConfirm: (count: number) => void;
}

const GameCountModal = ({ isOpen, onConfirm }: GameCountModalProps) => {
  const lastUiEvent = useStreamStore((s: StreamState) => s.lastUiEvent);
  const lastSessionEvent = useStreamStore((s: StreamState) => s.lastSessionEvent);
  const setMaxGames = useToolStore((s) => s.setMaxGames);

  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const lastJoyTs = useRef<number | null>(null);

  // 조이스틱 좌/우 → 옵션 순환
  useEffect(() => {
    if (!isOpen || !lastUiEvent) return;
    if (lastJoyTs.current === lastUiEvent.ts) return;

    if (lastUiEvent.type === 'JOY_LEFT') {
      lastJoyTs.current = lastUiEvent.ts;
      setSelectedIndex((i) => (i - 1 + OPTIONS.length) % OPTIONS.length);
    } else if (lastUiEvent.type === 'JOY_RIGHT') {
      lastJoyTs.current = lastUiEvent.ts;
      setSelectedIndex((i) => (i + 1) % OPTIONS.length);
    }
  }, [lastUiEvent, isOpen]);

  // SESSION_START 도착 = Arduino 가 PLAYING 진입 = 사용자가 파랑(시작) 누름
  // → maxGames 확정 + 모달 닫음
  useEffect(() => {
    if (!isOpen) return;
    if (lastSessionEvent?.type !== 'SESSION_START') return;
    const count = OPTIONS[selectedIndex];
    setMaxGames(count);
    onConfirm(count);
  }, [lastSessionEvent, isOpen, selectedIndex, setMaxGames, onConfirm]);

  const handleClick = (i: number) => {
    setSelectedIndex(i);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="absolute inset-0 z-modal flex items-center justify-center p-[5%] font-crayon pointer-events-none">
          <div className="absolute inset-0 bg-black/40 pointer-events-none" />
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="relative w-full max-w-[540px] bg-crayon-bg rounded-[2.5vw] shadow-2xl p-[clamp(24px,6vw,48px)] border-[clamp(4px,0.8vw,8px)] border-crayon-line flex flex-col items-center pointer-events-auto"
          >
            <h2 className="text-[clamp(24px,4vw,40px)] font-black text-crayon-line mb-[clamp(8px,1.5vw,12px)] break-keep">
              몇 판 하시겠어요?
            </h2>
            <p className="text-[clamp(14px,1.8vw,18px)] text-gray-500 font-bold mb-[clamp(20px,4vw,32px)] break-keep">
              조이스틱 좌/우 또는 클릭으로 선택
            </p>

            <div className="flex w-full justify-around gap-[clamp(8px,1.5vw,16px)]">
              {OPTIONS.map((count, i) => {
                const isActive = i === selectedIndex;
                return (
                  <button
                    key={count}
                    onClick={() => handleClick(i)}
                    className={`flex-1 py-[clamp(20px,4vw,32px)] rounded-[1.2vw] font-black text-[clamp(36px,6vw,64px)] border-b-[clamp(3px,0.5vw,6px)] transition-all ${
                      isActive
                        ? 'bg-yellow-400 text-gray-800 border-yellow-600 scale-105 shadow-lg'
                        : 'bg-white/70 text-gray-400 border-gray-300'
                    }`}
                  >
                    {count}
                  </button>
                );
              })}
            </div>

            <div className="mt-[clamp(20px,4vw,32px)] text-center">
              <p className="text-[clamp(14px,2vw,20px)] text-gray-600 font-bold break-keep">
                <span className="text-blue-500">파란 버튼</span>으로 시작 ·{' '}
                <span className="text-red-500">빨간 버튼</span>으로 뒤로
              </p>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default GameCountModal;
