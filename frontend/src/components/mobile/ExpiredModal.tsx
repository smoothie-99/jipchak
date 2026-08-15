import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import byeByeImg from '../../assets/images/bye_bye.png';

interface ExpiredModalProps {
  isExpired: boolean;
}

const ExpiredModal: React.FC<ExpiredModalProps> = ({ isExpired }) => {
  return (
    <AnimatePresence>
      {isExpired && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 bg-black/80 z-modal flex flex-col items-center justify-center p-[5%]"
        >
          <div className="bg-white p-[clamp(20px,6%,32px)] rounded-3xl flex flex-col items-center text-center shadow-2xl max-w-[400px] w-full border-[4px] border-crayon-line">

            {/* 모든 환경에서 줄바꿈 없이 정돈된 구조 (노트북 겹침/줄바꿈 방지) */}
            <div className="w-full mb-8 flex items-center justify-center gap-2">
              {/* 왼쪽: 보이지 않는 공간 (데코레이션 크기 축소) */}
              <div className="w-[clamp(36px,10vw,50px)] shrink-0" aria-hidden="true" />
              
              {/* 중앙: 텍스트 (강제 줄바꿈 방지) */}
              <span
                className="text-[clamp(30px,7.5vw,44px)] font-black text-[#FFD100] tracking-tighter leading-[1.1] text-center whitespace-nowrap"
                style={{ WebkitTextStroke: '2px #1f2937' }}
              >
                안녕히<br />가세요
              </span>

              {/* 오른쪽: 정적 이미지 (데코레이션 크기 축소) */}
              <img 
                src={byeByeImg} 
                alt="BYE BYE" 
                className="w-[clamp(36px,10vw,50px)] h-auto object-contain drop-shadow-sm shrink-0"
              />
            </div>

            <h2 className="text-[clamp(20px,5vw,26px)] font-bold mb-3 text-crayon-line break-keep text-center">세션이 만료되었습니다</h2>
            <p className="text-[clamp(14px,3.5vw,16px)] text-gray-500 leading-relaxed mb-4 break-keep text-center">
              보안을 위해 시간이 만료된 영상은 영구적으로 삭제됩니다.
            </p>

            {/* 버튼은 연결할 곳이 없으므로 삭제됨 */}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ExpiredModal;
