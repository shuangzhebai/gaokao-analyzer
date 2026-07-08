import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Paper, List, ListItemButton, ListItemText } from '@mui/material';
import LoadingState from '../../components/states/LoadingState';
import ErrorState from '../../components/states/ErrorState';
import { docService } from '../../services';

export default function DocsPage() {
  const [docs, setDocs] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetch = useCallback(() => {
    setLoading(true); setError('');
    docService.listDocs().then((data: unknown) => {
      const list = Array.isArray(data) ? data : ((data as Record<string, unknown>)?.data as unknown[]) || [];
      setDocs(list);
    }).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetch} />;

  return (
    <Box>
      <Typography variant="h5" sx={{ color: '#e0e0e0', mb: 2, fontWeight: 600 }}>官方文件库</Typography>
      <Paper sx={{ bgcolor: '#1a1a2e' }}>
        {docs.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4, color: '#666' }}>暂无文件</Box>
        ) : (
          <List>
            {docs.map((doc: unknown) => {
              const d = doc as Record<string, unknown>;
              return (
                <ListItemButton key={String(d.id)} component="a" href={String(d.source_url || '#')} target="_blank">
                  <ListItemText primary={String(d.title || '')} secondary={d.year ? String(d.year) : ''} />
                </ListItemButton>
              );
            })}
          </List>
        )}
      </Paper>
    </Box>
  );
}
