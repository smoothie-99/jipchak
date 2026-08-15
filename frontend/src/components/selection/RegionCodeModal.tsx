import React from 'react';
import { Search, X } from 'lucide-react';
import regionCodesData from '../../assets/data/regionCodes.json';

const REGION_MAP: Record<string, string> = regionCodesData;

interface RegionCodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectCode?: (code: string) => void;
}

const RegionCodeModal: React.FC<RegionCodeModalProps> = ({ isOpen, onClose, onSelectCode }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-modal flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between p-5 border-b border-gray-100 bg-gray-50">
          <h3 className="text-xl font-black text-slate-800 flex items-center gap-2">
            <Search size={20} className="text-blue-600" /> 지역코드 안내
          </h3>
          <button 
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-lg transition-colors active:scale-95"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-5 max-h-[60vh] overflow-y-auto custom-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-3 text-sm font-bold text-slate-600 border-b border-gray-200">지역명</th>
                <th className="p-3 text-sm font-bold text-slate-600 border-b border-gray-200">지역코드(앞5자리)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(REGION_MAP).map(([code, name]) => (
                <tr 
                  key={code} 
                  className="border-b border-gray-100 hover:bg-blue-50 cursor-pointer transition-colors active:bg-blue-100"
                  onClick={() => {
                    if (onSelectCode) onSelectCode(code);
                    onClose();
                  }}
                >
                  <td className="p-3 font-semibold text-slate-700">{name}</td>
                  <td className="p-3 font-bold text-blue-600">{code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-4 bg-gray-50 border-t border-gray-100">
          <p className="text-xs text-slate-500 font-medium text-center">
            * 위 목록은 대한민국 주요 시/군/구 단위 지역코드입니다.
          </p>
        </div>
      </div>
    </div>
  );
};

export default RegionCodeModal;
