import React, { useState } from 'react';
import {
  Box, Card, Typography, Stack, Chip, Button, Grid,
  LinearProgress, IconButton, Avatar,
} from '@mui/material';
import {
  Route, ChevronRight, CheckCircle2, Star, Clock, Calendar,
  TrendingUp, Zap, Target,
} from 'lucide-react';

// 模拟数据
const phases = [
  { week: 1, name: '函数基础复习', status: 'completed', date: '2026-06-15', progress: 100 },
  { week: 2, name: '导数与微分', status: 'in_progress', date: '2026-06-22', progress: 80 },
  { week: 3, name: '三角函数综合', status: 'pending', date: '2026-06-29', progress: 0 },
  { week: 4, name: '立体几何', status: 'pending', date: '2026-07-06', progress: 0 },
];

const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

/* ---------- 时间线节点 ---------- */
const TimelineNode: React.FC<{
  phase: typeof phases[0];
  isLast: boolean;
}> = ({ phase, isLast }) => {
  const nodeIcon = () => {
    if (phase.status === 'completed') return <CheckCircle2 size={16} color="white" />;
    if (phase.status === 'in_progress') return <Zap size={16} color="white" />;
    return null;
  };

  const nodeBg = phase.status === 'completed' ? '#16A34A'
    : phase.status === 'in_progress' ? '#2563EB'
    : '#E7E5E4';

  const nodeBorder = phase.status === 'pending' ? '2px solid #D6D3D1' : 'none';

  return (
    <Box sx={{ display: 'flex', position: 'relative', pb: isLast ? 0 : 0 }}>
      {/* 竖线 */}
      {!isLast && (
        <Box sx={{
          position: 'absolute', left: 27, top: 48, width: 2,
          height: 'calc(100% + 8px)',
          bgcolor: phase.status === 'completed' ? '#16A34A' : '#E7E5E4',
        }} />
      )}
      {/* 节点 */}
      <Box sx={{ display: 'flex', gap: 2, width: '100%', py: 1.5, cursor: 'pointer',
        borderRadius: 1, px: 1.5, transition: 'background 150ms',
        '&:hover': { bgcolor: '#FAFAF9' },
      }}>
        <Box sx={{
          width: 28, height: 28, borderRadius: '50%', display: 'flex',
          alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          bgcolor: nodeBg, border: nodeBorder,
          position: 'relative',
          ...(phase.status === 'in_progress' ? {
            boxShadow: '0 0 0 4px rgba(37,99,235,0.15)',
            animation: 'pulse 2s ease-in-out infinite',
            '@keyframes pulse': { '0%,100%': { boxShadow: '0 0 0 4px rgba(37,99,235,0.15)' }, '50%': { boxShadow: '0 0 0 8px rgba(37,99,235,0.08)' } },
          } : {}),
        }}>
          {nodeIcon()}
        </Box>
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.25 }}>
            <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#292524' }}>
              {phase.name}
              {phase.status === 'in_progress' && (
                <Chip label="进行中" size="small" sx={{ ml: 1, fontSize: 11, bgcolor: '#EFF6FF', color: '#2563EB', borderRadius: 9999, height: 20 }} />
              )}
            </Typography>
            <Typography sx={{ fontSize: 12, color: '#A8A29E', fontFamily: '"JetBrains Mono",monospace' }}>{phase.date}</Typography>
          </Box>
          {phase.status === 'in_progress' && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
              <Box sx={{ flex: 1, height: 6, bgcolor: '#E7E5E4', borderRadius: 9999 }}>
                <Box sx={{ width: `${phase.progress}%`, height: '100%', bgcolor: '#2563EB', borderRadius: 9999 }} />
              </Box>
              <Typography sx={{ fontSize: 12, color: '#2563EB', fontFamily: '"JetBrains Mono",monospace' }}>{phase.progress}%</Typography>
            </Box>
          )}
          {/* 周计划预览 */}
          {phase.status === 'in_progress' && (
            <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {WEEKDAY_LABELS.slice(0, 5).map((d, i) => (
                <Chip key={d} label={d} size="small"
                  sx={{ fontSize: 11, borderRadius: 9999,
                    bgcolor: i < 3 ? '#EFF6FF' : '#F5F5F4',
                    color: i < 3 ? '#2563EB' : '#A8A29E',
                    height: 22 }} />
              ))}
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
};

/* ---------- 里程碑（菱形） ---------- */
const MilestoneNode: React.FC = () => (
  <Box sx={{ display: 'flex', gap: 2, py: 2, px: 1.5, position: 'relative' }}>
    <Box sx={{ position: 'absolute', left: 27, top: 0, width: 2, height: '100%', bgcolor: '#E7E5E4' }} />
    <Box sx={{
      width: 28, height: 28, transform: 'rotate(45deg)', flexShrink: 0,
      bgcolor: '#0D9488', display: 'flex', alignItems: 'center',
      justifyContent: 'center', ml: 0,
    }}>
      <Star size={14} color="white" style={{ transform: 'rotate(-45deg)' }} />
    </Box>
    <Box>
      <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#0D9488' }}>◆ 里程碑：期中模拟测验</Typography>
      <Typography sx={{ fontSize: 14, color: '#57534E' }}>目标：2026-07-15 · 验证前3周学习成果</Typography>
    </Box>
  </Box>
);

/* ---------- 右侧统计面板 ---------- */
const StatsPanel: React.FC = () => (
  <Card sx={{ p: 2.5, borderRadius: 2, position: 'sticky', top: 24 }}>
    <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#292524', mb: 2 }}>学习统计</Typography>
    <Stack spacing={2}>
      <Box>
        <Typography sx={{ fontSize: 12, color: '#78716C', mb: 0.5 }}>完成率</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ flex: 1, height: 8, bgcolor: '#E7E5E4', borderRadius: 9999 }}>
            <Box sx={{ width: '72%', height: '100%', bgcolor: '#2563EB', borderRadius: 9999 }} />
          </Box>
          <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#2563EB', fontFamily: '"JetBrains Mono",monospace' }}>72%</Typography>
        </Box>
      </Box>
      <Box>
        <Typography sx={{ fontSize: 12, color: '#78716C', mb: 0.5 }}>
          <Clock size={12} style={{ marginRight: 4 }} />预计完成
        </Typography>
        <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>2026-08-20</Typography>
      </Box>
      <Box>
        <Typography sx={{ fontSize: 12, color: '#78716C', mb: 0.5 }}>待完成里程碑</Typography>
        <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>6 个</Typography>
      </Box>
      <Box>
        <Typography sx={{ fontSize: 12, color: '#78716C', mb: 0.5 }}>
          <Zap size={12} style={{ marginRight: 4 }} />连续学习
        </Typography>
        <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#D97706' }}>15 天</Typography>
      </Box>
      <Box sx={{ pt: 1, borderTop: '1px solid #E7E5E4' }}>
        <Typography sx={{ fontSize: 12, color: '#78716C', mb: 0.5 }}>下一个里程碑</Typography>
        <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>「三角函数综合」</Typography>
        <Typography sx={{ fontSize: 12, color: '#78716C' }}>预计开始：2026-07-01</Typography>
        <Typography sx={{ fontSize: 12, color: '#78716C' }}>预估时长：5天</Typography>
      </Box>
    </Stack>
  </Card>
);

