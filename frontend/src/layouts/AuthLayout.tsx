import { Box, Paper, Typography } from '@mui/material';
import type { ReactNode } from 'react';

export default function AuthLayout({ children, title }: { children: ReactNode; title: string }) {
  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#0f0f23' }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: '90%' }} elevation={6}>
        <Typography variant="h5" sx={{ mb: 3, textAlign: 'center', color: '#00d4ff', fontWeight: 700 }}>
          {title}
        </Typography>
        {children}
      </Paper>
    </Box>
  );
}
