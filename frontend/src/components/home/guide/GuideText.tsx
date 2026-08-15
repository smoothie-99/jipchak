import { ReactNode } from 'react';

interface GuideTextProps {
  title: string;
  description: ReactNode;
}

/**
 * GuideText
 * 사용 가이드 모달의 텍스트를 표시합니다.
 */
const GuideText = ({ title, description }: GuideTextProps) => {
  return (
    <div className="flex-1 h-full flex flex-col items-center justify-start overflow-hidden">
      {/* 가이드 제목 */}
      <div className="w-full pt-[1vh] pb-[0.5vh] flex flex-col items-center shrink-0">
        <span className="block text-center text-[clamp(24px,5vh,34px)] font-black text-crayon-line leading-[1.15] break-keep">
          {title}
        </span>
      </div>

      {/* 가이드 내용 */}
      <div className="w-full flex-1 flex items-center justify-center">
        <p className="w-full text-[clamp(18px,3.6vh,21px)] font-black text-crayon-line text-center break-keep leading-[1.45] [word-break:keep-all] [overflow-wrap:anywhere]">
          {description}
        </p>
      </div>
    </div>
  );
};

export default GuideText;
