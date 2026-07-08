import { BottomNavigation, BottomNavigationAction, Paper } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DescriptionIcon from '@mui/icons-material/Description';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import SearchIcon from '@mui/icons-material/Search';
import { useI18n } from '../hooks/useI18n';

const TABS = [
  { path: '/', labelKey: 'nav.dashboard', icon: <DashboardIcon /> },
  { path: '/papers', labelKey: 'nav.papers', icon: <DescriptionIcon /> },
  { path: '/collect', labelKey: 'nav.collect', icon: <CloudDownloadIcon /> },
  { path: '/papers?q=', labelKey: 'nav.search', icon: <SearchIcon /> },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useI18n();
  const value = TABS.findIndex((tab) => location.pathname === tab.path.split('?')[0]);

  return (
    <Paper sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, display: { md: 'none' } }} elevation={3}>
      <BottomNavigation
        value={Math.max(0, value)}
        onChange={(_, i) => navigate(TABS[i].path)}
        sx={{ bgcolor: '#1a1a2e', '& .Mui-selected': { '& .MuiBottomNavigationAction-label': { color: '#00d4ff' } } }}
      >
        {TABS.map((tab) => (
          <BottomNavigationAction
            key={tab.path}
            icon={tab.icon}
            label={t(tab.labelKey)}
            sx={{ color: '#a0a0b0', '&.Mui-selected': { color: '#00d4ff' } }}
          />
        ))}
      </BottomNavigation>
    </Paper>
  );
}
