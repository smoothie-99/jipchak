import Button from '@/components/common/Button';


type GuideButtonProps = {
  onClick: () => void;
  className?: string;
};


/**
 * GuideButton
 * 홈 화면에서 사용 가이드를 열기 위한 버튼입니다.
 */
const GuideButton = ({ onClick, className }: GuideButtonProps) => {
  return (
    <Button label="GUIDE" onClick={onClick} ariaLabel="GUIDE" className={className} />
  );
};

export default GuideButton;
