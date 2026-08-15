import { useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { useToolStore } from '@/store/toolStore';
import CrayonWrapper from '../common/CrayonWrapper';

/**
 * QRDisplay 컴포넌트
 * 생성된 QR 코드를 30초 동안 송출하고 전송이 완료되면 닫을 수 있게 합니다.
 */
const QRDisplay = () => {
  const { qrValue, qrTimer, tickQrTimer, resetSession } = useToolStore();

  // 테스트용 기본값 (실제 연동 전까지)
  const displayValue = qrValue || "https://github.com/grab-me/jipchak";

  // 1초마다 타이머 감소
  useEffect(() => {
    const intervalId = setInterval(() => {
      tickQrTimer();
    }, 1000);

    return () => clearInterval(intervalId);
  }, [tickQrTimer]);

  return (
    <CrayonWrapper showCharacter={false} className="justify-around items-center relative py-1">
      <div className="flex flex-col items-center w-full">
        <h3 className="text-[clamp(20px,2.8vw,26px)] font-bold text-gray-800 text-center leading-tight break-keep">
          QR 스캔하여 영상 받기
        </h3>
        <p className="text-[clamp(13px,1.6vw,16px)] text-gray-500 font-medium text-center mt-1 break-keep w-full">
          <span className="text-red-500 font-black">{qrTimer}</span>초 후 자동으로 삭제됩니다.
        </p>
      </div>

      {/* QR 코드 영역: 세로 공간 확보를 위해 크기 대폭 축소 */}
      <div className="bg-white p-[clamp(6px,1vw,12px)] rounded-[1vw] shadow-inner border-[clamp(1.5px,0.3vw,3px)] border-crayon-line flex items-center justify-center aspect-square h-[clamp(90px,30vh,130px)]">
        <QRCodeSVG
          value={displayValue}
          size={undefined}
          style={{ width: '100%', height: '100%' }}
          level={"M"}
          includeMargin={false}
        />
      </div>

      <button
        type="button"
        onClick={resetSession}
        className="w-full py-[clamp(10px,1.2vw,18px)] mt-3 bg-yellow-400 text-gray-800 rounded-[15px_225px_15px_255px/255px_15px_225px_15px] font-bold shadow-lg border-[clamp(1px,0.2vw,2px)] border-yellow-600 active:scale-95 transition-transform text-[clamp(14px,1.8vw,18px)]"
      >
        처음으로 돌아가기
      </button>
    </CrayonWrapper>
  );
};

export default QRDisplay;
