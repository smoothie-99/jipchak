import React from 'react';
import { LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const DeviceSelectionHeader: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200 shadow-sm z-header">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
        JIPCHAK <span className="text-blue-600 text-lg font-bold">Admin Portal</span>
      </h1>
      <button 
        onClick={() => {
          sessionStorage.removeItem('isAdmin');
          navigate('/');
        }}
        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold bg-red-50 text-red-600 active:scale-95 transition-transform border border-red-100"
      >
        <LogOut size={18} />
        종료
      </button>
    </div>
  );
};

export default DeviceSelectionHeader;
