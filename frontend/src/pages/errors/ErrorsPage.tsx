import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, TextField, MenuItem, Grid, Paper, Chip, Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import LoadingState from '../../components/states/LoadingState';
import ErrorState from '../../components/states/ErrorState';
import ErrorList from './ErrorList';
import WeaknessDiagnosisPanel from './WeaknessDiagnosis';
import SimilarRecommend from './SimilarRecommend';
import { errorService } from '../../services';
import type { ErrorRecord, ErrorStats, WeaknessDiagnosis } from '../../types/error';

const SUBJECTS = [
  { id: 'math', name: '数学' }, { id: 'chinese', name: '语文' }, { id: 'english', name: '英语' },
  { id: 'physics', name: '物理' }, { id: 'chemistry', name: '化学' }, { id: 'biology', name: '生物' },
  { id: 'history', name: '历史' }, { id: 'geography', name: '地理' }, { id: 'politics', name: '政治' },
];

const ERROR_REASONS = [
  { id: '', name: '全部' },
  { id: 'concept', name: '概念不清' },
  { id: 'careless', name: '粗心大意' },
  { id: 'calculation', name: '计算错误' },
  { id: 'strategy', name: '策略失误' },
  { id: 'other', name: '其他' },
];

const MOCK_USER_ID = 1;

export default function ErrorsPage() {
  const [records, setRecords] = useState<ErrorRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [subject, setSubject] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [stats, setStats] = useState<ErrorStats | null>(null);
  const [diagnosis, setDiagnosis] = useState<WeaknessDiagnosis | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<ErrorRecord | null>(null);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);

  const fetchRecords = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const params: Record<string, any> = { user_id: MOCK_USER_ID, page, size: 20 };
      if (subject) params.subject_id = subject;
      if (reason) params.error_reason = reason;
      const res = await errorService.list(params);
      setRecords(res.data.data);
      setTotal(res.data.total);
    } catch (e: unknown) {
      setError((e as { message?: string }).message || '加载失败');
    } finally { setLoading(false); }
  }, [page, subject, reason]);

  useEffect(() => { fetchRecords(); }, [fetchRecords]);

  useEffect(() => {
    errorService.getStats(MOCK_USER_ID, subject || undefined).then(r => setStats(r.data)).catch(() => {});
  }, [subject]);

  useEffect(() => {
    if (subject) {
      errorService.getDiagnosis(MOCK_USER_ID, subject).then(r => setDiagnosis(r.data)).catch(() => {});
    } else {
      setDiagnosis(null);
    }
  }, [subject]);

  const handleSelect = async (record: ErrorRecord) => {
    setSelectedRecord(record);
    setDetailOpen(true);
    try {
      const res = await errorService.recommend(record.question_id, 3);
      setRecommendations(res.data || []);
    } catch { setRecommendations([]); }
  };

  const handleMarkMastered = async (id: number) => {
    try {
      await errorService.update(id, { is_mastered: 1 });
      fetchRecords();
    } catch {}
  };

  const handleDelete = async (id: number) => {
    try {
      await errorService.delete(id);
      fetchRecords();
    } catch {}
  };

  return (
    <Box sx={{ height: 'calc(100vh - 120px)', overflow: 'auto' }}>
      <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>错题库</Typography>

      {/* 筛选栏 */}
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <TextField select label="学科" size="small" value={subject}
          onChange={(e) => { setSubject(e.target.value); setPage(1); }}
          sx={{ minWidth: 100, '& input, & .MuiSelect-select': { color: '#e0e0e0' } }}>
          {SUBJECTS.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
        </TextField>
        <TextField select label="错误原因" size="small" value={reason}
          onChange={(e) => { setReason(e.target.value); setPage(1); }}
          sx={{ minWidth: 120, '& input, & .MuiSelect-select': { color: '#e0e0e0' } }}>
          {ERROR_REASONS.map((r) => <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>)}
        </TextField>
        <Typography variant="body2" sx={{ color: '#666', alignSelf: 'center', ml: 'auto' }}>
          共 {total} 条错题
        </Typography>
      </Box>

      <Grid container spacing={2}>
        {/* 左侧：薄弱诊断 */}
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2, height: '100%' }}>
            <WeaknessDiagnosisPanel diagnosis={subject ? diagnosis : null} />
          </Paper>
        </Grid>

        {/* 中间：错题列表 */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2 }}>
            {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={fetchRecords} /> : (
              <ErrorList records={records} total={total} page={page}
                onPageChange={setPage} onSelect={handleSelect}
                onDelete={handleDelete} onMarkMastered={handleMarkMastered} />
            )}
          </Paper>
        </Grid>

        {/* 右侧：统计概览 */}
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2 }}>
            <Typography variant="subtitle2" sx={{ color: '#e0e0e0', mb: 1.5 }}>统计概览</Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-around', mb: 2 }}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography sx={{ color: '#f44336', fontSize: 24, fontWeight: 700 }}>{stats?.total_errors || 0}</Typography>
                <Typography sx={{ color: '#999', fontSize: 12 }}>错题总数</Typography>
              </Box>
              <Box sx={{ textAlign: 'center' }}>
                <Typography sx={{ color: '#00d4ff', fontSize: 24, fontWeight: 700 }}>{Object.keys(stats?.by_subject || {}).length}</Typography>
                <Typography sx={{ color: '#999', fontSize: 12 }}>涉及学科</Typography>
              </Box>
            </Box>

            <Typography variant="subtitle2" sx={{ color: '#999', fontSize: 12, mb: 1 }}>按原因分布</Typography>
            {stats?.by_reason && Object.entries(stats.by_reason).map(([k, v]) => (
              <Box key={k} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography sx={{ color: '#ccc', fontSize: 12 }}>{ERROR_REASONS.find(r => r.id === k)?.name || k}</Typography>
                <Typography sx={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>{v}</Typography>
              </Box>
            ))}
            {(!stats?.by_reason || Object.keys(stats.by_reason).length === 0) && (
              <Typography sx={{ color: '#666', fontSize: 12 }}>暂无数据</Typography>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* 详情弹窗 */}
      <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="sm" fullWidth
        PaperProps={{ sx: { bgcolor: '#1a1a2e', color: '#e0e0e0', backgroundImage: 'none' } }}>
        <DialogTitle sx={{ borderBottom: '1px solid #333' }}>
          <Typography variant="h6">错题详情 #{selectedRecord?.id}</Typography>
        </DialogTitle>
        <DialogContent sx={{ py: 2 }}>
          {selectedRecord && (
            <Box>
              <Typography variant="subtitle2" sx={{ color: '#999', mb: 1 }}>题目信息</Typography>
              <Typography sx={{ color: '#ccc', fontSize: 13, mb: 1 }}>题目 ID: {selectedRecord.question_id}</Typography>
              <Typography sx={{ color: '#ccc', fontSize: 13, mb: 1 }}>学科: {selectedRecord.subject_id}</Typography>
              <Typography sx={{ color: '#ccc', fontSize: 13, mb: 1 }}>错误原因: {ERROR_REASONS.find(r => r.id === selectedRecord.error_reason)?.name || selectedRecord.error_reason}</Typography>
              <Typography sx={{ color: '#ccc', fontSize: 13, mb: 1 }}>错误次数: {selectedRecord.attempt_count}</Typography>
              <Typography sx={{ color: '#ccc', fontSize: 13, mb: 2 }}>状态: {selectedRecord.is_mastered ? '已掌握' : '未掌握'}</Typography>

              <SimilarRecommend recommendations={recommendations} />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailOpen(false)} sx={{ color: '#999' }}>关闭</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
