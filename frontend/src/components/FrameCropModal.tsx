/**
 * Full-screen framing step shown when a frame is chosen for the pet's photo.
 *
 * Frames differ in the window they leave (round, a heart, a wide polaroid, a tall film strip), so the part of the photo that
 * suits one is not the part that suits another: each frame is cropped on its own, in a window of its own shape. Nothing is
 * written to the photo, only which part of it the frame shows.
 */

import { useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import Cropper, { type Area } from 'react-easy-crop';
import { Slider } from 'antd-mobile';
import { Check, X, ZoomIn } from 'lucide-react';

import { PetPhotoFill } from './PetPhotoFill';
import { PET_FRAMES, ROUND_FRAMES, petFrameAspect, petFrameStyle, type PetCrop } from '../utils/petLook';
import { hapticFeedback } from '../utils/haptic';

interface Props {
  src: string;
  species?: string | null;
  frame: string;
  /** What this frame was cropped to before, to start from. */
  initial?: PetCrop;
  onCancel: () => void;
  onDone: (crop: PetCrop) => void;
}

const round2 = (n: number) => Math.round(n * 100) / 100;

export function FrameCropModal({ src, species, frame, initial, onCancel, onDone }: Props) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [area, setArea] = useState<PetCrop | undefined>(initial);
  const label = PET_FRAMES.find((f) => f.key === frame)?.label ?? '';
  const aspect = petFrameAspect(frame);
  // The sample is as tall as the card's avatar slot at its scale, in the shape the frame gives it.
  const sample = petFrameStyle(frame, 0.7);

  const onCropComplete = useCallback((percent: Area) => {
    setArea({ x: round2(percent.x), y: round2(percent.y), w: round2(percent.width), h: round2(percent.height) });
  }, []);

  // Portaled to <body> above the navbar and tab bar, like the photo's own crop step (1020, below antd toasts).
  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Кадр для рамки «${label}»`}
      style={{ position: 'fixed', inset: 0, zIndex: 1020, background: '#000', display: 'flex', flexDirection: 'column' }}
    >
      <div style={{ color: 'var(--app-text-on-dark)', padding: '12px 16px', fontWeight: 600, fontSize: 'var(--text-md)' }}>
        Кадр для рамки «{label}»
      </div>
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        <Cropper
          image={src}
          crop={crop}
          zoom={zoom}
          aspect={aspect}
          cropShape={ROUND_FRAMES.includes(frame) ? 'round' : 'rect'}
          showGrid={!ROUND_FRAMES.includes(frame)}
          initialCroppedAreaPercentages={initial ? { x: initial.x, y: initial.y, width: initial.w, height: initial.h } : undefined}
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            aria-hidden
            style={{
              width: '80px',
              height: '80px',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              ['--app-card-background' as string]: '#111',
            }}
          >
            <div
              style={{
                width: '56px',
                height: '56px',
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                ...sample.box,
              }}
            >
              <PetPhotoFill src={src} alt="" species={species} size={56} crop={area} style={sample.image} />
            </div>
          </div>
          <ZoomIn size={18} strokeWidth={2} style={{ color: 'var(--app-text-on-dark)', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <Slider
              aria-label="Масштаб"
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
            style={buttonStyle('rgba(255, 255, 255, 0.12)')}
          >
            <X size={18} strokeWidth={2.4} />
            Отмена
          </button>
          <button
            type="button"
            disabled={!area}
            onClick={() => {
              if (!area) return;
              hapticFeedback('light');
              onDone(area);
            }}
            style={{ ...buttonStyle('var(--app-primary-fill)'), opacity: area ? 1 : 0.6 }}
          >
            <Check size={18} strokeWidth={2.4} />
            Готово
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function buttonStyle(background: string) {
  return {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    padding: '12px',
    minHeight: 'var(--touch-min)',
    borderRadius: 'var(--radius-md)',
    border: 'none',
    background,
    color: 'var(--app-text-on-dark)',
    fontWeight: 600,
    fontSize: 'var(--text-md)',
    fontFamily: 'inherit',
    cursor: 'pointer',
  } as const;
}
