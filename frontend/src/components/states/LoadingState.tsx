import { Box, CircularProgress, Typography } from '@mui/material';

export default function LoadingState({ message = '加载中...' }: { message?: string }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8 }}>
      <CircularProgress sx={{ color: '#00d4ff', mb: 2 }} />
      <Typography variant="body2" sx={{ color: '#a0a0b0' }}>{message}</Typography>
    </Box>
  );
}
