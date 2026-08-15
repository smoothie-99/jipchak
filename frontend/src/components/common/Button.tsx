import { useState } from 'react';
import { motion, useAnimationControls } from 'framer-motion';
import CrayonWrapper from './CrayonWrapper';

interface ButtonProps {
  label: string;
  onClick: () => void;
  className?: string;
  ariaLabel?: string;
}

/**
 * Button
 * 크레용 스타일 + 애니메이션이 적용된 공통 버튼
 */
const Button = ({ label, onClick, className, ariaLabel }: ButtonProps) => {
  const animationControls = useAnimationControls();
  const [isAnimating, setIsAnimating] = useState(false);

  const handleClick = async () => {
    if (isAnimating) return;
    setIsAnimating(true);
    try {
      await animationControls.start({
        scale: 0.9,
        transition: { duration: 0.12, ease: 'easeOut' },
      });
      await animationControls.start({
        scale: 1,
        transition: { duration: 0.16, ease: 'easeOut' },
      });
      onClick();
    } finally {
      setIsAnimating(false);
    }
  };

  const defaultStyle =
    'min-w-[28%] max-w-[48%] min-h-[13vh] drop-shadow-lg cursor-pointer appearance-none bg-transparent border-none p-0 outline-none';

  return (
    <motion.button
      type="button"
      aria-label={ariaLabel || label}
      onClick={handleClick}
      animate={animationControls}
      className={className ? `${defaultStyle} ${className}` : defaultStyle}
    >
      <CrayonWrapper showCharacter={false}>
        <span className="flex items-center justify-center w-full h-full font-black tracking-[0.08em] text-[clamp(28px,3.4vw,44px)]">
          {label}
        </span>
      </CrayonWrapper>
    </motion.button>
  );
};

export default Button;
