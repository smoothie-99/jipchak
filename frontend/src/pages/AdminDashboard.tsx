import { useState, useMemo, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Menu, XCircle, BarChart3, Target } from 'lucide-react'; 

import DashboardHeader from '../components/dashboard/DashboardHeader';
import Pagination from '../components/dashboard/Pagination';
import ProbabilityChart from '../components/dashboard/ProbabilityChart';
import ScatterDistributionChart from '../components/dashboard/ScatterDistributionChart';
import OutlierLogTable from '../components/dashboard/OutlierLogTable';

// --- MOCK DATA ---
const MOCK_KPI = {
  totalPlays: 1540,
  winRate: 34.5,
  aiAccuracy: 88.2 
};

// 수백 개의 대규모 Mock 데이터 동적 생성 (ID 시간 동기화)
const MOCK_OUTLIERS = (() => {
  const rawData = Array.from({ length: 250 }).map(() => {
    const isLiftSuccess = Math.random() > 0.4;
    const dropProbability = 20; 
    
    // 성공 조건: 들어올리기 성공 && 놓칠 확률(20%)을 무사히 통과함
    const isSuccess = isLiftSuccess && (Math.random() * 100 > dropProbability);
    
    // 기본적으로 성공하면 확률이 높고, 실패하면 확률이 낮게 분포
    let confidence = isSuccess 
      ? 50 + Math.random() * 50
      : Math.random() * 60;

    // 극단적 이상치 생성
    if (Math.random() < 0.05) confidence = isSuccess ? Math.random() * 15 : 85 + Math.random() * 15;

    // 날짜 랜덤 생성 (과거로)
    const randomTime = new Date(Date.now() - Math.floor(Math.random() * 10000000000));
    
    return {
      timestamp: randomTime.toISOString().replace('T', ' ').slice(0, 19),
      confidence,
      dropProbability,
      isSuccess,
      timestampValue: randomTime.getTime()
    };
  });

  // 시간순으로 오름차순 정렬 (과거 -> 최신) 한 뒤 ID를 1부터 순차적으로 부여
  rawData.sort((a, b) => a.timestampValue - b.timestampValue);
  
  return rawData.map((data, index) => ({
    ...data,
    id: index + 1
  }));
})();

// 누적 막대 차트를 위한 확률 구간별 데이터 계산
const MOCK_BAR_DATA = [
  { range: '0~20%', key: '0-20', success: 0, fail: 0 },
  { range: '20~40%', key: '20-40', success: 0, fail: 0 },
  { range: '40~60%', key: '40-60', success: 0, fail: 0 },
  { range: '60~80%', key: '60-80', success: 0, fail: 0 },
  { range: '80~100%', key: '80-100', success: 0, fail: 0 },
];

MOCK_OUTLIERS.forEach(item => {
  let bucket = 0;
  if (item.confidence > 80) bucket = 4;
  else if (item.confidence > 60) bucket = 3;
  else if (item.confidence > 40) bucket = 2;
  else if (item.confidence > 20) bucket = 1;
  else bucket = 0;

  if (item.isSuccess) MOCK_BAR_DATA[bucket].success++;
  else MOCK_BAR_DATA[bucket].fail++;
});

type SortOption = 'latest' | 'oldest' | 'high_conf' | 'low_conf';

