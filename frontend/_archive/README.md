# Archived code

여기 있는 파일들은 **현재 사용되지 않는 코드**입니다. 즉시 삭제하지 않고 보존하는 이유:

1. 향후 부활 가능성이 있는 모듈
2. git log 추적 + IDE Go-to-definition 으로 발견 안 되도록 src 밖으로 분리
3. 발표(2026-05-21) 이후 한 번 더 검토 후 진짜 삭제 여부 결정

**`src/` 밖이라 Vite/TypeScript 빌드에 자동으로 포함되지 않습니다.** 컴파일 영향 없음.

## 파일 목록

| 파일 | 미사용 사유 | Archive 일자 |
|------|-----------|-----------|
| `services/gameService.ts` | `createGameLog`, `getHomeMessage` 둘 다 호출처 없음. 백엔드 연동 시 신규 작성 예정 | 2026-05-16 |
| `utils/axios.ts` | `gameService.ts` 외 사용 없음. gameService archive 와 함께 이동 | 2026-05-16 |
| `hooks/useCameraStream.ts` | WebSocket 이 hook 안에 있어 컴포넌트 인스턴스마다 새 연결이 생기던 패턴. `streamStore` 로 대체되어 호출처 없어짐 | 2026-05-17 |

## 부활 또는 영구 삭제 기준

- **부활**: 2단계 백엔드 세션 연동 시 비슷한 API client 필요하면 여기서 가져가 수정
- **영구 삭제**: 발표 후 1주 내 미사용이면 `git rm` 처리
