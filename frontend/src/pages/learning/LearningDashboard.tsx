import React, { useState, useEffect } from 'react';
import {
  Box, Grid, Card, CardContent, Typography, Chip, Button,
  Tabs, Tab, LinearProgress, Avatar, Paper, Stack, IconButton,
} from '@mui/material';
import {
  TrendingUp, Clock, Brain, Route, BookOpen, ClipboardCheck,
  Activity, CheckCircle2, AlertTriangle, ChevronRight,
} from 'lucide-react';

interface MetricCard {
  label: string;
  value: string | number;
  trend?: { direction: 'up' | 'down'; value: string };
  icon: React.ReactNode;
  color: string;
}

interface AgentEntry {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  linkTo: string;
}

const metrics: MetricCard[] = [
  { label: '今日学习', value: '2.5h', trend: { direction: 'up', value: '15%' }, icon: <Clock size={24} />, color: '#2563EB' },
  { label: '已掌握', value: '128个', icon: <CheckCircle2 size={24} />, color: '#16A34A' },
  { label: '待复习', value: '23个', trend: { direction: 'down', value: '8%' }, icon: <AlertTriangle size={24} />, color: '#D97706' },
  { label: '本周进步', value: '+12%', trend: { direction: 'up', value: 'vs上周' }, icon: <TrendingUp size={24} />, color: '#0D9488' },
];

const agentEntries: AgentEntry[] = [
  { id: 'diagnosis', title: '学习诊断', description: '知识薄弱点热力图·能力雷达分析', icon: <Activity size={32} />, linkTo: '/dashboard/student/diagnosis' },
  { id: 'planning', title: '课程规划', description: '个性化学习路径·时间线+里程碑', icon: <Route size={32} />, linkTo: '/dashboard/student/learning-path' },
  { id: 'recommendation', title: '习题推荐', description: '智能推送练习题·难度+知识点筛选', icon: <BookOpen size={32} />, linkTo: '/dashboard/student/exercises' },
  { id: 'assessment', title: '阶段测评', description: '阶段测试+反馈·成绩报告+曲线', icon: <ClipboardCheck size={32} />, linkTo: '/dashboard/student/assessment' },
];

/* ---------- 指标卡片 ---------- */
const MetricCardRow: React.FC<{ metrics: MetricCard[] }> = ({ metrics }) => (
  <Grid container spacing={2} sx={{ mb: 3 }}>
    {metrics.map((m) => (
      <Grid item xs={6} md={3} key={m.label}>
        <Card sx={{ p: 2.5, boxShadow: '0 1px 3px rgba(0,0,0,0.06),0 1px 2px rgba(0,0,0,0.04)', borderRadius: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Box>
              <Typography variant="body2" sx={{ color: '#78716C', mb: 0.5, fontSize: 14 }}>{m.label}</Typography>
              <Typography sx={{ fontFamily: '"JetBrains Mono",monospace', fontSize: 30, fontWeight: 700, color: '#292524', lineHeight: 1.2 }}>
                {m.value}
              </Typography>
              {m.trend && (
                <Typography sx={{ fontSize: 12, color: m.trend.direction === 'up' ? '#16A34A' : '#DC2626', mt: 0.5, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  {m.trend.direction === 'up' ? '↑' : '↓'} {m.trend.value}
                </Typography>
              )}
            </Box>
            <Box sx={{ color: m.color, opacity: 0.8 }}>{m.icon}</Box>
          </Stack>
        </Card>
      </Grid>
    ))}
  </Grid>
);

/* ---------- 周活动图（简化版） ---------- */
const WeeklyActivity: React.FC = () => {
  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  const data = [2.0, 1.5, 2.5, 0, 3.0, 1.8, 0.5];
  const maxVal = Math.max(...data, 1);
  return (
    <Card sx={{ p: 3, borderRadius: 2 }}>
      <Typography variant="h6" sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 2 }}>本周学习活动</Typography>
      <Stack direction="row" spacing={1} alignItems="flex-end" sx={{ height: 120, pt: 1 }}>
        {data.map((v, i) => (
          <Box key={i} sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: '100%', maxWidth: 32, height: `${(v / maxVal) * 80}px`, bgcolor: v > 0 ? '#2563EB' : '#E7E5E4', borderRadius: '4px 4px 0 0', minHeight: v > 0 ? 4 : 20, transition: 'height 250ms' }} />
            <Typography sx={{ fontSize: 11, color: '#78716C' }}>{days[i]}</Typography>
          </Box>
        ))}
      </Stack>
    </Card>
  );
};

