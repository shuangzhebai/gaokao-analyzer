import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Navbar from './Navbar';
import BottomNav from './BottomNav';

export default function RootLayout() {
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Box sx={{ display: { xs: 'none', md: 'block' } }}>
        <Sidebar />
      </Box>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Navbar />
        <Box sx={{ flex: 1, p: { xs: 1.5, md: 3 }, overflow: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
      <BottomNav />
    </Box>
  );
}
