import { SpinLoading } from 'antd-mobile';

export function LoadingSpinner() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px', gap: '16px' }}>
      <SpinLoading style={{ '--size': '40px' }} />
      <p style={{ fontSize: '16px', color: '#EBEBF5' }}>Загрузка...</p>
    </div>
  );
}

