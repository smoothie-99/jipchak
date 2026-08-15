import { create } from 'zustand';
import { sessionService } from '@/services/sessionService';
import { useStreamStore } from './streamStore';

export type ToolAreaView = 'RECORDS' | 'QR_CONSENT' | 'QR_DISPLAY';

export interface RecordItem {
  id: string;
  filename: string;
  thumbnailUrl?: string;
  isSuccess: boolean;
}

interface ToolState {
  viewType: ToolAreaView;
  qrValue: string;
  sessionId: string;
  isSessionActive: boolean;
  records: RecordItem[];
  qrTimer: number;
  maxGames: number;
  isCatching: boolean;
  lastResult: 'win' | 'lose' | null;
  isAskingNextStep: boolean;
  isAutoStarting: boolean;

  startSession: (sessionId?: string) => void;
  setSessionId: (sessionId: string) => void;
  setMaxGames: (max: number) => void;
  addRecord: (record: RecordItem) => void;
  forceStopGame: () => void;
  handleQRConsent: (agreed: boolean) => Promise<void>;
  tickQrTimer: () => void;
  resetSession: () => void;
  setCatching: (catching: boolean) => void;
  setLastResult: (result: 'win' | 'lose' | null) => void;
  setAskingNextStep: (val: boolean) => void;
  setAutoStarting: (val: boolean) => void;
}

const DEFAULT_MAX_GAMES = 2;
const QR_TIMEOUT_SECONDS = 30;

export const useToolStore = create<ToolState>((set, get) => ({
  viewType: 'RECORDS',
  qrValue: '',
  sessionId: '',
  isSessionActive: false,
  records: [],
  qrTimer: 0,
  maxGames: DEFAULT_MAX_GAMES,
  isCatching: false,
  lastResult: null,
  isAskingNextStep: false,
  isAutoStarting: false,

  startSession: (sessionId?: string) => {
    const newSessionId = sessionId ?? `client_${Date.now()}`;
    set({
      sessionId: newSessionId,
      isSessionActive: true,
      records: [],
      viewType: 'RECORDS',
      qrValue: '',
      qrTimer: 0,
      maxGames: DEFAULT_MAX_GAMES,
    });
    console.log(`[Session] started: ${newSessionId}`);
  },

  setSessionId: (sessionId: string) => {
    const prev = get().sessionId;
    if (prev === sessionId) return;
    set({ sessionId });
    console.log(`[Session] sessionId updated: ${prev} -> ${sessionId}`);
  },

  setMaxGames: (max: number) => {
    set({ maxGames: max });
    console.log(`[Session] maxGames = ${max}`);
  },

  addRecord: (record: RecordItem) => {
    const { isSessionActive, records, maxGames, forceStopGame } = get();
    if (!isSessionActive || records.length >= maxGames) return;

    const nextRecords = [...records, record];
    set({ records: nextRecords });
    console.log(`[Session] record added: ${nextRecords.length}/${maxGames}`);

    if (nextRecords.length >= maxGames) {
      forceStopGame();
    }
  },

  // 2판 종료 후 바로 QR 생성하지 않고 동의 화면으로 먼저 이동
  forceStopGame: () => {
    console.log('[Session] max games reached, moving to QR consent.');
    set({
      viewType: 'QR_CONSENT',
      qrValue: '',
      qrTimer: 0,
    });
  },

  handleQRConsent: async (agreed: boolean) => {
    const { resetSession, sessionId } = get();

    try {
      if (!agreed) {
        await sessionService.deleteSessionVideos();
        resetSession();
        return;
      }

      let qrUrl: string;
      try {
        qrUrl = await sessionService.generateSessionQr(sessionId);
      } catch (error) {
        console.error('[Session] QR generation failed, using local fallback URL:', error);
        qrUrl = `${window.location.origin}${window.location.pathname}#/m/${sessionId}`;
      }

      set({
        qrValue: qrUrl,
        viewType: 'QR_DISPLAY',
        qrTimer: QR_TIMEOUT_SECONDS,
      });
    } catch (error) {
      console.error('[Session] QR consent handling failed:', error);
      alert('요청 처리 중 오류가 발생했습니다. 처음 화면으로 이동합니다.');
      resetSession();
    }
  },

  tickQrTimer: () => {
    const current = get().qrTimer;
    if (current <= 1) {
      get().resetSession();
      return;
    }
    set({ qrTimer: current - 1 });
  },

  resetSession: () => {
    useStreamStore.setState({
      frame2d: null,
      frame3d: null,
      lastSessionEvent: null,
      lastUiEvent: null,
      graspScore: 0,
      detections: [],
      graspPose: null,
    });

    set({
      sessionId: '',
      isSessionActive: false,
      records: [],
      viewType: 'RECORDS',
      qrValue: '',
      qrTimer: 0,
      maxGames: DEFAULT_MAX_GAMES,
      isCatching: false,
      lastResult: null,
      isAskingNextStep: false,
      isAutoStarting: false,
    });

    console.log('[Session] reset complete');
    window.location.hash = '#/';
  },

  setCatching: (catching: boolean) => set({ isCatching: catching }),
  setLastResult: (result: 'win' | 'lose' | null) => set({ lastResult: result }),
  setAskingNextStep: (val: boolean) => set({ isAskingNextStep: val }),
  setAutoStarting: (val: boolean) => set({ isAutoStarting: val }),
}));
