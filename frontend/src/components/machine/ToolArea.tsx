import { useToolStore } from '@/store/toolStore';
import RecordList from './RecordList';
import QRConsent from './QRConsent';
import QRDisplay from './QRDisplay';
import CatchAnimation from './CatchAnimation';

/**
 * ToolArea 컴포넌트
 * 전역 상태(useToolStore)에 따라 동적으로 뷰를 전환합니다.
 */
const ToolArea = () => {
  const { viewType, isCatching, lastResult } = useToolStore();

  const renderContent = () => {
    switch (viewType) {
      case 'RECORDS':
        return <RecordList />;
      case 'QR_CONSENT':
        return <QRConsent />;
      case 'QR_DISPLAY':
        return <QRDisplay />;
      default:
        return <RecordList />;
    }
  };

  return (
    <div className="w-full h-full flex flex-col min-h-0 min-w-0 relative">
      {renderContent()}
      
      {/* 뽑기 진행 중이거나 결과가 있을 때 연출 화면을 덮음 */}
      {(isCatching || lastResult) && <CatchAnimation />}
    </div>
  );
};

export default ToolArea;
