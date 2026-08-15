import React from 'react';
import { Star, Trash2, Edit2, MapPin } from 'lucide-react';

import regionCodesData from '../../assets/data/regionCodes.json';
const REGION_MAP: Record<string, string> = regionCodesData;

export interface DeviceInfo {
  id: string; // e.g., "47190-002"
  registeredAt: string;
  isFavorite?: boolean;
  memo?: string;
}

interface DeviceCardProps {
  device: DeviceInfo;
  onSelect: (id: string) => void;
  onToggleFavorite: (e: React.MouseEvent, id: string) => void;
  onDelete: (e: React.MouseEvent, id: string) => void;
  onEditMemo: (e: React.MouseEvent, id: string, currentMemo: string) => void;
}

const DeviceCard: React.FC<DeviceCardProps> = ({
  device, onSelect, onToggleFavorite, onDelete, onEditMemo
}) => {
  const getRegionName = (id: string) => {
    const code = id.split('-')[0];
    return REGION_MAP[code] || '알 수 없는 지역';
  };

  return (
    <div 
      onClick={() => onSelect(device.id)}
      className={`bg-white rounded-2xl p-6 shadow-sm border ${device.isFavorite ? 'border-yellow-200' : 'border-gray-200'} flex flex-col gap-3 cursor-pointer active:scale-95 transition-transform group relative`}
    >
      <div className="flex items-center justify-between min-h-[32px]">
        {device.memo ? (
          <span className="bg-gray-100 text-slate-600 text-xs font-bold px-2 py-1 rounded-md border border-gray-200 truncate max-w-[150px]">
            {device.memo}
          </span>
        ) : (
          <div />
        )}
        <div className="flex items-center gap-2">
          <button 
            onClick={(e) => onEditMemo(e, device.id, device.memo || '')}
            className="p-1.5 text-gray-300 hover:text-blue-500 hover:bg-blue-50 rounded-md transition-colors"
            title="메모 수정"
          >
            <Edit2 size={18} />
          </button>
          <button 
            onClick={(e) => onDelete(e, device.id)}
            className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
            title="기기 삭제"
          >
            <Trash2 size={18} />
          </button>
          <button 
            onClick={(e) => onToggleFavorite(e, device.id)}
            className={`p-1.5 rounded-md transition-colors ${device.isFavorite ? 'text-yellow-500 hover:bg-yellow-50' : 'text-gray-300 hover:text-yellow-500 hover:bg-yellow-50'}`}
          >
            <Star size={20} className={device.isFavorite ? 'fill-yellow-500' : ''} />
          </button>
        </div>
      </div>
      
      <div className="flex flex-col mt-2">
        <span className="text-xs font-bold text-slate-400 mb-1">기기 번호 (Serial ID)</span>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-black text-slate-900 tracking-tight">{device.id}</span>
        </div>
      </div>
      
      <div className="flex items-center gap-1 text-slate-600 bg-gray-50 px-3 py-2 rounded-lg mt-1 border border-gray-100">
        <MapPin size={16} className="text-blue-500" />
        <span className="text-sm font-bold">{getRegionName(device.id)}</span>
      </div>

      <div className="pt-4 mt-2 border-t border-gray-100 flex justify-between items-center text-xs">
        <span className="text-slate-400 font-medium">최초 등록일</span>
        <span className="text-slate-600 font-bold">{device.registeredAt.split(' ')[0]}</span>
      </div>
    </div>
  );
};

export default DeviceCard;
