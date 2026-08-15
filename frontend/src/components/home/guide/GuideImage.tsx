import { useState, useEffect } from 'react';

interface GuideImageProps {
  step: string;
}

/**
 * GuideImage
 * 사용 가이드 모달에서 이미지가 표시됩니다.
 * 해당 단계의 이미지가 없을 경우 플레이스홀더를 보여줍니다.
 */
const GuideImage = ({ step }: GuideImageProps) => {
  const [hasError, setHasError] = useState(false);

  // 단계가 바뀔 때마다 에러 상태 초기화
  useEffect(() => {
    setHasError(false);
  }, [step]);

  // 이미지 경로 설정 (src/assets/images/guide/guide-{step}.png)
  const imageUrl = new URL(`../../../assets/images/guide/guide-${step}.png`, import.meta.url).href;

  if (hasError) {
    return (
      <div className="shrink-0 w-[clamp(260px,62%,520px)] h-full rounded-[1.2vw] bg-gray-200 border-[clamp(2px,0.3vw,4px)] border-gray-300 flex flex-col items-center justify-center gap-[1vh] px-[clamp(8px,1vw,12px)]">
        <span className="text-[clamp(28px,3.6vw,46px)] text-gray-400 select-none">🖼</span>
        <span className="text-[clamp(11px,1.2vw,14px)] font-semibold text-gray-400 select-none text-center">
          이미지 준비 중
        </span>
      </div>
    );
  }

  return (
    <div className="shrink-0 w-[clamp(260px,62%,520px)] h-full rounded-[1.2vw] bg-white border-[clamp(2px,0.3vw,4px)] border-gray-300 overflow-hidden flex items-center justify-center">
      <img
        src={imageUrl}
        alt={`가이드 단계 ${step}`}
        className="w-full h-full object-contain"
        onError={() => setHasError(true)}
      />
    </div>
  );
};

export default GuideImage;
