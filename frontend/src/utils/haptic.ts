/**
 * Simple utility for haptic feedback
 */
export const hapticFeedback = (strength: 'light' | 'medium' | 'heavy' = 'light') => {
    if (typeof window !== 'undefined' && window.navigator && window.navigator.vibrate) {
        const pattern = strength === 'light' ? 10 : strength === 'medium' ? 20 : 40;
        window.navigator.vibrate(pattern);
    }
};
