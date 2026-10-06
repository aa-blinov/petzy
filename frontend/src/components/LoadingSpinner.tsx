import { SpinLoading } from 'antd-mobile';

interface LoadingSpinnerProps {
  fullscreen?: boolean;
}

export function LoadingSpinner({ fullscreen = true }: LoadingSpinnerProps) {
  const containerStyle: React.CSSProperties = fullscreen ? {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100dvh',
    width: '100%',
    gap: '16px',
    // The same background the screen behind it has, so waiting for a screen that is
    // still being fetched does not replace the pet's colour with the plain one.
    backgroundColor: 'var(--pet-scene-bg, var(--app-page-background))',
    position: 'fixed',
    top: 0,
    left: 0,
    zIndex: 1000
  } : {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '32px',
    width: '100%',
    gap: '12px',
  };

  return (
    <div style={containerStyle} role="status">
      <SpinLoading aria-hidden style={{ '--size': '40px', '--color': 'var(--adm-color-primary)' }} />
      <p style={{ fontSize: 'var(--text-md)', color: 'var(--app-text-secondary)' }}>Загрузка...</p>
    </div>
  );
}
