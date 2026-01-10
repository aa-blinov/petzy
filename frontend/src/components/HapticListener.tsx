import { useEffect } from 'react';
import { hapticFeedback } from '../utils/haptic';

/**
 * Global listener for haptic feedback on interactive elements
 */
export function HapticListener() {
    useEffect(() => {
        const handleGlobalClick = (e: MouseEvent) => {
            const target = e.target as HTMLElement;

            // Check if clicked element or its parent is a button or has tap-feedback
            const interactiveElement = target.closest('button, .tap-feedback, .adm-button, .adm-list-item-clickable, .adm-list-item-active-allow, .adm-tab-bar-item, .adm-picker-header-button, [role="button"]');

            if (interactiveElement) {
                // Use a slight delay to not interfere with potential immediate navigation
                // and to match the visual "press" timing
                hapticFeedback('light');
            }
        };

        window.addEventListener('click', handleGlobalClick, { capture: true });

        return () => {
            window.removeEventListener('click', handleGlobalClick, { capture: true });
        };
    }, []);

    return null;
}
