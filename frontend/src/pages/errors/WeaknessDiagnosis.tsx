import { Box, Typography, Chip, LinearProgress } from '@mui/material';
import type { WeaknessDiagnosis } from '../../types/error';

interface WeaknessDiagnosisProps {
  diagnosis: WeaknessDiagnosis | null;
}

export default function WeaknessDiagnosisPanel({ diagnosis }: WeaknessDiagnosisProps) {
  if (!diagnosis) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography sx={{ color: '#666', fontSize: 13 }}>暂无诊断数据</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ color: '#e0e0e0' }}>IRT θ 能力值</Typography>
        <Chip label={diagnosis.theta.toFixed(2)} size="small"
          sx={{ color: diagnosis.theta > 0 ? '#4caf50' : '#ff9800',
                borderColor: diagnosis.theta > 0 ? '#4caf50' : '#ff9800' }} variant="outlined" />
      </Box>

      <Typography variant="subtitle2" sx={{ color: '#e0e0e0', mb: 1.5 }}>薄弱知识点 Top 5</Typography>

      {diagnosis.weakness_top5.map((w, i) => {
        const severity = w.mastery < 0.3 ? '#f44336' : w.mastery < 0.6 ? '#ff9800' : '#4caf50';
        return (
          <Box key={i} sx={{ mb: 1.5 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
              <Typography sx={{ color: '#ccc', fontSize: 13 }}>
                {i + 1}. {w.knowledge_point}
              </Typography>
              <Typography sx={{ color: severity, fontSize: 12, fontWeight: 600 }}>
                {(w.mastery * 100).toFixed(0)}%
              </Typography>
            </Box>
            <LinearProgress variant="determinate" value={w.mastery * 100}
              sx={{ bgcolor: '#2a2a2a', height: 6, borderRadius: 3,
                '& .MuiLinearProgress-bar': { bgcolor: severity, borderRadius: 3 } }} />
          </Box>
        );
      })}

      {diagnosis.suggestions.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" sx={{ color: '#e0e0e0', mb: 1 }}>学习建议</Typography>
          {diagnosis.suggestions.map((s, i) => (
            <Typography key={i} sx={{ color: '#999', fontSize: 12, mb: 0.5 }}>💡 {s}</Typography>
          ))}
        </Box>
      )}
    </Box>
  );
}
