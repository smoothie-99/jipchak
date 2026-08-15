import { useEffect, useRef, useState } from 'react';
import { useToolStore } from '@/store/toolStore';
import { DetectionItem, GraspPose, useStreamStore } from '@/store/streamStore';
import type { StreamState } from '@/store/streamStore';
import Thermometer from './Thermometer';
import { useAudio } from '@/hooks/useAudio';
import { SOUND_ASSETS } from '@/constants/soundConfig';

interface CameraViewProps {
  label: string;
  channel: '2d' | '3d';
  isMainView?: boolean;
  onClick?: () => void;
  className?: string;
}

const CameraView = ({
  label,
  channel,
  isMainView = false,
  onClick,
  className = '',
}: CameraViewProps) => {
  const {
    addRecord,
    setCatching,
    setLastResult,
    startSession,
    setSessionId,
    forceStopGame,
    isSessionActive,
    setMaxGames,
  } = useToolStore();

  const lastProcessedTs = useRef<number>(0);
  const latestFrameRef = useRef<string | null>(null);
  const { playSfx } = useAudio();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const frameUrl = useStreamStore((s: StreamState) => (channel === '2d' ? s.frame2d : s.frame3d));
  const connected = useStreamStore((s: StreamState) => s.connected);
  const graspScore = useStreamStore((s: StreamState) => s.graspScore);
  const detections = useStreamStore((s: StreamState) => s.detections);
  const graspPose = useStreamStore((s: StreamState) => s.graspPose);
  const lastSessionEvent = useStreamStore((s: StreamState) => s.lastSessionEvent);

  const hasDetection = graspPose !== null || detections.length > 0;
  const currentProbability = hasDetection ? Math.min((graspScore ?? 0) * 1000, 90) : 0;

  // 타이머 작동 상태, 집게 하강 상태, 화면에 표시할 확률값 관리
  const [timerStarted, setTimerStarted] = useState(false);
  const [grabStarted, setGrabStarted] = useState(false);
  const [displayProbability, setDisplayProbability] = useState(0);
  const [returnMaskVisible, setReturnMaskVisible] = useState(false);

  // 매 AI 추론마다 detections/graspPose 가 갱신되면 canvas useEffect 가 재실행되어
  // 새 Image() + onload 대기 + redraw 가 frame 그리기와 race → 떨림 / jitter.
  // 최신 값을 ref 로만 추적하여 useEffect 는 frameUrl/channel/grabStarted 변경 시에만 재실행.
  const detectionsRef = useRef(detections);
  const graspPoseRef = useRef(graspPose);
  useEffect(() => { detectionsRef.current = detections; }, [detections]);
  useEffect(() => { graspPoseRef.current = graspPose; }, [graspPose]);

  const lastUiEvent = useStreamStore((s: StreamState) => s.lastUiEvent);
  const lastStartTs = useRef<number | null>(null);
  const lastGrabTs = useRef<number | null>(null);

  useEffect(() => {
    latestFrameRef.current = frameUrl ?? null;
  }, [frameUrl]);

  // 세션 이벤트에 따라 상태 초기화 (게임 리셋 및 다음 판 전환 시 게이지바 0)
  useEffect(() => {
    if (lastSessionEvent?.type === 'SESSION_END') {
      setTimerStarted(false);
      setGrabStarted(false);
      setReturnMaskVisible(false);
      setDisplayProbability(0);
      return;
    }

    if (
      lastSessionEvent?.type === 'SESSION_START' ||
      lastSessionEvent?.type === 'GAME_RESULT'
    ) {
      setTimerStarted(false);
      setDisplayProbability(0);
    }
  }, [lastSessionEvent?.type, lastSessionEvent?.session_id]);

  // UI 이벤트 감지 (타이머 시작 / 집게 하강 개시)
  useEffect(() => {
    if (!lastUiEvent) return;
    if (lastUiEvent.type === 'ROUND_TIMER_START') {
      if (lastStartTs.current === lastUiEvent.ts) return;
      lastStartTs.current = lastUiEvent.ts;
      setTimerStarted(true);
      setGrabStarted(false);
      setReturnMaskVisible(false);
    }
    if (lastUiEvent.type === 'GRAB_START') {
      if (lastGrabTs.current === lastUiEvent.ts) return;
      lastGrabTs.current = lastUiEvent.ts;
      setTimerStarted(false);
      setGrabStarted(true);
      setReturnMaskVisible(true);
    }
  }, [lastUiEvent]);

  // 타이머가 시작되었고 아직 집게 하강 전인 경우에만 확률 게이지를 실시간으로 업데이트
  useEffect(() => {
    if (timerStarted && !grabStarted) {
      setDisplayProbability(currentProbability);
    }
  }, [currentProbability, timerStarted, grabStarted]);

  useEffect(() => {
    if (!lastSessionEvent || !isMainView) return;

    if (lastSessionEvent.ts && lastProcessedTs.current === lastSessionEvent.ts) return;
    if (lastSessionEvent.ts) lastProcessedTs.current = lastSessionEvent.ts;

    if (lastSessionEvent.type === 'SESSION_START') {
      const sid = lastSessionEvent.session_id;
      if (!sid) return;

      // GameCountModal 비활성화로 인해 판수를 2판 고정 설정
      setMaxGames(2);

      if (!isSessionActive) {
        startSession(sid);
      } else {
        setSessionId(sid);
      }

      setCatching(true);
      setLastResult(null);
      playSfx(SOUND_ASSETS.SFX.TRY_CATCH);
      return;
    }

    if (lastSessionEvent.type === 'GAME_RESULT') {
      setCatching(false);
      const isWin = lastSessionEvent.is_caught ?? false;
      setLastResult(isWin ? 'win' : 'lose');

      const now = new Date();
      const pad = (n: number) => String(n).padStart(2, '0');
      const yy = String(now.getFullYear()).slice(-2);
      const filename = [
        yy,
        pad(now.getMonth() + 1),
        pad(now.getDate()),
        '_',
        pad(now.getHours()),
        pad(now.getMinutes()),
        pad(now.getSeconds()),
      ].join('');

      addRecord({
        id: Date.now().toString(),
        filename: `${filename}.mp4`,
        isSuccess: isWin,
        thumbnailUrl: latestFrameRef.current ?? '',
      });

      window.setTimeout(() => setLastResult(null), 3000);
      return;
    }

    if (lastSessionEvent.type === 'SESSION_END') {
      setCatching(false);
      setLastResult(null);

      // 마지막 판인 경우 곧 GAME_RESULT가 올 것이므로 forceStopGame() 호출을 미룹니다.
      // 만약 이전 판(예: 에러나 강제 중단)에 SESSION_END가 왔다면 즉시 이동합니다.
      const currentRecords = useToolStore.getState().records;
      const currentMaxGames = useToolStore.getState().maxGames;
      if (currentRecords.length + 1 < currentMaxGames) {
        forceStopGame();
      } else {
        // 마지막 판의 GAME_RESULT가 올 때까지 최대 5초 대기 (네트워크 지연 대비 안전장치)
        const timeoutId = window.setTimeout(() => {
          const state = useToolStore.getState();
          if (state.viewType !== 'QR_CONSENT') {
            state.forceStopGame();
          }
        }, 5000);
        return () => window.clearTimeout(timeoutId);
      }
    }
  }, [
    lastSessionEvent,
    isMainView,
    isSessionActive,
    startSession,
    setSessionId,
    setCatching,
    setLastResult,
    playSfx,
    addRecord,
    forceStopGame,
    setMaxGames,
  ]);

  useEffect(() => {
    if (!frameUrl || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    let alive = true;

    img.onload = () => {
      if (!alive) return;

      const cw = img.width;
      const ch = img.height;

      if (canvas.width !== cw) canvas.width = cw;
      if (canvas.height !== ch) canvas.height = ch;

      ctx.clearRect(0, 0, cw, ch);

      ctx.save();

      // 렌더링 (원본 그대로 출력)
      ctx.drawImage(img, 0, 0, cw, ch);

      // 최신 detection / graspPose 는 ref 에서 (useEffect 재실행 안 시키려고).
      const curDetections = detectionsRef.current;
      const curGraspPose = graspPoseRef.current;
      if (channel === '3d' && !grabStarted) {
        if (curGraspPose && curGraspPose.confidence > 0) {
          // AI 결과는 원본 이미지 기준 좌표이므로 원래 크기(cw, ch)를 넘겨줌
          drawGraspPose(ctx, curGraspPose, cw, ch);
        } else if (curDetections.length > 0) {
          drawDetections(ctx, curDetections);
        }
      }

      ctx.restore();
    };

    img.src = frameUrl;

    return () => {
      alive = false;
      img.onload = null;
    };
    // detections / graspPose 는 ref 로 빼서 dependency 에서 제거.
    // → frame 도착 시에만 redraw, AI 추론 결과 갱신만으론 redraw 안 함 (다음 frame 에 반영).
  }, [frameUrl, channel, grabStarted]);

  return (
    <div
      className={`w-full h-full bg-black relative flex flex-col items-center justify-center overflow-hidden gap-[4%] ${className}`}
      onClick={onClick}
    >
      {frameUrl && (
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full object-contain select-none pointer-events-none"
        />
      )}

      {!frameUrl && (
        <span className="text-white/20 font-bold text-[clamp(24px,5vw,64px)] select-none uppercase tracking-widest">
          {label}
        </span>
      )}

      {isMainView && returnMaskVisible && (
        <div className="absolute inset-x-0 bottom-0 h-[42%] bg-gradient-to-t from-black via-black to-transparent z-sub pointer-events-none" />
      )}

      <span
        className={`absolute top-2 right-2 w-2 h-2 rounded-full z-overlay ${connected ? 'bg-green-400' : 'bg-red-500'
          }`}
        title={connected ? 'WS connected' : 'WS disconnected'}
      />

      {isMainView && <Thermometer probability={displayProbability} />}
    </div>
  );
};


function drawGraspPose(
  ctx: CanvasRenderingContext2D,
  pose: GraspPose,
  canvasW: number,
  canvasH: number,
): void {
  const sx = pose.image_width > 0 ? canvasW / pose.image_width : 1;
  const sy = pose.image_height > 0 ? canvasH / pose.image_height : 1;
  const cx = pose.center_x * sx;
  const cy = pose.center_y * sy;
  const scale = (sx + sy) / 2;
  const r = Math.max(18, pose.radius * scale);
  const baseAngle = pose.angle_rad - Math.PI / 2;
  const conf = Math.max(0, Math.min(1, pose.confidence));

  const jawCount = 3;
  const tipR = Math.max(34, r * 0.94);
  const hookDepth = Math.max(10, r * 0.18);

  ctx.save();
  ctx.shadowBlur = 10;
  ctx.shadowColor = 'rgba(0, 0, 0, 0.45)';

  const outerRadius = tipR + hookDepth * 0.35;
  drawOuterGuide(ctx, cx, cy, outerRadius, conf);

  for (let i = 0; i < jawCount; i++) {
    const angle = baseAngle + (i * Math.PI * 2) / jawCount;

    // 3발의 집게 위치를 점선 원 위에 찍어주기 (흰색 날개 그리기는 제외)
    const jawX = cx + Math.cos(angle) * outerRadius;
    const jawY = cy + Math.sin(angle) * outerRadius;
    ctx.beginPath();
    ctx.arc(jawX, jawY, 4, 0, Math.PI * 2);
    ctx.fillStyle = 'red';
    ctx.fill();
  }

  // 집게 중심에 아주 작은 빨간색 원
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  ctx.fillStyle = 'red';
  ctx.fill();

  // 중심에 집게로 인형을 뽑을 확률 수치 표시
  ctx.fillStyle = 'white';
  ctx.font = 'bold 80px Arial';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(`${Math.min(pose.confidence * 1000, 90).toFixed(0)}`, cx, cy);

  ctx.restore();
}

function drawOuterGuide(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  confidence: number,
): void {
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.strokeStyle = getThermometerColor(confidence, 0.72);
  ctx.lineWidth = 4;
  ctx.setLineDash([12, 10]);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawDetections(
  ctx: CanvasRenderingContext2D,
  detections: DetectionItem[],
): void {
  if (detections.length === 0) return;

  const best = detections.reduce((a, b) =>
    a.grasp_confidence > b.grasp_confidence ? a : b,
  );

  for (const det of detections) {
    const [xmin, ymin, xmax, ymax] = det.bbox;
    const isBest = det === best;

    ctx.strokeStyle = isBest ? getThermometerColor(det.grasp_confidence) : 'rgba(255, 255, 255, 0.5)';
    ctx.lineWidth = isBest ? 3 : 2;
    ctx.setLineDash(isBest ? [] : [6, 4]);
    ctx.strokeRect(xmin, ymin, xmax - xmin, ymax - ymin);
    ctx.setLineDash([]);

    const text = `${Math.min(det.grasp_confidence * 1000, 90).toFixed(0)}%`;
    ctx.font = 'bold 14px Arial';
    const tw = ctx.measureText(text).width;
    ctx.fillStyle = isBest ? getThermometerColor(det.grasp_confidence, 0.8) : 'rgba(0, 0, 0, 0.6)';
    ctx.fillRect(xmin, ymin - 20, tw + 8, 20);
    ctx.fillStyle = 'white';
    ctx.fillText(text, xmin + 4, ymin - 5);

    if (!isBest && Array.isArray(det.grasp_center_px) && det.grasp_center_px.length >= 2) {
      const [gx, gy] = det.grasp_center_px as [number, number];
      ctx.beginPath();
      ctx.arc(gx, gy, 4, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255, 255, 0, 0.6)';
      ctx.fill();
      ctx.strokeStyle = 'white';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  if (Array.isArray(best.grasp_center_px) && best.grasp_center_px.length >= 2) {
    const [gx, gy] = best.grasp_center_px as [number, number];
    ctx.beginPath();
    ctx.arc(gx, gy, 6, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 50, 50, 0.9)';
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
  ctx.fillRect(8, 8, 190, 28);
  ctx.fillStyle = 'white';
  ctx.font = 'bold 14px Arial';
  ctx.textAlign = 'left';
  ctx.fillText(
    `Best: ${Math.min(best.grasp_confidence * 1000, 90).toFixed(1)}%  (${detections.length} obj)`,
    14,
    27,
  );
}

export default CameraView;

// ─────────────────────────────────────────
// 헬퍼: 온도계 컴포넌트와 동일한 색상 보간 (Blue -> Green -> Yellow -> Red)
// ─────────────────────────────────────────
function getThermometerColor(confidence: number, alpha: number = 1): string {
  const v = Math.min(confidence * 1000, 90);
  let r, g, b;
  if (v <= 30) {
    const p = v / 30;
    r = 59 + (34 - 59) * p;
    g = 130 + (197 - 130) * p;
    b = 246 + (94 - 246) * p;
  } else if (v <= 60) {
    const p = (v - 30) / 30;
    r = 34 + (234 - 34) * p;
    g = 197 + (179 - 197) * p;
    b = 94 + (8 - 94) * p;
  } else if (v <= 90) {
    const p = (v - 60) / 30;
    r = 234 + (239 - 234) * p;
    g = 179 + (68 - 179) * p;
    b = 8 + (68 - 8) * p;
  } else {
    r = 239; g = 68; b = 68;
  }
  return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${alpha})`;
}
