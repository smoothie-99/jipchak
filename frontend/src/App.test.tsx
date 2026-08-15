import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from './App';

describe('App routing', () => {
  beforeEach(() => {
    window.location.hash = '';
  });

  afterEach(() => {
    cleanup();
    window.location.hash = '';
  });

  it('renders the landing page by default', () => {
    render(<App />);

    expect(screen.getByText('JIPCHAK')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'START' })).toBeTruthy();
  });

  // UI-driven session start 흐름(PR #159 이후): START 버튼 클릭은 WS 로 REQUEST_START 만
  // 송신하고, AI 서버가 발급한 SESSION_START 이벤트를 받아야 navigate 한다.
  // jsdom 환경에서는 실제 WebSocket 이 열리지 않아 navigate 가 트리거되지 않는다.
  // TODO: WS mocking 으로 SESSION_START 시뮬레이션해서 정식 복원.
  it.skip('navigates to the play screen from the landing page', async () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: 'START' }));

    // 애니메이션 및 페이지 이동 대기
    expect(await screen.findByText('Cam1')).toBeTruthy();
    expect(screen.getByText('나의 기록')).toBeTruthy();
    expect(window.location.hash).toContain('/play');
  });
});
