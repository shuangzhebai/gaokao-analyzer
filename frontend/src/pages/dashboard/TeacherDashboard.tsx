import { Box, Typography, Grid, Paper, Button, Chip, Card, CardContent } from '@mui/material';

export default function TeacherDashboard() {
  return (
    <Box>
      <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>教师工作台</Typography>

      <Grid container spacing={2}>
        {/* 快速操作面板 */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2, height: '100%' }}>
            <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>快速操作</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Button variant="contained" component="a" href="/composition"
                sx={{ bgcolor: '#00d4ff', '&:hover': { bgcolor: '#00b8e6' }, py: 1.2 }}>
                🎯 智能组卷
              </Button>
              <Button variant="outlined" component="a" href="/quality"
                sx={{ color: '#4caf50', borderColor: '#4caf50', '&:hover': { borderColor: '#388e3c' }, py: 1.2 }}>
                📊 质量诊断
              </Button>
              <Button variant="outlined" component="a" href="/questions"
                sx={{ color: '#ff9800', borderColor: '#ff9800', '&:hover': { borderColor: '#ed6c02' }, py: 1.2 }}>
                📝 题库管理
              </Button>
              <Button variant="outlined"
                sx={{ color: '#999', borderColor: '#333', '&:hover': { borderColor: '#555' }, py: 1.2 }}>
                📄 批量导出
              </Button>
            </Box>
          </Paper>
        </Grid>

        {/* 班级错题概览 */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 2, minHeight: 300 }}>
            <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>班级错题概览</Typography>
            <Typography sx={{ color: '#666', textAlign: 'center', py: 6 }}>班级功能待对接学生数据后完善</Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {['数学', '语文', '英语', '物理', '化学'].map((s) => (
                <Card key={s} sx={{ bgcolor: '#12121e', border: '1px solid #2a2a2a', flex: 1, minWidth: 120 }}>
                  <CardContent sx={{ textAlign: 'center', py: 2 }}>
                    <Typography sx={{ color: '#ccc', fontSize: 14, mb: 0.5 }}>{s}</Typography>
                    <Typography sx={{ color: '#f44336', fontSize: 20, fontWeight: 700 }}>-</Typography>
                    <Typography sx={{ color: '#666', fontSize: 11 }}>人均错题</Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
