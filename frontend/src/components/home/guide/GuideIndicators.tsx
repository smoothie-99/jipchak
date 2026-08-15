interface GuideIndicatorsProps {
  count: number;
  currentIndex: number;
  onSelect: (index: number) => void;
}

/**
 * GuideIndicators
 * 사용 가이드 모달의 슬라이드 인디케이터입니다.
 */
const GuideIndicators = ({ count, currentIndex, onSelect }: GuideIndicatorsProps) => {
  return (
    <div className="shrink-0 mt-[clamp(10px,1.4vh,16px)] flex items-center justify-center gap-[clamp(8px,1.2vw,14px)]">
      {Array.from({ length: count }).map((_, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onSelect(i)}
          className={`rounded-full transition-all active:scale-90 ${
            i === currentIndex
              ? 'w-[clamp(20px,2.8vw,32px)] h-[clamp(8px,1.1vw,12px)] bg-crayon-line'
              : 'w-[clamp(8px,1.1vw,12px)] h-[clamp(8px,1.1vw,12px)] bg-gray-300'
          }`}
          aria-label={`${i + 1}번 슬라이드로 이동`}
        />
      ))}
    </div>
  );
};

export default GuideIndicators;
