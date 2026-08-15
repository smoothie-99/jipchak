import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToolStore } from '@/store/toolStore';
import { useStreamSocket, useStreamStore, StreamState, sendStartRequest } from '@/store/streamStore';
import { useAudio } from '@/hooks/useAudio';
import { useCameraSwap } from '@/hooks/useCameraSwap';
import { useGameKeyboard } from '@/hooks/useGameKeyboard';
import { useGameConfetti } from '@/hooks/useGameConfetti';
import { SOUND_ASSETS } from '@/constants/soundConfig';
import Confetti from '@/components/common/Confetti';
import CameraTransitionOverlay from '@/components/machine/CameraTransitionOverlay';
import MainCameraPanel from '@/components/machine/MainCameraPanel';
import SidePanel from '@/components/machine/SidePanel';
// import GameCountModal from '@/components/machine/GameCountModal'; // [비활성화] 판수 선택 모달 - 2판 고정으로 변경

/**
 * 게임 플레이 화면.
 *
 * 외부 라이프사이클은 hooks 로 분리되어 있다:
 *   - useStreamSocket      : WebSocket 단일 인스턴스 관리 (Phase 1)
 *   - useGameKeyboard      : Enter/Space 키 입력 처리
 *   - useGameConfetti      : 성공 시 폭죽 + 효과음
 *   - useCameraSwap        : 메인/보조 카메라 스왑
 *
 * 화면 구성도 두 패널로 분리:
 *   - <MainCameraPanel>    : 메인 카메라 + 가이드 + 설정 버튼 + 모달들
 *   - <SidePanel>          : 우측 ToolArea + 보조 카메라
 *
 * 이 컴포넌트는 페이지 레벨 가드와 BGM 라이프사이클만 책임진다.
 */
const PlayGround = () => {
    const navigate = useNavigate();
    const isSessionActive = useToolStore((s) => s.isSessionActive);
    const lastResult = useToolStore((s) => s.lastResult);
    const resetSession = useToolStore((s) => s.resetSession);

    const { playBgm, stopBgm } = useAudio();
    const { isSwapped, isTransitioning, handleSwap } = useCameraSwap();

    // 인프라성 hooks
    useStreamSocket();
    useGameKeyboard();
    const { confettiBursts, removeBurst } = useGameConfetti();

    // GameCountModal — 비활성화 (판수 2판 고정, 파란 버튼으로 바로 시작)
    // const [isCountModalOpen, setIsCountModalOpen] = useState(true);

    // 아두이노 빨강 (READY 단계) → BACK_TO_HOME 이벤트 → 메인 페이지로
    const lastUiEvent = useStreamStore((s: StreamState) => s.lastUiEvent);
    const lastBackTs = useRef<number | null>(null);
    useEffect(() => {
        if (lastUiEvent?.type === 'BACK_TO_HOME') {
            if (lastBackTs.current === lastUiEvent.ts) return;
            lastBackTs.current = lastUiEvent.ts;
            resetSession(); // 세션 / 카메라 / QR 상태 정리 + 홈으로 navigate
        }
    }, [lastUiEvent, resetSession]);

    // 1판 종료 후 호밍 복귀 (READY 상태)에서 조이스틱 이동 시 다음 판 자동 시작
    const lastJoyTs = useRef<number | null>(null);
    useEffect(() => {
        if (!lastUiEvent) return;
        if (lastUiEvent.type === 'JOY_LEFT' || lastUiEvent.type === 'JOY_RIGHT') {
            if (lastJoyTs.current === lastUiEvent.ts) return;
            lastJoyTs.current = lastUiEvent.ts;
            
            // maxGames에 도달하지 않았고 현재 게임 진행 중이 아닐 때만 시작 요청
            const { records, maxGames, isCatching } = useToolStore.getState();
            if (records.length > 0 && records.length < maxGames && !isCatching) {
                sendStartRequest();
            }
        }
    }, [lastUiEvent]);

    // 페이지 진입 시 BGM 재생, 이탈 시 정지
    useEffect(() => {
        playBgm(SOUND_ASSETS.BGM.MAIN);
        return () => {
            stopBgm();
        };
    }, [playBgm, stopBgm]);

    // 세션 가드: 활성 세션이 없으면 시작 페이지로 리다이렉트
    useEffect(() => {
        if (!isSessionActive) {
            console.warn('[SessionGuard] 활성화된 세션이 없어 시작 페이지로 이동합니다.');
            navigate('/');
        }
    }, [isSessionActive, navigate]);

    if (!isSessionActive) return null; // 리다이렉트 전 찰나의 렌더링 방지

    return (
        <div
            className="flex w-full h-screen bg-[#dfdfdf] p-[calc(24/1024*100vw)] gap-[calc(16/1024*100vw)] overflow-hidden relative"
            onContextMenu={(e) => e.preventDefault()}
        >
            {/* 카메라 스왑 시 발생하는 딜레이를 가려주는 전환 오버레이 */}
            <CameraTransitionOverlay isTransitioning={isTransitioning} />

            {/* 폭죽 버스트 매니저 (성공 화면 활성 여부 전달) */}
            <Confetti
                bursts={confettiBursts}
                onBurstComplete={removeBurst}
                isActive={lastResult === 'win'}
            />

            <MainCameraPanel
                label={isSwapped ? 'Cam2' : 'Cam1'}
                channel={isSwapped ? '2d' : '3d'}
            />

            <SidePanel
                label={isSwapped ? 'Cam1' : 'Cam2'}
                channel={isSwapped ? '3d' : '2d'}
                onCameraSwap={handleSwap}
            />

            {/* [비활성화] 판수 선택 모달 — 2판 고정으로 대체
            <GameCountModal
                isOpen={isCountModalOpen}
                onConfirm={() => setIsCountModalOpen(false)}
            />
            */}
        </div>
    );
};

export default PlayGround;
