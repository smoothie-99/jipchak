import { useState, useRef, useCallback } from 'react';

export const useCameraSwap = () => {
  const [isSwapped, setIsSwapped] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const swapThrottleRef = useRef<boolean>(false);

  const handleSwap = useCallback(() => {
    if (swapThrottleRef.current) return;
    swapThrottleRef.current = true;
    
    // 깜빡임 애니메이션 시작
    setIsTransitioning(true);
    
    // 화면이 가려진 중간 시점에 스왑 처리
    setTimeout(() => {
      setIsSwapped((prev) => !prev);
    }, 150);

    // 애니메이션 종료 후 화면 복구
    setTimeout(() => {
      setIsTransitioning(false);
    }, 500);

    // 1초 쿨다운 후 다시 스왑 가능하도록 해제
    setTimeout(() => {
      swapThrottleRef.current = false;
    }, 1000);
  }, []);

  return { isSwapped, isTransitioning, handleSwap };
};
