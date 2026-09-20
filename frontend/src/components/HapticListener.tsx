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
            // The antd controls a form is mostly built from — switches,
            // Selector chips, checkboxes, radios — are divs, not
            // buttons, so they fell outside this list. On the medication
            // form that left nine pressable controls (seven weekday
            // chips and two toggles) silent while every button on the
            // same screen buzzed.
            const interactiveElement = target.closest('button, .tap-feedback, .adm-button, .adm-list-item-clickable, .adm-list-item-active-allow, .adm-tab-bar-item, .adm-picker-header-button, .adm-switch, .adm-selector-item, .adm-checkbox, .adm-radio, [role="button"]');

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
