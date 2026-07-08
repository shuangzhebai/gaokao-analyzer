import { Snackbar, Alert } from '@mui/material';
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface ToastMessage { message: string; severity: 'success' | 'error' | 'info' | 'warning'; }
interface ToastContextType { show: (message: string, severity?: ToastMessage['severity']) => void; }

const ToastContext = createContext<ToastContextType>({ show: () => {} });
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState<ToastMessage>({ message: '', severity: 'info' });
  const show = useCallback((message: string, severity: ToastMessage['severity'] = 'info') => {
    setMsg({ message, severity }); setOpen(true);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <Snackbar open={open} autoHideDuration={3000} onClose={() => setOpen(false)} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity={msg.severity} variant="filled" onClose={() => setOpen(false)}>{msg.message}</Alert>
      </Snackbar>
    </ToastContext.Provider>
  );
}
