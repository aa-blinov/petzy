import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ImageViewer } from 'antd-mobile';
import { X } from 'lucide-react';
import { hapticFeedback } from '../utils/haptic';

interface PhotoViewerProps {
  image: string;
  visible: boolean;
  onClose: () => void;
}

/**
 * A photo at full size. antd-mobile's ImageViewer has no close button of its own and
 * relies on a tap on the picture, which does nothing if the browser can't draw it, so this
 * adds a visible «Закрыть» and Esc.
 */
export function PhotoViewer({ image, visible, onClose }: PhotoViewerProps) {
  useEffect(() => {
    if (!visible) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [visible, onClose]);

  return (
    <>
      <ImageViewer image={image} visible={visible} onClose={onClose} />
      {visible &&
        createPortal(
          <button
            type="button"
            onClick={() => {
              hapticFeedback('light');
              onClose();
            }}
            className="touch-target"
            aria-label="Закрыть"
            style={{
              position: 'fixed',
              top: 'calc(env(safe-area-inset-top) + var(--spacing-md))',
              right: 'var(--spacing-md)',
              zIndex: 1001,
              background: 'rgba(0, 0, 0, 0.5)',
              color: 'var(--app-text-on-dark)',
              border: 'none',
              borderRadius: '50%',
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
          >
            <X size={20} strokeWidth={2.4} />
          </button>,
          document.body,
        )}
    </>
  );
}
