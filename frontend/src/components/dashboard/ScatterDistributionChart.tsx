import React from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface ScatterDistributionChartProps {
  data: any[];
  onScatterClick: (data: any) => void;
}

const ScatterDistributionChart: React.FC<ScatterDistributionChartProps> = ({ data, onScatterClick }) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis type="number" dataKey="id" name="시행 순서(ID)" stroke="#6b7280" />
        <YAxis type="number" dataKey="confidence" name="AI 예측 확률" unit="%" stroke="#6b7280" />
        <Tooltip 
          cursor={{ strokeDasharray: '3 3' }} 
          contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
          itemStyle={{ color: '#1e293b', fontWeight: 'bold' }}
        />
        <Scatter 
          name="실패 (Fail)" data={data.filter(d => !d.isSuccess)} fill="#ef4444" 
          onClick={onScatterClick}
          className="focus:outline-none"
        />
        <Scatter 
          name="성공 (Success)" data={data.filter(d => d.isSuccess)} fill="#10b981" 
          onClick={onScatterClick}
          className="focus:outline-none"
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
};

export default ScatterDistributionChart;
