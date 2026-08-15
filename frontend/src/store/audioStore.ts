import { create } from 'zustand';

interface AudioState {
  bgmVolume: number;
  sfxVolume: number;
  voiceVolume: number;
  isSettingsOpen: boolean;

  setBgmVolume: (vol: number) => void;
  setSfxVolume: (vol: number) => void;
  setVoiceVolume: (vol: number) => void;
  setSettingsOpen: (isOpen: boolean) => void;
}

/**
 * useAudioStore
 * 오디오 볼륨 조절 및 설정창 UI 상태 관리
 */
export const useAudioStore = create<AudioState>((set) => ({
  bgmVolume: 50,
  sfxVolume: 50,
  voiceVolume: 50,
  isSettingsOpen: false,

  setBgmVolume: (vol) => set({ bgmVolume: vol }),
  setSfxVolume: (vol) => set({ sfxVolume: vol }),
  setVoiceVolume: (vol) => set({ voiceVolume: vol }),
  setSettingsOpen: (isOpen) => set({ isSettingsOpen: isOpen }),
}));
