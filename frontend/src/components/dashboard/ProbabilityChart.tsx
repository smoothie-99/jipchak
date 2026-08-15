import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface ProbabilityChartProps {
  data: any[];
  onBarClick: (data: any, type: 'success' | 'fail') => void;
}

const ProbabilityChart: React.FC<ProbabilityChartProps> = ({ data, onBarClick }) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart 
        data={data} 
        margin={{ top: 20, right: 30, left: 0, bottom: 5 }} 
        maxBarSize={80}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
        <XAxis dataKey="range" stroke="#6b7280" tick={{ fill: '#6b7280', fontWeight: 500 }} />
        <YAxis stroke="#6b7280" tick={{ fill: '#6b7280', fontWeight: 500 }} />
        <Tooltip 
          cursor={{ fill: '#f3f4f6' }}
          contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
          itemStyle={{ color: '#1e293b', fontWeight: 'bold' }}
        />
        <Legend wrapperStyle={{ paddingTop: '20px', fontWeight: 600, color: '#475569' }} />
        <Bar 
          dataKey="success" name="성공 (Success)" stackId="a" fill="#10b981" radius={[0, 0, 6, 6]} 
          onClick={(data) => onBarClick(data, 'success')}
        />
        <Bar 
          dataKey="fail" name="실패 (Fail)" stackId="a" fill="#ef4444" radius={[6, 6, 0, 0]} 
          onClick={(data) => onBarClick(data, 'fail')}
        />
      </BarChart>
    </ResponsiveContainer>
  );
};

export default ProbabilityChart;
