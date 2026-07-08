import { useState } from 'react';
import { Box, Typography, Paper, TextField, Button, Alert } from '@mui/material';
import { useToast } from '../../components/common/Toast';
import { collectService } from '../../services';

export default function CollectPage() {
  const { show } = useToast();
  const [year, setYear] = useState(new Date().getFullYear());
  const [source, setSource] = useState('');
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<unknown>(null);

  const handleStart = async () => {
    if (year < 2000 || year > 2030) { show('年份无效', 'error'); return; }
    setRunning(true);
    try {
      const result = await collectService.startCollect({ source: source || undefined, year });
      setStatus(result);
      show('采集任务已提交', 'success');
    } catch (e: unknown) {
      const err = e as { message?: string };
      show(err.message || '启动失败', 'error');
    } finally { setRunning(false); }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ color: '#e0e0e0', mb: 3, fontWeight: 600 }}>试卷采集</Typography>
      <Paper sx={{ bgcolor: '#1a1a2e', p: 2, maxWidth: 500 }}>
        <TextField fullWidth label="年份" type="number" size="small" value={year} onChange={(e) => setYear(parseInt(e.target.value) || 2026)} sx={{ mb: 2 }} />
        <TextField fullWidth label="数据源（可选）" size="small" value={source} onChange={(e) => setSource(e.target.value)} helperText="留空表示使用所有数据源" sx={{ mb: 2 }} />
        <Button variant="contained" disabled={running} onClick={handleStart} sx={{ bgcolor: '#00d4ff' }}>
          {running ? '采集中...' : '开始采集'}
        </Button>
        {status ? (
          <Alert severity="info" sx={{ mt: 2 }}>
            任务已提交：{JSON.stringify(status)}
          </Alert>
        ) : null}
      </Paper>
    </Box>
  );
}
