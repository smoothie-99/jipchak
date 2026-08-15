import { useEffect, useRef, useState } from 'react';
import { decode } from '@msgpack/msgpack';

/**
 * AI 서버가 송출하는 카메라 스트림(/ws/stream)을 구독하여,
 * 매 프레임 JPEG 바이트를 ObjectURL 로 변환해 반환한다.
 *
 * - channel: '2d' = 일반 웹캠(color_2d), '3d' = D435 RGB(color_3d)
 * - 자동 재연결: 끊겼을 때 지수 백오프(최대 5초)
 * - 메모리 관리: 이전 ObjectURL 은 다음 프레임이 도착할 때 즉시 revoke
 *
 * 페이로드 스키마 (RPi의 FramePacker 와 일치):
 *   { timestamp, color_2d?: Uint8Array, color_3d?: Uint8Array, depth_3d?, depth_3d_shape? }
 */

type Channel = '2d' | '3d';

interface DecodedPayload {
    color_2d?: Uint8Array;
    color_3d?: Uint8Array;
    timestamp?: number | bigint;
}

export interface SessionEvent {
    type: 'SESSION_START' | 'GAME_RESULT';
    session_id: string;
    is_caught?: boolean;
    confidence?: number;
}

export interface DetectionItem {
    bbox: number[];           // [xmin, ymin, xmax, ymax]
    label: number;
    det_score: number;
    grasp_confidence: number;
    grasp_center_px: number[]; // [x, y]
    x_mm: number;
    y_mm: number;
    z_mm: number;
}

export interface GraspPose {
    center_x: number;
    center_y: number;
    angle_rad: number;
    radius: number;
    jaw_count: number;
    confidence: number;
    image_width: number;
    image_height: number;
}

export interface CameraStreamState {
    frameUrl: string | null;
    connected: boolean;
    graspScore: number;
    detections: DetectionItem[];
    graspPose: GraspPose | null;
    lastSessionEvent: SessionEvent | null;
}

/**
 * 환경에 따라 ws URL 을 결정한다.
 *  - VITE_WS_STREAM_PATH 가 절대 URL 이면 그대로 사용
 *  - 상대 경로(/ws/stream)면 현재 origin 에 붙여 ws[s]:// 로 변환
 */
