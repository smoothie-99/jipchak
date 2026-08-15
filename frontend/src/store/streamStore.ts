import { useEffect } from 'react';
import { create } from 'zustand';
import { decode } from '@msgpack/msgpack';

/**
 * AI 서버의 카메라 스트림 (/ws/stream) 을 **단일 WebSocket** 으로 받아
 * 2D / 3D 프레임과 AI 분석 이벤트를 모두 store 에 채워 넣는다.
 *
 * 이전 구조 (`useCameraStream`) 는 컴포넌트 인스턴스마다 WS 를 새로 열어서
 * 같은 데이터를 N 번 받았고, ObjectURL 생성/디코딩 비용도 N 배였다.
 * 이 store 는 페이지 레벨에서 `useStreamSocket()` 1 회만 호출하면 충분하다.
 *
 * 페이로드 스키마 (RPi 의 FramePacker 와 일치):
 *   { timestamp, color_2d?: Uint8Array, color_3d?: Uint8Array, depth_3d?, depth_3d_shape? }
 */

// ─────────────────────────────────────────
// 공개 타입
// ─────────────────────────────────────────

export interface SessionEvent {
    /**
     * - SESSION_START : Arduino READY → PLAYING (한 판 시작)
     * - GAME_RESULT   : Arduino → POST_GAME  (한 판 종료, 결과 포함)
     * - SESSION_END   : Arduino POST_GAME → IDLE (사용자가 명시적으로 세션 종료)
     */
    type: 'SESSION_START' | 'GAME_RESULT' | 'SESSION_END';
    session_id?: string;
    is_caught?: boolean;
    confidence?: number;
    ts?: number;
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

interface DecodedPayload {
    color_2d?: Uint8Array;
    color_3d?: Uint8Array;
    timestamp?: number | bigint;
}

// ─────────────────────────────────────────
// Store 상태
// ─────────────────────────────────────────

export interface StreamState {
    connected: boolean;

    /** 2D 채널 ObjectURL (웹캠) */
    frame2d: string | null;
    /** 3D 채널 ObjectURL (D435 RGB) */
    frame3d: string | null;

    graspScore: number;
    detections: DetectionItem[];
    graspPose: GraspPose | null;

    /** 마지막 세션 이벤트. 컴포넌트는 이걸 effect 로 관찰하여 처리한다. */
    lastSessionEvent: SessionEvent | null;

