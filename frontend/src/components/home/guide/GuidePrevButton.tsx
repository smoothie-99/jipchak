interface GuidePrevButtonProps {
  onClick: () => void;
}

/**
 * GuidePrevButton
 * 사용 가이드 모달의 이전 버튼입니다.
 */
const GuidePrevButton = ({ onClick }: GuidePrevButtonProps) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute left-[var(--guide-btn-offset)] top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 rounded-full bg-gray-800/90 text-white font-bold transition-transform duration-150 ease-out active:scale-90 flex items-center justify-center w-[clamp(30px,3.8vw,44px)] h-[clamp(30px,3.8vw,44px)] text-[clamp(20px,2.8vw,34px)]"
      aria-label="이전 슬라이드"
    >
      ‹
    </button>
  );
};

export default GuidePrevButton;
