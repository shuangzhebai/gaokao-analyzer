import { useState, useEffect, useRef } from 'react';
import { Box, Typography, Grid, Paper, Chip } from '@mui/material';
import { errorService } from '../../services';
import * as echarts from 'echarts/core';

export default function StudentDashboard() {
  const [stats, setStats] = useState<any>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    errorService.getStats(1).then(r => setStats(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!chartRef.current || !stats?.by_subject) return;
    const chart = echarts.init(chartRef.current);
    const subjects = Object.keys(stats.by_subject);
    const values = Object.values(stats.by_subject) as number[];
    chart.setOption({
      tooltip: { trigger: 'axis' },
      radar: {
        indicator: subjects.map(s => ({ name: s, max: Math.max(...values, 10) })),
        shape: 'circle',
        splitArea: { areaStyle: { color: ['rgba(0,212,255,0.02)', 'rgba(0,212,255,0.04)'] } },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.15)' } },
        axisName: { color: '#999', fontSize: 11 },
      },
      series: [{
        type: 'radar',
        data: [{ value: values, areaStyle: { color: 'rgba(0,212,255,0.2)' }, lineStyle: { color: '#00d4ff' }, itemStyle: { color: '#00d4ff' } }],
      }],
    });
    return () => chart.dispose();
  }, [stats]);

  return (
    <Box>
      <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>学生工作台</Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2, textAlign: 'center' }}>
            <Typography sx={{ color: '#f44336', fontSize: 36, fontWeight: 700 }}>{stats?.total_errors || 0}</Typography>
            <Typography sx={{ color: '#999', fontSize: 13 }}>累计错题</Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2, textAlign: 'center' }}>
            <Typography sx={{ color: '#00d4ff', fontSize: 36, fontWeight: 700 }}>
              {Object.keys(stats?.by_subject || {}).length}
            </Typography>
            <Typography sx={{ color: '#999', fontSize: 13 }}>学科数</Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2, textAlign: 'center' }}>
            <Typography sx={{ color: '#4caf50', fontSize: 36, fontWeight: 700 }}>-</Typography>
            <Typography sx={{ color: '#999', fontSize: 13 }}>IRT θ 均值</Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2 }}>
            <Typography variant="subtitle2" sx={{ color: '#e0e0e0', mb: 1 }}>各科错题分布</Typography>
            <div ref={chartRef} style={{ width: '100%', height: 280 }} />
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2 }}>
            <Typography variant="subtitle2" sx={{ color: '#e0e0e0', mb: 1 }}>快速入口</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Chip label="错题本" component="a" href="/errors" clickable sx={{ color: '#00d4ff', borderColor: '#00d4ff' }} variant="outlined" />
              <Chip label="质量诊断" component="a" href="/quality" clickable sx={{ color: '#4caf50', borderColor: '#4caf50' }} variant="outlined" />
              <Chip label="题型库" component="a" href="/questions" clickable sx={{ color: '#ff9800', borderColor: '#ff9800' }} variant="outlined" />
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