function resolveWsUrl(): string {
    const path = (import.meta.env.VITE_WS_STREAM_PATH as string | undefined) ?? '/ws/stream';
    if (/^wss?:\/\//.test(path)) return path;

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}${path}`;
}

export function useCameraStream(channel: Channel): CameraStreamState {
    const [frameUrl, setFrameUrl] = useState<string | null>(null);
    const [connected, setConnected] = useState(false);
    const [graspScore, setGraspScore] = useState(0);
    const [detections, setDetections] = useState<DetectionItem[]>([]);
    const [graspPose, setGraspPose] = useState<GraspPose | null>(null);
    const [lastSessionEvent, setLastSessionEvent] = useState<SessionEvent | null>(null);

    // ObjectURL 누수 방지용: 직전 URL 을 보관해두고 다음 프레임 도착 시 revoke
    const prevUrlRef = useRef<string | null>(null);
    // GRASP_SCORE 이벤트가 일정 시간 안 오면 detection 화면 잔상(ghosting) 방지
    const detectionStaleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const DETECTION_STALE_MS = 1500; // 1.5초간 새 GRASP_SCORE 없으면 클리어

    useEffect(() => {
        const url = resolveWsUrl();
        let ws: WebSocket | null = null;
        let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
        let backoffMs = 500;
        let cancelled = false;

        const armDetectionStaleTimer = () => {
            if (detectionStaleTimerRef.current) {
                clearTimeout(detectionStaleTimerRef.current);
            }
            detectionStaleTimerRef.current = setTimeout(() => {
                setDetections([]);
                setGraspPose(null);
                setGraspScore(0);
            }, DETECTION_STALE_MS);
        };

        const connect = () => {
            if (cancelled) return;

            ws = new WebSocket(url);
            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {
                setConnected(true);
                backoffMs = 500; // 성공 시 백오프 리셋
            };

            ws.onmessage = (event) => {
                // 텍스트 메시지: JSON 이벤트
                if (typeof event.data === 'string') {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.event === 'GRASP_POSE' && typeof msg.confidence === 'number') {
                            // YOLOv8-seg + ThreeJawGrasp 결과 (3-jaw 그리퍼 오버레이용)
                            setGraspScore(msg.confidence);
                            setGraspPose({
                                center_x: msg.center_x,
                                center_y: msg.center_y,
                                angle_rad: msg.angle_rad,
                                radius: msg.radius,
                                jaw_count: msg.jaw_count,
                                confidence: msg.confidence,
                                image_width: msg.image_width,
                                image_height: msg.image_height,
                            });
                            setDetections([]); // 다른 경로 결과는 비움
                            armDetectionStaleTimer();
                        } else if (msg.event === 'GRASP_SCORE' && typeof msg.confidence === 'number') {
                            setGraspScore(msg.confidence);
                            if (Array.isArray(msg.detections)) {
                                setDetections(msg.detections);
                            } else {
                                setDetections([]);
                            }
                            setGraspPose(null); // 다른 경로 결과는 비움
                            armDetectionStaleTimer();
                        } else if (msg.event === 'SESSION_START') {
                            setLastSessionEvent({ type: 'SESSION_START', session_id: msg.session_id });
                        } else if (msg.event === 'GAME_RESULT') {
                            setLastSessionEvent({
                                type: 'GAME_RESULT',
                                session_id: msg.session_id,
                                is_caught: msg.is_caught,
                                confidence: msg.confidence,
                            });
                        }
                    } catch { /* ignore */ }
                    return;
                }

                if (!(event.data instanceof ArrayBuffer)) return;

                let payload: DecodedPayload;
                try {
                    payload = decode(new Uint8Array(event.data)) as DecodedPayload;
                } catch (e) {
                    // 깨진 프레임은 조용히 무시 (다음 프레임이 곧 도착)
                    return;
                }

                const jpegBytes = channel === '2d' ? payload.color_2d : payload.color_3d;
                if (!jpegBytes || jpegBytes.length === 0) return;

                // Uint8Array<ArrayBufferLike> → 새 ArrayBuffer 로 복사하여
                // BlobPart 타입 호환성 확보 (TS 5.7+ 의 엄격 generic).
                const ab = new ArrayBuffer(jpegBytes.byteLength);
                new Uint8Array(ab).set(jpegBytes);
                const blob = new Blob([ab], { type: 'image/jpeg' });
                const next = URL.createObjectURL(blob);

                // 이전 URL 즉시 해제 → 메모리 누적 방지
                if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
                prevUrlRef.current = next;

                setFrameUrl(next);
            };

            ws.onerror = () => {
                // close 가 뒤이어 호출되므로 여기서는 로깅만
            };

            ws.onclose = () => {
                setConnected(false);
                if (cancelled) return;
                // 지수 백오프 재연결 (최대 5초)
                reconnectTimer = setTimeout(connect, backoffMs);
                backoffMs = Math.min(backoffMs * 2, 5000);
            };
        };

        connect();

        return () => {
            cancelled = true;
            if (reconnectTimer) clearTimeout(reconnectTimer);
            if (detectionStaleTimerRef.current) {
                clearTimeout(detectionStaleTimerRef.current);
                detectionStaleTimerRef.current = null;
            }
            if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
            if (prevUrlRef.current) {
                URL.revokeObjectURL(prevUrlRef.current);
                prevUrlRef.current = null;
            }
        };
    }, [channel]);

    return { frameUrl, connected, graspScore, detections, graspPose, lastSessionEvent };
}
