import { useState, useEffect, useCallback } from 'react';
import { Grid, Paper, Typography, Box, Card, CardContent } from '@mui/material';
import LoadingState from '../../components/states/LoadingState';
import ErrorState from '../../components/states/ErrorState';
import ChartView from '../../components/common/ChartView';
import { getDashboard } from '../../services/dashboard';
import type { DashboardStats } from '../../types';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(() => {
    setLoading(true);
    setError('');
    getDashboard().then(setStats).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetch} />;
  if (!stats) return <ErrorState message="暂无数据" />;

  const statusOption = {
    title: { text: '试卷状态分布', textStyle: { color: '#e0e0e0' } },
    tooltip: { trigger: 'item' },
    series: [{ type: 'pie', data: Object.entries(stats.status_distribution || {}).map(([k, v]) => ({ name: k, value: v })), itemStyle: { borderRadius: 4 } }],
  };
  const subjectOption = {
    title: { text: '科目分布', textStyle: { color: '#e0e0e0' } },
    xAxis: { type: 'category', data: Object.keys(stats.subject_distribution || {}), axisLabel: { color: '#a0a0b0' } },
    yAxis: { type: 'value', axisLabel: { color: '#a0a0b0' } },
    series: [{ type: 'bar', data: Object.values(stats.subject_distribution || {}), itemStyle: { color: '#00d4ff', borderRadius: [4, 4, 0, 0] } }],
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ color: '#e0e0e0', mb: 3, fontWeight: 600 }}>仪表盘</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[
          { label: '试卷总数', value: stats.total_papers, color: '#00d4ff' },
          { label: '试题总数', value: stats.total_questions, color: '#7c4dff' },
          { label: '已分析', value: stats.analyzed_count, color: '#4caf50' },
        ].map((item) => (
          <Grid size={{ xs: 4 }} key={item.label}>
            <Card sx={{ bgcolor: '#1a1a2e', textAlign: 'center' }}>
              <CardContent>
                <Typography variant="h4" sx={{ color: item.color, fontWeight: 700 }}>{item.value}</Typography>
                <Typography variant="body2" sx={{ color: '#a0a0b0' }}>{item.label}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      <Grid container spacing={2}>
        {[statusOption, subjectOption].map((opt, i) => (
          <Grid size={{ xs: 12, md: 6 }} key={i}>
            <Paper sx={{ bgcolor: '#1a1a2e', p: 2 }}>
              <ChartView option={opt} height={280} />
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
