import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, TextField, MenuItem, Button, IconButton,
  Chip, Paper as MuiPaper,
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useSearchParams } from 'react-router-dom';
import LoadingState from '../../components/states/LoadingState';
import ErrorState from '../../components/states/ErrorState';
import QuestionTree from './QuestionTree';
import QuestionDetail from './QuestionDetail';
import { questionService } from '../../services';
import type { Question, QuestionType, ClassifyResult } from '../../types/question';

const SUBJECTS = [
  { id: 'math', name: '数学' }, { id: 'chinese', name: '语文' }, { id: 'english', name: '英语' },
  { id: 'physics', name: '物理' }, { id: 'chemistry', name: '化学' }, { id: 'biology', name: '生物' },
  { id: 'history', name: '历史' }, { id: 'geography', name: '地理' }, { id: 'politics', name: '政治' },
];

export default function QuestionsListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [types, setTypes] = useState<QuestionType[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const subject = searchParams.get('subject_id') || '';
  const qTypeId = searchParams.get('question_type_id') || '';
  const page = parseInt(searchParams.get('page') || '1', 10);
  const size = 20;

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
      const params: Record<string, string | number> = { page, size };
      if (subject) params.subject_id = subject;
      if (qTypeId) params.question_type_id = parseInt(qTypeId, 10);
      const res = await questionService.list(params);
      setQuestions(res.data.data);
      setTotal(res.data.total);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [subject, qTypeId, page, size]);

  useEffect(() => { fetchTypes(); }, []);
  useEffect(() => { fetchQuestions(); }, [fetchQuestions]);

  const updateParam = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val);
    else next.delete(key);
    if (key !== 'page') next.set('page', '1');
    setSearchParams(next);
  };

  const handleTypeSelect = (typeId: number | undefined) => {
    updateParam('question_type_id', typeId ? String(typeId) : '');
  };

  const handleViewDetail = async (id: number) => {
    try {
      const res = await questionService.getById(id);
      setSelectedQuestion(res.data);
      setDetailOpen(true);
    } catch {
      setError('加载题目详情失败');
    }
  };

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    {
      field: 'q_type', headerName: '题型', width: 80, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => (
        <Chip label={params.value} size="small" variant="outlined"
          sx={{ color: '#00d4ff', borderColor: '#00d4ff', fontSize: 11 }} />
      ),
    },
    {
      field: 'content', headerName: '内容', width: 300, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => (
        <Typography noWrap sx={{ fontSize: 13, color: '#ccc' }}>
          {params.value?.substring(0, 80) || '(空)'}
        </Typography>
      ),
    },
    {
      field: 'difficulty_tag', headerName: '难度', width: 80, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => {
        const tag = params.value as string | undefined;
        const color = tag === '易' ? '#4caf50' : tag === '中' ? '#ff9800' : tag === '难' ? '#f44336' : '#999';
        return <Chip label={tag || '-'} size="small" sx={{ color, borderColor: color }} variant="outlined" />;
      },
    },
    {
      field: 'irt_a', headerName: '区分度', width: 80, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => (
        <Typography sx={{ fontSize: 13, color: '#ccc' }}>{params.value?.toFixed(2) ?? '-'}</Typography>
      ),
    },
    {
      field: 'irt_b', headerName: '难度参数', width: 80, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => (
        <Typography sx={{ fontSize: 13, color: '#ccc' }}>{params.value?.toFixed(2) ?? '-'}</Typography>
      ),
    },
    {
      field: 'score', headerName: '分值', width: 70, headerClassName: 'header-theme', cellClassName: 'cell-theme',
    },
    {
      field: 'actions', headerName: '操作', width: 100, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Button size="small" variant="text" onClick={() => handleViewDetail(params.row.id)}
          sx={{ color: '#00d4ff', fontSize: 12 }}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 120px)', gap: 2 }}>
      {/* 左侧题型树 */}
      <MuiPaper sx={{
        width: 260, flexShrink: 0, bgcolor: '#1a1a2e', borderRadius: 2,
        border: '1px solid #2a2a2a', overflow: 'auto',
      }}>
        <QuestionTree types={types} selectedTypeId={qTypeId ? parseInt(qTypeId, 10) : undefined}
          onSelect={handleTypeSelect} />
      </MuiPaper>

      {/* 右侧题目列表 */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* 筛选栏 */}
        <Box sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center' }}>
          <TextField select label="科目" size="small" value={subject}
            onChange={(e) => updateParam('subject_id', e.target.value)}
            sx={{ minWidth: 100, '& input, & .MuiSelect-select': { color: '#e0e0e0' } }}>
            <MenuItem value="">全部</MenuItem>
            {SUBJECTS.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
          </TextField>
          <Typography variant="body2" sx={{ color: '#666', ml: 'auto' }}>
            共 {total} 题
          </Typography>
        </Box>

        {/* 数据表格 */}
        <MuiPaper sx={{
          flex: 1, bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', overflow: 'hidden',
          '& .header-theme': { bgcolor: '#12121e', color: '#999', fontWeight: 600, fontSize: 12 },
          '& .cell-theme': { color: '#e0e0e0', fontSize: 13 },
          '& .MuiDataGrid-root': { border: 'none', bgcolor: 'transparent' },
          '& .MuiDataGrid-cell': { borderColor: '#2a2a2a' },
          '& .MuiTablePagination-root': { color: '#999' },
        }}>
          {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={fetchQuestions} /> : (
            <DataGrid
              rows={questions}
              columns={columns}
              rowCount={total}
              paginationMode="server"
              pageSizeOptions={[20]}
              paginationModel={{ page: page - 1, pageSize: size }}
              onPaginationModelChange={(model) => updateParam('page', String(model.page + 1))}
              disableRowSelectionOnClick
              getRowId={(row) => row.id}
              sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
            />
          )}
        </MuiPaper>
      </Box>

      {/* 详情弹窗 */}
      <QuestionDetail question={selectedQuestion} open={detailOpen} onClose={() => setDetailOpen(false)} />
    </Box>
  );
}
