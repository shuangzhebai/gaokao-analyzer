import { Box, Typography, Chip, Card, CardContent } from '@mui/material';

interface SimilarRecommendProps {
  recommendations: Array<{
    id: number;
    content?: string;
    irt_b?: number;
    difficulty_tag?: string;
    score?: number;
  }>;
}

export default function SimilarRecommend({ recommendations }: SimilarRecommendProps) {
  if (!recommendations || recommendations.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography sx={{ color: '#666', fontSize: 13 }}>暂无同类推荐</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ color: '#e0e0e0', mb: 1.5 }}>同类题目推荐</Typography>
      {recommendations.map((r, i) => (
        <Card key={r.id} sx={{ bgcolor: '#12121e', mb: 1, border: '1px solid #2a2a2a', borderRadius: 1 }}>
          <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <Typography sx={{ color: '#666', fontSize: 12 }}>#{i + 1}</Typography>
              <Chip label={`题号 ${r.id}`} size="small" sx={{ color: '#00d4ff', borderColor: '#00d4ff', fontSize: 10 }} variant="outlined" />
              {r.difficulty_tag && (
                <Chip label={r.difficulty_tag} size="small"
                  sx={{ fontSize: 10, color: r.difficulty_tag === '易' ? '#4caf50' : r.difficulty_tag === '中' ? '#ff9800' : '#f44336',
                        borderColor: r.difficulty_tag === '易' ? '#4caf50' : r.difficulty_tag === '中' ? '#ff9800' : '#f44336' }} variant="outlined" />
              )}
              {r.score && <Typography sx={{ color: '#999', fontSize: 12 }}>{r.score}分</Typography>}
            </Box>
            <Typography noWrap sx={{ color: '#ccc', fontSize: 13 }}>
              {r.content?.substring(0, 80) || '(无内容)'}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}
