import { useEffect } from 'react';
import { motion, useMotionValue, useTransform, animate } from 'framer-motion';

interface ThermometerProps {
  probability: number; // 0 ~ 100
}

/**
 * Thermometer (Bar Type)
 * 기존 온도계 구슬을 제거하고 평범한 수직 막대(Progress Bar) 형태로 리디자인된 버전
 * 기존 애니메이션 및 색상 변화 기능은 유지
 */
const Thermometer = ({ probability }: ThermometerProps) => {
  const animatedValue = useMotionValue(0);

  useEffect(() => {
    const controls = animate(animatedValue, probability, {
      type: 'spring',
      stiffness: 60,
      damping: 15,
      mass: 1,
    });
    return controls.stop;
  }, [probability, animatedValue]);

  // 확률 100%일 때, 온도계 막대의 최대 높이를 90% 지점까지만 채우도록 설정 (백분율 분할)
  const heightPercent = useTransform(animatedValue, [0, 100], ['0%', '90%']);

  const fluidColor = useTransform(
    animatedValue,
    [0, 30, 60, 90],
    ['#3b82f6', '#22c55e', '#eab308', '#ef4444']
  );

  // 컨벤션에 따른 유동적 사이즈
  const glassBorderWidth = "clamp(2.5px,0.4vw,5px)";
  const liquidInset = "clamp(3px,0.4vw,6px)";

  return (
    <div
      className="absolute right-4 bottom-[4%] h-[92%] w-[clamp(30px,4vw,60px)] z-overlay pointer-events-none select-none drop-shadow-lg flex flex-col items-center"
      onContextMenu={(e) => e.preventDefault()} // [컨벤션 147] 우클릭 방지
    >
      <span className="font-bold text-center text-[clamp(15px,2.1vw,24px)] mb-1 select-none [text-shadow:clamp(1px,0.2vw,2.5px)_clamp(1px,0.2vw,2.5px)_0_#1f2937,_-clamp(0.5px,0.15vw,2px)_-clamp(0.5px,0.15vw,2px)_0_#1f2937,clamp(0.5px,0.15vw,2px)_-clamp(0.5px,0.15vw,2px)_0_#1f2937,_-clamp(0.5px,0.15vw,2px)_clamp(0.5px,0.15vw,2px)_0_#1f2937]">
        게이지
      </span>
      {/* 1. 기둥 (Bar) */}
      <div
        className="relative flex-1 w-full bg-white rounded-full border-crayon-line overflow-hidden"
        style={{
          borderWidth: glassBorderWidth,
        }}
      >
        {/* 기둥 내부 액체 */}
        <div
          className="absolute z-10"
          style={{
            top: liquidInset,
            left: liquidInset,
            right: liquidInset,
            bottom: liquidInset,
          }}
        >
          <motion.div
            className="absolute left-0 right-0 bottom-0 rounded-full origin-bottom"
            style={{ height: heightPercent, backgroundColor: fluidColor }}
          />
        </div>
      </div>
    </div>
  );
};

export default Thermometer;

