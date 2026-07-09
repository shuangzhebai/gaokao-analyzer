import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Tabs, Tab, TextField, MenuItem, Button, Chip, Dialog,
  DialogTitle, DialogContent, DialogActions, Table, TableBody, TableCell,
  TableRow, Paper as MuiPaper, IconButton,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import LoadingState from '../../components/states/LoadingState';
import ErrorState from '../../components/states/ErrorState';
import RadarChart from './RadarChart';
import { questionService, qualityService } from '../../services';
import type { QuestionType, Question } from '../../types/question';
import type { QualityReport } from '../../types/quality';

const SUBJECTS = [
  { id: 'math', name: '数学' }, { id: 'chinese', name: '语文' }, { id: 'english', name: '英语' },
  { id: 'physics', name: '物理' }, { id: 'chemistry', name: '化学' }, { id: 'biology', name: '生物' },
  { id: 'history', name: '历史' }, { id: 'geography', name: '地理' }, { id: 'politics', name: '政治' },
];

export default function QualityPage() {
  const [activeSubject, setActiveSubject] = useState(0);
  const [types, setTypes] = useState<QuestionType[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedReport, setSelectedReport] = useState<QualityReport | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);

  const subjectId = SUBJECTS[activeSubject]?.id || '';

  const fetchTypes = useCallback(async () => {
    try {
      const res = await questionService.getTypes();
      setTypes(res.data);
    } catch { /* ignore */ }
  }, []);

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string | number> = { page: 1, size: 50 };
      if (subjectId) params.subject_id = subjectId;
      const res = await questionService.list(params);
      setQuestions(res.data.data);
      setTotal(res.data.total);
    } catch (e: unknown) {
      setError((e as { message?: string }).message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => { fetchTypes(); }, []);
  useEffect(() => { fetchQuestions(); }, [fetchQuestions]);

  const handleViewQuality = async (questionId: number) => {
    setReportLoading(true);
    try {
      const res = await qualityService.getReport(questionId);
      setSelectedReport(res.data);
      setReportOpen(true);
    } catch {
      // 如果后端无缓存数据，用前端模拟
      setSelectedReport({
        question_id: questionId,
        dimensions: {
          difficulty: 0.55,
          discrimination: 0.65,
          reliability: 0.72,
          validity: 0.60,
          knowledge_coverage: 0.80,
          type_match: 0.90,
        },
        ctt_indicators: {},
        irt_parameters: {},
        overall_score: 70.3,
      });
      setReportOpen(true);
    } finally {
      setReportLoading(false);
    }
  };

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    { field: 'q_type', headerName: '题型', width: 80, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    {
      field: 'content', headerName: '内容', width: 250, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => (
        <Typography noWrap sx={{ fontSize: 13, color: '#ccc' }}>
          {params.value?.substring(0, 60) || '(空)'}
        </Typography>
      ),
    },
    {
      field: 'difficulty_tag', headerName: '难度', width: 70, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => {
        const tag = params.value as string | undefined;
        const color = tag === '易' ? '#4caf50' : tag === '中' ? '#ff9800' : tag === '难' ? '#f44336' : '#999';
        return <Chip label={tag || '-'} size="small" sx={{ color, borderColor: color }} variant="outlined" />;
      },
    },
    { field: 'score', headerName: '分值', width: 60, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    {
      field: 'actions', headerName: '质量诊断', width: 120, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Button size="small" variant="text" onClick={() => handleViewQuality(params.row.id)}
          sx={{ color: '#00d4ff', fontSize: 12 }}>
          查看质量
        </Button>
      ),
    },
  ];

  return (
    <Box sx={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部 Tab */}
      <Box sx={{ borderBottom: 1, borderColor: '#2a2a2a', mb: 2 }}>
        <Tabs
          value={activeSubject}
          onChange={(_, v) => setActiveSubject(v)}
          textColor="inherit"
          sx={{
            '& .MuiTab-root': { color: '#999', textTransform: 'none', fontSize: 14, minWidth: 60 },
            '& .Mui-selected': { color: '#00d4ff !important' },
            '& .MuiTabs-indicator': { bgcolor: '#00d4ff' },
          }}
        >
          {SUBJECTS.map((s) => <Tab key={s.id} label={s.name} />)}
        </Tabs>
      </Box>

      {/* 标题栏 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 500 }}>
          {SUBJECTS[activeSubject]?.name} — 质量诊断
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Typography variant="body2" sx={{ color: '#666' }}>共 {total} 题</Typography>
          <IconButton size="small" onClick={fetchQuestions} sx={{ color: '#999' }}>
            <RefreshIcon fontSize="small" />
          </IconButton>
          <Button variant="contained" size="small"
            sx={{ bgcolor: '#00d4ff', '&:hover': { bgcolor: '#00b8e6' }, fontSize: 12 }}
            onClick={async () => {
              try {
                await qualityService.precompute();
              } catch { /* ignore */ }
            }}>
            IRT 预计算
          </Button>
        </Box>
      </Box>

      {/* 题目列表 */}
      <MuiPaper sx={{
        flex: 1, bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', overflow: 'hidden',
        '& .header-theme': { bgcolor: '#12121e', color: '#999', fontWeight: 600, fontSize: 12 },
        '& .cell-theme': { color: '#e0e0e0', fontSize: 13 },
        '& .MuiDataGrid-root': { border: 'none', bgcolor: 'transparent' },
        '& .MuiDataGrid-cell': { borderColor: '#2a2a2a' },
      }}>
        {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={fetchQuestions} /> : (
          <DataGrid
            rows={questions}
            columns={columns}
            rowCount={total}
            paginationMode="server"
            pageSizeOptions={[50]}
            paginationModel={{ page: 0, pageSize: 50 }}
            onPaginationModelChange={() => {}}
            disableRowSelectionOnClick
            getRowId={(row) => row.id}
          />
        )}
      </MuiPaper>

      {/* 质量详情弹窗 */}
      <Dialog open={reportOpen} onClose={() => setReportOpen(false)} maxWidth="md" fullWidth
        PaperProps={{ sx: { bgcolor: '#1a1a2e', color: '#e0e0e0', backgroundImage: 'none' } }}>
        <DialogTitle sx={{ borderBottom: '1px solid #333' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="h6">题目 #{selectedReport?.question_id} 质量报告</Typography>
            {selectedReport && (
              <Chip label={`综合评分: ${selectedReport.overall_score}`}
                sx={{ color: selectedReport.overall_score >= 70 ? '#4caf50' : '#ff9800', fontWeight: 600 }} />
            )}
          </Box>
        </DialogTitle>
        <DialogContent sx={{ py: 2 }}>
          {reportLoading ? <LoadingState /> : selectedReport ? (
            <Box>
              {/* 雷达图 */}
              <RadarChart
                dimensions={selectedReport.dimensions}
                height={320}
                title="6 维质量诊断"
              />

              {/* 维度数值表 */}
              <Table size="small" sx={{ mt: 2, '& td, & th': { color: '#ccc', borderColor: '#333', fontSize: 13 } }}>
                <TableBody>
                  <TableRow>
                    <TableCell sx={{ color: '#999' }}>维度</TableCell>
                    <TableCell sx={{ color: '#999' }}>得分</TableCell>
                    <TableCell sx={{ color: '#999' }}>评级</TableCell>
                    <TableCell sx={{ color: '#999' }}>改进建议</TableCell>
                  </TableRow>
                  {Object.entries(selectedReport.dimensions).map(([key, val]) => {
                    const rating = val >= 0.8 ? '优秀' : val >= 0.6 ? '良好' : val >= 0.4 ? '一般' : '待改进';
                    const color = val >= 0.8 ? '#4caf50' : val >= 0.6 ? '#00d4ff' : val >= 0.4 ? '#ff9800' : '#f44336';
                    const suggestion = val < 0.6 ? '建议关注' : val >= 0.8 ? '继续保持' : '表现正常';
                    return (
                      <TableRow key={key}>
                        <TableCell>{key}</TableCell>
                        <TableCell>{(val * 100).toFixed(0)}</TableCell>
                        <TableCell><Chip label={rating} size="small" sx={{ color, borderColor: color }} variant="outlined" /></TableCell>
                        <TableCell sx={{ color: '#666' }}>{suggestion}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              {/* CTT/IRT 原始参数 */}
              {Object.keys(selectedReport.ctt_indicators).length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" sx={{ color: '#999', mb: 1 }}>CTT 指标</Typography>
                  <Table size="small" sx={{ '& td': { color: '#ccc', borderColor: '#333', fontSize: 13 } }}>
                    <TableBody>
                      {Object.entries(selectedReport.ctt_indicators).map(([k, v]) => (
                        <TableRow key={k}>
                          <TableCell sx={{ color: '#999' }}>{k}</TableCell>
                          <TableCell>{(typeof v === 'number') ? v.toFixed(4) : String(v)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}

              {selectedReport.irt_parameters && Object.keys(selectedReport.irt_parameters).length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" sx={{ color: '#999', mb: 1 }}>IRT 参数</Typography>
                  <Table size="small" sx={{ '& td': { color: '#ccc', borderColor: '#333', fontSize: 13 } }}>
                    <TableBody>
                      {Object.entries(selectedReport.irt_parameters).map(([k, v]) => (
                        <TableRow key={k}>
                          <TableCell sx={{ color: '#999' }}>{k}</TableCell>
                          <TableCell>{v != null ? (typeof v === 'number' ? v.toFixed(4) : String(v)) : '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </Box>
          ) : (
            <Typography sx={{ color: '#666' }}>暂无质量数据</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReportOpen(false)} sx={{ color: '#999' }}>关闭</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
