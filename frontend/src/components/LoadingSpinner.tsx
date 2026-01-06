import { SpinLoading } from 'antd-mobile';

export function LoadingSpinner() {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100dvh',
      width: '100%',
      gap: '16px',
      backgroundColor: 'var(--app-page-background)',
      position: 'fixed',
      top: 0,
      left: 0,
      zIndex: 1000
    }}>
      <SpinLoading style={{ '--size': '40px', '--color': 'var(--adm-color-primary)' }} />
      <p style={{ fontSize: '16px', color: 'var(--app-text-secondary)' }}>Загрузка...</p>
    </div>
  );
}

