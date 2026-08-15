import React, { useRef, useEffect } from 'react';
import { Plus, Search, AlertCircle, StickyNote } from 'lucide-react';

interface DeviceRegistrationFormProps {
  onRegister: (prefix: string, suffix: string, memo: string) => void;
  onOpenRegionModal: () => void;
  error: string;
  setError: (err: string) => void;
  newDevicePrefix: string;
  setNewDevicePrefix: (val: string) => void;
  newDeviceSuffix: string;
  setNewDeviceSuffix: (val: string) => void;
  newDeviceMemo: string;
  setNewDeviceMemo: (val: string) => void;
}

const DeviceRegistrationForm: React.FC<DeviceRegistrationFormProps> = ({
  onRegister, onOpenRegionModal, error, setError,
  newDevicePrefix, setNewDevicePrefix,
  newDeviceSuffix, setNewDeviceSuffix,
  newDeviceMemo, setNewDeviceMemo
}) => {
  const suffixInputRef = useRef<HTMLInputElement>(null);

  // 모달을 통해 값이 채워졌을 때도 포커스가 자동으로 넘어가도록 useEffect 추가
  useEffect(() => {
    if (newDevicePrefix.length === 5 && suffixInputRef.current) {
      suffixInputRef.current.focus();
    }
  }, [newDevicePrefix]);

  const handlePrefixChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.replace(/[^0-9]/g, '').slice(0, 5);
    setNewDevicePrefix(val);
    setError('');
    
    // 5자리가 다 입력되면 뒷자리 칸으로 포커스 이동
    if (val.length === 5 && suffixInputRef.current) {
      suffixInputRef.current.focus();
    }
  };

  const handleSuffixChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.replace(/[^0-9]/g, '').slice(0, 4);
    setNewDeviceSuffix(val);
    setError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRegister(newDevicePrefix, newDeviceSuffix, newDeviceMemo);
  };

  return (
    <div className="bg-white rounded-2xl p-6 md:p-8 shadow-sm border border-gray-200 flex flex-col gap-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-1 h-full bg-blue-500" />
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
          <Plus size={20} className="text-blue-600" /> 신규 기기 등록
        </h3>
        <button 
          type="button"
          onClick={onOpenRegionModal}
          className="flex items-center gap-1 text-sm font-bold text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg active:scale-95 border border-blue-100"
        >
          <Search size={16} /> 지역코드 조회
        </button>
      </div>
      
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 mt-2">
        <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
          {/* 분할된 기기 번호 입력 영역 */}
          <div className="flex items-center gap-2 w-full md:w-auto flex-1">
            <input 
              type="text" 
              value={newDevicePrefix}
              onChange={handlePrefixChange}
              placeholder="앞자리(5자)"
              className={`w-full md:w-32 bg-gray-50 border ${error ? 'border-red-400 focus:ring-red-500' : 'border-gray-300 focus:ring-blue-500'} rounded-xl px-4 py-3 font-bold text-slate-800 outline-none focus:ring-2 transition-all placeholder:text-gray-400 placeholder:font-medium text-center`}
            />
            <span className="text-slate-400 font-bold">-</span>
            <input 
              type="text" 
              ref={suffixInputRef}
              value={newDeviceSuffix}
              onChange={handleSuffixChange}
              placeholder="뒷자리(3~4자)"
              className={`w-full md:w-36 bg-gray-50 border ${error ? 'border-red-400 focus:ring-red-500' : 'border-gray-300 focus:ring-blue-500'} rounded-xl px-4 py-3 font-bold text-slate-800 outline-none focus:ring-2 transition-all placeholder:text-gray-400 placeholder:font-medium text-center`}
            />
          </div>

          {/* 메모 입력 영역 */}
          <div className="w-full md:w-auto flex-1 relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <StickyNote size={18} className="text-gray-400" />
            </div>
            <input 
              type="text" 
              maxLength={12}
              value={newDeviceMemo}
              onChange={(e) => setNewDeviceMemo(e.target.value)}
              placeholder="메모 입력 (선택사항, 예: 1층 로비)"
              className="w-full bg-gray-50 border border-gray-300 focus:ring-blue-500 rounded-xl pl-10 pr-4 py-3 font-bold text-slate-800 outline-none focus:ring-2 transition-all placeholder:text-gray-400 placeholder:font-medium"
            />
          </div>
          
          <button 
            type="submit"
            className="w-full md:w-auto bg-blue-600 text-white font-bold px-6 py-3 rounded-xl active:scale-95 transition-transform whitespace-nowrap"
          >
            등록하기
          </button>
        </div>
      </form>
      {error && (
        <p className="text-red-500 text-sm font-bold flex items-center gap-1">
          <AlertCircle size={16} /> {error}
        </p>
      )}
      <p className="text-xs text-slate-400 mt-1 font-medium">
        * 기기 번호는 [지역코드 5자리]-[기기 식별번호 3~4자리] 형태의 규칙을 따릅니다.
      </p>
    </div>
  );
};

export default DeviceRegistrationForm;