const AdminDashboard = () => {
  const { deviceId } = useParams<{ deviceId: string }>();
  
  const [activeTab, setActiveTab] = useState<'overview'|'logs'>('overview');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [chartType, setChartType] = useState<'bar'|'scatter'>('bar');

  // 필터링 및 정렬 상태
  const [sortOption, setSortOption] = useState<SortOption>('latest');
  const [resultFilter, setResultFilter] = useState<'all'|'success'|'fail'>('all');
  const [outlierFilter, setOutlierFilter] = useState<'all'|'high_fail'|'low_success'>('all');
  const [rangeFilter, setRangeFilter] = useState<'all'|'0-20'|'20-40'|'40-60'|'60-80'|'80-100'>('all');

  // 특정 ID 직접 검색 (산점도 클릭 시)
  const [searchTargetId, setSearchTargetId] = useState<number | null>(null);

  // 페이지네이션 상태
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 20;

  // 어드민 권한 체크는 App.tsx 의 <AdminRoute> 에서 일괄 처리.

  // --- 차트 인터랙션 핸들러 ---
  
  // 1. 막대 차트 클릭
  const handleBarClick = (data: any, type: 'success' | 'fail') => {
    if (!data) return;

    const clickedRangeKey = data.key; // "0-20" 등

    // 필터 세팅
    setRangeFilter(clickedRangeKey);
    setResultFilter(type);
    
    setSearchTargetId(null);
    setActiveTab('logs');
  };

  // 2. 산점도 점 클릭
  const handleScatterClick = (data: any) => {
    // Recharts onClick on Scatter returns an object. data.payload contains the item.
    if (data && data.payload) {
      setSearchTargetId(data.payload.id);
      setActiveTab('logs');
    }
  };

  const clearSearchTarget = () => {
    setSearchTargetId(null);
  };

  // 1. 필터링 로직
  const filteredData = useMemo(() => {
    // 특정 ID 검색이 최우선
    if (searchTargetId !== null) {
      return MOCK_OUTLIERS.filter(item => item.id === searchTargetId);
    }

    return MOCK_OUTLIERS.filter(item => {
      // 결과 필터
      if (resultFilter === 'success' && !item.isSuccess) return false;
      if (resultFilter === 'fail' && item.isSuccess) return false;

      // 주목 이상치 필터
      if (outlierFilter === 'high_fail' && !(item.confidence >= 80 && !item.isSuccess)) return false;
      if (outlierFilter === 'low_success' && !(item.confidence <= 20 && item.isSuccess)) return false;

      // 확률 구간 필터
      if (rangeFilter !== 'all') {
        const conf = item.confidence;
        if (rangeFilter === '0-20' && (conf < 0 || conf > 20)) return false;
        if (rangeFilter === '20-40' && (conf <= 20 || conf > 40)) return false;
        if (rangeFilter === '40-60' && (conf <= 40 || conf > 60)) return false;
        if (rangeFilter === '60-80' && (conf <= 60 || conf > 80)) return false;
        if (rangeFilter === '80-100' && (conf <= 80 || conf > 100)) return false;
      }

      return true;
    });
  }, [resultFilter, outlierFilter, rangeFilter, searchTargetId]);

  // 2. 정렬 로직
  const sortedData = useMemo(() => {
    const list = [...filteredData];
    switch (sortOption) {
      case 'latest': return list.sort((a, b) => b.timestampValue - a.timestampValue);
      case 'oldest': return list.sort((a, b) => a.timestampValue - b.timestampValue);
      case 'high_conf': return list.sort((a, b) => b.confidence - a.confidence);
      case 'low_conf': return list.sort((a, b) => a.confidence - b.confidence);
      default: return list;
    }
  }, [filteredData, sortOption]);

  // 3. 페이지네이션 로직
  const totalPages = Math.max(1, Math.ceil(sortedData.length / ITEMS_PER_PAGE));
  const currentData = sortedData.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);

  // 필터가 변경되면 1페이지로 리셋
  useEffect(() => {
    setCurrentPage(1);
  }, [sortOption, resultFilter, outlierFilter, rangeFilter, searchTargetId]);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  return (
    <div 
      className="flex flex-col md:flex-row w-full h-screen bg-[#fdfbf7] text-slate-800 overflow-hidden font-pretendard"
      onContextMenu={(e) => e.preventDefault()}
    >
      <style>
        {`
          /* Recharts 포커스 아웃라인 제거 */
          .recharts-wrapper *:focus {
            outline: none !important;
          }
        `}
      </style>
      
      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-overlay md:hidden" 
          onClick={toggleSidebar} 
        />
      )}

      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-modal w-64 bg-white border-r border-gray-200 shadow-xl flex flex-col transform transition-transform duration-300 md:relative md:translate-x-0 ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex flex-col">
            JIPCHAK <span className="text-blue-600 text-sm font-semibold mt-1">Admin Portal</span>
          </h1>
          <button className="md:hidden p-2 text-gray-500 active:scale-95" onClick={toggleSidebar}>
            <Menu size={24} />
          </button>
        </div>
        
        <div className="flex flex-col gap-2 p-4 flex-1">
          <button 
            onClick={() => { setActiveTab('overview'); setIsSidebarOpen(false); }}
            className={`text-left px-4 py-3 rounded-lg font-bold text-lg transition-colors active:scale-95 ${
              activeTab === 'overview' ? 'bg-blue-50 text-blue-700 shadow-sm border border-blue-100' : 'text-slate-500 bg-transparent'
            }`}
          >
            📊 통계 뷰
          </button>
          <button 
            onClick={() => { setActiveTab('logs'); setIsSidebarOpen(false); }}
            className={`text-left px-4 py-3 rounded-lg font-bold text-lg transition-colors active:scale-95 ${
              activeTab === 'logs' ? 'bg-blue-50 text-blue-700 shadow-sm border border-blue-100' : 'text-slate-500 bg-transparent'
            }`}
          >
            📋 이상치 로그
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative">
        
        {/* Top Header Extracted */}
        <DashboardHeader deviceId={deviceId} toggleSidebar={toggleSidebar} />

        {/* Scrollable Area */}
        <div className="flex-1 w-full h-full p-4 md:p-8 overflow-y-auto overflow-x-hidden custom-scrollbar">
          
          {activeTab === 'overview' && (
            <div className="flex flex-col h-full gap-4 md:gap-8 max-w-7xl mx-auto">
              {/* KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-8">
                <div className="bg-white rounded-2xl p-6 flex flex-col justify-center shadow-md border border-gray-100">
                  <span className="text-slate-500 text-sm md:text-base font-medium mb-2">총 시행 횟수</span>
                  <span className="text-slate-900 text-2xl md:text-4xl font-black">{MOCK_KPI.totalPlays.toLocaleString()}회</span>
                </div>
                <div className="bg-white rounded-2xl p-6 flex flex-col justify-center shadow-md border border-gray-100">
                  <span className="text-slate-500 text-sm md:text-base font-medium mb-2">종합 성공률</span>
                  <span className="text-green-600 text-2xl md:text-4xl font-black">{MOCK_KPI.winRate}%</span>
                </div>
                <div className="bg-white rounded-2xl p-6 flex flex-col justify-center shadow-md border border-gray-100 relative overflow-hidden">
                  <span className="text-slate-500 text-sm md:text-base font-medium mb-2 z-header">AI 예측 적중률</span>
                  <span className="text-blue-600 text-2xl md:text-4xl font-black z-header">{MOCK_KPI.aiAccuracy}%</span>
                </div>
              </div>

              {/* Chart Container */}
              <div className="flex-1 min-h-[400px] bg-white rounded-2xl p-4 md:p-8 flex flex-col shadow-md border border-gray-100">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
                  <h2 className="text-slate-900 text-xl md:text-2xl font-bold flex items-center gap-2">
                    AI 신뢰도 분석
                  </h2>
                  
                  {/* Chart Toggle Buttons */}
                  <div className="flex bg-gray-100 p-1 rounded-lg">
                    <button 
                      onClick={() => setChartType('bar')}
                      className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-bold transition-colors ${chartType === 'bar' ? 'bg-white shadow-sm text-blue-600' : 'text-slate-500'}`}
                    >
                      <BarChart3 size={16} /> 막대 차트
                    </button>
                    <button 
                      onClick={() => setChartType('scatter')}
                      className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-bold transition-colors ${chartType === 'scatter' ? 'bg-white shadow-sm text-blue-600' : 'text-slate-500'}`}
                    >
                      <Target size={16} /> 산점도
                    </button>
                  </div>
                </div>
                
                <p className="text-slate-400 text-sm mb-4">
                  ※ 차트의 막대(색상 부분)나 산점도의 점을 클릭하면 해당 데이터의 로그 목록으로 바로 이동합니다.
                </p>

                <div className="flex-1 w-full h-full cursor-pointer overflow-hidden">
                  {chartType === 'bar' ? (
                    <ProbabilityChart data={MOCK_BAR_DATA} onBarClick={handleBarClick} />
                  ) : (
                    <ScatterDistributionChart data={MOCK_OUTLIERS} onScatterClick={handleScatterClick} />
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="flex flex-col h-full bg-white rounded-2xl p-4 md:p-8 shadow-md border border-gray-100 max-w-7xl mx-auto min-h-[600px]">
              <h2 className="text-slate-900 text-xl md:text-2xl font-bold mb-4">
                이상치 (Edge Cases) 이미지 로그
              </h2>
              
              {/* ID 검색 배너 */}
              {searchTargetId !== null && (
                <div className="flex items-center justify-between bg-blue-50 border border-blue-200 p-4 rounded-xl mb-4">
                  <span className="text-blue-800 font-bold">
                    🎯 차트에서 선택한 특정 데이터 (ID: #{searchTargetId})를 조회 중입니다.
                  </span>
                  <button 
                    onClick={clearSearchTarget}
                    className="flex items-center gap-1 bg-white text-blue-600 px-3 py-1.5 rounded-lg font-bold border border-blue-200 active:scale-95"
                  >
                    <XCircle size={18} /> 목록으로 돌아가기
                  </button>
                </div>
              )}

              {/* Advanced Filter Bar */}
              <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6 bg-gray-50 p-4 rounded-xl border border-gray-200 ${searchTargetId !== null ? 'opacity-50 pointer-events-none' : ''}`}>
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-bold text-slate-500">정렬 기준</label>
                  <select value={sortOption} onChange={(e) => setSortOption(e.target.value as SortOption)} className="bg-white border border-gray-300 rounded-md px-3 py-2 text-sm font-medium outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="latest">최신순</option>
                    <option value="oldest">오래된순</option>
                    <option value="high_conf">AI 확률 높은순</option>
                    <option value="low_conf">AI 확률 낮은순</option>
                  </select>
                </div>
                
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-bold text-slate-500">결과 필터</label>
                  <select value={resultFilter} onChange={(e) => setResultFilter(e.target.value as any)} className="bg-white border border-gray-300 rounded-md px-3 py-2 text-sm font-medium outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="all">전체 (성공+실패)</option>
                    <option value="success">성공만</option>
                    <option value="fail">실패만</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-xs font-bold text-slate-500">확률 구간 필터</label>
                  <select value={rangeFilter} onChange={(e) => setRangeFilter(e.target.value as any)} className="bg-white border border-gray-300 rounded-md px-3 py-2 text-sm font-medium outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="all">전체 확률</option>
                    <option value="0-20">0% ~ 20%</option>
                    <option value="20-40">20% ~ 40%</option>
                    <option value="40-60">40% ~ 60%</option>
                    <option value="60-80">60% ~ 80%</option>
                    <option value="80-100">80% ~ 100%</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-xs font-bold text-slate-500">주목 이상치 필터</label>
                  <select value={outlierFilter} onChange={(e) => setOutlierFilter(e.target.value as any)} className="bg-white border border-gray-300 rounded-md px-3 py-2 text-sm font-medium outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="all">전체 보기</option>
                    <option value="high_fail">🔥 높은 확률 실패</option>
                    <option value="low_success">🍀 낮은 확률 성공</option>
                  </select>
                </div>
              </div>

              {/* Table Extracted */}
              <OutlierLogTable currentData={currentData} />

              {/* Pagination Extracted */}
              <Pagination 
                currentPage={currentPage} 
                totalPages={totalPages} 
                onPageChange={setCurrentPage} 
              />

            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