/* ---------- 诊断摘要 ---------- */
const DiagnosisSummaryCard: React.FC = () => (
  <Card sx={{ p: 3, borderRadius: 2 }}>
    <Typography variant="h6" sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 1.5 }}>最近诊断摘要</Typography>
    <Stack spacing={1.5}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography sx={{ fontSize: 14, color: '#57534E' }}>优势领域</Typography>
        <Chip label="函数与导数" size="small" sx={{ bgcolor: '#F0FDF4', color: '#16A34A', fontWeight: 500, fontSize: 12 }} />
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography sx={{ fontSize: 14, color: '#57534E' }}>薄弱领域</Typography>
        <Chip label="立体几何" size="small" sx={{ bgcolor: '#FEF2F2', color: '#DC2626', fontWeight: 500, fontSize: 12 }} />
      </Box>
      <Box sx={{ textAlign: 'right', mt: 0.5 }}>
        <Typography component="a" href="/dashboard/student/diagnosis" sx={{ fontSize: 14, color: '#2563EB', fontWeight: 500, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 0.5, '&:hover': { textDecoration: 'underline' } }}>
          查看完整报告 <ChevronRight size={16} />
        </Typography>
      </Box>
    </Stack>
  </Card>
);

/* ---------- Agent入口卡片 ---------- */
const AgentCard: React.FC<{ entry: AgentEntry }> = ({ entry }) => (
  <Card
    component="a"
    href={entry.linkTo}
    sx={{
      p: 2.5, borderRadius: 2, cursor: 'pointer', textDecoration: 'none',
      display: 'flex', gap: 2, transition: 'all 250ms ease-out',
      '&:hover': { boxShadow: '0 4px 6px rgba(0,0,0,0.04),0 2px 4px rgba(0,0,0,0.04)', transform: 'translateY(-2px)' },
    }}
  >
    <Box sx={{ color: '#2563EB', flexShrink: 0 }}>{entry.icon}</Box>
    <Box sx={{ flex: 1 }}>
      <Typography sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 0.5 }}>{entry.title}</Typography>
      <Typography sx={{ fontSize: 14, color: '#78716C', mb: 0.5 }}>{entry.description}</Typography>
      <Typography sx={{ fontSize: 14, color: '#2563EB', fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
        {entry.id === 'diagnosis' ? '进入诊断' :
         entry.id === 'planning' ? '查看规划' :
         entry.id === 'recommendation' ? '开始练习' : '进入测评'} <ChevronRight size={16} />
      </Typography>
    </Box>
  </Card>
);

/* ============================================================ */
/* 主组件：学习概览仪表盘                                         */
/* ============================================================ */
const LearningDashboard: React.FC = () => {
  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 4 }}>
      {/* 顶部欢迎栏 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, pb: 2, borderBottom: '1px solid #E7E5E4' }}>
        <Box>
          <Typography sx={{ fontSize: 30, fontWeight: 700, color: '#292524' }}>
            欢迎回来，同学<span style={{ fontSize: 18, fontWeight: 400, color: '#78716C', marginLeft: 8 }}>今天也是进步的一天</span>
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Chip icon={<TrendingUp size={16} />} label="连续学习 15 天" variant="outlined" sx={{ borderRadius: 9999, fontSize: 12, fontWeight: 500 }} />
          <Typography sx={{ fontSize: 14, color: '#A8A29E' }}>距高考 312 天</Typography>
        </Box>
      </Box>

      {/* 指标卡片 */}
      <MetricCardRow metrics={metrics} />

      {/* 第二行：活动图 + 诊断摘要 */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={8}>
          <WeeklyActivity />
        </Grid>
        <Grid item xs={12} md={4}>
          <DiagnosisSummaryCard />
        </Grid>
      </Grid>

      {/* AI 学习助手 2×2 */}
      <Typography variant="h6" sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 2 }}>AI 学习助手</Typography>
      <Grid container spacing={2}>
        {agentEntries.map((entry) => (
          <Grid item xs={12} sm={6} key={entry.id}>
            <AgentCard entry={entry} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default LearningDashboard;
