import { Box, Typography, Button } from '@mui/material';
import ErrorIcon from '@mui/icons-material/Error';

export default function ErrorState({ message = '出错了', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8 }}>
      <ErrorIcon sx={{ fontSize: 64, color: '#f44336', mb: 2 }} />
      <Typography variant="body1" sx={{ color: '#e0e0e0', mb: 1 }}>{message}</Typography>
      {onRetry && (
        <Button variant="outlined" color="error" onClick={onRetry}>重试</Button>
      )}
    </Box>
  );
}
