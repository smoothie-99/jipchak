import React from 'react';
import { Image as ImageIcon } from 'lucide-react';

interface OutlierLogTableProps {
  currentData: any[];
}

const OutlierLogTable: React.FC<OutlierLogTableProps> = ({ currentData }) => {
  return (
    <div className="flex-1 overflow-x-auto min-h-[400px]">
      <table className="w-full text-left border-collapse min-w-[700px]">
        <thead className="bg-gray-50 border-y border-gray-200">
          <tr className="text-slate-500 text-sm">
            <th className="p-3 font-semibold">ID</th>
            <th className="p-3 font-semibold">시간</th>
            <th className="p-3 font-semibold">AI 예측 확률</th>
            <th className="p-3 font-semibold text-center">놓칠 확률</th>
            <th className="p-3 font-semibold text-center">실제 결과</th>
            <th className="p-3 font-semibold text-center">파지 이미지</th>
          </tr>
        </thead>
        <tbody>
          {currentData.map((item) => {
            const isExtreme = (item.confidence >= 80 && !item.isSuccess) || (item.confidence <= 20 && item.isSuccess);
            
            return (
              <tr key={item.id} className={`border-b border-gray-100 transition-colors ${isExtreme ? 'bg-red-50' : 'hover:bg-gray-50 active:bg-gray-50'}`}>
                <td className="p-3 text-slate-400 text-sm font-bold">#{item.id}</td>
                <td className="p-3 text-slate-600 text-sm font-medium">{item.timestamp}</td>
                <td className="p-3">
                  <span className={`text-base font-bold ${item.confidence > 50 ? 'text-green-600' : 'text-red-600'}`}>
                    {item.confidence.toFixed(1)}%
                  </span>
                </td>
                <td className="p-3 text-center">
                  <span className="text-slate-500 text-sm font-bold bg-gray-100 px-2 py-1 rounded">
                    {item.dropProbability}%
                  </span>
                </td>
                <td className="p-3 text-center">
                  <span className={`px-3 py-1 rounded-md font-bold text-xs ${
                    item.isSuccess ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {item.isSuccess ? '성공' : '실패'}
                  </span>
                </td>
                <td className="p-3 text-center">
                  <button className="bg-blue-50 text-blue-600 p-2 rounded-lg hover:bg-blue-100 active:bg-blue-100 active:scale-95 transition-transform border border-blue-200 inline-flex items-center justify-center">
                    <ImageIcon size={18} />
                  </button>
                </td>
              </tr>
            );
          })}
          {currentData.length === 0 && (
            <tr>
              <td colSpan={6} className="p-8 text-center text-slate-500 font-medium">
                조건에 맞는 데이터가 없습니다. 필터를 변경해 보세요.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default OutlierLogTable;
