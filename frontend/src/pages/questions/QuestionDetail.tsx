import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Typography, Box, Chip, Divider, Table, TableBody, TableCell, TableRow,
} from '@mui/material';
import type { Question } from '../../types/question';

interface QuestionDetailProps {
  question: Question | null;
  open: boolean;
  onClose: () => void;
}

export default function QuestionDetail({ question, open, onClose }: QuestionDetailProps) {
  if (!question) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth
      PaperProps={{ sx: { bgcolor: '#1a1a2e', color: '#e0e0e0', backgroundImage: 'none' } }}>
      <DialogTitle sx={{ borderBottom: '1px solid #333' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">题目 #{question.id}</Typography>
          <Chip label={question.q_type} size="small" sx={{ color: '#00d4ff', borderColor: '#00d4ff' }} variant="outlined" />
          {question.difficulty_tag && (
            <Chip label={question.difficulty_tag} size="small"
              sx={{ color: '#ff9800', borderColor: '#ff9800' }} variant="outlined" />
          )}
        </Box>
      </DialogTitle>
      <DialogContent sx={{ py: 2 }}>
        {/* 题目内容 */}
        <Typography variant="subtitle2" sx={{ color: '#999', mb: 1 }}>题目内容</Typography>
        <Box sx={{ bgcolor: '#12121e', p: 2, borderRadius: 1, mb: 2, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 13 }}>
          {question.content || '(无内容)'}
        </Box>

        {/* 选项 */}
        {question.options && (
          <>
            <Typography variant="subtitle2" sx={{ color: '#999', mb: 1 }}>选项</Typography>
            <Box sx={{ bgcolor: '#12121e', p: 2, borderRadius: 1, mb: 2, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 13 }}>
              {question.options}
            </Box>
          </>
        )}

        {/* 答案与解析 */}
        <Divider sx={{ my: 2, borderColor: '#333' }} />
        <Typography variant="subtitle2" sx={{ color: '#4caf50', mb: 1 }}>答案</Typography>
        <Box sx={{ bgcolor: '#12121e', p: 2, borderRadius: 1, mb: 2, fontFamily: 'monospace', fontSize: 13 }}>
          {question.answer || '(无答案)'}
        </Box>

        {question.explanation && (
          <>
            <Typography variant="subtitle2" sx={{ color: '#2196f3', mb: 1 }}>解析</Typography>
            <Box sx={{ bgcolor: '#12121e', p: 2, borderRadius: 1, mb: 2, fontSize: 13 }}>
              {question.explanation}
            </Box>
          </>
        )}

        {/* IRT 参数 */}
        <Divider sx={{ my: 2, borderColor: '#333' }} />
        <Typography variant="subtitle2" sx={{ color: '#999', mb: 1 }}>IRT 参数</Typography>
        <Table size="small" sx={{ '& td': { color: '#ccc', borderColor: '#333', fontSize: 13 } }}>
          <TableBody>
            <TableRow>
              <TableCell sx={{ color: '#999' }}>区分度 (a)</TableCell>
              <TableCell>{question.irt_a?.toFixed(3) ?? '-'}</TableCell>
              <TableCell sx={{ color: '#999' }}>难度 (b)</TableCell>
              <TableCell>{question.irt_b?.toFixed(3) ?? '-'}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ color: '#999' }}>猜测系数 (c)</TableCell>
              <TableCell>{question.irt_c?.toFixed(3) ?? '-'}</TableCell>
              <TableCell sx={{ color: '#999' }}>知识点</TableCell>
              <TableCell>{question.knowledge_points || '-'}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} sx={{ color: '#999' }}>关闭</Button>
      </DialogActions>
    </Dialog>
  );
}
