import React, { useState } from 'react';
import {
  Box, Card, Typography, Chip, Stack, Button, Grid, Select,
  MenuItem, Autocomplete, TextField, Avatar, Divider, IconButton,
} from '@mui/material';
import {
  BookOpen, Clock, Star, FileText, Search, SlidersHorizontal,
  ChevronRight, Lightbulb, TrendingUp,
} from 'lucide-react';

interface QuestionCard {
  id: number;
  type: string;
  difficulty: number;
  title: string;
  tags: string[];
  estimatedTime: string;
  kpName: string;
  mastery: number;
  kpCode: string;
}

const mockQuestions: QuestionCard[] = [
  { id: 1, type: '选择题', difficulty: 3, title: '函数单调性判断', tags: ['函数', '单调性', '导数'], estimatedTime: '5分钟', kpName: '函数单调性', mastery: 0.23, kpCode: 'math_func_mono' },
  { id: 2, type: '填空题', difficulty: 4, title: '空间向量夹角计算', tags: ['空间向量', '立体几何'], estimatedTime: '8分钟', kpName: '空间向量', mastery: 0.31, kpCode: 'math_vec_space' },
  { id: 3, type: '解答题', difficulty: 3, title: '导数应用综合题', tags: ['导数', '综合应用'], estimatedTime: '12分钟', kpName: '导数应用', mastery: 0.35, kpCode: 'math_derivative' },
  { id: 4, type: '选择题', difficulty: 2, title: '集合运算基础', tags: ['集合'], estimatedTime: '3分钟', kpName: '集合', mastery: 0.65, kpCode: 'math_set' },
  { id: 5, type: '填空题', difficulty: 5, title: '圆锥曲线综合', tags: ['圆锥曲线', '解析几何'], estimatedTime: '15分钟', kpName: '圆锥曲线', mastery: 0.28, kpCode: 'math_conic' },
];

const DifficultyStars: React.FC<{ level: number }> = ({ level }) => (
  <Box sx={{ display: 'flex', gap: 0.25 }}>
    {[1, 2, 3, 4, 5].map((i) => (
      <Star key={i} size={12} fill={i <= level ? '#F59E0B' : 'none'} color={i <= level ? '#F59E0B' : '#D6D3D1'} />
    ))}
  </Box>
);

/* ---------- 知识点标签 ---------- */
const KpChip: React.FC<{ label: string; onDelete?: () => void }> = ({ label, onDelete }) => (
  <Chip
    label={label}
    size="small"
    onDelete={onDelete}
    sx={{ borderRadius: 9999, fontSize: 12, fontWeight: 500, bgcolor: '#EFF6FF', color: '#1D4ED8', '& .MuiChip-deleteIcon': { width: 14, height: 14 } }}
  />
);

