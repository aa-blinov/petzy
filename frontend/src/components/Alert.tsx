import { useEffect, useRef } from 'react';
import { showToast } from '../utils/toast';
import type { ToastHandler } from 'antd-mobile/es/components/toast';

interface AlertProps {
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  onClose?: () => void;
  duration?: number;
}

export function Alert({ type, message, onClose, duration = 3000 }: AlertProps) {
  // Use a ref to always have the latest onClose without re-triggering the effect
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  const handlerRef = useRef<ToastHandler | null>(null);

  useEffect(() => {
    // Map onto the shared helpers so these inherit the app-wide toast
    // position instead of antd's centred default.
    const variant = {
      success: showToast.success,
      error: showToast.failure,
      info: showToast.info,
      warning: showToast.failure,
    }[type];

    handlerRef.current = variant(message, {
      duration, // antd-mobile v5 uses ms
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

