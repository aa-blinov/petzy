/**
 * Full-screen crop step shown right after picking a pet photo.
 *
 * Every photo ends up displayed as a 1:1 tile (Pets list, dashboard
 * avatar, navbar) — without this, that square crop was decided for the
 * user by CSS `object-position` guessing at where the subject's face
 * probably was in whatever aspect ratio they happened to take the photo
 * in. Cropping once, here, means the uploaded file already is the square
 * the user actually chose.
 */

import { useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import Cropper, { type Area, type Point } from 'react-easy-crop';
import { Slider } from 'antd-mobile';
import { Check, X, ZoomIn } from 'lucide-react';

import { getCroppedImageFile } from '../utils/cropImage';
import { showToast } from '../utils/toast';
import { hapticFeedback } from '../utils/haptic';

interface PhotoCropModalProps {
  /** object URL of the just-picked file. */
  imageSrc: string;
  /** Original filename — reused (with a .jpg extension) for the crop output. */
  filename: string;
  onCancel: () => void;
  onCropped: (file: File) => void;
}

export function PhotoCropModal({ imageSrc, filename, onCancel, onCropped }: PhotoCropModalProps) {
  const [crop, setCrop] = useState<Point>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const onCropComplete = useCallback((_croppedArea: Area, areaPixels: Area) => {
    setCroppedAreaPixels(areaPixels);
  }, []);

  const handleConfirm = async () => {
    if (!croppedAreaPixels) return;
    hapticFeedback('light');
    setIsSaving(true);
    try {
      const file = await getCroppedImageFile(imageSrc, croppedAreaPixels, filename);
      onCropped(file);
    } catch (err) {
      console.error('Crop failed:', err);
      showToast.failure('Не удалось обрезать фото');
    } finally {
      setIsSaving(false);
    }
  };

  // Portaled to <body>: rendered in place, it was stacked inside the page
  // and the navbar and tab bar drew over it, covering Отмена/Готово.
  // 1020 sits above both (1000 / 100) and below antd toasts (1030).
  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1020,
        background: '#000',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        <Cropper
          image={imageSrc}
          crop={crop}
          zoom={zoom}
          aspect={1}
          cropShape="rect"
          showGrid
          onCropChange={setCrop}
          onZoomChange={setZoom}
          onCropComplete={onCropComplete}
        />
      </div>

      <div
        style={{
          background: '#111',
          padding: '16px max(16px, env(safe-area-inset-right)) calc(16px + env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left))',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <ZoomIn size={18} strokeWidth={2} style={{ color: '#fff', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <Slider
              min={1}
              max={3}
              step={0.01}
              value={zoom}
              onChange={(val) => setZoom(Array.isArray(val) ? val[0] : val)}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            type="button"
            onClick={() => {
              hapticFeedback('light');
              onCancel();
            }}
            disabled={isSaving}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '12px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'rgba(255, 255, 255, 0.12)',
              color: '#fff',
              fontWeight: 600,
              fontSize: 'var(--text-md)',
              cursor: isSaving ? 'not-allowed' : 'pointer',
            }}
          >
            <X size={18} strokeWidth={2.4} />
            Отмена
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isSaving || !croppedAreaPixels}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '12px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--app-primary-color)',
              color: '#fff',
              fontWeight: 600,
              fontSize: 'var(--text-md)',
              cursor: isSaving || !croppedAreaPixels ? 'not-allowed' : 'pointer',
              opacity: isSaving ? 0.7 : 1,
            }}
          >
            <Check size={18} strokeWidth={2.4} />
            {isSaving ? 'Сохранение...' : 'Готово'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
