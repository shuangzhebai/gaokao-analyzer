import { createContext, useMemo, type ReactNode } from 'react';
import type { FC } from 'react';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

interface ThemeContextType {
  mode: 'dark';
}

export const ThemeContext = createContext<ThemeContextType>({ mode: 'dark' });

export const ThemeContextProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const theme = useMemo(() => createTheme({
    palette: {
      mode: 'dark',
      primary: { main: '#00d4ff' },
      secondary: { main: '#7c4dff' },
      background: { default: '#0f0f23', paper: '#1a1a2e' },
    },
    typography: { fontFamily: '"Inter", "Roboto", sans-serif' },
    shape: { borderRadius: 8 },
  }), []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
};
