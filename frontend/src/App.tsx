
import { HashRouter, Route, Routes } from 'react-router-dom';
import Home from './pages/Home';
import PlayGround from './pages/PlayGround';
import AdminDashboard from './pages/AdminDashboard';
import AdminDeviceSelection from './pages/AdminDeviceSelection';
import MobileLanding from './pages/mobile/MobileLanding';
import AdminRoute from './components/common/AdminRoute';

const App = () => {
  return (
    // 정적/상대 경로 배포에서도 새로고침과 직접 진입이 깨지지 않도록 해시 라우팅을 사용한다.
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/play" element={<PlayGround />} />
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminDeviceSelection />
            </AdminRoute>
          }
        />
        <Route
          path="/admin/dashboard/:deviceId"
          element={
            <AdminRoute>
              <AdminDashboard />
            </AdminRoute>
          }
        />
        <Route path="/m/:sessionId" element={<MobileLanding />} />
      </Routes>
    </HashRouter>
  );
};

export default App;
