import React, { useState, useEffect } from 'react';
import { ThemeContext, type Theme } from './themeContextObject';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<Theme>(() => {
        const saved = localStorage.getItem('theme') as Theme;
        return saved || 'system';
    });

    const [isDark, setIsDark] = useState(false);

    useEffect(() => {
        const root = document.documentElement;
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

        const applyTheme = () => {
            const isSystemDark = mediaQuery.matches;
            const effectivelyDark = theme === 'dark' || (theme === 'system' && isSystemDark);

            setIsDark(effectivelyDark);

            if (effectivelyDark) {
                root.setAttribute('data-prefers-color-scheme', 'dark');
                root.classList.add('dark'); // Optional but helpful
            } else {
                root.setAttribute('data-prefers-color-scheme', 'light');
                root.classList.remove('dark');
            }
        };

        applyTheme();

        const handleSystemChange = () => {
            if (theme === 'system') {
                applyTheme();
            }
        };

        mediaQuery.addEventListener('change', handleSystemChange);
        return () => mediaQuery.removeEventListener('change', handleSystemChange);
    }, [theme]);

    const setTheme = (newTheme: Theme) => {
        setThemeState(newTheme);
        localStorage.setItem('theme', newTheme);
    };

    return (
        <ThemeContext.Provider value={{ theme, setTheme, isDark }}>
            {children}
        </ThemeContext.Provider>
    );
}