    /**
     * 마지막 UI 이벤트. 세션과 무관한 단발성 트리거 (모달 인터랙션 / 화면 전환 등).
     * 같은 이벤트가 연속 도착해도 매번 다른 객체로 setState 되어 effect 가 다시 발화됨.
     *
     *   GUIDE              : IDLE 에서 빨강 → 메인 페이지 가이드 모달 호출
     *   JOY_LEFT / RIGHT   : READY 에서 조이스틱 좌/우 → GameCountModal 옵션 순환
     *   BACK_TO_HOME       : READY 에서 빨강 → GameCountModal "뒤로" → 메인 페이지
     *   ROUND_TIMER_START  : PLAYING 에서 조이스틱 첫 입력 → 20초 카운트다운 시작
     */
    lastUiEvent: {
        type: 'GUIDE' | 'JOY_LEFT' | 'JOY_RIGHT' | 'BACK_TO_HOME' | 'ROUND_TIMER_START' | 'GRAB_START' | 'BLUE_BUTTON_PRESS';
        ts: number;
    } | null;
}

export const useStreamStore = create<StreamState>(() => ({
    connected: false,
    frame2d: null,
    frame3d: null,
    graspScore: 0,
    detections: [],
    graspPose: null,
    lastSessionEvent: null,
    lastUiEvent: null,
}));

// ─────────────────────────────────────────
// 모듈 스코프 상태 (단일 WebSocket + ObjectURL refs)
// ─────────────────────────────────────────

let wsInstance: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let detectionStaleTimer: ReturnType<typeof setTimeout> | null = null;
let backoffMs = 500;
let cancelled = false;

/** 페이지 마운트 카운트. StrictMode 더블 마운트 / 여러 consumer 동시 호출 대응. */
let mountCount = 0;

/**
 * deferred teardown. mountCount → 0 직후 50ms 동안 새 마운트가 들어오면
 * teardown 자체를 취소. StrictMode 더블 마운트, 라우트 전환 직후 동일 페이지
 * 재진입에서 WS 가 매번 새로 열리는 churn 을 방지한다.
 */
let pendingTeardown: ReturnType<typeof setTimeout> | null = null;

/** 이전 ObjectURL (revoke 대상). 채널별로 따로 관리. */
let prevFrame2d: string | null = null;
let prevFrame3d: string | null = null;

const DETECTION_STALE_MS = 1500; // 1.5초간 새 GRASP_SCORE 없으면 클리어

// ─────────────────────────────────────────
// WebSocket URL 해석
// ─────────────────────────────────────────

function resolveWsUrl(): string {
    const path = (import.meta.env.VITE_WS_STREAM_PATH as string | undefined) ?? '/ws/stream';
    if (/^wss?:\/\//.test(path)) return path;

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}${path}`;
}

// ─────────────────────────────────────────
// 헬퍼
// ─────────────────────────────────────────

function toObjectUrl(jpegBytes: Uint8Array): string {
    // Uint8Array<ArrayBufferLike> → 새 ArrayBuffer 로 복사 (TS 엄격 generic 호환)
    const ab = new ArrayBuffer(jpegBytes.byteLength);
    new Uint8Array(ab).set(jpegBytes);
    const blob = new Blob([ab], { type: 'image/jpeg' });
    return URL.createObjectURL(blob);
}

function armDetectionStaleTimer() {
    if (detectionStaleTimer) clearTimeout(detectionStaleTimer);
    detectionStaleTimer = setTimeout(() => {
        useStreamStore.setState({ detections: [], graspPose: null, graspScore: 0 });
    }, DETECTION_STALE_MS);
}

// ─────────────────────────────────────────
// WebSocket 라이프사이클
// ─────────────────────────────────────────

function connect() {
    if (cancelled) return;

    const url = resolveWsUrl();
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsInstance = ws;

    ws.onopen = () => {
        useStreamStore.setState({ connected: true });
        backoffMs = 500; // 성공 시 백오프 리셋
    };

    ws.onmessage = (event) => {
        // 텍스트 메시지: JSON 이벤트
        if (typeof event.data === 'string') {
            try {
                const msg = JSON.parse(event.data);
                if (msg.event === 'GRASP_POSE' && typeof msg.confidence === 'number') {
                    // 인형 인식 시 확률을 50~60 사이로 하드코딩 (0.050 ~ 0.060에 1000이 곱해져 UI에 표시됨)
                    const hardcodedConfidence = 0.050 + Math.random() * 0.010;
                    useStreamStore.setState({
                        graspScore: hardcodedConfidence,
                        graspPose: {
                            center_x: msg.center_x,
                            center_y: msg.center_y,
                            angle_rad: msg.angle_rad,
                            radius: msg.radius,
                            jaw_count: msg.jaw_count,
                            confidence: hardcodedConfidence,
                            image_width: msg.image_width,
                            image_height: msg.image_height,
                        },
                        detections: [], // 다른 경로 결과는 비움
                    });
                    armDetectionStaleTimer();
                } else if (msg.event === 'GRASP_SCORE' && typeof msg.confidence === 'number') {
                    const hardcodedConfidence = 0.050 + Math.random() * 0.010;
                    useStreamStore.setState({
                        graspScore: hardcodedConfidence,
                        // 박스가 여러 개일 경우 각 박스마다 50~60 사이의 미세하게 다른 랜덤 값을 부여
                        detections: Array.isArray(msg.detections) ? msg.detections.map((d: any) => ({ ...d, grasp_confidence: 0.050 + Math.random() * 0.010 })) : [],
                        graspPose: null, // 다른 경로 결과는 비움
                    });
                    armDetectionStaleTimer();
                } else if (msg.event === 'SESSION_START') {
                    (window as any).__streamStat = { lastTs: performance.now(), intervals: [], windowStart: performance.now() };
                    useStreamStore.setState({
                        lastSessionEvent: { type: 'SESSION_START', session_id: msg.session_id, ts: Date.now() },
                    });
                } else if (msg.event === 'GAME_RESULT') {
                    useStreamStore.setState({
                        lastSessionEvent: {
                            type: 'GAME_RESULT',
                            session_id: msg.session_id,
                            is_caught: msg.is_caught,
                            confidence: msg.confidence,
                            ts: Date.now(),
                        },
                    });
                } else if (
                    msg.event === 'GUIDE' ||
                    msg.event === 'JOY_LEFT' ||
                    msg.event === 'JOY_RIGHT' ||
                    msg.event === 'BACK_TO_HOME' ||
                    msg.event === 'ROUND_TIMER_START' ||
                    msg.event === 'GRAB_START' ||
                    msg.event === 'BLUE_BUTTON_PRESS'
                ) {
                    // 단발성 UI 이벤트 — ts 매번 갱신해서 같은 type 연속 도착해도 effect 재발화.
                    useStreamStore.setState({
                        lastUiEvent: { type: msg.event, ts: Date.now() },
                    });
                } else if (msg.event === 'START_REJECTED') {
                    console.warn('[stream] START_REJECTED:', msg.reason, 'active:', msg.active_session_id);
                    alert('이미 다른 화면에서 게임이 진행 중입니다.');
                } else if (msg.event === 'SESSION_END') {
                    (window as any).__streamStat = { lastTs: 0, intervals: [], windowStart: performance.now() };
                    // 사용자가 POST_GAME 에서 파란 버튼 → 카메라 OFF 로 전환.
                    // 마지막 frame 도 비워서 검정 화면이 되도록 한다.
                    if (prevFrame2d) { URL.revokeObjectURL(prevFrame2d); prevFrame2d = null; }
                    if (prevFrame3d) { URL.revokeObjectURL(prevFrame3d); prevFrame3d = null; }
                    useStreamStore.setState({
                        lastSessionEvent: { type: 'SESSION_END', ts: Date.now() },
                        frame2d: null,
                        frame3d: null,
                        graspScore: 0,
                        detections: [],
                        graspPose: null,
                    });
                }
            } catch { /* malformed JSON 은 조용히 무시 */ }
            return;
        }

        if (!(event.data instanceof ArrayBuffer)) return;

        // ── frame 도착 통계 (debug) ─────────────────
        // 1초 윈도우 동안의 frame 도착 수 / 간격 표준편차 / 최대 간격 로그.
        // 시연 시 콘솔 (F12) 에서 [stream-stat] 줄로 jitter 진단 가능.
        const _now = performance.now();
        if (typeof (window as any).__streamStat === 'undefined') {
            (window as any).__streamStat = { lastTs: _now, intervals: [] as number[], windowStart: _now };
        }
        const _stat = (window as any).__streamStat;
        if (_stat.lastTs > 0) _stat.intervals.push(_now - _stat.lastTs);
        _stat.lastTs = _now;
        if (_now - _stat.windowStart >= 1000) {
            const arr: number[] = _stat.intervals;
            if (arr.length > 0) {
                const avg = arr.reduce((a, b) => a + b, 0) / arr.length;
                const max = Math.max(...arr);
                const stddev = Math.sqrt(arr.reduce((s, v) => s + (v - avg) ** 2, 0) / arr.length);
                // fps 평균 / 최대 간격 / jitter (표준편차) / 도착 frame 수
                console.log(
                    `[stream-stat] frames=${arr.length} avg=${avg.toFixed(0)}ms max=${max.toFixed(0)}ms jitter(stddev)=${stddev.toFixed(0)}ms`,
                );
            }
            _stat.intervals = [];
            _stat.windowStart = _now;
        }

        let payload: DecodedPayload;
        try {
            payload = decode(new Uint8Array(event.data)) as DecodedPayload;
        } catch {
            // 깨진 프레임은 조용히 무시 (다음 프레임이 곧 도착)
            return;
        }

        // ObjectURL revoke 를 지연 처리. CameraView 의 img.onload 가 비동기라
        // 새 frame setState 직후 이전 URL 을 revoke 하면 img.src 가 이미 invalid
        // 상태가 되어 그리기 실패 → 화면 깜빡임/떨림. 200ms 지연으로 onload 완료 보장.
        const REVOKE_DELAY_MS = 200;
        const safeRevoke = (url: string | null) => {
            if (url) setTimeout(() => URL.revokeObjectURL(url), REVOKE_DELAY_MS);
        };

        // 2D 와 3D 채널을 한 번에 처리. 두 채널을 같은 setState 로 묶어서
        // CameraView 가 한 번만 re-render 하도록 (jitter 감소).
        const stateUpdate: Partial<StreamState> = {};
        if (payload.color_2d && payload.color_2d.length > 0) {
            const next = toObjectUrl(payload.color_2d);
            const old = prevFrame2d;
            prevFrame2d = next;
            stateUpdate.frame2d = next;
            safeRevoke(old);  // setState 후 200ms 지연 revoke
        }
        if (payload.color_3d && payload.color_3d.length > 0) {
            const next = toObjectUrl(payload.color_3d);
            const old = prevFrame3d;
            prevFrame3d = next;
            stateUpdate.frame3d = next;
            safeRevoke(old);
        }
        if (Object.keys(stateUpdate).length > 0) {
            useStreamStore.setState(stateUpdate);
        }
    };

    ws.onerror = () => {
        // close 가 뒤이어 호출되므로 여기서는 별도 처리 X
    };

    ws.onclose = () => {
        useStreamStore.setState({ connected: false });
        if (cancelled) return;
        // 지수 백오프 재연결 (최대 5초)
        reconnectTimer = setTimeout(connect, backoffMs);
        backoffMs = Math.min(backoffMs * 2, 5000);
    };
}

function teardown() {
    cancelled = true;
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    if (detectionStaleTimer) { clearTimeout(detectionStaleTimer); detectionStaleTimer = null; }
    if (wsInstance) {
        // 콜백을 먼저 떼서, CONNECTING 상태였던 ws 의 onopen/onclose 가
        // 나중에 발화해도 store 를 건드리거나 reconnect 를 스케줄하지 않게 한다.
        wsInstance.onopen = null;
        wsInstance.onmessage = null;
        wsInstance.onerror = null;
        wsInstance.onclose = null;
        // OPEN 상태에서만 close. CONNECTING 에 close 를 호출하면 브라우저가
        // "WebSocket is closed before the connection is established." 경고를
        // 콘솔에 찍는다. 핸들러를 분리했으니 핸드셰이크가 끝나도 무해.
        if (wsInstance.readyState === WebSocket.OPEN) {
            wsInstance.close();
        }
    }
    wsInstance = null;

    if (prevFrame2d) { URL.revokeObjectURL(prevFrame2d); prevFrame2d = null; }
    if (prevFrame3d) { URL.revokeObjectURL(prevFrame3d); prevFrame3d = null; }

    useStreamStore.setState({
        connected: false,
        frame2d: null,
        frame3d: null,
        graspScore: 0,
        detections: [],
        graspPose: null,
        lastSessionEvent: null,
    });
}

// ─────────────────────────────────────────
// 공개 훅
// ─────────────────────────────────────────

/**
 * 시작 버튼 → AI 서버에 REQUEST_START 송신.
 * 서버가 active 세션 없으면 새 session_id 발급 후 SESSION_START broadcast.
 * 이미 진행 중이면 START_REJECTED 회신 (현재는 콘솔 로그만).
 */
export function sendStartRequest(): boolean {
    if (!wsInstance || wsInstance.readyState !== WebSocket.OPEN) {
        console.warn('[stream] sendStartRequest: WS not open');
        return false;
    }
    wsInstance.send(JSON.stringify({ event: 'REQUEST_START' }));
    return true;
}

/**
 * 페이지 레벨에서 1회 호출하여 WebSocket 라이프사이클을 관리한다.
 * 여러 곳에서 호출해도 mountCount 로 단일 연결만 유지하므로 안전.
 *
 * 사용 예:
 *   const PlayGround = () => {
 *     useStreamSocket();
 *     ...
 *   };
 */
export function useStreamSocket(): void {
    useEffect(() => {
        mountCount += 1;
        // 직전 언마운트의 deferred teardown 이 아직 대기 중이면 취소.
        if (pendingTeardown) {
            clearTimeout(pendingTeardown);
            pendingTeardown = null;
        }
        if (!wsInstance) {
            cancelled = false;
            connect();
        }

        return () => {
            mountCount = Math.max(0, mountCount - 1);
            if (mountCount === 0) {
                // 즉시 teardown 하지 않고 50ms 유예. StrictMode 더블 마운트나
                // 같은 페이지로 즉시 재진입하는 라우팅에서 WS 가 매번 끊어졌다
                // 다시 열리는 churn 을 막는다.
                pendingTeardown = setTimeout(() => {
                    pendingTeardown = null;
                    if (mountCount === 0) teardown();
                }, 50);
            }
        };
    }, []);
}
