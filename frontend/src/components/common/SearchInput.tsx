import { useState, useEffect, useRef } from 'react';
import { Box, InputBase, Paper, ListItemButton, ListItemText, Popper } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useDebounce } from '../../hooks/useDebounce';
import { getSuggestions } from '../../services/search';
import { useNavigate } from 'react-router-dom';
import type { SearchSuggestion } from '../../types';

export default function SearchInput() {
  const [q, setQ] = useState('');
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const debouncedQ = useDebounce(q, 300);
  const anchorRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (debouncedQ.length < 2) { setSuggestions([]); setOpen(false); return; }
    getSuggestions(debouncedQ).then((data) => {
      setSuggestions(data || []); setOpen((data?.length || 0) > 0);
    }).catch(() => {});
  }, [debouncedQ]);

  return (
    <Box ref={anchorRef} sx={{ position: 'relative' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', bgcolor: '#1a1a2e', borderRadius: 1, px: 1.5 }}>
        <SearchIcon sx={{ color: '#666', mr: 1 }} />
        <InputBase
          placeholder="搜索试卷..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && q.trim()) { setOpen(false); navigate(`/papers?q=${encodeURIComponent(q)}`); } }}
          sx={{ color: '#e0e0e0', width: 300, fontSize: 14 }}
        />
      </Box>
      <Popper open={open} anchorEl={anchorRef.current} placement="bottom-start" style={{ zIndex: 1300, width: anchorRef.current?.offsetWidth }}>
        <Paper sx={{ mt: 1, bgcolor: '#1a1a2e', border: '1px solid #333' }}>
          {suggestions.slice(0, 6).map((s) => (
            <ListItemButton key={s.id} onClick={() => { setOpen(false); navigate(`/papers/${s.id}`); }}>
              <ListItemText primary={s.title} secondary={`${s.subject_name} ${s.year}`} />
            </ListItemButton>
          ))}
        </Paper>
      </Popper>
    </Box>
  );
}
