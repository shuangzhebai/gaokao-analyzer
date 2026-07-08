import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Grid, TextField, MenuItem, Button } from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import LoadingState from '../../components/states/LoadingState';
import ErrorState from '../../components/states/ErrorState';
import PaperCard from '../../components/common/PaperCard';
import Pagination from '../../components/common/Pagination';
import UploadDialog from './UploadDialog';
import { paperService, filterService } from '../../services';
import type { Paper, FilterMeta } from '../../types';

export default function PaperListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<FilterMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);

  const q = searchParams.get('q') || '';
  const subject = searchParams.get('subject') || '';
  const paperType = searchParams.get('paper_type') || '';
  const year = searchParams.get('year') || '';
  const province = searchParams.get('province') || '';
  const page = parseInt(searchParams.get('page') || '1', 10);

  const fetch = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [paperData, filterData] = await Promise.all([
        paperService.listPapers({
          q: q || undefined, subject: subject || undefined,
          paper_type: paperType || undefined, year: year ? parseInt(year) : undefined,
          province: province || undefined, page, size: 20,
        }),
        filters ? null : filterService.getFilters(),
      ]);
      setPapers(paperData.data); setTotal(paperData.total);
      if (filterData) setFilters(filterData);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || '加载失败');
    } finally { setLoading(false); }
  }, [q, subject, paperType, year, province, page, filters]);

  useEffect(() => { fetch(); }, [fetch]);

  const updateParam = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val); else next.delete(key);
    if (key !== 'page') next.set('page', '1');
    setSearchParams(next);
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600 }}>试卷列表</Typography>
        <Button variant="contained" onClick={() => setUploadOpen(true)} sx={{ bgcolor: '#00d4ff', '&:hover': { bgcolor: '#00b8e6' } }}>
          上传试卷
        </Button>
      </Box>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        <TextField select label="科目" size="small" value={subject} onChange={(e) => updateParam('subject', e.target.value)}
          sx={{ minWidth: 100, '& input, & .MuiSelect-select': { color: '#e0e0e0' } }}>
          <MenuItem value="">全部</MenuItem>
          {filters?.subjects?.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
        </TextField>
        <TextField label="搜索" size="small" value={q} onChange={(e) => updateParam('q', e.target.value)}
          sx={{ minWidth: 160, '& input': { color: '#e0e0e0' } }} />
      </Box>
      {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={fetch} /> : (
        <>
          <Typography variant="body2" sx={{ color: '#666', mb: 1 }}>共 {total} 份试卷</Typography>
          <Grid container spacing={1.5}>
            {papers.map((p) => (<Grid size={{ xs: 12, sm: 6, md: 4 }} key={p.id}><PaperCard paper={p} /></Grid>))}
          </Grid>
          {papers.length === 0 && <Box sx={{ textAlign: 'center', py: 4, color: '#666' }}>无匹配结果</Box>}
          <Pagination page={page} totalPages={totalPages} onPageChange={(p) => updateParam('page', String(p))} />
        </>
      )}
      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onSuccess={fetch} />
    </Box>
  );
}
