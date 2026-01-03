import { useTheme } from '../hooks/useTheme';

/**
 * ThemeProvider - компонент для инициализации темы при загрузке приложения
 * Применяет сохраненную тему из localStorage сразу при монтировании
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Вызываем useTheme только для применения темы при загрузке
  // setTheme не используется здесь, он используется только в Settings
  useTheme();

  return <>{children}</>;
}

