import React from 'react';
import fallbackImage from '@/assets/images/X_sign_character.png';

interface RecordThumbnailProps {
  src?: string;
  alt: string;
  success: boolean;
}

/**
 * RecordThumbnail
 * 개별 기록의 영상 썸네일을 표시하며, 성공 여부에 따른 효과를 적용합니다.
 */
const RecordThumbnail = ({ src, alt, success }: RecordThumbnailProps) => {
  const [imgSrc, setImgSrc] = React.useState(src || fallbackImage);
  const [isError, setIsError] = React.useState(!src);

  // src prop 변경 시 상태 동기화 (반응성 확보)
  React.useEffect(() => {
    setImgSrc(src || fallbackImage);
    setIsError(!src);
  }, [src]);

  const handleError = () => {
    setImgSrc(fallbackImage);
    setIsError(true);
  };

  return (
    <div
      className={`relative w-full aspect-video rounded-[0.6vw] flex items-center justify-center overflow-hidden transition-all duration-500
        ${success 
          ? 'shadow-[0_0_15px_rgba(255,191,0,0.3)] ring-1 ring-yellow-400/30' 
          : 'bg-gray-200'
        }`}
    >
      <div className="relative w-full h-full bg-white rounded-[0.4vw] overflow-hidden flex items-center justify-center">
        <img
          src={imgSrc}
          alt={alt}
          className={`w-full h-full transition-opacity duration-300 ${isError ? 'object-contain p-[12%] opacity-80' : 'object-cover'}`}
          onError={handleError}
        />
      </div>
      {success && <div className="absolute inset-0 bg-gradient-to-tr from-yellow-400/5 to-transparent pointer-events-none" />}
    </div>
  );
};

export default RecordThumbnail;
