import { motion, AnimatePresence } from 'framer-motion';
import { useToolStore } from '@/store/toolStore';
import catchGif from '@/assets/images/catch_anim.gif';

/**
 * [Convention Constants]
 * 타이포그래피 스타일 상수화 (가독성 및 유지보수성 향상)
 */
const SFX_STYLE_PINK = { 
  WebkitTextStroke: '3px white', 
  textShadow: '5px 5px 0px #000, 0 0 25px #EC4899' 
};

const SFX_STYLE_CYAN = { 
  WebkitTextStroke: '3px white', 
  textShadow: '5px 5px 0px #000, 0 0 25px #22D3EE' 
};

const WIN_TEXT_STYLE = { 
  WebkitTextStroke: '4px white', 
  textShadow: '6px 6px 0px #000, 0 0 40px #FACC15' 
};

const LOSE_TEXT_STYLE = { 
  WebkitTextStroke: '2px #666', 
  textShadow: '4px 4px 0px #222' 
};

/**
 * CatchAnimation Component
 * 오타게(Wotagei) 특유의 하이텐션 액션과 역동적인 타이포그래피 연출
 */
const CatchAnimation = () => {
  const { isCatching, lastResult } = useToolStore();

  return (
    <div className={`absolute inset-0 z-overlay flex items-center justify-center overflow-hidden transition-all duration-300
      ${lastResult === 'lose' ? 'bg-zinc-800 grayscale' : 'bg-slate-900'}`}
      onContextMenu={(e) => e.preventDefault()} // 컨벤션: 우클릭 방지
    >
      {/* 1. 집중선 (Speed Lines) - 회전하는 배경 */}
      <motion.div
        animate={isCatching || lastResult === 'win' ? { rotate: 360 } : { rotate: 0 }}
        transition={{ duration: 5, repeat: Infinity, ease: 'linear' }}
        className="absolute w-[400%] h-[400%] opacity-30 pointer-events-none"
        style={{
          background: lastResult === 'win' 
            ? 'repeating-conic-gradient(from 0deg, transparent 0deg 10deg, #FDE68A 10deg 20deg)' 
            : 'repeating-conic-gradient(from 0deg, transparent 0deg 10deg, #FFFFFF 10deg 20deg)'
        }}
      />

      {/* 2. 오타게 형광봉 궤적 (Light Trails) - 진행 중에만 표시 */}
      {isCatching && (
        <div className="absolute inset-0 pointer-events-none select-none">
          {[
            { color: 'bg-pink-500', top: '15%', delay: 0 },
            { color: 'bg-cyan-400', top: '55%', delay: 0.2 },
            { color: 'bg-lime-400', top: '85%', delay: 0.4 },
            { color: 'bg-yellow-400', top: '35%', delay: 0.1 },
          ].map((trail, i) => (
            <motion.div
              key={`trail-${i}`}
              initial={{ x: '-100vw', opacity: 0, skewX: -45 }}
              animate={{ x: '100vw', opacity: [0, 1, 1, 0] }}
              transition={{ duration: 0.7, repeat: Infinity, delay: trail.delay, ease: 'linear' }}
              className={`absolute w-[150%] h-[1.5vw] min-h-[15px] ${trail.color} blur-[2px]`}
              style={{ top: trail.top, rotate: 15 }}
            />
          ))}
        </div>
      )}

      <AnimatePresence mode="wait">
        {isCatching ? (
          <motion.div
            key="catching"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="relative w-full h-full flex items-center justify-center"
          >
            {/* 캐릭터 GIF */}
            <div className="relative z-header w-[70%] max-w-[280px] aspect-square flex items-center justify-center">
               <motion.div 
                animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.8, 0.5] }}
                transition={{ duration: 0.5, repeat: Infinity }}
                className="absolute w-[110%] h-[110%] bg-white rounded-full blur-[40px] mix-blend-overlay" 
              />
              <img 
                src={catchGif} 
                alt="Catching..." 
                className="w-full h-full object-contain relative z-header select-none pointer-events-none"
              />
            </div>

            {/* 3. 만화책 SFX 타이포그래피 (영! 차!) */}
            <div className="absolute inset-0 pointer-events-none z-header">
              <motion.div
                animate={{ scale: [1, 1.4, 1], rotate: [-15, -5, -15] }}
                transition={{ duration: 0.6, repeat: Infinity, ease: 'backOut' }}
                className="absolute top-[5%] left-[2%] text-[clamp(45px,12vw,90px)] font-black text-pink-500 font-crayon"
                style={SFX_STYLE_PINK}
              >
                영!
              </motion.div>
              
              <motion.div
                animate={{ scale: [1, 1.4, 1], rotate: [15, 5, 15] }}
                transition={{ duration: 0.6, repeat: Infinity, ease: 'backOut', delay: 0.3 }}
                className="absolute bottom-[10%] right-[2%] text-[clamp(45px,12vw,90px)] font-black text-cyan-400 font-crayon"
                style={SFX_STYLE_CYAN}
              >
                차!
              </motion.div>
            </div>
          </motion.div>
        ) : lastResult === 'win' ? (
          <motion.div
            key="win"
            initial={{ opacity: 0, scale: 2 }}
            animate={{ opacity: 1, scale: 1, x: [-8, 8, -8, 8, 0], y: [-8, 8, 8, -8, 0] }} 
            transition={{ duration: 0.5 }}
            className="flex flex-col items-center justify-center z-overlay w-full h-full"
          >
            <div className="flex flex-col gap-2 mb-[10%] px-10">
              {['성!', '공!'].map((char, index) => (
                <motion.span
                  key={index}
                  initial={{ opacity: 0, x: -50, scale: 2 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  transition={{ delay: index * 0.15, type: 'spring', stiffness: 300 }}
                  className="text-[clamp(70px,16vw,110px)] font-black text-yellow-400 font-crayon italic leading-none whitespace-nowrap pr-8"
                  style={WIN_TEXT_STYLE}
                >
                  {char}
                </motion.span>
              ))}
            </div>
          </motion.div>
        ) : lastResult === 'lose' ? (
          <motion.div
            key="lose"
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center z-overlay h-full w-full"
          >
            <motion.div 
              animate={{ rotate: [-2, 2, -2] }}
              transition={{ duration: 4, repeat: Infinity }}
              className="text-[clamp(45px,10vw,90px)] font-black text-gray-400 font-crayon"
              style={LOSE_TEXT_STYLE}
            >
              실패
            </motion.div>
            <span className="text-gray-400 font-bold text-[clamp(14px,2.5vw,22px)] mt-6 tracking-widest select-none break-keep">
              다음 기회에...
            </span>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
};

export default CatchAnimation;
