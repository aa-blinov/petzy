import { useState, createElement, type CSSProperties } from 'react';
import { PetImage } from './PetImage';
import { petCropStyle, type PetCrop } from '../utils/petLook';
import { getSpecies } from '../utils/species';

/**
 * The pet's photo filling the window of its box, whole or the part of it a frame was cropped to. The box (the card's
 * avatar, a sample in the picker, the preview in the crop editor) sets the size and the frame; this fills it.
 */
export function PetPhotoFill({
  src,
  alt,
  species,
  size,
  crop,
  priority,
  style,
}: {
  src: string;
  alt: string;
  species?: string | null;
  size: number;
  crop?: PetCrop;
  priority?: boolean;
  /** For the photo's own corners, where the box's rounding does not reach (the story's round photo). */
  style?: CSSProperties;
}) {
  // A cropped photo that fails to load shows the species picture, like the plain one (PetImage).
  const [failed, setFailed] = useState(false);
  if (crop && failed) {
    const FallbackIcon = getSpecies(species).icon;
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--adm-color-border)', color: 'var(--app-text-tertiary)', ...style }}>
        {createElement(FallbackIcon, { size: Math.round(size * 0.55), strokeWidth: 1.6, 'aria-hidden': true })}
      </div>
    );
  }
  if (!crop) {
    return (
      <PetImage
        src={src}
        alt={alt}
        size={size}
        species={species}
        priority={priority}
        style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 0, ...style }}
      />
    );
  }
  // The window is a box the size of the part; the photo is laid out as large as the whole of it would be, offset so that
  // the part sits in the window, and the window clips the rest.
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', ...style }}>
      <img
        src={src}
        alt={alt}
        draggable={false}
        loading={priority ? 'eager' : 'lazy'}
        decoding="async"
        onError={() => setFailed(true)}
        style={petCropStyle(crop)}
      />
    </div>
  );
}
