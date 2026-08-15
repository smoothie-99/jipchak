import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { sessionService } from '../../services/sessionService';

import ExpiredModal from '../../components/mobile/ExpiredModal';
import LandingHeader from '../../components/mobile/LandingHeader';
import VideoCard from '../../components/mobile/VideoCard';

const MobileLanding = () => {
  const { sessionId } = useParams();

  const [videos, setVideos] = useState<any[]>([]);
  const [timeLeft, setTimeLeft] = useState<number>(0);
  const [isExpired, setIsExpired] = useState<boolean>(false);
  const [createdAt, setCreatedAt] = useState<number>(Date.now());

  useEffect(() => {
    if (!sessionId) {
      setIsExpired(true);
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        const data = await sessionService.getSessionVideos(sessionId);
        if (cancelled) return;

        const ttl = Number(data?.timeLeft ?? 0);
        if (ttl <= 0) {
          setVideos([]);
          setTimeLeft(0);
          setIsExpired(true);
          return;
        }

        setVideos(Array.isArray(data?.videos) ? data.videos : []);
        setTimeLeft(ttl);
        setCreatedAt(Date.now());
        setIsExpired(false);
      } catch (error) {
        if (cancelled) return;
        console.error('[MobileLanding] failed to load session videos:', error);
        setVideos([]);
        setTimeLeft(0);
        setIsExpired(true);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    if (isExpired || timeLeft <= 0) {
      if (timeLeft <= 0) setIsExpired(true);
      return;
    }

    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setIsExpired(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isExpired, timeLeft]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const formatFilename = (baseTime: number, index: number) => {
    const date = new Date(baseTime + index * 1000);
    const yy = date.getFullYear().toString().slice(-2);
    const mm = (date.getMonth() + 1).toString().padStart(2, '0');
    const dd = date.getDate().toString().padStart(2, '0');
    const hh = date.getHours().toString().padStart(2, '0');
    const min = date.getMinutes().toString().padStart(2, '0');
    const ss = date.getSeconds().toString().padStart(2, '0');
    return `${yy}${mm}${dd}_${hh}${min}${ss}`;
  };

  const handleDownload = async (url: string, index: number) => {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = blobUrl;
      a.download = `jipchak_${formatFilename(createdAt, index)}.mp4`;
      document.body.appendChild(a);
      a.click();

      window.URL.revokeObjectURL(blobUrl);
      document.body.removeChild(a);
    } catch (error) {
      console.error('[MobileLanding] download failed:', error);
      alert('영상 다운로드에 실패했습니다.');
    }
  };

  return (
    <div
      className="w-full h-[100dvh] bg-crayon-bg text-crayon-line font-crayon overflow-hidden relative flex flex-col items-center"
      onContextMenu={(e) => e.preventDefault()}
    >
      {isExpired ? (
        <ExpiredModal isExpired={isExpired} />
      ) : (
        <div className="w-full h-full max-w-[500px] flex flex-col flex-1 pb-safe relative">
          <LandingHeader timeLeft={timeLeft} formatTime={formatTime} />

          <div className="flex-1 overflow-y-auto px-[5%] pb-[5%] flex flex-col gap-[4%] snap-y snap-mandatory">
            {videos.map((video, index) => (
              <VideoCard
                key={video.id ?? `${index}-${video.url}`}
                video={video}
                index={index}
                filename={formatFilename(createdAt, index)}
                onDownload={handleDownload}
              />
            ))}
            <div className="h-[40px] shrink-0" />
          </div>
        </div>
      )}
    </div>
  );
};

export default MobileLanding;
