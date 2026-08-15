import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

interface AdminRouteProps {
  children: React.ReactNode;
}

/**
 * 어드민 페이지 진입 가드.
 *
 * 가드 로직이 AdminDeviceSelection / AdminDashboard 에 동일하게 복붙되어 있던 것을 통합.
 * App.tsx 에서 <AdminRoute><AdminPage /></AdminRoute> 형태로 래핑한다.
 *
 * 한계 (의도)
 *  - sessionStorage 기반 검증은 클라이언트 측이라 보안 가드 아님 (DevTools 우회 가능).
 *    URL 직접 진입 차단 + UX 안내 목적에 한정.
 *  - 진짜 보안은 Phase 2 의 백엔드 인증 API 도입 후 교체.
 */
const AdminRoute = ({ children }: AdminRouteProps) => {
  const navigate = useNavigate();

  // 초기 렌더 시 동기 체크 — useState/useEffect 사이 1프레임 노출 방지
  const isAdmin =
    typeof window !== 'undefined' &&
    window.sessionStorage.getItem('isAdmin') === 'true';

  useEffect(() => {
    if (!isAdmin) {
      alert('비정상적인 접근입니다. 관리자 비밀번호를 입력해주세요.');
      navigate('/');
    }
  }, [isAdmin, navigate]);

  if (!isAdmin) return null;
  return <>{children}</>;
};

export default AdminRoute;
