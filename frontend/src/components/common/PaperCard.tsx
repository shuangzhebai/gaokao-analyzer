import { Card, CardContent, Typography, Chip, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { Paper } from '../../types';
import { ANALYSIS_STATUS_MAP } from '../../constants';

export default function PaperCard({ paper }: { paper: Paper }) {
  const navigate = useNavigate();
  const statusColors: Record<string, string> = {
    pending: '#666', parsed: '#2196f3', analyzing: '#ff9800',
    irt_estimated: '#4caf50', simulated: '#00bcd4',
    analyzed: '#00d4ff', failed: '#f44336',
  };

  return (
    <Card
      sx={{ bgcolor: '#1a1a2e', cursor: 'pointer', '&:hover': { bgcolor: '#1e1e38', transform: 'translateY(-1px)', transition: '0.2s' } }}
      onClick={() => navigate(`/papers/${paper.id}`)}
    >
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Typography variant="subtitle2" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 0.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {paper.title}
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 0.5 }}>
          <Chip label={paper.subject_name} size="small" sx={{ height: 20, fontSize: 11, bgcolor: 'rgba(0,212,255,0.1)', color: '#00d4ff' }} />
          <Chip label={paper.paper_type} size="small" sx={{ height: 20, fontSize: 11, bgcolor: 'rgba(124,77,255,0.1)', color: '#7c4dff' }} />
          <Chip label={String(paper.year)} size="small" sx={{ height: 20, fontSize: 11, bgcolor: 'rgba(255,255,255,0.05)', color: '#a0a0b0' }} />
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="caption" sx={{ color: '#666' }}>
            {paper.province} {paper.school ? `· ${paper.school}` : ''}
          </Typography>
          <Chip
            label={ANALYSIS_STATUS_MAP[paper.analysis_status] || paper.analysis_status}
            size="small"
            sx={{ height: 20, fontSize: 11, bgcolor: `${statusColors[paper.analysis_status] || '#666'}22`, color: statusColors[paper.analysis_status] || '#666' }}
          />
        </Box>
      </CardContent>
    </Card>
  );
}
