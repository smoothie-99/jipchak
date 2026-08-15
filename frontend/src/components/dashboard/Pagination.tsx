import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const Pagination: React.FC<PaginationProps> = ({ currentPage, totalPages, onPageChange }) => {
  const [jumpPageInput, setJumpPageInput] = useState<string>(currentPage.toString());

  // currentPage가 외부에서 바뀌면 input도 동기화
  useEffect(() => {
    setJumpPageInput(currentPage.toString());
  }, [currentPage]);

  const handlePageJump = () => {
    const pageNum = parseInt(jumpPageInput, 10);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      onPageChange(pageNum);
    } else {
      setJumpPageInput(currentPage.toString());
    }
  };

  const handlePageKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handlePageJump();
      e.currentTarget.blur();
    }
  };

  const handlePageInputBlur = () => {
    handlePageJump();
  };

  if (totalPages <= 0) return null;

  return (
    <div className="flex flex-wrap justify-center items-center gap-4 mt-6 pt-6 border-t border-gray-100">
      <button 
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
        className="flex items-center gap-1 px-4 py-2 rounded-xl bg-white border border-gray-200 text-slate-700 shadow-sm disabled:opacity-50 disabled:bg-gray-50 disabled:cursor-not-allowed hover:bg-gray-50 active:scale-95 transition-all font-bold"
      >
        <ChevronLeft size={18} /> 이전
      </button>
      
      <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-gray-300 shadow-sm focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
        <input 
          type="text" 
          value={jumpPageInput}
          onChange={(e) => setJumpPageInput(e.target.value.replace(/[^0-9]/g, ''))}
          onBlur={handlePageInputBlur}
          onKeyDown={handlePageKeyDown}
          className="w-12 text-center font-bold text-blue-600 bg-transparent outline-none"
        />
        <span className="text-gray-300">/</span>
        <span className="font-medium text-slate-500 px-2">{totalPages}</span>
      </div>

      <button 
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        className="flex items-center gap-1 px-4 py-2 rounded-xl bg-white border border-gray-200 text-slate-700 shadow-sm disabled:opacity-50 disabled:bg-gray-50 disabled:cursor-not-allowed hover:bg-gray-50 active:scale-95 transition-all font-bold"
      >
        다음 <ChevronRight size={18} />
      </button>
    </div>
  );
};

export default Pagination;
