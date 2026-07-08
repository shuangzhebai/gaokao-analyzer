import { ToastProvider } from './components/common/Toast';
import AppRoutes from './routes';

function App() {
  return (
    <ToastProvider>
      <AppRoutes />
    </ToastProvider>
  );
}

export default App;
