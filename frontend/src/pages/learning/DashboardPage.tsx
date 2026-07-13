/**
 * 学习仪表盘 — 数据可视化面板
 * 使用 ECharts 展示：能力轨迹、掌握度分布、学习统计
 */
import React, { useEffect, useState } from 'react';
import {
  Box, Grid, Card, CardContent, Typography, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Chip, Alert,
} from '@mui/material';
import {
  TrendingUp, School, EmojiEvents, LocalFireDepartment, ErrorOutline,
} from '@mui/icons-material';

// ECharts 将按需加载，此处先定义基础类型
interface ThetaPoint {
  date: string;
  theta: number;
}

interface MasteryItem {
  name: string;
  value: number;
}

interface DashboardData {
  theta_trace: ThetaPoint[];
  mastery_distribution: MasteryItem[];
}

interface SummaryData {
  theta: number;
  total_errors: number;
  total_diagnoses: number;
  streak: { current: number; longest: number; total_days: number };
  achievements: number;
  top_weak_points: Array<{ kp: string; mastery: number }>;
}

const StatCard: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}> = ({ icon, label, value, color }) => (
  <Card sx={{ p: 2, borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <Box sx={{ color, display: 'flex' }}>{icon}</Box>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, color }}>{value}</Typography>
        <Typography variant="body2" color="text.secondary">{label}</Typography>
      </Box>
    </Box>
  </Card>
);

const LearningDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DashboardData | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/dashboard/learning-progress').then(r => r.json()),
      fetch('/api/v1/reports/learning-summary').then(r => r.json()),
    ])
      .then(([progress, sum]) => {
        setData(progress);
        setSummary(sum);
        setLoading(false);
      })
      .catch(err => {
        setError('获取数据失败，请确保已登录');
        setLoading(false);
      });
  }, []);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', p: 8 }}><CircularProgress /></Box>;
  if (error) return <Alert severity="warning" sx={{ m: 2 }}>{error}</Alert>;
  if (!summary) return <Alert severity="info" sx={{ m: 2 }}>暂无数据</Alert>;

  return (
    <Box sx={{ p: 3, maxWidth: 1200, mx: 'auto' }}>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 600 }}>学习仪表盘</Typography>

      {/* 统计卡片 */}
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid item xs={6} md={3}>
          <StatCard icon={<School />} label="能力值 θ" value={summary.theta.toFixed(2)} color="#2563EB" />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatCard icon={<LocalFireDepartment />} label="连续学习" value={`${summary.streak.current}天`} color="#F97316" />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatCard icon={<EmojiEvents />} label="成就" value={summary.achievements} color="#F59E0B" />
        </Grid>
        <Grid item xs={6} md={3}>
          <StatCard icon={<ErrorOutline />} label="错题" value={summary.total_errors} color="#EF4444" />
        </Grid>
      </Grid>

      {/* 能力轨迹图（ECharts） */}
      <Card sx={{ mb: 3, p: 2, borderRadius: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>能力变化轨迹</Typography>
        <Box id="theta-chart" sx={{ height: 300, width: '100%' }}>
          {data?.theta_trace && data.theta_trace.length > 0 ? (
            <ThetaChart data={data.theta_trace} />
          ) : (
            <Typography color="text.secondary" sx={{ textAlign: 'center', pt: 10 }}>
              暂无评估数据，完成一次诊断即可生成轨迹
            </Typography>
          )}
        </Box>
      </Card>

      {/* 薄弱知识点 */}
      <Card sx={{ mb: 3, borderRadius: 2 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>薄弱知识点 TOP 5</Typography>
          {summary.top_weak_points.length === 0 ? (
            <Typography color="text.secondary">暂无薄弱知识点 🎉</Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>知识点</TableCell>
                    <TableCell>掌握度</TableCell>
                    <TableCell>建议</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {summary.top_weak_points.map((w, i) => (
                    <TableRow key={i}>
                      <TableCell>{w.kp}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Box sx={{
                            flex: 1, height: 8, borderRadius: 4,
                            background: '#E5E7EB', overflow: 'hidden',
                          }}>
                            <Box sx={{
                              width: `${Math.round(w.mastery * 100)}%`,
                              height: '100%',
                              background: w.mastery < 0.3 ? '#EF4444' : w.mastery < 0.5 ? '#F97316' : '#F59E0B',
                              borderRadius: 4,
                            }} />
                          </Box>
                          <Typography variant="caption">{Math.round(w.mastery * 100)}%</Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={w.mastery < 0.3 ? '急需加强' : w.mastery < 0.5 ? '重点突破' : '持续巩固'}
                          size="small"
                          color={w.mastery < 0.3 ? 'error' : w.mastery < 0.5 ? 'warning' : 'info'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

// ====== Lightweight Theta Chart (SVG-based, no ECharts dep) ======
const ThetaChart: React.FC<{ data: ThetaPoint[] }> = ({ data }) => {
  if (!data || data.length < 2) return null;

  const values = data.map(d => d.theta);
  const min = Math.min(...values) - 0.2;
  const max = Math.max(...values) + 0.2;
  const range = max - min || 1;
  const w = 600, h = 250, px = 50, py = 20;

  const xScale = (i: number) => px + (i / (data.length - 1)) * (w - px * 2);
  const yScale = (v: number) => h - py - ((v - min) / range) * (h - py * 2);

  const points = data.map((d, i) => `${xScale(i)},${yScale(d.theta)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: '100%' }}>
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map(r => {
        const y = yScale(min + range * r);
        return (
          <g key={r}>
            <line x1={px} y1={y} x2={w - px} y2={y} stroke="#E5E7EB" strokeWidth={1} />
            <text x={px - 8} y={y + 4} textAnchor="end" fontSize={11} fill="#9CA3AF">
              {(min + range * r).toFixed(1)}
            </text>
          </g>
        );
      })}

      {/* Line */}
      <polyline points={points} fill="none" stroke="#2563EB" strokeWidth={2.5} strokeLinejoin="round" />

      {/* Dots */}
      {data.map((d, i) => (
        <circle key={i} cx={xScale(i)} cy={yScale(d.theta)} r={4} fill="#2563EB" stroke="white" strokeWidth={2} />
      ))}

      {/* X-axis labels (show first, last, and every other) */}
      {data.filter((_, i) => i === 0 || i === data.length - 1 || i % Math.ceil(data.length / 5) === 0).map((d, i) => (
        <text key={i} x={xScale(data.indexOf(d))} y={h - 4} textAnchor="middle" fontSize={10} fill="#9CA3AF">
          {d.date.slice(5, 10)}
        </text>
      ))}

      <text x={w / 2} y={h - py + 12} textAnchor="middle" fontSize={11} fill="#9CA3AF">日期</text>
      <text x={12} y={h / 2} textAnchor="middle" fontSize={11} fill="#9CA3AF"
            transform={`rotate(-90, 12, ${h/2})`}>能力值 θ</text>
    </svg>
  );
};

export default LearningDashboard;
