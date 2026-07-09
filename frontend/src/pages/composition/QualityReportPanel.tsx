import { Box, Typography, Chip, LinearProgress } from '@mui/material';

interface QualityReportProps {
  report: CompositionResult['quality_report'] | null | undefined;
}

export default function QualityReportPanel({ report }: QualityReportProps) {
  if (!report) return null;

  return (
    <Box sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2, mt: 2 }}>
      <Typography variant="subtitle2" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 1.5 }}>
        组卷质量预检
      </Typography>

      {/* 知识点覆盖率 */}
      <Box sx={{ mb: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
          <Typography sx={{ color: '#999', fontSize: 12 }}>知识点覆盖率</Typography>
          <Typography sx={{ color: '#00d4ff', fontSize: 12, fontWeight: 600 }}>
            {(report.knowledge_coverage * 100).toFixed(0)}%
          </Typography>
        </Box>
        <LinearProgress variant="determinate" value={report.knowledge_coverage * 100}
          sx={{ bgcolor: '#2a2a2a', height: 6, borderRadius: 3,
            '& .MuiLinearProgress-bar': { bgcolor: '#00d4ff', borderRadius: 3 } }} />
      </Box>

      {/* 信度估计 */}
      <Box sx={{ mb: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
          <Typography sx={{ color: '#999', fontSize: 12 }}>信度估计</Typography>
          <Typography sx={{ color: '#4caf50', fontSize: 12, fontWeight: 600 }}>
            {(report.reliability_estimate * 100).toFixed(0)}%
          </Typography>
        </Box>
        <LinearProgress variant="determinate" value={report.reliability_estimate * 100}
          sx={{ bgcolor: '#2a2a2a', height: 6, borderRadius: 3,
            '& .MuiLinearProgress-bar': { bgcolor: '#4caf50', borderRadius: 3 } }} />
      </Box>

      {/* 难度分布 */}
      <Typography sx={{ color: '#999', fontSize: 12, mb: 0.5 }}>难度分布</Typography>
      <Box sx={{ display: 'flex', gap: 1, mb: 1.5 }}>
        {Object.entries(report.difficulty_distribution || {}).map(([key, val]) => {
          const color = key === 'easy' ? '#4caf50' : key === 'medium' ? '#ff9800' : '#f44336';
          return (
            <Chip key={key} label={`${key}: ${(val * 100).toFixed(0)}%`} size="small"
              sx={{ color, borderColor: color, fontSize: 11 }} variant="outlined" />
          );
        })}
      </Box>

      {/* 警告 */}
      {report.warnings && report.warnings.length > 0 && (
        <Box>
          <Typography sx={{ color: '#f44336', fontSize: 12, mb: 0.5 }}>告警</Typography>
          {report.warnings.map((w, i) => (
            <Typography key={i} sx={{ color: '#ff9800', fontSize: 12 }}>⚠ {w}</Typography>
          ))}
        </Box>
      )}

      {(!report.warnings || report.warnings.length === 0) && (
        <Typography sx={{ color: '#4caf50', fontSize: 12 }}>✓ 无告警，试卷质量良好</Typography>
      )}
    </Box>
  );
}
