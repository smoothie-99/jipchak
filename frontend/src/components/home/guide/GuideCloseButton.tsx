interface GuideCloseButtonProps {
  onClick: () => void;
}

/**
 * GuideCloseButton
 * 사용 가이드 모달의 닫기 버튼입니다.
 */
const GuideCloseButton = ({ onClick }: GuideCloseButtonProps) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full bg-gray-800 px-[clamp(9px,1.2vw,14px)] text-[clamp(20px,2.8vw,34px)] font-bold text-white active:scale-95"
    >
      X
    </button>
  );
};

export default GuideCloseButton;