/* ============================================================ */
/* 主组件：学习路径页                                            */
/* ============================================================ */
const LearningPath: React.FC = () => {
  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 4 }}>
      {/* 顶部进度区 */}
      <Card sx={{ p: 3, borderRadius: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
            <Typography sx={{ fontSize: 30, fontWeight: 700, color: '#292524', fontFamily: '"JetBrains Mono",monospace' }}>
              650<Box component="span" sx={{ fontSize: 20, color: '#A8A29E', fontWeight: 400 }}>/750</Box>
            </Typography>
            <Typography sx={{ fontSize: 14, color: '#78716C', ml: 1 }}>目标分数</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Calendar size={16} color="#A8A29E" />
            <Typography sx={{ fontSize: 14, color: '#78716C' }}>预计完成：2026-08-20</Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box sx={{ flex: 1, height: 8, bgcolor: '#E7E5E4', borderRadius: 9999, position: 'relative' }}>
            <Box sx={{ width: '72%', height: '100%', bgcolor: '#2563EB', borderRadius: 9999 }} />
          </Box>
          <Typography sx={{ fontSize: 14, color: '#2563EB', fontFamily: '"JetBrains Mono",monospace', fontWeight: 600 }}>72%</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5, mt: 1.5 }}>
          {[
            { label: '全部学科', active: true },
            { label: '数学', active: false },
            { label: '最近30天', active: false },
          ].map((tab) => (
            <Chip key={tab.label} label={tab.label}
              sx={{
                borderRadius: 9999, fontSize: 12, fontWeight: 500,
                bgcolor: tab.active ? '#2563EB' : '#F5F5F4',
                color: tab.active ? 'white' : '#57534E',
                '&:hover': { bgcolor: tab.active ? '#1D4ED8' : '#E7E5E4' },
                cursor: 'pointer',
              }} />
          ))}
        </Box>
      </Card>

      <Grid container spacing={3}>
        {/* 左：时间线 */}
        <Grid item xs={12} md={8}>
          <Card sx={{ p: 2.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 2 }}>学习路径时间线</Typography>
            {phases.slice(0, 2).map((p, i) => (
              <TimelineNode key={p.week} phase={p} isLast={false} />
            ))}
            <MilestoneNode />
            {phases.slice(2).map((p, i) => (
              <TimelineNode key={p.week} phase={p} isLast={i === phases.slice(2).length - 1} />
            ))}
          </Card>
        </Grid>

        {/* 右：统计面板 */}
        <Grid item xs={12} md={4}>
          <StatsPanel />
        </Grid>
      </Grid>
    </Box>
  );
};

export default LearningPath;
