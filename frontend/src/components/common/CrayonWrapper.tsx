import React from 'react';
import diaryImg from '@/assets/images/crayon_diary.png';

interface CrayonWrapperProps {
  children: React.ReactNode;
  showCharacter?: boolean;
  className?: string;
}

/**
 * CrayonWrapper
 * 자식 컴포넌트에게 크레파스 화풍 테마(배경, 테두리, 폰트)를 입혀주는 컨테이너입니다.
 */
const CrayonWrapper = ({ children, showCharacter = true, className = '' }: CrayonWrapperProps) => {
  return (
    <div
      className="w-full h-full bg-crayon-bg relative overflow-hidden rounded-[1vw] font-crayon"
    >
      {/* 크레파스 느낌의 스크래치 외곽선 (3중 레이어) */}
      <div className="absolute inset-[clamp(2px,0.5vw,6px)] border-[clamp(1px,0.4vw,4px)] border-crayon-line opacity-40 pointer-events-none rounded-[255px_15px_225px_15px/15px_225px_15px_255px] -rotate-[0.5deg]" />
      <div className="absolute inset-[clamp(2px,0.5vw,6px)] border-[clamp(1.5px,0.4vw,5px)] border-crayon-line opacity-60 pointer-events-none rounded-[15px_225px_15px_255px/255px_15px_225px_15px] rotate-[0.5deg]" />
      <div className="absolute inset-[clamp(3px,0.8vw,8px)] border-[clamp(1px,0.3vw,3px)] border-crayon-line opacity-80 pointer-events-none rounded-[225px_15px_255px_15px/15px_225px_15px_225px] -rotate-1" />

      {/* 배경 장식 (일기장 워터마크) */}
      {showCharacter && (
        <img
          src={diaryImg}
          alt="diary decoration"
          className="absolute bottom-[5%] right-[5%] h-[30%] object-contain opacity-25 pointer-events-none -rotate-12 mix-blend-multiply"
        />
      )}

      {/* 실제 콘텐츠 영역 (가로 패딩 최적화: 썸네일 크기 확보) */}
      <div className={`relative z-header w-full h-full flex flex-col px-[clamp(12px,2.8vw,24px)] py-[clamp(16px,4vh,36px)] overflow-hidden min-h-0 min-w-0 ${className}`}>
        {children}
      </div>
    </div>
  );
};

export default CrayonWrapper;
