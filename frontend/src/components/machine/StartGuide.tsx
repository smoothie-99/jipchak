import { motion } from 'framer-motion';
import { useStreamStore, StreamState } from '@/store/streamStore';

/**
 * StartGuide
 *
 * 카메라 영역 위에 떠 있는 안내 문구. PlayGround 의 게임 흐름 단계에 따라
 * 3 가지 메시지로 분기된다:
 *
 *   1) CAM_OFF   : 캠 OFF (frame 없음, lastSessionEvent 없거나 SESSION_END)
 *                 → "파란 버튼을 누르면 캠이 켜집니다" (점멸 X)
 *   2) READY     : 캠 ON, 아직 게임 시작 전 (frame 있음, SESSION_START 미수신)
 *                 → "게임 시작을 위해 파란색 버튼을 눌러주세요" (점멸 O)
 *   3) POST_GAME : 한 판 종료 직후 (lastSessionEvent.type === 'GAME_RESULT')
 *                 → "다음 판: 파란 / 종료: 빨강" (점멸 O)
 *
 * PLAYING (집기 시퀀스 포함) 단계의 카운트다운은 별도 <PlayingTimer /> 가 담당.
 */
type Stage = 'CAM_OFF' | 'READY' | 'POST_GAME';

function useStage(): Stage {
  const frame2d = useStreamStore((s: StreamState) => s.frame2d);
  const frame3d = useStreamStore((s: StreamState) => s.frame3d);
  const lastSessionEvent = useStreamStore((s: StreamState) => s.lastSessionEvent);

  if (lastSessionEvent?.type === 'GAME_RESULT') return 'POST_GAME';
  if (!frame2d && !frame3d) return 'CAM_OFF';
  return 'READY';
}

const StartGuide = () => {
  const stage = useStage();

  if (stage === 'CAM_OFF') return null;
  if (stage === 'POST_GAME') return <PostGameGuide />;
  return <ReadyGuide />;
};


// ─────────────────────────────────────────
// 2) READY — 점멸 + 화살표
// ─────────────────────────────────────────
const ReadyGuide = () => (
  <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-sub">
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: [0, 1, 1, 0] }}
      transition={{ duration: 1.5, repeat: Infinity, times: [0, 0.2, 0.8, 1], ease: 'easeInOut' }}
      className="flex flex-col items-center gap-[1vh]"
    >
      <div className="relative">
        <span className="absolute inset-0 text-white font-crayon text-[clamp(24px,4.5vw,48px)] font-black select-none text-center break-keep leading-tight opacity-20 blur-[2px]">
          게임 시작을 위해<br />파란색 버튼을 눌러주세요!
        </span>
        <h2 className="relative text-white font-crayon text-[clamp(24px,4.5vw,48px)] font-black select-none text-center break-keep leading-tight drop-shadow-[0_4px_4px_rgba(0,0,0,0.5)]">
          게임 시작을 위해<br />
          <span className="text-blue-500 [text-shadow:2px_2px_0_#fff,-2px_-2px_0_#fff,2px_-2px_0_#fff,-2px_2px_0_#fff]">파란색 버튼</span>을 눌러주세요!
        </h2>
      </div>
      <div className="flex gap-[1vw] mt-[1vh]">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            animate={{ y: [0, 5, 0] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
            className="w-[1vw] h-[1vw] min-w-[10px] min-h-[10px] bg-blue-500 rounded-full border-2 border-white shadow-sm"
          />
        ))}
      </div>
    </motion.div>
  </div>
);

// ─────────────────────────────────────────
// 3) POST_GAME — 다음판 / 종료 분기 안내
// ─────────────────────────────────────────
const PostGameGuide = () => (
  <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-sub">
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: [0, 1, 1, 0] }}
      transition={{ duration: 1.8, repeat: Infinity, times: [0, 0.2, 0.8, 1], ease: 'easeInOut' }}
      className="flex flex-col items-center gap-[1.2vh]"
    >
      <h2 className="text-white font-crayon text-[clamp(20px,3.6vw,40px)] font-black text-center break-keep leading-tight drop-shadow-[0_4px_4px_rgba(0,0,0,0.5)]">
        한 판 끝!
      </h2>
      <div className="flex flex-col gap-[0.6vh] text-[clamp(18px,3vw,32px)] font-crayon font-black text-white drop-shadow-[0_2px_3px_rgba(0,0,0,0.7)]">
        <p>
          <span className="text-blue-500 [text-shadow:2px_2px_0_#fff,-2px_-2px_0_#fff,2px_-2px_0_#fff,-2px_2px_0_#fff]">파란색</span> = 한 판 더
        </p>
        <p>
          <span className="text-red-500 [text-shadow:2px_2px_0_#fff,-2px_-2px_0_#fff,2px_-2px_0_#fff,-2px_2px_0_#fff]">빨간색</span> = 그만하기
        </p>
      </div>
    </motion.div>
  </div>
);

export default StartGuide;
