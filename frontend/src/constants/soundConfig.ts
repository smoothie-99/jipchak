// BGM Imports
import bgmMain from '@/assets/sounds/bgm/bgm-main.mp3';

// SFX Imports
import sfxClawMove from '@/assets/sounds/sfx/sfx-claw-move.mp3';
import sfxClawFalling from '@/assets/sounds/sfx/sfx-claw-falling.mp3';
import sfxClawComeback from '@/assets/sounds/sfx/sfx-claw-comeback.mp3';
import sfxTryCatch from '@/assets/sounds/sfx/sfx-try-catch.mp3';
import sfxYouWin from '@/assets/sounds/sfx/sfx-you-win.mp3';
import sfxContinue from '@/assets/sounds/sfx/sfx-continue.mp3';

// Voice Imports
import voiceQrAgree from '@/assets/sounds/voice/voice-qr-agree.mp3';

/**
 * SOUND_ASSETS
 * 시스템에서 사용하는 모든 오디오 에셋의 경로를 관리합니다.
 * Vite의 빌드 프로세스에서 에셋이 올바르게 포함되도록 import 방식을 사용합니다.
 */
export const SOUND_ASSETS = {
  BGM: {
    MAIN: bgmMain,
  },
  SFX: {
    CLAW_MOVE: sfxClawMove,
    CLAW_FALL: sfxClawFalling,
    CLAW_RETURN: sfxClawComeback,
    TRY_CATCH: sfxTryCatch,
    WIN: sfxYouWin,
    BUTTON_CLICK: sfxContinue,
  },
  VOICE: {
    QR_AGREE: voiceQrAgree,
  },
} as const;

export type BgmName = keyof typeof SOUND_ASSETS.BGM;
export type SfxName = keyof typeof SOUND_ASSETS.SFX;
export type VoiceName = keyof typeof SOUND_ASSETS.VOICE;
