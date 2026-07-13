import React, { useState } from 'react';
import {
  Box, Card, Typography, Stack, Chip, Button, Grid,
  LinearProgress, IconButton, Divider,
} from '@mui/material';
import {
  ClipboardCheck, CheckCircle2, Clock, TrendingUp,
  AlertTriangle, ChevronLeft, ChevronRight, Lightbulb,
} from 'lucide-react';

/* ============================================================ */
/* 测评列表视图                                                 */
/* ============================================================ */
const assessmentHistory = [
  { stage: 3, subject: '数学', score: 87, total: 100, status: 'completed', date: '2026-06-20', kps: '函数、导数、三角函数' },
  { stage: 4, subject: '数学', score: 0, total: 100, status: 'pending', date: null, kps: '立体几何、概率统计、向量', duration: '90分钟', questionCount: 22 },
];

const AssessmentListView: React.FC<{ onStart: () => void }> = ({ onStart }) => (
  <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 4 }}>
    <Typography sx={{ fontSize: 24, fontWeight: 700, color: '#292524', mb: 3 }}>阶段测评</Typography>
    <Stack spacing={2}>
      {assessmentHistory.map((a) => (
        <Card key={a.stage} sx={{ p: 2.5, borderRadius: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <Box sx={{
              width: 44, height: 44, borderRadius: 2,
              bgcolor: a.status === 'completed' ? '#F0FDF4' : '#F5F5F4',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {a.status === 'completed'
                ? <CheckCircle2 size={24} color="#16A34A" />
                : <ClipboardCheck size={24} color="#A8A29E" />
              }
            </Box>
            <Box>
              <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#292524' }}>
                第{a.stage}阶段测评 · {a.subject}
                {a.status === 'completed'
                  ? <Chip label={`得分 ${a.score}/${a.total}`} size="small" sx={{ ml: 1, bgcolor: '#F0FDF4', color: '#16A34A', borderRadius: 9999, fontSize: 12 }} />
                  : <Chip label="待开始" size="small" sx={{ ml: 1, bgcolor: '#F5F5F4', color: '#A8A29E', borderRadius: 9999, fontSize: 12 }} />
                }
              </Typography>
              <Typography sx={{ fontSize: 14, color: '#78716C', mt: 0.25 }}>
                涵盖：{a.kps}
                {a.status === 'completed' ? ` · ${a.date}` : ` · 预计${a.duration} · ${a.questionCount}题`}
              </Typography>
            </Box>
          </Box>
          <Button
            variant={a.status === 'completed' ? 'outlined' : 'contained'}
            size="small"
            onClick={a.status === 'completed' ? undefined : onStart}
            sx={{ borderRadius: 2, textTransform: 'none', fontSize: 13,
              ...(a.status === 'completed' ? {} : { bgcolor: '#2563EB' }) }}
          >
            {a.status === 'completed' ? '查看报告' : '开始测评'}
          </Button>
        </Card>
      ))}
    </Stack>
  </Box>
);

/* ============================================================ */
/* 答题界面                                                    */
/* ============================================================ */
const MOCK_QUESTIONS = [
  { id: 1, type: '选择题', points: 5, content: '已知函数 f(x) = x³ - 3x² + 2x - 1，求 f(x) 在区间 [-1, 2] 上的最大值是多少？' },
  { id: 2, type: '选择题', points: 5, content: '设等差数列 {aₙ} 的前 n 项和为 Sₙ，若 a₁ = 2，S₃ = 12，则 a₅ = ?' },
  { id: 3, type: '填空题', points: 5, content: '已知向量 a=(1,2), b=(3,-1)，则 2a + b = ______' },
];

const ExamInterface: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const [currentQ, setCurrentQ] = useState(0);
  const [answered, setAnswered] = useState<Record<number, boolean>>({});
  const totalQ = MOCK_QUESTIONS.length;

  const q = MOCK_QUESTIONS[currentQ];

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 4 }}>
      {/* 顶部栏 */}
      <Card sx={{ p: 2, borderRadius: 2, mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography sx={{ fontSize: 18, fontWeight: 600, color: '#292524' }}>第4阶段测评 · 数学</Typography>
          <Typography sx={{ fontSize: 18, fontFamily: '"JetBrains Mono",monospace', color: '#57534E', display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Clock size={18} /> 78:45
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography sx={{ fontSize: 14, color: '#78716C' }}>{currentQ + 1}/{totalQ} 已完成</Typography>
          <Box sx={{ width: 120, height: 6, bgcolor: '#E7E5E4', borderRadius: 9999 }}>
            <Box sx={{ width: `${((currentQ + 1) / totalQ) * 100}%`, height: '100%', bgcolor: '#2563EB', borderRadius: 9999 }} />
          </Box>
        </Box>
      </Card>

      <Grid container spacing={3}>
        {/* 题目区域 */}
        <Grid item xs={12} md={8}>
          <Card sx={{ p: 3, borderRadius: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography sx={{ fontSize: 14, color: '#78716C' }}>
                第{q.id}题（{q.type} · {q.points}分）
              </Typography>
            </Box>
            <Typography sx={{ fontSize: 16, lineHeight: 1.8, color: '#292524', mb: 4 }}>
              {q.content}
            </Typography>
            {/* 答题区域 */}
            <Box sx={{
              minHeight: 160, p: 2, bgcolor: '#FAFAF9', borderRadius: 2,
              border: '1px dashed #D6D3D1', mb: 3,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Typography sx={{ fontSize: 14, color: '#A8A29E' }}>答题区域（支持Markdown/LaTeX）</Typography>
            </Box>
            {/* 导航按钮 */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button size="small" variant="outlined" onClick={() => setAnswered(prev => ({ ...prev, [q.id]: true }))}
                  sx={{ borderRadius: 2, textTransform: 'none', fontSize: 13 }}>
                  标记待定
                </Button>
              </Box>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button size="small" variant="outlined" disabled={currentQ === 0}
                  onClick={() => setCurrentQ(prev => prev - 1)}
                  sx={{ borderRadius: 2, textTransform: 'none', fontSize: 13 }}>
                  <ChevronLeft size={16} /> 上一题
                </Button>
                <Button size="small" variant="outlined" disabled={currentQ === totalQ - 1}
                  onClick={() => setCurrentQ(prev => prev + 1)}
                  sx={{ borderRadius: 2, textTransform: 'none', fontSize: 13 }}>
                  下一题 <ChevronRight size={16} />
                </Button>
              </Box>
            </Box>
          </Card>
        </Grid>

        {/* 答题卡 */}
        <Grid item xs={12} md={4}>
          <Card sx={{ p: 2.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524', mb: 1.5 }}>答题卡</Typography>
            <Grid container spacing={1}>
              {MOCK_QUESTIONS.map((qItem) => (
                <Grid item xs={3} key={qItem.id}>
                  <Box sx={{
                    width: '100%', aspectRatio: '1', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    borderRadius: 1, cursor: 'pointer',
                    bgcolor: qItem.id === q.id ? '#2563EB'
                      : answered[qItem.id] ? '#16A34A'
                      : '#F5F5F4',
                    color: qItem.id === q.id || answered[qItem.id] ? 'white' : '#57534E',
                    fontWeight: 600,
                    fontFamily: '"JetBrains Mono",monospace',
                    fontSize: 14,
                    transition: 'all 150ms',
                    '&:hover': { opacity: 0.8 },
                  }}
                    onClick={() => setCurrentQ(MOCK_QUESTIONS.findIndex(x => x.id === qItem.id))}>
                    {qItem.id}
                  </Box>
                </Grid>
              ))}
            </Grid>
            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              <Box sx={{ width: 12, height: 12, bgcolor: '#2563EB', borderRadius: '2px' }} />
              <Typography sx={{ fontSize: 11, color: '#78716C' }}>当前</Typography>
              <Box sx={{ width: 12, height: 12, bgcolor: '#16A34A', borderRadius: '2px' }} />
              <Typography sx={{ fontSize: 11, color: '#78716C' }}>已答</Typography>
              <Box sx={{ width: 12, height: 12, bgcolor: '#F5F5F4', borderRadius: '2px' }} />
              <Typography sx={{ fontSize: 11, color: '#78716C' }}>未答</Typography>
            </Box>
            <Button fullWidth variant="contained" size="small" sx={{ mt: 2, borderRadius: 2, textTransform: 'none', bgcolor: '#2563EB' }}>
              提交答卷
            </Button>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

/* ============================================================ */
/* 成绩报告                                                    */
/* ============================================================ */
const ScoreReport: React.FC = () => {
  const progressData = [
    { stage: 1, score: 72 },
    { stage: 2, score: 78 },
    { stage: 3, score: 82 },
    { stage: 4, score: 87 },
  ];

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 4 }}>
      {/* 总分 */}
      <Card sx={{ p: 3, borderRadius: 2, mb: 3, textAlign: 'center' }}>
        <Typography sx={{ fontSize: 36, fontWeight: 700, fontFamily: '"JetBrains Mono",monospace', color: '#292524' }}>87<Box component="span" sx={{ fontSize: 20, color: '#A8A29E', fontWeight: 400 }}>/100</Box></Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 3, mt: 1 }}>
          <Typography sx={{ fontSize: 14, color: '#78716C' }}>排名：前15%</Typography>
          <Typography sx={{ fontSize: 14, color: '#78716C' }}>用时：72分钟</Typography>
        </Box>
      </Card>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* 各题型得分 */}
        <Grid item xs={12} md={6}>
          <Card sx={{ p: 2.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#292524', mb: 2 }}>各题型得分</Typography>
            <Stack spacing={1.5}>
              {[
                { label: '选择题', score: 25, total: 25, color: '#16A34A' },
                { label: '填空题', score: 15, total: 20, color: '#D97706' },
                { label: '解答题', score: 47, total: 55, color: '#2563EB' },
              ].map((item) => (
                <Box key={item.label}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                    <Typography sx={{ fontSize: 14, color: '#57534E' }}>{item.label}</Typography>
                    <Typography sx={{ fontSize: 14, fontFamily: '"JetBrains Mono",monospace', color: '#292524', fontWeight: 600 }}>
                      {item.score}<Box component="span" sx={{ color: '#A8A29E', fontWeight: 400 }}>/{item.total}</Box>
                    </Typography>
                  </Box>
                  <Box sx={{ height: 10, bgcolor: '#E7E5E4', borderRadius: 9999 }}>
                    <Box sx={{ width: `${(item.score / item.total) * 100}%`, height: '100%', bgcolor: item.color, borderRadius: 9999 }} />
                  </Box>
                </Box>
              ))}
            </Stack>
          </Card>
        </Grid>
        {/* 知识点得分 */}
        <Grid item xs={12} md={6}>
          <Card sx={{ p: 2.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#292524', mb: 2 }}>知识点掌握</Typography>
            <Stack spacing={1.5}>
              {[
                { label: '函数', score: 18, total: 20, color: '#16A34A' },
                { label: '导数', score: 15, total: 15, color: '#16A34A' },
                { label: '立体几何', score: 8, total: 15, color: '#D97706' },
                { label: '概率', score: 20, total: 25, color: '#2563EB' },
                { label: '向量', score: 26, total: 25, color: '#16A34A' },
              ].map((item) => (
                <Box key={item.label}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                    <Typography sx={{ fontSize: 14, color: '#57534E' }}>{item.label}</Typography>
                    <Typography sx={{ fontSize: 14, fontFamily: '"JetBrains Mono",monospace', color: '#292524', fontWeight: 600 }}>
                      {item.score}<Box component="span" sx={{ color: '#A8A29E', fontWeight: 400 }}>/{item.total}</Box>
                    </Typography>
                  </Box>
                  <Box sx={{ height: 10, bgcolor: '#E7E5E4', borderRadius: 9999 }}>
                    <Box sx={{ width: `${(item.score / item.total) * 100}%`, height: '100%', bgcolor: item.color, borderRadius: 9999 }} />
                  </Box>
                </Box>
              ))}
            </Stack>
          </Card>
        </Grid>
      </Grid>

      {/* 进步曲线 */}
      <Card sx={{ p: 2.5, borderRadius: 2, mb: 3 }}>
        <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#292524', mb: 2 }}>进步曲线</Typography>
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 120, py: 1 }}>
          {progressData.map((p, i) => (
            <Box key={p.stage} sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
              <Typography sx={{ fontSize: 12, fontFamily: '"JetBrains Mono",monospace', color: '#2563EB', fontWeight: 600 }}>{p.score}</Typography>
              <Box sx={{
                width: '100%', maxWidth: 48,
                height: `${(p.score / 100) * 80}px`,
                bgcolor: `rgba(37,99,235,${0.3 + (i / progressData.length) * 0.5})`,
                borderRadius: '4px 4px 0 0',
                position: 'relative',
              }}>
                {/* 小箭头标注 */}
                {i > 0 && (
                  <Box sx={{ position: 'absolute', top: -18, left: '50%', transform: 'translateX(-50%)', color: '#16A34A' }}>
                    <TrendingUp size={14} />
                  </Box>
                )}
              </Box>
              <Typography sx={{ fontSize: 12, color: '#78716C' }}>阶段{p.stage}</Typography>
            </Box>
          ))}
        </Box>
      </Card>

      {/* AI建议 */}
      <Box sx={{
        p: 2.5, borderRadius: 2, bgcolor: '#F0FDFA',
        borderLeft: '2px solid #0D9488',
      }}>
        <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#0D9488', display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
          <Lightbulb size={16} /> AI 学习建议
        </Typography>
        <Stack spacing={0.5}>
          <Typography sx={{ fontSize: 14, color: '#292524' }}>• 「立体几何」得分率仅53%，建议优先复习</Typography>
          <Typography sx={{ fontSize: 14, color: '#292524' }}>• 选择题正确率提升明显（阶段1: 68% → 阶段4: 100%）</Typography>
          <Typography sx={{ fontSize: 14, color: '#292524' }}>• 解答题在「逻辑推理」维度仍有提升空间</Typography>
        </Stack>
      </Box>
    </Box>
  );
};

/* ============================================================ */
/* 主组件                                                      */
/* ============================================================ */
const AssessmentPage: React.FC = () => {
  const [view, setView] = useState<'list' | 'exam' | 'report'>('list');

  if (view === 'exam') return <ExamInterface onBack={() => setView('list')} />;
  if (view === 'report') return <ScoreReport />;
  return <AssessmentListView onStart={() => setView('exam')} />;
};

export default AssessmentPage;
