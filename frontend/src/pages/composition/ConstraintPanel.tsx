import { Box, Typography, TextField, MenuItem, Slider, Switch, FormControlLabel, Chip, Button } from '@mui/material';
import type { CompositionConstraints } from '../../types/composition';

const SUBJECTS = [
  { id: 'math', name: '数学' }, { id: 'chinese', name: '语文' }, { id: 'english', name: '英语' },
  { id: 'physics', name: '物理' }, { id: 'chemistry', name: '化学' }, { id: 'biology', name: '生物' },
  { id: 'history', name: '历史' }, { id: 'geography', name: '地理' }, { id: 'politics', name: '政治' },
];

interface ConstraintPanelProps {
  constraints: CompositionConstraints;
  onChange: (c: CompositionConstraints) => void;
  onGenerate: () => void;
  generating: boolean;
}

export default function ConstraintPanel({ constraints, onChange, onGenerate, generating }: ConstraintPanelProps) {
  const update = (partial: Partial<CompositionConstraints>) => {
    onChange({ ...constraints, ...partial });
  };

  return (
    <Box sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2 }}>
      <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>
        组卷约束条件
      </Typography>

      {/* 学科 */}
      <TextField select label="学科" size="small" fullWidth
        value={constraints.subject_id}
        onChange={(e) => update({ subject_id: e.target.value })}
        sx={{ mb: 2, '& input, & .MuiSelect-select': { color: '#e0e0e0' } }}>
        {SUBJECTS.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
      </TextField>

      {/* 题量 */}
      <Box sx={{ mb: 2 }}>
        <Typography sx={{ color: '#999', fontSize: 13, mb: 0.5 }}>题目数量: {constraints.total_count}</Typography>
        <Slider
          value={constraints.total_count}
          onChange={(_, v) => update({ total_count: v as number })}
          min={5} max={50} step={5}
          sx={{ color: '#00d4ff', '& .MuiSlider-thumb': { width: 16, height: 16 } }}
        />
      </Box>

      {/* 难度均值 */}
      <Box sx={{ mb: 2 }}>
        <Typography sx={{ color: '#999', fontSize: 13, mb: 0.5 }}>
          目标难度: {constraints.difficulty_mean.toFixed(2)}
        </Typography>
        <Slider
          value={constraints.difficulty_mean}
          onChange={(_, v) => update({ difficulty_mean: v as number })}
          min={0.2} max={0.9} step={0.05}
          sx={{ color: '#ff9800', '& .MuiSlider-thumb': { width: 16, height: 16 } }}
        />
      </Box>

      {/* 难度标准差 */}
      <Box sx={{ mb: 2 }}>
        <Typography sx={{ color: '#999', fontSize: 13, mb: 0.5 }}>
          难度分布: {constraints.difficulty_std.toFixed(2)}
        </Typography>
        <Slider
          value={constraints.difficulty_std}
          onChange={(_, v) => update({ difficulty_std: v as number })}
          min={0.05} max={0.3} step={0.05}
          sx={{ color: '#4caf50', '& .MuiSlider-thumb': { width: 16, height: 16 } }}
        />
      </Box>

      {/* 总分 */}
      <TextField label="目标总分（可选）" type="number" size="small" fullWidth
        value={constraints.total_score || ''}
        onChange={(e) => update({ total_score: e.target.value ? parseInt(e.target.value) : undefined })}
        sx={{ mb: 2, '& input': { color: '#e0e0e0' } }} />

      {/* 真题优先 */}
      <FormControlLabel
        control={<Switch checked={constraints.prefer_real_exam}
          onChange={(e) => update({ prefer_real_exam: e.target.checked })}
          sx={{ '& .MuiSwitch-thumb': { bgcolor: '#00d4ff' } }} />}
        label={<Typography sx={{ color: '#ccc', fontSize: 13 }}>真题优先</Typography>}
        sx={{ mb: 2 }}
      />

      {/* 题型配置简要显示 */}
      <Box sx={{ mb: 2 }}>
        <Typography sx={{ color: '#999', fontSize: 12, mb: 0.5 }}>题型配置</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {constraints.types.map((t, i) => (
            <Chip key={i} label={`${t.name || `#${t.id}`}: ${t.count}题`}
              size="small" sx={{ color: '#00d4ff', borderColor: '#00d4ff', fontSize: 11 }} variant="outlined" />
          ))}
        </Box>
      </Box>

      {/* 生成按钮 */}
      <Button variant="contained" fullWidth disabled={generating}
        onClick={onGenerate}
        sx={{ bgcolor: '#00d4ff', '&:hover': { bgcolor: '#00b8e6' }, py: 1.2, fontWeight: 600 }}>
        {generating ? '组卷中...' : '一键组卷'}
      </Button>
    </Box>
  );
}
