import React, { useState } from 'react';
import {
  Box, Tabs, Tab, Card, Typography, Chip, Stack, Button,
  Grid, LinearProgress, Tooltip,
} from '@mui/material';
import {
  CheckCircle2, AlertTriangle, XCircle, Brain, BookOpen,
  Lightbulb, ChevronRight,
} from 'lucide-react';

const subjects = ['数学', '语文', '英语', '物理', '化学', '生物'];

// 模拟数据
const heatmapData: { label: string; kps: { name: string; mastery: number }[] }[] = [
  { label: '基础概念', kps: [{ name: '函数', mastery: 0.9 }, { name: '几何', mastery: 0.6 }, { name: '概率', mastery: 0.85 }, { name: '数列', mastery: 0.75 }, { name: '三角', mastery: 0.7 }, { name: '向量', mastery: 0.8 }, { name: '导数', mastery: 0.85 }] },
  { label: '公式应用', kps: [{ name: '函数', mastery: 0.75 }, { name: '几何', mastery: 0.25 }, { name: '概率', mastery: 0.6 }, { name: '数列', mastery: 0.7 }, { name: '三角', mastery: 0.65 }, { name: '向量', mastery: 0.55 }, { name: '导数', mastery: 0.7 }] },
  { label: '计算能力', kps: [{ name: '函数', mastery: 0.5 }, { name: '几何', mastery: 0.55 }, { name: '概率', mastery: 0.8 }, { name: '数列', mastery: 0.2 }, { name: '三角', mastery: 0.7 }, { name: '向量', mastery: 0.6 }, { name: '导数', mastery: 0.5 }] },
  { label: '综合应用', kps: [{ name: '函数', mastery: 0.6 }, { name: '几何', mastery: 0.15 }, { name: '概率', mastery: 0.55 }, { name: '数列', mastery: 0.45 }, { name: '三角', mastery: 0.5 }, { name: '向量', mastery: 0.55 }, { name: '导数', mastery: 0.25 }] },
  { label: '解题策略', kps: [{ name: '函数', mastery: 0.7 }, { name: '几何', mastery: 0.45 }, { name: '概率', mastery: 0.6 }, { name: '数列', mastery: 0.5 }, { name: '三角', mastery: 0.35 }, { name: '向量', mastery: 0.6 }, { name: '导数', mastery: 0.55 }] },
];

const kpColumns = ['函数', '几何', '概率', '数列', '三角', '向量', '导数'];

const heatColor = (m: number): string => {
  if (m >= 0.8) return '#16A34A';
  if (m >= 0.6) return '#65A30D';
  if (m >= 0.4) return '#F59E0B';
  if (m >= 0.2) return '#F97316';
  return '#EF4444';
};

const heatLabel = (m: number): string => {
  if (m >= 0.8) return '掌握';
  if (m >= 0.6) return '熟练';
  if (m >= 0.4) return '发展中';
  if (m >= 0.2) return '薄弱';
  return '严重薄弱';
};

