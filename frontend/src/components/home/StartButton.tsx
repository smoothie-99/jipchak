import { useEffect } from 'react';
import Button from '@/components/common/Button';

type StartButtonProps = {
  onStart: () => void;
  autoClick?: boolean;
};

/**
 * StartButton
 * 홈 화면에서 플레이 시작을 위한 버튼입니다.
 * 클릭 시 플레이 페이지로 이동합니다.
 */
const StartButton = ({ onStart, autoClick }: StartButtonProps) => {
  // autoClick 지원만 별도 유지
  const handleStartClick = onStart;
  // autoClick이 true면 600ms 후 자동 클릭
  useEffect(() => {
    if (autoClick) {
      const timer = setTimeout(() => {
        handleStartClick();
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [autoClick]);

  return (
    <Button label="START" onClick={handleStartClick} ariaLabel="START" />
  );
};

export default StartButton;
