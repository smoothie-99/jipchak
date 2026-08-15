import { useCallback } from 'react';
import { useAudioStore } from '@/store/audioStore';

/**
 * useAudio
 *
 * 전역 BGM 1 개와 다수의 SFX / Voice 인스턴스를 관리하면서
 * BGM Ducking (SFX/Voice 재생 중 BGM 일시정지) 까지 처리한다.
 *
 * audioStore 와 실시간 동기화되어, 볼륨 슬라이더를 옮기면
 * 재생 중인 audio 인스턴스의 볼륨도 즉시 갱신된다.
 *
 * 이전 구현 (`useAudioStore.getState()` 일회 캡쳐) 의 문제:
 *   - sfx / voice 가 재생 시작 시점의 볼륨에 고정 → 슬라이더 변경 무시됨
 *   - useEffect 가 5 개 consumer 에 등록되며 globalBgmVolume 을 매번 덮어쓰던 경합
 * 두 가지 모두 본 리팩토링에서 해소.
 */

// ─────────────────────────────────────────
// 모듈 스코프 상태
//   - BGM 은 단일 인스턴스
//   - SFX / Voice 는 동시에 여러 개 재생될 수 있으므로 Set 으로 추적
// ─────────────────────────────────────────

let bgmInstance: HTMLAudioElement | null = null;
const activeSfxAudios: Set<HTMLAudioElement> = new Set();
const activeVoiceAudios: Set<HTMLAudioElement> = new Set();

// ─────────────────────────────────────────
// audioStore → audio 인스턴스 단방향 동기화
//   볼륨 슬라이더를 옮기면 재생 중인 모든 audio 의 volume 을 즉시 갱신.
// ─────────────────────────────────────────

useAudioStore.subscribe((state, prev) => {
    if (state.bgmVolume !== prev.bgmVolume) {
        // BGM 은 ducking 중이 아닐 때만 (재생 중일 때만) 즉시 반영.
        // ducking 종료 시점에 어차피 최신 volume 으로 set 하므로 ducking 중 갱신은 불필요.
        if (bgmInstance && !isDucking()) {
            bgmInstance.volume = state.bgmVolume / 100;
        }
    }
    if (state.sfxVolume !== prev.sfxVolume) {
        const v = state.sfxVolume / 100;
        activeSfxAudios.forEach((a) => { a.volume = v; });
    }
    if (state.voiceVolume !== prev.voiceVolume) {
        const v = state.voiceVolume / 100;
        activeVoiceAudios.forEach((a) => { a.volume = v; });
    }
});

// ─────────────────────────────────────────
// 헬퍼
// ─────────────────────────────────────────

function isDucking(): boolean {
    return activeSfxAudios.size > 0 || activeVoiceAudios.size > 0;
}

function updateBgmDucking() {
    if (!bgmInstance) return;
    if (isDucking()) {
        bgmInstance.pause();
    } else {
        bgmInstance.volume = useAudioStore.getState().bgmVolume / 100;
        bgmInstance.play().catch(() => {});
    }
}

// ─────────────────────────────────────────
// 공개 훅
// ─────────────────────────────────────────

export const useAudio = () => {
    /** BGM 시작 (loop). 기존 BGM 은 자동 중지. */
    const playBgm = useCallback((path: string) => {
        if (bgmInstance) {
            bgmInstance.pause();
        }
        const audio = new Audio(path);
        audio.loop = true;
        audio.volume = useAudioStore.getState().bgmVolume / 100;
        bgmInstance = audio;

        // SFX/Voice 진행 중이 아니면 즉시 재생.
        // jsdom 등 테스트 환경에서는 play() 가 undefined 반환할 수 있음 → 가드 필요.
        if (!isDucking()) {
            const p = audio.play();
            if (p !== undefined) {
                p.catch(() => {
                    console.warn('[Audio] BGM autoplay blocked. Interaction required.');
                });
            }
        }
    }, []);

    /** BGM 정지 + 인스턴스 해제. */
    const stopBgm = useCallback(() => {
        if (bgmInstance) {
            bgmInstance.pause();
            bgmInstance = null;
        }
    }, []);

    /** SFX 1 회 재생. cleanup 불필요. 자동으로 끝나면 추적에서 제거. */
    const playSfx = useCallback((path: string) => {
        const audio = new Audio(path);
        audio.volume = useAudioStore.getState().sfxVolume / 100;
        activeSfxAudios.add(audio);
        updateBgmDucking();

        const cleanup = () => {
            activeSfxAudios.delete(audio);
            updateBgmDucking();
        };

        audio.onended = cleanup;
        // jsdom 등 테스트 환경에서는 play() 가 undefined 반환할 수 있음 → 가드 필요.
        const p = audio.play();
        if (p !== undefined) {
            p.catch(cleanup);
        }
    }, []);

    /**
     * Voice 재생. 컴포넌트 cleanup 시 호출할 함수를 반환한다.
     *
     * 사용 예:
     *   useEffect(() => {
     *     const stop = playVoice(SOUND_ASSETS.VOICE.QR_AGREE);
     *     return stop;
     *   }, [playVoice]);
     */
    const playVoice = useCallback((path: string): (() => void) => {
        const audio = new Audio(path);
        audio.volume = useAudioStore.getState().voiceVolume / 100;
        activeVoiceAudios.add(audio);
        updateBgmDucking();

        const cleanup = () => {
            if (!activeVoiceAudios.has(audio)) return;
            audio.pause();
            activeVoiceAudios.delete(audio);
            updateBgmDucking();
        };

        audio.onended = () => {
            activeVoiceAudios.delete(audio);
            updateBgmDucking();
        };

        // jsdom 등 테스트 환경에서는 play() 가 undefined 반환할 수 있음 → 가드 필요.
        const p = audio.play();
        if (p !== undefined) {
            p.catch(cleanup);
        }

        return cleanup;
    }, []);

    return {
        playBgm,
        stopBgm,
        playSfx,
        playVoice,
    };
};
