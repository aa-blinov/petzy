import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { Button } from 'antd-mobile';
import { useSession } from '../hooks/useSession';
import { LoadingSpinner } from './LoadingSpinner';

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isFetching, probeError, retryProbe } = useSession();

  // Known signed in — render, even if a background refetch is running.
  if (isAuthenticated === true) {
    return <>{children}</>;
  }

  // Known signed out (a 401, and only a 401). Router navigation is the
  // single sign-out path; api.ts no longer competes with a hard
  // window.location redirect.
  if (isAuthenticated === false) {
    return <Navigate to="/login" replace />;
  }

  // Not known yet. If the probe failed for a reason other than 401 the
  // session may well be fine, so offer a retry instead of either
  // spinning forever or bouncing an authenticated user to /login.
  if (!isFetching && probeError) {
    return (
      <div
        style={{
          minHeight: '100dvh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 16,
          padding: 24,
          textAlign: 'center',
        }}
      >
        <p style={{ color: 'var(--app-text-secondary)', fontSize: 16, margin: 0 }}>
          Не удалось связаться с сервером
        </p>
        <Button color="primary" fill="outline" onClick={() => { void retryProbe(); }}>
          Повторить
        </Button>
      </div>
    );
  }

  return <LoadingSpinner />;
}
