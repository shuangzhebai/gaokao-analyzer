import { lazy, Suspense, type ReactNode } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import RootLayout from '../layouts/RootLayout';
import AuthLayout from '../layouts/AuthLayout';
import LoadingState from '../components/states/LoadingState';
import NotFoundPage from '../pages/not-found/NotFoundPage';
import { useAuth } from '../hooks/useAuth';

const LoginPage = lazy(() => import('../pages/auth/LoginPage'));
const RegisterPage = lazy(() => import('../pages/auth/RegisterPage'));
const DashboardPage = lazy(() => import('../pages/dashboard/DashboardPage'));
const PaperListPage = lazy(() => import('../pages/papers/PaperListPage'));
const PaperDetailPage = lazy(() => import('../pages/papers/PaperDetailPage'));
const CollectPage = lazy(() => import('../pages/collect/CollectPage'));
const DocsPage = lazy(() => import('../pages/docs/DocsPage'));
const AuditPage = lazy(() => import('../pages/audit/AuditPage'));
const QuestionsListPage = lazy(() => import('../pages/questions/QuestionsListPage'));

function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function LazyLoad({ children }: { children: ReactNode }) {
  return <Suspense fallback={<LoadingState />}>{children}</Suspense>;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LazyLoad><AuthLayout title="登录"><LoginPage /></AuthLayout></LazyLoad>} />
      <Route path="/register" element={<LazyLoad><AuthLayout title="注册"><RegisterPage /></AuthLayout></LazyLoad>} />

      <Route element={<AuthGuard><RootLayout /></AuthGuard>}>
        <Route index element={<LazyLoad><DashboardPage /></LazyLoad>} />
        <Route path="papers" element={<LazyLoad><PaperListPage /></LazyLoad>} />
        <Route path="papers/:id" element={<LazyLoad><PaperDetailPage /></LazyLoad>} />
        <Route path="collect" element={<LazyLoad><CollectPage /></LazyLoad>} />
        <Route path="docs" element={<LazyLoad><DocsPage /></LazyLoad>} />
        <Route path="audit" element={<LazyLoad><AuditPage /></LazyLoad>} />
        <Route path="questions" element={<LazyLoad><QuestionsListPage /></LazyLoad>} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