/* ---------- 热力图 ---------- */
const HeatmapChart: React.FC = () => (
  <Box sx={{ overflowX: 'auto', py: 2 }}>
    <Box sx={{ display: 'inline-block', minWidth: 420 }}>
      {/* 列头 */}
      <Box sx={{ display: 'flex', ml: '100px', mb: 0.5 }}>
        {kpColumns.map((col) => (
          <Box key={col} sx={{ width: 44, textAlign: 'center', mr: 0.5 }}>
            <Typography sx={{ fontSize: 12, color: '#78716C', writingMode: 'vertical-lr', rotate: '180deg' }}>{col}</Typography>
          </Box>
        ))}
      </Box>
      {/* 行 */}
      {heatmapData.map((row) => (
        <Box key={row.label} sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
          <Typography sx={{ width: 96, fontSize: 12, color: '#78716C', textAlign: 'right', pr: 1 }}>{row.label}</Typography>
          {row.kps.map((kp, i) => (
            <Tooltip key={i} title={`${row.label}·${kpColumns[i]}: ${heatLabel(kp.mastery)}(${(kp.mastery * 100).toFixed(0)}%)`} placement="top">
              <Box sx={{
                width: 44, height: 44, mr: 0.5, borderRadius: 1,
                bgcolor: heatColor(kp.mastery), cursor: 'pointer',
                transition: 'all 150ms',
                '&:hover': { transform: 'scale(1.08)', boxShadow: '0 0 0 2px #2563EB' },
              }} />
            </Tooltip>
          ))}
        </Box>
      ))}
      {/* 图例 */}
      <Box sx={{ display: 'flex', gap: 1.5, mt: 1.5, ml: '100px', alignItems: 'center' }}>
        {[['#16A34A', '掌握'], ['#65A30D', '熟练'], ['#F59E0B', '发展中'], ['#F97316', '薄弱'], ['#EF4444', '严重薄弱']].map(([c, l]) => (
          <Box key={l} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 12, height: 12, borderRadius: '2px', bgcolor: c }} />
            <Typography sx={{ fontSize: 11, color: '#78716C' }}>{l}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  </Box>
);

/* ---------- 能力雷达（简化水平条） ---------- */
const AbilityBar: React.FC<{ label: string; value: number; isWeak?: boolean }> = ({ label, value, isWeak }) => (
  <Box sx={{ mb: 1 }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
      <Typography sx={{ fontSize: 14, color: isWeak ? '#DC2626' : '#57534E', fontWeight: isWeak ? 600 : 400 }}>{label}</Typography>
      <Typography sx={{ fontSize: 14, color: '#292524', fontFamily: '"JetBrains Mono",monospace' }}>{(value * 100).toFixed(0)}%</Typography>
    </Box>
    <LinearProgress
      variant="determinate"
      value={value * 100}
      sx={{ height: 8, borderRadius: 9999, bgcolor: '#E7E5E4',
        '& .MuiLinearProgress-bar': { bgcolor: isWeak ? '#D97706' : '#2563EB', borderRadius: 9999 } }}
    />
  </Box>
);

/* ---------- 知识点树 ---------- */
const KnowledgeTree: React.FC = () => (
  <Box>
    <Box sx={{ mb: 1.5 }}>
      <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524', display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Brain size={16} /> 函数 (85%)
      </Typography>
      <Stack spacing={0.5} sx={{ ml: 3, mt: 0.5 }}>
        {['函数定义域✅', '函数值域✅', '函数单调性⚠️', '函数图像变换❌'].map((item) => (
          <Typography key={item} sx={{ fontSize: 14, color: '#57534E', display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {item}
          </Typography>
        ))}
      </Stack>
    </Box>
    <Box>
      <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#DC2626', display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <AlertTriangle size={16} color="#D97706" /> 几何 (42%)
      </Typography>
      <Stack spacing={0.5} sx={{ ml: 3, mt: 0.5 }}>
        {['平面几何基础✅', '空间向量计算❌'].map((item) => (
          <Typography key={item} sx={{ fontSize: 14, color: '#57534E', display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {item}
          </Typography>
        ))}
      </Stack>
    </Box>
  </Box>
);

/* ============================================================ */
/* 主组件：诊断报告页                                            */
/* ============================================================ */
const DiagnosisReport: React.FC = () => {
  const [tab, setTab] = useState(0);

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 4 }}>
      {/* 顶部 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{
          '& .MuiTab-root': { textTransform: 'none', fontWeight: 500, fontSize: 14, minHeight: 36 },
          '& .MuiTabs-indicator': { backgroundColor: '#2563EB' },
        }}>
          {subjects.map((s) => <Tab key={s} label={s} />)}
        </Tabs>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" size="small" sx={{ borderRadius: 2, textTransform: 'none' }}>选择日期</Button>
          <Button variant="contained" size="small" sx={{ borderRadius: 2, textTransform: 'none', bgcolor: '#2563EB' }}>重新诊断</Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* 左：热力图 */}
        <Grid item xs={12} md={7}>
          <Card sx={{ p: 2.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 1 }}>知识薄弱点热力图</Typography>
            <HeatmapChart />
          </Card>
        </Grid>

        {/* 右：雷达+知识树 */}
        <Grid item xs={12} md={5}>
          <Card sx={{ p: 2.5, borderRadius: 2, mb: 2 }}>
            <Typography sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 1.5 }}>能力雷达</Typography>
            <AbilityBar label="概念理解" value={0.82} />
            <AbilityBar label="计算能力" value={0.65} />
            <AbilityBar label="逻辑推理" value={0.78} />
            <AbilityBar label="空间想象" value={0.42} isWeak />
            <AbilityBar label="应用能力" value={0.58} />
            <AbilityBar label="综合分析" value={0.61} />
          </Card>
          <Card sx={{ p: 2.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: 18, fontWeight: 600, color: '#292524', mb: 1.5 }}>知识点掌握树</Typography>
            <KnowledgeTree />
          </Card>
        </Grid>
      </Grid>

      {/* AI 诊断建议 */}
      <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {[
          { text: '建议优先复习「空间向量」和「函数图像变换」，这两个知识点是当前最薄弱环节，且在高考试卷中占比达18%', color: '#0D9488' },
          { text: '「立体几何」薄弱可能影响「空间想象」能力维度，建议配合3D可视化工具进行辅助理解', color: '#0D9488' },
        ].map((s, i) => (
          <Box key={i} sx={{
            p: 2, borderRadius: 2, bgcolor: '#F0FDFA',
            borderLeft: '2px solid', borderColor: s.color,
            display: 'flex', gap: 1.5, alignItems: 'flex-start',
          }}>
            <Lightbulb size={20} color={s.color} style={{ flexShrink: 0, marginTop: 2 }} />
            <Typography sx={{ fontSize: 14, color: '#292524' }}>{s.text}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

export default DiagnosisReport;
