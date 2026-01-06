import { ThemeProvider as ContextProvider } from '../context/ThemeContext';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <ContextProvider>{children}</ContextProvider>;
}

