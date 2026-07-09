import { Box, Typography, Chip, Paper } from '@mui/material';
import type { CompositionResult } from '../../types/composition';

interface PreviewPanelProps {
  result: CompositionResult | null;
  loading: boolean;
}

export default function PreviewPanel({ result, loading }: PreviewPanelProps) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <Typography sx={{ color: '#666' }}>组卷求解中...</Typography>
      </Box>
    );
  }

  if (!result) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <Typography sx={{ color: '#666' }}>设置约束条件后点击"一键组卷"</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600 }}>
          组卷结果
        </Typography>
        <Chip label={`${result.question_ids.length} 题`} size="small"
          sx={{ color: '#00d4ff', borderColor: '#00d4ff' }} variant="outlined" />
        <Chip label={`总分 ${result.total_score}`} size="small"
          sx={{ color: '#4caf50', borderColor: '#4caf50' }} variant="outlined" />
        <Chip label={`目标达成: ${result.constraints_satisfied ? '是' : '否'}`} size="small"
          sx={{ color: result.constraints_satisfied ? '#4caf50' : '#f44336',
                borderColor: result.constraints_satisfied ? '#4caf50' : '#f44336' }} variant="outlined" />
      </Box>

      <Paper sx={{ bgcolor: '#12121e', p: 2, borderRadius: 1, maxHeight: 400, overflow: 'auto' }}>
        {result.question_ids.map((qid, idx) => (
          <Box key={qid} sx={{
            display: 'flex', alignItems: 'center', gap: 1.5, py: 0.8,
            borderBottom: idx < result.question_ids.length - 1 ? '1px solid #2a2a2a' : 'none',
          }}>
            <Typography sx={{ color: '#666', fontSize: 12, minWidth: 24 }}>{idx + 1}.</Typography>
            <Typography sx={{ color: '#ccc', fontSize: 13 }}>题目 #{qid}</Typography>
          </Box>
        ))}
      </Paper>
    </Box>
  );
}
