import { useEffect } from 'react';
import { useToolStore } from '@/store/toolStore';

const MAX_RECORDS = 5;

/**
 * 게임 플레이 화면의 키보드 입력 핸들러.
 *
 * 화이트리스트:
 *   - Enter / Space 만 허용. F12, Esc, Tab 등은 무시 (우발적 세션 종료 방지).
 *   - Modifier 조합 (Ctrl/Alt/Meta) 무시 → 브라우저/OS 단축키와 충돌 방지.
 *   - 키 홀드 (e.repeat) 무시 → 손가락 떨림 한 번에 종료되는 사고 차단.
 *   - IME 합성 중 입력 무시.
 *
 * 동작:
 *   - 5 판 종료 후 입력: 세션 리셋 + 자동 재시작 연출
 *   - 일반 상황: 안내 모달만 닫기
 */
export function useGameKeyboard(): void {
    const records = useToolStore((s) => s.records);
    const resetSession = useToolStore((s) => s.resetSession);
    const setAskingNextStep = useToolStore((s) => s.setAskingNextStep);
    const setAutoStarting = useToolStore((s) => s.setAutoStarting);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.ctrlKey || e.altKey || e.metaKey) return;
            if (e.repeat) return;
            if (e.isComposing) return;
            if (e.key !== 'Enter' && e.key !== ' ') return;

            e.preventDefault();

            if (records.length >= MAX_RECORDS) {
                console.log('[Session] 사용자 입력 감지: 자동 재시작 연출을 시작합니다.');
                resetSession();
                setAutoStarting(true);
            } else {
                setAskingNextStep(false);
            }
        };

        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [records, resetSession, setAskingNextStep, setAutoStarting]);
}
