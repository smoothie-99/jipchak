import { useToolStore } from '@/store/toolStore';
import { useAudioStore } from '@/store/audioStore';
import CameraView from './CameraView';
import StartGuide from './StartGuide';
import PlayingTimer from './PlayingTimer';
import NextStepModal from './NextStepModal';
import SettingsModal from './SettingsModal';

interface MainCameraPanelProps {
    label: string;
    channel: '2d' | '3d';
}

/**
 * 메인 카메라 패널.
 * 큰 카메라 뷰 + 게임 가이드 + 설정 버튼 + 모달들을 묶어서 PlayGround 가 단순해지도록 분리.
 */
const MainCameraPanel = ({ label, channel }: MainCameraPanelProps) => {
    const isCatching = useToolStore((s) => s.isCatching);
    const lastResult = useToolStore((s) => s.lastResult);
    const isAskingNextStep = useToolStore((s) => s.isAskingNextStep);
    const setSettingsOpen = useAudioStore((s) => s.setSettingsOpen);

    return (
        <div
            className="flex-[766] bg-black rounded-[1vw] shadow-sm relative overflow-hidden"
            style={{ aspectRatio: '766 / 552' }}
        >
            <CameraView label={label} channel={channel} isMainView={true} />

            {/* 게임 시작 안내 가이드 (아이들 상태일 때만 표시) */}
            {!isCatching && !lastResult && !isAskingNextStep && <StartGuide />}

            {/* 플레이 중 15초 카운트다운 (SESSION_START ~ GAME_RESULT 구간) */}
            {isCatching && !lastResult && <PlayingTimer />}

            {/* 설정 버튼 (좌상단 고정, 스왑 시에도 유지됨) */}
            <button
                onClick={() => setSettingsOpen(true)}
                className="absolute top-[3%] left-[3%] z-overlay active:scale-95 transition-transform text-white/90"
                aria-label="Settings"
            >
                <svg className="w-[clamp(28px,4vw,48px)] h-[clamp(28px,4vw,48px)] drop-shadow-lg" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.06-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.73,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.06,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.49-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z" />
                </svg>
            </button>

            {/* 세션 지속 여부 확인 모달 */}
            <NextStepModal />

            {/* 볼륨 설정 모달 */}
            <SettingsModal />
        </div>
    );
};

export default MainCameraPanel;
