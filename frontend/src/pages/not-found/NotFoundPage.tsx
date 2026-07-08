import { Box, Typography, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', bgcolor: '#0f0f23' }}>
      <Typography variant="h2" sx={{ color: '#00d4ff', fontWeight: 700, mb: 1 }}>404</Typography>
      <Typography variant="body1" sx={{ color: '#a0a0b0', mb: 3 }}>页面不存在</Typography>
      <Button variant="outlined" onClick={() => navigate('/')}>返回首页</Button>
    </Box>
  );
}
