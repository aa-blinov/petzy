import { useEffect, useRef } from 'react';
import { Toast } from 'antd-mobile';

interface AlertProps {
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  onClose?: () => void;
  duration?: number;
}

export function Alert({ type, message, onClose, duration = 3000 }: AlertProps) {
  // Use a ref to always have the latest onClose without re-triggering the effect
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const handlerRef = useRef<any>(null);

  useEffect(() => {
    const iconMap = {
      success: 'success',
      error: 'fail',
      info: 'loading',
      warning: 'fail',
    } as const;

    handlerRef.current = Toast.show({
      icon: iconMap[type],
      content: message,
      duration: duration, // antd-mobile v5 uses ms
      afterClose: () => {
        handlerRef.current = null;
        if (typeof onCloseRef.current === 'function') {
          onCloseRef.current();
        }
      },
    });

    return () => {
      if (handlerRef.current) {
        handlerRef.current.close();
        handlerRef.current = null;
      }
    };
  }, [type, message, duration]);

  return null; // Toast is rendered by antd-mobile
}

