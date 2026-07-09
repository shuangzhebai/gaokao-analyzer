import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  Chip,
  LinearProgress,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  Tooltip,
  IconButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import BarChartIcon from '@mui/icons-material/BarChart';
import { useToast } from '../../components/common/Toast';
import {
  getCollectionStats,
  getCollectionTarget,
  triggerCollection,
  getCollectionLogs,
} from '../../services/collect';
import type {
  CollectionStats,
  CollectionTargetProgress,
  CollectionLog,
} from '../../types/collection';

/** 科目中文映射 */
const SUBJECT_NAMES: Record<string, string> = {
  chinese: '语文',
  math: '数学',
  english: '英语',
  physics: '物理',
  chemistry: '化学',
  biology: '生物',
  history: '历史',
  geography: '地理',
  politics: '政治',
};

/** 来源中文映射 */
const SOURCE_NAMES: Record<string, string> = {
  moe: '教育部',
  zxxk: '学科网',
  zujuan: '组卷网',
  jyeoo: '菁优网',
  gaosan: '高考网',
  paperpass: '试卷吧',
  '21cnjy': '21世纪教育网',
  auto_scraper: '自动采集',
  manual_trigger: '手动触发',
  unknown: '未知来源',
};

/** 状态 Chip 颜色映射 */
const STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  completed: 'success',
  running: 'warning',
  failed: 'error',
};

