import { motion, AnimatePresence } from 'framer-motion';
import { useAudioStore } from '@/store/audioStore';

const SettingsModal = () => {
  const {
    isSettingsOpen,
    setSettingsOpen,
    bgmVolume,
    setBgmVolume,
    sfxVolume,
    setSfxVolume,
    voiceVolume,
    setVoiceVolume
  } = useAudioStore();

  if (!isSettingsOpen) return null;

  return (
    <AnimatePresence>
      <div
        className="absolute inset-0 z-modal flex items-center justify-center p-[5%] font-crayon"
        // 모달 바깥쪽을 클릭하면 닫히도록 설정. 내부 클릭은 전파를 막아 모달 유지.
        onClick={() => setSettingsOpen(false)}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.9, opacity: 0, y: 20 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-[440px] max-h-[90vh] overflow-y-auto bg-crayon-bg rounded-[2.5vw] shadow-2xl py-[clamp(16px,3vh,32px)] px-[clamp(20px,5vw,40px)] border-[clamp(4px,0.8vw,8px)] border-crayon-line flex flex-col items-center pointer-events-auto"
        >
          {/* 타이틀 및 닫기 버튼 영역 */}
          <div className="w-full flex justify-between items-center mb-[clamp(12px,2vh,20px)] border-b-[clamp(2px,0.4vw,4px)] border-crayon-line pb-[clamp(6px,1vh,10px)]">
            <h2 className="text-[clamp(20px,3.5vw,28px)] font-black text-crayon-line tracking-tighter select-none break-keep">
              소리 설정
            </h2>
            <button
              onClick={() => setSettingsOpen(false)}
              className="text-gray-400 active:scale-90 transition-transform flex items-center justify-center p-[1vw] -mr-[1vw]"
            >
              <svg className="w-[clamp(20px,3.5vw,32px)] h-[clamp(20px,3.5vw,32px)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* 슬라이더 영역 */}
          <div className="w-full flex flex-col gap-[clamp(12px,2.5vh,20px)] w-full">
            <VolumeSlider
              label="배경음 (BGM)"
              value={bgmVolume}
              onChange={setBgmVolume}
              colorClass="accent-blue-500"
            />
            <VolumeSlider
              label="효과음 (SFX)"
              value={sfxVolume}
              onChange={setSfxVolume}
              colorClass="accent-yellow-500"
            />
            <VolumeSlider
              label="안내음 (Voice)"
              value={voiceVolume}
              onChange={setVoiceVolume}
              colorClass="accent-pink-500"
            />
          </div>

        </motion.div>
      </div>
    </AnimatePresence>
  );
};

// 재사용을 위한 슬라이더 하위 컴포넌트
interface VolumeSliderProps {
  label: string;
  value: number;
  onChange: (val: number) => void;
  colorClass: string;
}

const VolumeSlider = ({ label, value, onChange, colorClass }: VolumeSliderProps) => {
  return (
    <div className="flex flex-col w-full gap-[clamp(8px,1.5vw,12px)]">
      {/* 1. 라벨 & N% 수치 (더 크고 진하게) */}
      <div className="flex justify-between items-end w-full select-none">
        <span className="text-[clamp(16px,2.5vw,22px)] font-bold text-gray-800 break-keep">
          {label}
        </span>
        <span className="text-[clamp(18px,2.8vw,24px)] font-black text-gray-800 tracking-wider">
          {value}%
        </span>
      </div>

      {/* 2. 슬라이더 & 음소거 토글 박스 (가로 배치) */}
      <div className="flex items-center gap-[clamp(16px,2.5vw,24px)] w-full">
        {/* 슬라이더 (남은 공간 차지) */}
        <input
          type="range"
          min="0"
          max="100"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className={`flex-1 h-[clamp(12px,1.8vw,20px)] bg-gray-200 rounded-full appearance-none cursor-pointer shadow-inner outline-none ${colorClass}`}
          style={{
            WebkitAppearance: 'none',
          }}
        />

        {/* 음소거 체크박스 버튼 (슬라이더 우측 배치) */}
        <button
          onClick={() => onChange(value === 0 ? 50 : 0)}
          aria-label="음소거 토글"
          className="flex items-center gap-[clamp(6px,1vw,10px)] active:scale-95 transition-all outline-none group"
        >
          {/* 체크박스 사각형 (흑백 대비 테마) */}
          <div className={`flex items-center justify-center w-[clamp(26px,4vw,36px)] h-[clamp(26px,4vw,36px)] border-[clamp(2.5px,0.4vw,4px)] rounded-[0.6vw] shadow-sm transition-colors ${
            value === 0 
              ? 'bg-gray-800 border-gray-800 text-white' 
              : 'bg-white border-gray-400 text-transparent group-active:bg-gray-100'
          }`}>
            <svg className="w-[80%] h-[80%]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={4}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          {/* '음소거' 텍스트 */}
          <span className={`text-[clamp(14px,2.2vw,20px)] font-black break-keep transition-colors ${
            value === 0 ? 'text-gray-800' : 'text-gray-500 group-active:text-gray-700'
          }`}>
            음소거
          </span>
        </button>
      </div>

      {/* Thumb(슬라이더 핸들)을 7인치 터치에 맞게 조금 더 크게 조절 */}
      <style>{`
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: clamp(24px, 4vw, 36px);
          height: clamp(24px, 4vw, 36px);
          border-radius: 50%;
          background: #fff;
          border: clamp(2.5px, 0.4vw, 4px) solid currentColor;
          cursor: pointer;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
        }
      `}</style>
    </div>
  );
};

export default SettingsModal;
