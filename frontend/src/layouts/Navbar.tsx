import { AppBar, Toolbar, Box, InputBase, Avatar, IconButton } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useI18n } from '../hooks/useI18n';

export default function Navbar() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [q, setQ] = useState('');

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && q.trim()) {
      navigate(`/papers?q=${encodeURIComponent(q.trim())}`);
    }
  };

  const getInitial = (): string => {
    try {
      const stored = localStorage.getItem('auth_user');
      if (stored) {
        const u = JSON.parse(stored);
        return u.username?.[0]?.toUpperCase() || 'U';
      }
    } catch {
      // ignore
    }
    return 'U';
  };

  return (
    <AppBar position="static" elevation={0} sx={{ bgcolor: '#16213e', borderBottom: '1px solid #333' }}>
      <Toolbar sx={{ gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', bgcolor: '#1a1a2e', borderRadius: 1, px: 1.5, flex: 1, maxWidth: 400 }}>
          <SearchIcon sx={{ color: '#666', mr: 1 }} />
          <InputBase
            placeholder={t('search.placeholder')}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={handleSearch}
            sx={{ color: '#e0e0e0', width: '100%', fontSize: 14 }}
          />
        </Box>
        <Box sx={{ flex: 1 }} />
        <IconButton size="small" sx={{ color: '#a0a0b0' }}>
          <Avatar sx={{ width: 32, height: 32, bgcolor: '#00d4ff', fontSize: 14 }}>
            {getInitial()}
          </Avatar>
        </IconButton>
      </Toolbar>
    </AppBar>
  );
}
