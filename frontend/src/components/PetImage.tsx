import { useState, createElement } from 'react';
import { getSpecies } from '../utils/species';

interface PetImageProps {
    src: string;
    alt: string;
    size?: number; // Base size in pixels (e.g. 48 for avatar)
    className?: string;
    style?: React.CSSProperties;
    /** Optional species hint — picks the lucide placeholder icon
        when the photo fails to load. Falls back to PawPrint. */
    species?: string | null;
    /** object-position for the cropped photo. Defaults to biasing
        toward the top: a `cover` crop centered on a tall portrait photo
        (the common shape for a pet photo taken by a phone) cuts off the
        face — which sits in the upper third, not the vertical middle —
        and shows fur/torso instead. */
    objectPosition?: string;
}

export function PetImage({ src, alt, size = 48, className, style, species, objectPosition = 'center 20%' }: PetImageProps) {
    const [isLoaded, setIsLoaded] = useState(false);
    const [error, setError] = useState(false);
    // getSpecies() picks among a fixed set of module-level lucide icons —
    // it never creates a new component. createElement (rather than JSX
    // <FallbackIcon .../>) keeps the react-hooks/static-components rule from
    // flagging this as a component defined during render, which it can't
    // tell apart from a real one from the syntax alone.
    const FallbackIcon = getSpecies(species).icon;

    // Generate srcset for common screen densities
    // Expecting src to be /api/pets/:id/photo
    const generateSrcSet = (baseUrl: string, baseSize: number) => {
        if (!baseUrl.includes('/api/pets/')) return undefined;

        // photo_url already carries `?v=…` — a second `?` turned `w` into
        // part of `v`, so every thumbnail silently fetched the full photo.
        const sep = baseUrl.includes('?') ? '&' : '?';
        const s1 = `${baseUrl}${sep}w=${baseSize}`;
        const s2 = `${baseUrl}${sep}w=${baseSize * 2} 2x`;
        const s3 = `${baseUrl}${sep}w=${baseSize * 3} 3x`;

        return `${s1}, ${s2}, ${s3}`;
    };

    const srcset = generateSrcSet(src, size);
    const placeholderUrl = src.includes('/api/pets/') ? `${src}${src.includes('?') ? '&' : '?'}w=20` : src;

    return (
        <div
            className={className}
            style={{
                position: 'relative',
                overflow: 'hidden',
                width: size ? `${size}px` : '100%',
                height: size ? `${size}px` : '100%',
                backgroundColor: 'var(--app-white-05)',
                ...style
            }}
        >
            {/* Blurred Placeholder */}
            {!isLoaded && !error && (
                <img
                    src={placeholderUrl}
                    alt=""
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        objectPosition,
                        filter: 'blur(10px)',
                        transform: 'scale(1.1)',
                        position: 'absolute',
                        top: 0,
                        left: 0,
                    }}
                />
            )}

            {/* Main Image */}
            {!error && (
                <img
                    src={`${src}${src.includes('?') ? '&' : '?'}w=${size * 2}`} // Default to 2x for quality
                    srcSet={srcset}
                    alt={alt}
                    loading="lazy"
                    decoding="async"
                    onLoad={() => setIsLoaded(true)}
                    onError={() => setError(true)}
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        objectPosition,
                        opacity: isLoaded ? 1 : 0,
                        transition: `opacity var(--motion-duration-base) var(--motion-ease-standard)`,
                        display: 'block',
                    }}
                />
            )}

            {/* Fallback */}
            {error && (
                <div style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: 'var(--adm-color-border)',
                    color: 'var(--app-text-tertiary)',
                }}>
                    {createElement(FallbackIcon, { size: size ? Math.round(size * 0.55) : 24, strokeWidth: 1.6, 'aria-hidden': true })}
                </div>
            )}
        </div>
    );
}
