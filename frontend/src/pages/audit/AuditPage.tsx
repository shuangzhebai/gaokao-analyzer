import { useState } from 'react';
import { Box, Typography, Paper, TextField, Button, Alert } from '@mui/material';
import { useToast } from '../../components/common/Toast';
import { auditService } from '../../services';

export default function AuditPage() {
  const { show } = useToast();
  const [paperId, setPaperId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<unknown>(null);

  const handleRun = async () => {
    const id = parseInt(paperId);
    if (!id || id < 1) { show('请输入有效试卷 ID', 'error'); return; }
    setRunning(true);
    try {
      const res = await auditService.runAudit(id);
      setResult(res);
      show('审核完成', 'success');
    } catch (e: unknown) {
      const err = e as { message?: string };
      show(err.message || '审核失败', 'error');
    } finally { setRunning(false); }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ color: '#e0e0e0', mb: 3, fontWeight: 600 }}>真实性审核</Typography>
      <Paper sx={{ bgcolor: '#1a1a2e', p: 2, maxWidth: 500 }}>
        <TextField fullWidth label="试卷 ID" type="number" size="small" value={paperId} onChange={(e) => setPaperId(e.target.value)} sx={{ mb: 2 }} />
        <Button variant="contained" disabled={running} onClick={handleRun} sx={{ bgcolor: '#00d4ff' }}>
          {running ? '审核中...' : '开始审核'}
        </Button>
        {result ? (
          <Alert severity={(result as Record<string, unknown>).verified ? 'success' : 'warning'} sx={{ mt: 2 }}>
            {JSON.stringify(result)}
          </Alert>
        ) : null}
      </Paper>
    </Box>
  );
}
