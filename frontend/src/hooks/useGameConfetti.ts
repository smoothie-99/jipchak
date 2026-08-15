import { useCallback, useEffect, useRef, useState } from 'react';
import { useToolStore } from '@/store/toolStore';
import { useAudio } from '@/hooks/useAudio';
import { ConfettiOptions } from '@/components/common/Confetti';
import { SOUND_ASSETS } from '@/constants/soundConfig';

export interface ConfettiBurst {
    id: number;
    options?: ConfettiOptions;
    type?: 'direct' | 'launch';
}

/**
 * 게임 성공 시 폭죽 발사 + 효과음 재생.
 *
 * - `lastResult === 'win'` 으로 전이되는 그 순간에만 발사 (이전 처리된 결과 ref 로 dedup)
 * - 함수형 setState 로 연타 가드 (이전 stale closure 문제 해결)
 * - 컴포넌트는 burst 목록과 제거 콜백만 사용
 */
export function useGameConfetti(): {
    confettiBursts: ConfettiBurst[];
    removeBurst: (id: number) => void;
} {
    const lastResult = useToolStore((s) => s.lastResult);
    const { playSfx } = useAudio();

    const [confettiBursts, setConfettiBursts] = useState<ConfettiBurst[]>([]);
    const lastProcessedResult = useRef<string | null>(null);

    const triggerConfetti = useCallback((type: 'direct' | 'launch' = 'direct') => {
        // 함수형 업데이트로 stale state 가드 — 같은 tick 안에서 두 번 호출되어도 1 개만 추가됨.
        setConfettiBursts((prev) => {
            if (prev.length > 0) return prev;
            return [...prev, { id: Date.now(), type, options: {} }];
        });
    }, []);

    const removeBurst = useCallback((id: number) => {
        setConfettiBursts((prev) => prev.filter((b) => b.id !== id));
    }, []);

    useEffect(() => {
        if (lastResult === lastProcessedResult.current) return;
        if (lastResult === 'win') {
            playSfx(SOUND_ASSETS.SFX.WIN);
            triggerConfetti('launch');
        }
        lastProcessedResult.current = lastResult;
    }, [lastResult, playSfx, triggerConfetti]);

    return { confettiBursts, removeBurst };
}
