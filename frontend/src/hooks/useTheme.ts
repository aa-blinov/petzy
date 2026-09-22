import { useContext } from 'react';
import { ThemeContext } from '../context/themeContextObject';

export type { Theme } from '../context/themeContextObject';

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
