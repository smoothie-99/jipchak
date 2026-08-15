interface GuideNextButtonProps {
  onClick: () => void;
}

/**
 * GuideNextButton
 * 사용 가이드 모달의 다음 버튼입니다.
 */
const GuideNextButton = ({ onClick }: GuideNextButtonProps) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute right-[var(--guide-btn-offset)] top-1/2 translate-x-1/2 -translate-y-1/2 z-10 rounded-full bg-gray-800/90 text-white font-bold transition-transform duration-150 ease-out active:scale-90 flex items-center justify-center w-[clamp(30px,3.8vw,44px)] h-[clamp(30px,3.8vw,44px)] text-[clamp(20px,2.8vw,34px)]"
      aria-label="다음 슬라이드"
    >
      ›
    </button>
  );
};

export default GuideNextButton;
