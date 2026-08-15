import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cpu, Star, Search } from 'lucide-react';

import DeviceSelectionHeader from '../components/selection/DeviceSelectionHeader';
import RegionCodeModal from '../components/selection/RegionCodeModal';
import DeviceRegistrationForm from '../components/selection/DeviceRegistrationForm';
import DeviceCard, { DeviceInfo } from '../components/selection/DeviceCard';

const MOCK_DEVICES: DeviceInfo[] = [
  { id: '11680-001', registeredAt: '2026-05-01 10:00:00', isFavorite: true, memo: '1층 로비' },
  { id: '47190-002', registeredAt: '2026-05-10 14:30:00', isFavorite: false, memo: '오락실 구석' },
];

const AdminDeviceSelection = () => {
  const navigate = useNavigate();
  const [devices, setDevices] = useState<DeviceInfo[]>(MOCK_DEVICES);
  
  // 분할된 입력 상태
  const [newDevicePrefix, setNewDevicePrefix] = useState('');
  const [newDeviceSuffix, setNewDeviceSuffix] = useState('');
  const [newDeviceMemo, setNewDeviceMemo] = useState('');
  
  const [error, setError] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 어드민 권한 체크는 App.tsx 의 <AdminRoute> 에서 일괄 처리.

  const handleRegister = (prefix: string, suffix: string, memo: string) => {
    setError('');

    // Validation: Prefix 5 digits, Suffix 3~4 digits
    if (prefix.length !== 5) {
      setError('지역코드(앞자리)는 5자리 숫자여야 합니다.');
      return;
    }
    
    if (suffix.length < 3 || suffix.length > 4) {
      setError('기기 일련번호(뒷자리)는 3~4자리 숫자여야 합니다.');
      return;
    }

    const newDeviceId = `${prefix}-${suffix}`;

    if (devices.some(d => d.id === newDeviceId)) {
      setError('이미 등록된 기기 번호입니다.');
      return;
    }

    const newDevice: DeviceInfo = {
      id: newDeviceId,
      registeredAt: new Date().toISOString().replace('T', ' ').slice(0, 19),
      isFavorite: false,
      memo: memo.trim() || undefined
    };

    setDevices([newDevice, ...devices]);
    setNewDevicePrefix('');
    setNewDeviceSuffix('');
    setNewDeviceMemo('');
  };

  const handleSelectDevice = (id: string) => {
    navigate(`/admin/dashboard/${id}`);
  };

  const toggleFavorite = (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); 
    setDevices(devices.map(d => 
      d.id === id ? { ...d, isFavorite: !d.isFavorite } : d
    ));
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); 
    if (window.confirm(`정말 ${id} 기기를 삭제하시겠습니까?\n삭제 후에는 복구할 수 없습니다.`)) {
      setDevices(devices.filter(d => d.id !== id));
    }
  };

  const handleEditMemo = (e: React.MouseEvent, id: string, currentMemo: string = '') => {
    e.stopPropagation();
    const newMemo = window.prompt(`[${id}] 기기의 새로운 메모를 입력하세요 (최대 12자):`, currentMemo);
    if (newMemo !== null) {
      if (newMemo.length > 12) {
        alert('메모는 최대 12자까지만 입력 가능합니다.');
        return;
      }
      setDevices(devices.map(d => 
        d.id === id ? { ...d, memo: newMemo.trim() || undefined } : d
      ));
    }
  };

  const favoriteDevices = devices.filter(d => d.isFavorite);
  const normalDevices = devices.filter(d => !d.isFavorite);

  return (
    <div 
      className="flex flex-col w-full min-h-screen bg-[#fdfbf7] text-slate-800 font-pretendard"
    >
      <RegionCodeModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onSelectCode={(code) => {
          setNewDevicePrefix(code);
          setError('');
        }}
      />

      <DeviceSelectionHeader />

      <div className="flex-1 w-full max-w-5xl mx-auto p-6 md:p-10 flex flex-col gap-8">
        
        {/* Title */}
        <div className="flex flex-col gap-2">
          <h2 className="text-3xl font-black text-slate-900 flex items-center gap-3">
            <Cpu className="text-blue-600" size={32} /> 기기 선택 및 관리
          </h2>
          <p className="text-slate-500 font-medium">
            대시보드를 확인할 기기를 선택하거나 새로운 기기를 등록하세요.
          </p>
        </div>

        {/* Registration Form */}
        <DeviceRegistrationForm 
          onRegister={handleRegister}
          onOpenRegionModal={() => setIsModalOpen(true)}
          error={error}
          setError={setError}
          newDevicePrefix={newDevicePrefix}
          setNewDevicePrefix={setNewDevicePrefix}
          newDeviceSuffix={newDeviceSuffix}
          setNewDeviceSuffix={setNewDeviceSuffix}
          newDeviceMemo={newDeviceMemo}
          setNewDeviceMemo={setNewDeviceMemo}
        />

        {/* Favorite Devices */}
        {favoriteDevices.length > 0 && (
          <div className="flex flex-col gap-4">
            <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <Star size={20} className="text-yellow-500 fill-yellow-500" /> 즐겨찾는 기기 ({favoriteDevices.length})
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {favoriteDevices.map((device) => (
                <DeviceCard 
                  key={device.id}
                  device={device}
                  onSelect={handleSelectDevice}
                  onToggleFavorite={toggleFavorite}
                  onDelete={handleDelete}
                  onEditMemo={handleEditMemo}
                />
              ))}
            </div>
          </div>
        )}

        {/* All Devices */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <Search size={20} className="text-blue-600" /> 등록된 전체 기기 ({normalDevices.length})
            </h3>
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {normalDevices.map((device) => (
              <DeviceCard 
                key={device.id}
                device={device}
                onSelect={handleSelectDevice}
                onToggleFavorite={toggleFavorite}
                onDelete={handleDelete}
                onEditMemo={handleEditMemo}
              />
            ))}
          </div>

          {normalDevices.length === 0 && devices.length === 0 && (
            <div className="bg-white rounded-2xl p-10 shadow-sm border border-gray-200 flex flex-col items-center justify-center text-center gap-3 mt-4">
              <Cpu size={48} className="text-gray-300" />
              <p className="text-slate-500 font-bold text-lg">등록된 기기가 없습니다.</p>
              <p className="text-slate-400 text-sm">상단에서 새로운 기기를 등록해주세요.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDeviceSelection;
