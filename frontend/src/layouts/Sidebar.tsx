import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useI18n } from '../hooks/useI18n';
import {
  Box, List, ListItemButton, ListItemIcon, ListItemText,
  Typography, Button, Divider,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DescriptionIcon from '@mui/icons-material/Description';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import type { ReactElement } from 'react';

interface NavItem {
  path: string;
  labelKey: string;
  icon: ReactElement;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', labelKey: 'nav.dashboard', icon: <DashboardIcon /> },
  { path: '/papers', labelKey: 'nav.papers', icon: <DescriptionIcon /> },
  { path: '/collect', labelKey: 'nav.collect', icon: <CloudDownloadIcon /> },
  { path: '/docs', labelKey: 'nav.docs', icon: <LibraryBooksIcon /> },
  { path: '/audit', labelKey: 'nav.audit', icon: <VerifiedUserIcon /> },
];

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useI18n();

  return (
    <Box sx={{ width: 240, bgcolor: '#1a1a2e', height: '100vh', display: 'flex', flexDirection: 'column', borderRight: '1px solid #333' }}>
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="h6" sx={{ color: '#00d4ff', fontWeight: 700 }}>
          {t('app.name')}
        </Typography>
      </Box>
      <Divider sx={{ borderColor: '#333' }} />
      <List sx={{ flex: 1, pt: 1 }}>
        {NAV_ITEMS.map((item) => (
          <ListItemButton
            key={item.path}
            selected={location.pathname === item.path}
            onClick={() => navigate(item.path)}
            sx={{ mx: 1, borderRadius: 1, mb: 0.5,
              '&.Mui-selected': { bgcolor: 'rgba(0,212,255,0.12)' },
            }}
          >
            <ListItemIcon sx={{ color: location.pathname === item.path ? '#00d4ff' : '#a0a0b0', minWidth: 40 }}>
              {item.icon}
            </ListItemIcon>
            <ListItemText primary={t(item.labelKey)} sx={{ '& .MuiListItemText-primary': { fontSize: 14 } }} />
          </ListItemButton>
        ))}
      </List>
      <Divider sx={{ borderColor: '#333' }} />
      <Box sx={{ p: 2 }}>
        {user && (
          <Typography variant="body2" sx={{ color: '#a0a0b0', mb: 1 }}>
            {user.username} ({user.role})
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" variant="outlined" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')} sx={{ flex: 1, fontSize: 12 }}>
            {lang === 'zh' ? 'EN' : '中文'}
          </Button>
          {user && (
            <Button size="small" variant="text" color="error" onClick={logout} sx={{ flex: 1, fontSize: 12 }}>
              {t('auth.logout')}
            </Button>
          )}
        </Box>
      </Box>
    </Box>
  );
}
