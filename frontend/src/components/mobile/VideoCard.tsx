import React from 'react';
import { motion } from 'framer-motion';

interface VideoCardProps {
  video: any;
  index: number;
  filename: string;
  onDownload: (url: string, index: number) => void;
}

const VideoCard: React.FC<VideoCardProps> = ({ video, index, filename, onDownload }) => {
  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: index * 0.1 }}
      className="w-full bg-white rounded-[24px] shadow-md border-[3px] border-crayon-line overflow-hidden flex flex-col shrink-0 snap-center"
    >
      {/* 비디오 플레이어 영역 */}
      <div className="w-full aspect-video bg-black relative">
        <video
          src={video.url}
          poster={video.thumb}
          controls
          muted
          controlsList="novolume"
          playsInline
          className="w-full h-full object-contain"
        />
      </div>

      {/* 하단 컨트롤 영역 (2단 구조로 개선) */}
      <div className="p-[4%] flex flex-col bg-[#FAFAFA] border-t-[3px] border-crayon-line">

        {/* 상단: 성공/실패 뱃지는 잠시 비활성화하고 다운로드 안내만 표시 */}
        <div className="w-full text-center py-2.5 rounded-xl mb-3 border-2 bg-gray-50 border-gray-200">
          <p className="text-[clamp(14px,3.8vw,17px)] font-bold break-keep text-gray-700">
            촬영된 영상을 확인하고 다운로드할 수 있어요
          </p>
        </div>

        {/* 하단: 파일명 및 저장 버튼 */}
        <div className="flex items-center justify-between gap-2">
          {/* 왼쪽: 파일명 */}
          <span className="font-bold text-[clamp(11px,3vw,13px)] text-gray-400">
            {filename}
          </span>

          {/* 오른쪽: 저장 버튼 */}
          <button
            onClick={() => onDownload(video.url, index)}
            className="px-5 py-2.5 bg-[#FFD100] text-crayon-line border-[3px] border-crayon-line rounded-2xl font-bold shadow-[3px_3px_0px_0px_rgba(31,41,55,1)] active:shadow-none active:translate-x-[1.5px] active:translate-y-[1.5px] transition-all flex items-center justify-center min-w-[110px] shrink-0"
          >
            <span className="text-[clamp(15px,4vw,18px)] tracking-tight break-keep">저장하기</span>
          </button>
        </div>
      </div>
    </motion.div>
  );
};

export default VideoCard;
