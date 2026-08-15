import React, { useEffect, useRef } from 'react';
import { AnimatePresence, useAnimationFrame } from 'framer-motion';

// 6가지 핵심 옵션 인터페이스
export interface ConfettiOptions {
  count?: number;      // 입자 개수
  velocity?: number;   // 초기 뿜어지는 힘
  spread?: number;     // 퍼지는 각도
  gravity?: number;    // 중력 (아래로 당기는 힘)
  decay?: number;      // 공기 저항 (속도 감쇠)
  drift?: number;      // 바람 (가로 밀림)
  colors?: string[];   // 색상
}

interface PhysicsParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  size: number;
  rotationX: number;
  rotationY: number;
  rotationZ: number;
  speedX: number;
  speedY: number;
  speedZ: number;
  opacity: number;
}

const DEFAULT_COLORS = [
  '#FF36FF', '#FFA62D', '#FCFF42', '#26CCFF', '#A25AFD', '#FF5E7E', '#88FF5A'
];

/**
 * ConfettiBurst Component (지향성 발사 보강)
 */
export const ConfettiBurst: React.FC<ConfettiOptions & {
  onComplete: () => void;
  origin?: { x: string; y: string };
  angle?: number; // 발사 중심 각도 (기본 -90: 위쪽)
}> = ({
  count = 240,
  velocity = 64,
  spread = 70,
  gravity = 0.8,
  decay = 0.92,
  drift = 0,
  colors = DEFAULT_COLORS,
  origin = { x: '0px', y: '0px' },
  angle = -90,
  onComplete
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const particlesRef = useRef<PhysicsParticle[]>([]);

    // 7인치 키오스크(800px)를 기준으로 물리량을 스케일링하는 유닛
    const unitScale = typeof window !== 'undefined' ? window.innerWidth / 800 : 1;

    // 리렌더링 시 onComplete 함수가 바뀌어도 이펙트가 재실행되지 않도록 Ref 사용
    const onCompleteRef = useRef(onComplete);
    onCompleteRef.current = onComplete;

    useEffect(() => {
      particlesRef.current = Array.from({ length: count }).map(() => {
        // 지정된 angle을 중심으로 spread 범위 내에서 발사
        const randomAngle = angle + (Math.random() * spread - spread / 2);
        const rad = randomAngle * (Math.PI / 180);

        // 속도와 크기를 화면 스케일에 맞게 보정
        const actualVelocity = (Math.random() * 0.7 + 0.3) * velocity * unitScale;
        const actualSize = (Math.random() * 7 + 4) * unitScale;

        return {
          x: 0,
          y: 0,
          vx: Math.cos(rad) * actualVelocity,
          vy: Math.sin(rad) * actualVelocity,
          color: colors[Math.floor(Math.random() * colors.length)],
          size: actualSize,
          rotationX: Math.random() * 360,
          rotationY: Math.random() * 360,
          rotationZ: Math.random() * 360,
          speedX: (Math.random() - 0.5) * 15,
          speedY: (Math.random() - 0.5) * 15,
          speedZ: (Math.random() - 0.5) * 15,
          opacity: 1,
        };
      });

      const timer = setTimeout(() => {
        onCompleteRef.current();
      }, 4500);
      return () => clearTimeout(timer);
    }, [count, velocity, spread, colors, angle, unitScale]); // onComplete를 의존성에서 제외하여 리셋 방지

    useAnimationFrame((time, delta) => {
      const dt = delta / 16.66;
      if (!containerRef.current) return;
      const children = containerRef.current.children;

      // 중력과 난류도 화면 스케일에 맞게 보정
      const actualGravity = gravity * unitScale;
      const actualDrift = drift * unitScale;

      particlesRef.current.forEach((p, i) => {
        if (!children[i]) return;
        p.vx += (Math.random() - 0.5) * 0.5 * dt * unitScale + (actualDrift * 0.1 * dt);
        p.vy += (actualGravity * 0.22 * dt) + (Math.random() - 0.5) * 0.2 * dt * unitScale;
        p.vx *= Math.pow(decay, dt);
        p.vy *= Math.pow(decay, dt);
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.rotationX += p.speedX * dt;
        p.rotationY += p.speedY * dt;
        p.rotationZ += p.speedZ * dt;
        if (time > 3000) p.opacity = Math.max(0, 1 - ((time - 3000) / 1500));

        const el = children[i] as HTMLElement;
        el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0) rotateX(${p.rotationX}deg) rotateY(${p.rotationY}deg) rotateZ(${p.rotationZ}deg)`;
        el.style.opacity = p.opacity.toString();
      });
    });

    return (
      <div
        ref={containerRef}
        className="absolute pointer-events-none flex items-center justify-center z-toast"
        style={{ left: origin.x, top: origin.y }}
      >
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            ref={(el) => {
              if (el && particlesRef.current[i]) {
                el.style.backgroundColor = particlesRef.current[i].color;
                el.style.width = `${particlesRef.current[i].size}px`;
                el.style.height = `${particlesRef.current[i].size * 0.6}px`;
                el.style.borderRadius = '1px';
              }
            }}
            style={{ position: 'absolute' }}
          />
        ))}
      </div>
    );
  };

/**
 * ConfettiPopper Component
 * 원뿔 모양의 폭죽 통 오브젝트와 발사 로직을 결합합니다.
 */
export const ConfettiPopper: React.FC<ConfettiOptions & { 
  onComplete: () => void;
  isActive?: boolean; // 현재 성공 화면이 떠 있는지 여부
}> = ({
  onComplete,
  isActive = true,
  ...options
}) => {
  // ToolArea 중앙부(88vw)에서 좌상단(215도)으로 조준
  const popperOrigin = { x: '88vw', y: '25vh' };
  const targetAngle = 215;

  return (
    <div className="fixed inset-0 pointer-events-none z-toast">
      {/* 폭죽 통 비주얼: 대성공 글자를 가리는 문제로 임시 주석 처리
      <AnimatePresence>
        {isActive && (
          <motion.div
            initial={{ scale: 0, rotate: targetAngle + 90 }}
            animate={{ scale: 1, rotate: targetAngle + 90 }}
            exit={{ scale: 0, opacity: 0 }}
            className="absolute w-[4vw] h-[6vw] bg-gradient-to-b from-pink-500 via-purple-600 to-indigo-800"
            style={{
              left: popperOrigin.x,
              top: popperOrigin.y,
              clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)', // 원뿔 모양
              transformOrigin: '50% 100%'
            }}
          >
            <div className="absolute inset-x-0 bottom-0 h-[1vw] bg-yellow-400 opacity-50" />
          </motion.div>
        )}
      </AnimatePresence>
      */}

      {/* 실제 종이 파편 발사: 통의 유무와 상관없이 물리 엔진은 수명만큼 작동 */}
      <ConfettiBurst
        {...options}
        origin={popperOrigin}
        angle={targetAngle}
        onComplete={onComplete}
      />
    </div>
  );
};

/**
 * Confetti (Manager)
 */
const ConfettiContainer: React.FC<{
  bursts: { id: number; options?: ConfettiOptions; type?: 'direct' | 'launch' }[];
  onBurstComplete: (id: number) => void;
  isActive?: boolean;
}> = ({
  bursts,
  onBurstComplete,
  isActive = true
}) => {
    return (
      <div className="fixed inset-0 pointer-events-none z-toast">
        <AnimatePresence>
          {bursts.map((b) => (
            b.type === 'launch' ? (
              <ConfettiPopper
                key={b.id}
                {...b.options}
                isActive={isActive}
                onComplete={() => onBurstComplete(b.id)}
              />
            ) : (
              <div key={b.id} className="absolute inset-0 flex items-center justify-center">
                <ConfettiBurst
                  {...b.options}
                  onComplete={() => onBurstComplete(b.id)}
                />
              </div>
            )
          ))}
        </AnimatePresence>
      </div>
    );
  };

export default ConfettiContainer;
