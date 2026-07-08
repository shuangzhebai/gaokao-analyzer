import { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, TextField, Button, MenuItem, Alert } from '@mui/material';
import { useToast } from '../../components/common/Toast';
import { paperService } from '../../services';
import { SUBJECTS, PAPER_TYPES } from '../../constants';

export default function UploadDialog({ open, onClose, onSuccess }: { open: boolean; onClose: () => void; onSuccess?: () => void }) {
  const { show } = useToast();
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('math');
  const [paperType, setPaperType] = useState('模拟卷');
  const [year, setYear] = useState(new Date().getFullYear());
  const [province, setProvince] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setError('');
    if (!file) { setError('请选择文件'); return; }
    if (!title.trim()) { setError('请填写标题'); return; }
    if (year < 2000 || year > 2030) { setError('年份无效'); return; }
    setLoading(true);
    try {
      await paperService.uploadPaper({ file, title: title.trim(), subject, paper_type: paperType, year, province: province.trim() });
      show('上传成功', 'success');
      onSuccess?.();
      onClose();
    } catch (e: unknown) {
      const axiosErr = e as { response?: { data?: { detail?: string } } };
      setError(axiosErr?.response?.data?.detail || '上传失败');
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { bgcolor: '#1a1a2e' } } }}>
      <DialogTitle sx={{ color: '#e0e0e0' }}>上传试卷</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField fullWidth label="标题" size="small" value={title} onChange={(e) => setTitle(e.target.value)} sx={{ mb: 2 }} />
        <TextField select fullWidth label="科目" size="small" value={subject} onChange={(e) => setSubject(e.target.value)} sx={{ mb: 2 }}>
          {Object.entries(SUBJECTS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
        </TextField>
        <TextField select fullWidth label="类型" size="small" value={paperType} onChange={(e) => setPaperType(e.target.value)} sx={{ mb: 2 }}>
          {PAPER_TYPES.map((t) => <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>)}
        </TextField>
        <TextField fullWidth label="年份" type="number" size="small" value={year} onChange={(e) => setYear(parseInt(e.target.value) || 2026)} sx={{ mb: 2 }} />
        <TextField fullWidth label="地区" size="small" value={province} onChange={(e) => setProvince(e.target.value)} sx={{ mb: 2 }} />
        <Button variant="outlined" component="label" fullWidth sx={{ mb: 2 }}>
          选择文件 {file ? `(${file.name})` : ''}
          <input type="file" hidden accept=".pdf,.docx,.doc" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </Button>
        <Button fullWidth variant="contained" disabled={loading} onClick={handleSubmit} sx={{ bgcolor: '#00d4ff' }}>
          {loading ? '上传中...' : '上传'}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