/* ---------- 习题卡片 ---------- */
const ExerciseCard: React.FC<{ question: QuestionCard; onStart: () => void; onExplain: () => void }> = ({ question, onStart, onExplain }) => (
  <Card sx={{ p: 2.5, borderRadius: 2, transition: 'all 250ms ease-out', '&:hover': { boxShadow: '0 4px 6px rgba(0,0,0,0.06),0 2px 4px rgba(0,0,0,0.04)', transform: 'translateY(-2px)' } }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <FileText size={16} color="#78716C" />
        <Typography sx={{ fontSize: 12, color: '#78716C' }}>{question.type}</Typography>
      </Box>
      <DifficultyStars level={question.difficulty} />
    </Box>
    <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#292524', mb: 1.5, lineHeight: 1.4 }}>{question.title}</Typography>
    <Box sx={{ display: 'flex', gap: 0.5, mb: 1.5, flexWrap: 'wrap' }}>
      {question.tags.map((tag) => (<KpChip key={tag} label={tag} />))}
    </Box>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pt: 1, borderTop: '1px solid #E7E5E4' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Clock size={14} color="#A8A29E" />
        <Typography sx={{ fontSize: 12, color: '#A8A29E' }}>预计{question.estimatedTime}</Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        {question.mastery < 0.4 && (
          <Button size="small" onClick={onExplain} sx={{ borderRadius: 2, textTransform: 'none', fontSize: 12, color: '#0D9488', minWidth: 'auto' }}>
            讲解
          </Button>
        )}
        <Button size="small" variant="outlined" onClick={onStart} sx={{ borderRadius: 2, textTransform: 'none', fontSize: 12, color: '#2563EB', borderColor: '#2563EB' }}>
          开始练习
        </Button>
      </Box>
    </Box>
  </Card>
);

/* ---------- 推荐理由面板 ---------- */
const ExplainPanel: React.FC<{ show: boolean; onClose: () => void }> = ({ show, onClose }) => {
  if (!show) return null;
  return (
    <Card sx={{ p: 2.5, borderRadius: 2, bgcolor: '#F0FDFA', borderLeft: '2px solid #0D9488', mb: 2 }}>
      <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#0D9488', mb: 1 }}>💡 结构化讲解</Typography>
      <Stack spacing={1.5}>
        <Box>
          <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>1. 概念回归</Typography>
          <Typography sx={{ fontSize: 14, color: '#57534E' }}>复合函数：设y=f(u)，u=g(x)，当x在定义域内取值，u在g(x)值域内时，y=f(g(x))称为复合函数。</Typography>
        </Box>
        <Box>
          <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>2. 关键难点</Typography>
          <Typography sx={{ fontSize: 14, color: '#57534E' }}>核心是内层函数的值域必须包含在外层函数的定义域中。易错点：混淆复合函数与函数复合运算。</Typography>
        </Box>
        <Box>
          <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>3. 典型例题</Typography>
          <Typography sx={{ fontSize: 14, color: '#57534E' }}>2024全国I卷第8题：f(x)=sin(2x+π/3)，求f(x)在[0,π]上的单调递增区间。思路：换元u=2x+π/3→求外层sin u的增区间→代回。</Typography>
        </Box>
        <Box>
          <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>4. 变式练习</Typography>
          <Typography sx={{ fontSize: 14, color: '#57534E' }}>已知f(x)=cos(3x-π/4)，求f(x)的对称轴方程。关键区别：余弦的对称轴公式不同。</Typography>
        </Box>
        <Box>
          <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524' }}>5. 延伸提问</Typography>
          <Typography sx={{ fontSize: 14, color: '#57534E' }}>复合函数求导和复合函数求值域有什么不同？它们的核心思路分别是什么？</Typography>
        </Box>
      </Stack>
      <Button size="small" onClick={onClose} sx={{ mt: 1, borderRadius: 2, textTransform: 'none', fontSize: 12 }}>收起讲解</Button>
    </Card>
  );
};

/* ============================================================ */
/* 主组件：习题推荐页                                            */
/* ============================================================ */
const ExerciseRecommendation: React.FC = () => {
  const [showExplain, setShowExplain] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [difficulty, setDifficulty] = useState<number>(0);

  const allTags = ['函数', '导数', '立体几何', '空间向量', '圆锥曲线', '集合', '概率', '数列', '三角'];
  const filtered = mockQuestions.filter(q =>
    (difficulty === 0 || q.difficulty === difficulty) &&
    (selectedTags.length === 0 || q.tags.some(t => selectedTags.includes(t)))
  );

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 4 }}>
      {/* 筛选栏 */}
      <Box sx={{ p: 2, bgcolor: '#F5F5F4', borderRadius: 2, mb: 3, display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
        <Select size="small" defaultValue="math" sx={{ borderRadius: 2, fontSize: 14, minWidth: 80, bgcolor: 'white' }}>
          <MenuItem value="math">数学</MenuItem>
          <MenuItem value="physics">物理</MenuItem>
          <MenuItem value="chemistry">化学</MenuItem>
        </Select>
        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
          {[1, 2, 3, 4, 5].map((l) => (
            <IconButton key={l} size="small" onClick={() => setDifficulty(difficulty === l ? 0 : l)} sx={{ opacity: difficulty === 0 || difficulty === l ? 1 : 0.3 }}>
              <Star size={14} fill={l <= (difficulty || 5) ? '#F59E0B' : 'none'} color={l <= (difficulty || 5) ? '#F59E0B' : '#D6D3D1'} />
            </IconButton>
          ))}
        </Box>
        <Autocomplete
          multiple
          size="small"
          options={allTags}
          value={selectedTags}
          onChange={(_, v) => setSelectedTags(v)}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => (
              <Chip label={option} {...getTagProps({ index })} key={option}
                sx={{ borderRadius: 9999, fontSize: 12, bgcolor: '#EFF6FF', color: '#1D4ED8' }} />
            ))
          }
          renderInput={(params) => <TextField {...params} placeholder="添加标签" size="small" sx={{ minWidth: 120, '& .MuiOutlinedInput-root': { borderRadius: 2, bgcolor: 'white' } }} />}
          sx={{ minWidth: 200 }}
        />
        <TextField placeholder="搜索题目" size="small" sx={{ minWidth: 160, '& .MuiOutlinedInput-root': { borderRadius: 2, bgcolor: 'white' } }}
          InputProps={{ startAdornment: <Search size={16} style={{ marginRight: 8, color: '#A8A29E' }} /> }} />
      </Box>

      <Grid container spacing={3}>
        {/* 左：习题卡片流 3列 */}
        <Grid item xs={12} md={9}>
          {showExplain && <ExplainPanel show={showExplain} onClose={() => setShowExplain(false)} />}
          <Grid container spacing={2}>
            {filtered.map((q) => (
              <Grid item xs={12} sm={6} lg={4} key={q.id}>
                <ExerciseCard
                  question={q}
                  onStart={() => {}}
                  onExplain={() => setShowExplain(true)}
                />
              </Grid>
            ))}
          </Grid>
          {filtered.length === 0 && (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography sx={{ fontSize: 16, color: '#A8A29E' }}>没有找到匹配的题目，试试调整筛选条件</Typography>
            </Box>
          )}
        </Grid>

        {/* 右：推荐理由 */}
        <Grid item xs={12} md={3}>
          <Box sx={{ position: 'sticky', top: 24 }}>
            <Card sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography sx={{ fontSize: 14, fontWeight: 600, color: '#292524', mb: 1.5, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Lightbulb size={16} /> 推荐理由
              </Typography>
              <Typography sx={{ fontSize: 14, color: '#57534E', mb: 2 }}>
                根据你的诊断报告，「函数单调性」是当前薄弱环节，建议优先练习。
              </Typography>
              <Divider sx={{ my: 1.5 }} />
              <Box sx={{ mb: 1 }}>
                <Typography sx={{ fontSize: 12, color: '#78716C', mb: 0.5 }}>同类题正确率</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ flex: 1, height: 6, bgcolor: '#E7E5E4', borderRadius: 9999 }}>
                    <Box sx={{ width: '45%', height: '100%', bgcolor: '#D97706', borderRadius: 9999 }} />
                  </Box>
                  <Typography sx={{ fontSize: 12, fontFamily: '"JetBrains Mono",monospace', color: '#292524' }}>45%</Typography>
                </Box>
              </Box>
              <Box>
                <Typography sx={{ fontSize: 12, color: '#78716C', mb: 0.5 }}>高考出现频率</Typography>
                <Chip label="高" size="small" sx={{ borderRadius: 9999, fontSize: 12, bgcolor: '#FEF2F2', color: '#DC2626', fontWeight: 500 }} />
              </Box>
            </Card>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ExerciseRecommendation;
