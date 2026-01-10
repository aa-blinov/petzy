import { useState } from 'react';

interface PetImageProps {
    src: string;
    alt: string;
    size?: number; // Base size in pixels (e.g. 48 for avatar)
    className?: string;
    style?: React.CSSProperties;
}

export function PetImage({ src, alt, size = 48, className, style }: PetImageProps) {
    const [isLoaded, setIsLoaded] = useState(false);
    const [error, setError] = useState(false);

    // Generate srcset for common screen densities
    // Expecting src to be /api/pets/:id/photo
    const generateSrcSet = (baseUrl: string, baseSize: number) => {
        if (!baseUrl.includes('/api/pets/')) return undefined;

        const s1 = `${baseUrl}?w=${baseSize}`;
        const s2 = `${baseUrl}?w=${baseSize * 2} 2x`;
        const s3 = `${baseUrl}?w=${baseSize * 3} 3x`;

        return `${s1}, ${s2}, ${s3}`;
    };

    const srcset = generateSrcSet(src, size);
    const placeholderUrl = src.includes('/api/pets/') ? `${src}?w=20` : src;

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
                        opacity: isLoaded ? 1 : 0,
                        transition: 'opacity 0.3s ease-in-out',
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
                    fontSize: size ? `${size / 2}px` : '24px'
                }}>
                    🐱
                </div>
            )}
        </div>
    );
}
