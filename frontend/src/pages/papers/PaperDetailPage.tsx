import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Paper as MuiPaper, Button, Grid } from '@mui/material';
import LoadingState from '../../components/states/LoadingState';
import ErrorState from '../../components/states/ErrorState';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import { useToast } from '../../components/common/Toast';
import { paperService } from '../../services';
import type { Paper, SimulationResult } from '../../types';

export default function PaperDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { show } = useToast();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<SimulationResult | null>(null);

  const fetch = useCallback(() => {
    if (!id) return;
    setLoading(true); setError('');
    paperService.getPaper(parseInt(id))
      .then(setPaper).catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { fetch(); }, [fetch]);

  const handleDelete = async () => {
    if (!id) return;
    try {
      await paperService.deletePaper(parseInt(id));
      show('删除成功', 'success');
      navigate('/papers');
    } catch { show('删除失败', 'error'); }
    setDeleteOpen(false);
  };

  const handleSimulate = async () => {
    if (!id) return;
    setSimulating(true);
    try {
      const result = await paperService.estimateIrt(parseInt(id));
      show('模拟任务已提交', 'info');
      const poll = setInterval(async () => {
        try {
          const status = await paperService.getTaskStatus(result.task_id) as { status: string; result?: SimulationResult };
          if (status.status === 'SUCCESS') {
            setSimResult(status.result || null);
            show('模拟完成', 'success');
            clearInterval(poll);
          } else if (status.status === 'FAILURE') {
            show('模拟失败', 'error');
            clearInterval(poll);
          }
        } catch {
          clearInterval(poll);
        }
      }, 1000);
      setTimeout(() => clearInterval(poll), 60000);
    } catch { show('提交失败', 'error'); }
    finally { setSimulating(false); }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetch} />;
  if (!paper) return <ErrorState message="试卷不存在" />;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Button onClick={() => navigate('/papers')} sx={{ color: '#00d4ff', mb: 1 }}>← 返回列表</Button>
          <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600 }}>{paper.title}</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="contained" disabled={simulating} onClick={handleSimulate} sx={{ bgcolor: '#7c4dff' }}>
            {simulating ? '模拟中...' : 'IRT 模拟'}
          </Button>
          <Button variant="outlined" color="error" onClick={() => setDeleteOpen(true)}>删除</Button>
        </Box>
      </Box>
      <MuiPaper sx={{ bgcolor: '#1a1a2e', p: 2, mb: 2 }}>
        <Grid container spacing={2}>
          {[
            ['科目', paper.subject_name], ['类型', paper.paper_type],
            ['年份', String(paper.year)], ['地区', paper.province],
            ['学校', paper.school], ['状态', paper.analysis_status],
          ].map(([label, value]) => (
            <Grid size={{ xs: 6, md: 4 }} key={label}>
              <Typography variant="caption" sx={{ color: '#666' }}>{label}</Typography>
              <Typography variant="body2" sx={{ color: '#e0e0e0' }}>{value}</Typography>
            </Grid>
          ))}
        </Grid>
      </MuiPaper>
      {simResult && (
        <MuiPaper sx={{ bgcolor: '#1a1a2e', p: 2 }}>
          <Typography variant="h6" sx={{ color: '#00d4ff', mb: 2 }}>模拟结果</Typography>
          <Grid container spacing={2}>
            {[['平均分', simResult.mean], ['标准差', simResult.std], ['中位数', simResult.median],
              ['最高', simResult.max], ['最低', simResult.min], ['P90', simResult.p90]].map(([label, value]) => (
              <Grid size={{ xs: 4, md: 2 }} key={label}>
                <Typography variant="caption" sx={{ color: '#666' }}>{label}</Typography>
                <Typography variant="body1" sx={{ color: '#e0e0e0', fontWeight: 600 }}>{String(value)}</Typography>
              </Grid>
            ))}
          </Grid>
        </MuiPaper>
      )}
      <ConfirmDialog open={deleteOpen} title="确认删除" message={`删除试卷「${paper.title}」？此操作不可恢复。`}
        onConfirm={handleDelete} onCancel={() => setDeleteOpen(false)} />
    </Box>
  );
}
