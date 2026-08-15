import React, { useState } from 'react';
import { Menu, Cpu, Settings, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface DashboardHeaderProps {
  deviceId?: string;
  toggleSidebar: () => void;
}

const DashboardHeader: React.FC<DashboardHeaderProps> = ({ deviceId, toggleSidebar }) => {
  const navigate = useNavigate();
  // 추후 백엔드 API와 연동될 원격 확률 제어 상태 (임시로 로컬에서 관리)
  const [dropProb, setDropProb] = useState<number>(20);

  const handleAdjustProb = () => {
    const input = window.prompt(`현재 놓칠 확률은 ${dropProb}% 입니다.\n변경할 확률을 0에서 100 사이의 숫자로 입력하세요.`);
    if (input !== null) {
      const parsed = parseInt(input, 10);
      if (!isNaN(parsed) && parsed >= 0 && parsed <= 100) {
        setDropProb(parsed);
        // TODO: 추후 여기에 백엔드 API 연동 로직 추가 (예: api.updateDropProbability(deviceId, parsed))
      } else {
        alert('0에서 100 사이의 올바른 숫자를 입력해주세요.');
      }
    }
  };

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200 shadow-sm z-header">
      <div className="flex items-center gap-2 md:gap-4">
        <button className="md:hidden p-2 text-slate-600 active:scale-95" onClick={toggleSidebar}>
          <Menu size={28} />
        </button>
        
        {/* 현재 조회 중인 기기 정보 */}
        {deviceId && (
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-100 text-blue-700 rounded-lg">
            <Cpu size={16} />
            <span className="text-sm font-bold tracking-wide">Device ID: <span className="font-black">{deviceId}</span></span>
          </div>
        )}
      </div>
      
      <div className="flex gap-2 sm:gap-4 items-center ml-auto">
        <button 
          onClick={handleAdjustProb}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm sm:text-base font-semibold text-slate-600 hover:bg-gray-100 active:scale-95 transition-colors"
        >
          <Settings size={18} />
          <span className="hidden sm:inline">설정 (기본 놓칠확률: {dropProb}%)</span>
        </button>
        <button 
          onClick={() => navigate('/admin')}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm sm:text-base font-semibold bg-gray-100 text-slate-700 active:scale-95 transition-transform border border-gray-200"
        >
          <Cpu size={18} />
          <span className="hidden sm:inline">기기 선택으로 돌아가기</span>
          <span className="inline sm:hidden">기기</span>
        </button>
        <button 
          onClick={() => {
            sessionStorage.removeItem('isAdmin');
            navigate('/');
          }}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm sm:text-base font-bold bg-red-50 text-red-600 active:scale-95 transition-transform border border-red-100"
        >
          <LogOut size={18} />
          종료
        </button>
      </div>
    </div>
  );
};

export default DashboardHeader;
