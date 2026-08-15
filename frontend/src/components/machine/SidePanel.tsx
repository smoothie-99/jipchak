import CameraView from './CameraView';
import ToolArea from './ToolArea';

interface SidePanelProps {
    /** 보조 카메라 라벨 (스왑 상태에 따라 Cam1/Cam2 가 교대) */
    label: string;
    /** 보조 카메라 채널 */
    channel: '2d' | '3d';
    /** 보조 카메라 클릭 시 메인 카메라와 swap */
    onCameraSwap: () => void;
}

/**
 * 우측 사이드 패널.
 * ToolArea (RecordList / QRConsent / QRDisplay 등) + 보조 카메라 뷰.
 */
const SidePanel = ({ label, channel, onCameraSwap }: SidePanelProps) => {
    return (
        <div className="flex-[194] min-w-0 flex flex-col gap-[calc(16/600*100vh)]">
            {/* Tool 영역 (우상단) */}
            <div className="flex-[411] min-h-0 min-w-0 rounded-[1vw] shadow-sm relative overflow-hidden flex flex-col">
                <ToolArea />
            </div>

            {/* 보조 카메라 뷰 (클릭 시 메인 뷰와 스왑) */}
            <div className="flex-[125] min-h-0 min-w-0 bg-black rounded-[1vw] shadow-sm relative overflow-hidden">
                <CameraView
                    label={label}
                    channel={channel}
                    isMainView={false}
                    onClick={onCameraSwap}
                    className="cursor-pointer active:scale-[0.98] transition-transform"
                />
            </div>
        </div>
    );
};

export default SidePanel;
