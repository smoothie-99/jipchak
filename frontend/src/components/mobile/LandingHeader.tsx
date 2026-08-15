import React from 'react';

interface LandingHeaderProps {
  timeLeft: number;
  formatTime: (seconds: number) => string;
}

const LandingHeader: React.FC<LandingHeaderProps> = ({ timeLeft, formatTime }) => {
  return (
    <header className="w-full p-[5%] flex flex-col items-center pt-[10%] shrink-0">
      <h1 className="text-[clamp(24px,6vw,32px)] font-bold mb-3 tracking-wide text-center text-crayon-line break-keep">
        인형뽑기 플레이 영상
      </h1>
      <p className="text-[clamp(14px,3.5vw,18px)] text-gray-500 mb-4 text-center break-keep">
        지금 바로 다운로드 하세요!
      </p>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-red-50 text-red-500 px-4 py-2 rounded-full border border-red-100 shadow-sm">
          <span className="text-sm font-bold break-keep">만료까지</span>
          <span className="text-lg font-bold tracking-widest">{formatTime(timeLeft)}</span>
        </div>
      </div>
    </header>
  );
};

export default LandingHeader;
