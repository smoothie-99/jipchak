import { useRef } from 'react';
import { useToolStore } from '@/store/toolStore';
import CrayonWrapper from '../common/CrayonWrapper';
import RecordThumbnail from './RecordThumbnail';

const RecordList = () => {
  const { records } = useToolStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const getDisplayName = (filename: string) => {
    return filename.split('.')[0];
  };

  const scrollToTop = () => {
    scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <CrayonWrapper className="items-center">
      <h2 className="text-[clamp(18px,2.4vw,28px)] font-bold text-center text-yellow-400 mb-[4%] select-none [text-shadow:clamp(1px,0.2vw,2.5px)_clamp(1px,0.2vw,2.5px)_0_#1f2937,_-clamp(0.5px,0.15vw,2px)_-clamp(0.5px,0.15vw,2px)_0_#1f2937,clamp(0.5px,0.15vw,2px)_-clamp(0.5px,0.15vw,2px)_0_#1f2937,_-clamp(0.5px,0.15vw,2px)_clamp(0.5px,0.15vw,2px)_0_#1f2937]">
        나의 기록
      </h2>

      <div 
        ref={scrollRef}
        className="flex-1 w-full overflow-y-auto pt-[8%] flex flex-col gap-[1%] z-header no-scrollbar"
      >
        {records.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <span className="text-gray-400/60 font-medium text-[clamp(14px,1.8vw,20px)] text-center select-none break-keep">
              아직 기록이 없어요!
            </span>
          </div>
        ) : (
          <>
            {[...records].reverse().map((record, index) => {
              const displayIndex = records.length - index;
              // 성공/실패 판정 로직 안정화 전까지 훈장(성공 강조) UI 비활성화
              const success = false;

              return (
                <div 
                  key={record.id} 
                  className="relative flex flex-col w-full shrink-0 bg-white p-[3%] rounded-[0.8vw] gap-[2%] mb-[8%]"
                >
                  <div className="absolute inset-0 border-[clamp(1px,0.3vw,3px)] border-crayon-line opacity-30 pointer-events-none rounded-[255px_15px_225px_15px/15px_225px_15px_255px]" />
                  <div className="absolute inset-0 border-[clamp(1px,0.3vw,3px)] border-crayon-line opacity-50 pointer-events-none rounded-[15px_225px_15px_255px/255px_15px_225px_15px] rotate-[0.5deg]" />

                  {/* 순번 배지 영역: 7인치 최적화 초소형 사이즈 */}
                  <div className="absolute top-[2%] left-[2%] z-header flex flex-col items-center">
                    {success ? (
                      <>
                        <div className="relative w-[clamp(16px,2.5vw,24px)] aspect-square bg-gradient-to-br from-yellow-200 via-yellow-400 to-yellow-600 rounded-full flex items-center justify-center border-[clamp(0.5px,0.1vw,1.5px)] border-yellow-600 shadow-sm z-sub">
                          <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-[clamp(9px,1.2vw,13px)] select-none">
                            {displayIndex}
                          </span>
                        </div>
                        <div className="flex -mt-[10%] gap-[0.1vw] z-header">
                          {/* 리본 극초소형화 */}
                          <div className="w-[0.6vw] h-[1.1vw] min-w-[3px] min-h-[7px] bg-gradient-to-b from-red-500 to-red-800 origin-top rotate-[12deg] rounded-b-[0.1vw] border-x-[0.3px] border-b-[0.3px] border-red-900" />
                          <div className="w-[0.6vw] h-[1.1vw] min-w-[3px] min-h-[7px] bg-gradient-to-b from-red-500 to-red-800 origin-top -rotate-[12deg] rounded-b-[0.1vw] border-x-[0.3px] border-b-[0.3px] border-red-900" />
                        </div>
                      </>
                    ) : (
                      <div className="relative w-[clamp(14px,2.2vw,22px)] aspect-square bg-white rounded-[255px_15px_225px_15px/15px_225px_15px_255px] border-[clamp(0.8px,0.15vw,1.5px)] border-crayon-line shadow-sm z-sub flex items-center justify-center">
                        <span className="text-gray-800 font-bold text-[clamp(9px,1.2vw,12px)] select-none">
                          {displayIndex}
                        </span>
                      </div>
                    )}
                  </div>
                  
                  <RecordThumbnail 
                    src={record.thumbnailUrl} 
                    alt={record.filename} 
                    success={success} 
                  />

                  <span className="text-[clamp(12px,1.4vw,17px)] font-medium text-gray-800 break-words leading-tight select-none text-center break-keep">
                    {getDisplayName(record.filename)}
                  </span>
                </div>
              );
            })}

            {records.length >= 4 && (
              <div className="w-full flex justify-center pt-[2%] pb-[8%] shrink-0">
                <button 
                  onClick={scrollToTop}
                  className="px-[clamp(20px,2.4vw,36px)] py-[clamp(8px,1vw,14px)] bg-gray-800 text-white rounded-[255px_15px_225px_15px/15px_225px_15px_255px] font-bold shadow-lg border-[clamp(1px,0.2vw,2.5px)] border-white flex items-center gap-[0.8vw] active:scale-95 transition-transform"
                >
                  <svg className="w-[1em] h-[1em]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 15l7-7 7 7" />
                  </svg>
                  <span className="text-[clamp(12px,1.4vw,18px)]">TOP</span>
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </CrayonWrapper>
  );
};

export default RecordList;