export default function CollectionDashboard() {
  const { show } = useToast();
  const [stats, setStats] = useState<CollectionStats | null>(null);
  const [target, setTarget] = useState<CollectionTargetProgress | null>(null);
  const [logs, setLogs] = useState<CollectionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);

  /** 加载所有数据 */
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, targetData, logsData] = await Promise.all([
        getCollectionStats(),
        getCollectionTarget(),
        getCollectionLogs(20, 0),
      ]);
      setStats(statsData);
      setTarget(targetData);
      setLogs(logsData.data);
    } catch (e: unknown) {
      const err = e as { message?: string };
      show(err.message || '加载采集数据失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [show]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /** 手动触发采集 */
  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const result = await triggerCollection();
      if (result.triggered) {
        show('采集任务已提交，后台执行中', 'success');
        // 延迟刷新数据
        setTimeout(loadData, 3000);
      } else {
        show(result.error || '触发失败', 'error');
      }
    } catch (e: unknown) {
      const err = e as { message?: string };
      show(err.message || '触发失败', 'error');
    } finally {
      setTriggering(false);
    }
  };

  if (loading && !stats) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      {/* 标题栏 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600 }}>
          采集管理仪表盘
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="刷新数据">
            <IconButton onClick={loadData} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={triggering ? <CircularProgress size={20} /> : <PlayArrowIcon />}
            disabled={triggering}
            onClick={handleTrigger}
            sx={{ bgcolor: '#00d4ff', '&:hover': { bgcolor: '#00b8e6' } }}
          >
            {triggering ? '触发中...' : '手动采集'}
          </Button>
        </Box>
      </Box>

      {/* 目标进度区 */}
      {target && (
        <Paper sx={{ bgcolor: '#1a1a2e', p: 3, mb: 3, borderRadius: 2 }}>
          <Typography variant="h6" sx={{ color: '#e0e0e0', mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <BarChartIcon /> 采集目标进度
          </Typography>

          <Grid container spacing={3}>
            {/* 模拟卷进度 */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="body2" sx={{ color: '#aaa', mb: 0.5 }}>
                模拟卷：{target.collected_mock_papers} / {target.target.mock_papers}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={target.mock_progress_pct}
                  sx={{
                    flexGrow: 1,
                    height: 10,
                    borderRadius: 5,
                    bgcolor: '#2a2a4e',
                    '& .MuiLinearProgress-bar': { bgcolor: '#00d4ff' },
                  }}
                />
                <Typography variant="body2" sx={{ color: '#00d4ff', minWidth: 40, textAlign: 'right' }}>
                  {target.mock_progress_pct}%
                </Typography>
              </Box>
            </Grid>

            {/* 真题进度 */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="body2" sx={{ color: '#aaa', mb: 0.5 }}>
                高考真题（近 {target.target.real_exams_years} 年）
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={target.real_progress_pct}
                  sx={{
                    flexGrow: 1,
                    height: 10,
                    borderRadius: 5,
                    bgcolor: '#2a2a4e',
                    '& .MuiLinearProgress-bar': { bgcolor: '#ff9800' },
                  }}
                />
                <Typography variant="body2" sx={{ color: '#ff9800', minWidth: 40, textAlign: 'right' }}>
                  {target.real_progress_pct}%
                </Typography>
              </Box>
            </Grid>

            {/* 总进度 */}
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" sx={{ color: '#aaa', mb: 0.5 }}>
                总体进度
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={target.overall_progress_pct}
                  sx={{
                    flexGrow: 1,
                    height: 14,
                    borderRadius: 7,
                    bgcolor: '#2a2a4e',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: target.overall_progress_pct >= 80 ? '#4caf50' : '#ff9800',
                    },
                  }}
                />
                <Typography
                  variant="body1"
                  sx={{
                    color: target.overall_progress_pct >= 80 ? '#4caf50' : '#ff9800',
                    minWidth: 50,
                    textAlign: 'right',
                    fontWeight: 600,
                  }}
                >
                  {target.overall_progress_pct}%
                </Typography>
              </Box>
            </Grid>

            {/* 年份覆盖标签 */}
            <Grid size={{ xs: 12 }}>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                {Object.entries(target.year_coverage).map(([year, count]) => (
                  <Chip
                    key={year}
                    label={`${year}年 ${count > 0 ? `(${count}套)` : '(未覆盖)'}`}
                    size="small"
                    color={count > 0 ? 'success' : 'default'}
                    variant="outlined"
                  />
                ))}
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* 统计卡片区 */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card sx={{ bgcolor: '#1a1a2e', border: '1px solid #2a2a4e' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: '#aaa' }}>总试卷数</Typography>
                <Typography variant="h4" sx={{ color: '#00d4ff', fontWeight: 700 }}>
                  {stats.total_papers}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card sx={{ bgcolor: '#1a1a2e', border: '1px solid #2a2a4e' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: '#aaa' }}>总题目数</Typography>
                <Typography variant="h4" sx={{ color: '#7c4dff', fontWeight: 700 }}>
                  {stats.total_questions}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card sx={{ bgcolor: '#1a1a2e', border: '1px solid #2a2a4e' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: '#aaa' }}>来源数</Typography>
                <Typography variant="h4" sx={{ color: '#ff9800', fontWeight: 700 }}>
                  {Object.keys(stats.source_distribution).length}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card sx={{ bgcolor: '#1a1a2e', border: '1px solid #2a2a4e' }}>
              <CardContent>
                <Typography variant="body2" sx={{ color: '#aaa' }}>学科数</Typography>
                <Typography variant="h4" sx={{ color: '#4caf50', fontWeight: 700 }}>
                  {Object.keys(stats.subject_distribution).length}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* 来源与学科分布 */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {/* 来源分布 */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ bgcolor: '#1a1a2e', p: 2, borderRadius: 2 }}>
              <Typography variant="subtitle1" sx={{ color: '#e0e0e0', mb: 1, fontWeight: 600 }}>
                各来源占比
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }}>来源</TableCell>
                      <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }} align="right">
                        试卷数
                      </TableCell>
                      <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }} align="right">
                        占比
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {Object.entries(stats.source_distribution)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 8)
                      .map(([source, count]) => (
                        <TableRow key={source}>
                          <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }}>
                            {SOURCE_NAMES[source] || source}
                          </TableCell>
                          <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }} align="right">
                            {count}
                          </TableCell>
                          <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }} align="right">
                            {stats.total_papers > 0
                              ? ((count / stats.total_papers) * 100).toFixed(1) + '%'
                              : '0%'}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>

          {/* 学科分布 */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ bgcolor: '#1a1a2e', p: 2, borderRadius: 2 }}>
              <Typography variant="subtitle1" sx={{ color: '#e0e0e0', mb: 1, fontWeight: 600 }}>
                各学科占比
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }}>学科</TableCell>
                      <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }} align="right">
                        试卷数
                      </TableCell>
                      <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }} align="right">
                        题目数
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {Object.entries(stats.subject_distribution)
                      .sort(([, a], [, b]) => b - a)
                      .map(([subject, count]) => (
                        <TableRow key={subject}>
                          <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }}>
                            {SUBJECT_NAMES[subject] || subject}
                          </TableCell>
                          <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }} align="right">
                            {count}
                          </TableCell>
                          <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }} align="right">
                            {stats.questions_by_subject[subject] || 0}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* 采集日志列表 */}
      <Paper sx={{ bgcolor: '#1a1a2e', p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle1" sx={{ color: '#e0e0e0', mb: 2, fontWeight: 600 }}>
          采集记录
        </Typography>

        {logs.length === 0 ? (
          <Alert severity="info" sx={{ bgcolor: '#2a2a4e', color: '#aaa' }}>
            暂无采集记录
          </Alert>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }}>时间</TableCell>
                  <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }}>来源</TableCell>
                  <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }}>类型</TableCell>
                  <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }} align="right">
                    发现
                  </TableCell>
                  <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }} align="right">
                    新增试卷
                  </TableCell>
                  <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }} align="right">
                    新增题目
                  </TableCell>
                  <TableCell sx={{ color: '#aaa', borderBottom: '1px solid #2a2a4e' }}>状态</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }}>
                      {log.started_at
                        ? new Date(log.started_at).toLocaleString('zh-CN', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : '-'}
                    </TableCell>
                    <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }}>
                      {SOURCE_NAMES[log.source] || log.source}
                    </TableCell>
                    <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }}>
                      <Chip
                        label={log.task_type === 'manual' ? '手动' : '定时'}
                        size="small"
                        variant="outlined"
                        sx={{ color: log.task_type === 'manual' ? '#ff9800' : '#00d4ff' }}
                      />
                    </TableCell>
                    <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }} align="right">
                      {log.papers_found}
                    </TableCell>
                    <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }} align="right">
                      {log.papers_new}
                    </TableCell>
                    <TableCell sx={{ color: '#e0e0e0', borderBottom: '1px solid #2a2a4e' }} align="right">
                      {log.questions_new}
                    </TableCell>
                    <TableCell sx={{ borderBottom: '1px solid #2a2a4e' }}>
                      <Chip
                        label={log.status}
                        size="small"
                        color={STATUS_COLORS[log.status] || 'default'}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Box>
  );
}
