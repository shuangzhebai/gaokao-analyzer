import { useState, useCallback } from 'react';
import { Box, Typography, Grid, LinearProgress, Button, Chip } from '@mui/material';
import ConstraintPanel from './ConstraintPanel';
import PreviewPanel from './PreviewPanel';
import QualityReportPanel from './QualityReportPanel';
import { compositionService } from '../../services';
import type { CompositionConstraints, CompositionResult } from '../../types/composition';

const DEFAULT_CONSTRAINTS: CompositionConstraints = {
  subject_id: 'math',
  total_count: 20,
  total_score: undefined,
  difficulty_mean: 0.55,
  difficulty_std: 0.15,
  types: [
    { id: 1, name: '选择题', count: 10, score: 5 },
    { id: 2, name: '填空题', count: 5, score: 5 },
    { id: 3, name: '解答题', count: 5, score: 10 },
  ],
  knowledge_points: [],
  prefer_real_exam: true,
};

export default function CompositionPage() {
  const [constraints, setConstraints] = useState<CompositionConstraints>(DEFAULT_CONSTRAINTS);
  const [generating, setGenerating] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<CompositionResult | null>(null);
  const [error, setError] = useState('');

  const pollTask = useCallback(async (tid: string) => {
    const maxAttempts = 30;
    for (let i = 0; i < maxAttempts; i++) {
      try {
        const res = await compositionService.getTask(tid);
        const task = res.data;
        setProgress(task.progress || 0);
        if (task.status === 'completed') {
          const resultData = task.result_data as CompositionResult;
          setResult({
            id: 0,
            name: '组卷结果',
            question_ids: resultData?.question_ids || [],
            total_score: resultData?.total_score || 0,
            constraints_satisfied: resultData?.constraints_satisfied || false,
            objective_score: resultData?.objective_score || 0,
            quality_report: resultData?.quality_report,
          });
          setGenerating(false);
          return;
        }
        if (task.status === 'failed') {
          setError(task.error || '组卷失败');
          setGenerating(false);
          return;
        }
      } catch {
        // ignore polling errors
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    setGenerating(false);
    setError('组卷超时');
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    setResult(null);
    setProgress(0);
    try {
      const res = await compositionService.generate(constraints);
      const tid = res.data.task_id;
      setTaskId(tid);
      pollTask(tid);
    } catch (e: unknown) {
      setError((e as { message?: string }).message || '组卷请求失败');
      setGenerating(false);
    }
  };

  return (
    <Box sx={{ height: 'calc(100vh - 120px)', overflow: 'auto' }}>
      <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>
        智能组卷
      </Typography>

      <Grid container spacing={2}>
        {/* 左侧：约束条件面板 */}
        <Grid size={{ xs: 12, md: 4 }}>
          <ConstraintPanel constraints={constraints} onChange={setConstraints}
            onGenerate={handleGenerate} generating={generating} />
        </Grid>

        {/* 右侧：结果预览 */}
        <Grid size={{ xs: 12, md: 8 }}>
          {/* 进度条 */}
          {generating && (
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography sx={{ color: '#999', fontSize: 12 }}>组卷进度</Typography>
                <Typography sx={{ color: '#00d4ff', fontSize: 12 }}>{progress}%</Typography>
              </Box>
              <LinearProgress variant="determinate" value={progress}
                sx={{ bgcolor: '#2a2a2a', height: 8, borderRadius: 4,
                  '& .MuiLinearProgress-bar': { bgcolor: '#00d4ff', borderRadius: 4 } }} />
            </Box>
          )}

          {/* 错误提示 */}
          {error && (
            <Chip label={error} color="error" size="small" sx={{ mb: 1 }} onDelete={() => setError('')} />
          )}

          {/* 预览区 */}
          <PreviewPanel result={result} loading={generating && !result} />

          {/* 质量预检报告 */}
          {result?.quality_report && (
            <QualityReportPanel report={result.quality_report} />
          )}

          {/* 操作按钮 */}
          {result && (
            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              <Button variant="outlined" size="small"
                sx={{ color: '#00d4ff', borderColor: '#00d4ff', '&:hover': { borderColor: '#00b8e6' } }}>
                导出 PDF
              </Button>
              <Button variant="outlined" size="small"
                sx={{ color: '#4caf50', borderColor: '#4caf50', '&:hover': { borderColor: '#388e3c' } }}>
                导出 Word
              </Button>
              <Button variant="outlined" size="small"
                sx={{ color: '#ff9800', borderColor: '#ff9800', '&:hover': { borderColor: '#ed6c02' } }}>
                存为模板
              </Button>
            </Box>
          )}
        </Grid>
      </Grid>
    </Box>
  );
}
