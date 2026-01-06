import { useTheme as useThemeContext } from '../context/ThemeContext';

export type { Theme } from '../context/ThemeContext';

export function useTheme() {
  return useThemeContext();
}

