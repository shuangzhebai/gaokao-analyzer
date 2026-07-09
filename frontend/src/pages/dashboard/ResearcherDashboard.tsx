import { Box, Typography, Grid, Paper, Button, Chip } from '@mui/material';

export default function ResearcherDashboard() {
  return (
    <Box>
      <Typography variant="h5" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 2 }}>研究员工作台</Typography>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 3, minHeight: 180 }}>
            <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 1 }}>多卷质量对比</Typography>
            <Typography sx={{ color: '#666', fontSize: 13, mb: 2 }}>选择多份试卷进行横向质量对比分析</Typography>
            <Button variant="outlined" component="a" href="/quality"
              sx={{ color: '#00d4ff', borderColor: '#00d4ff', '&:hover': { borderColor: '#00b8e6' } }}>
              进入质量诊断
            </Button>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 3, minHeight: 180 }}>
            <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 1 }}>命题趋势分析</Typography>
            <Typography sx={{ color: '#666', fontSize: 13, mb: 2 }}>分析历年高考真题的知识点分布和命题趋势</Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip label="数学" clickable sx={{ color: '#4caf50', borderColor: '#4caf50' }} variant="outlined" />
              <Chip label="语文" clickable sx={{ color: '#ff9800', borderColor: '#ff9800' }} variant="outlined" />
              <Chip label="英语" clickable sx={{ color: '#2196f3', borderColor: '#2196f3' }} variant="outlined" />
            </Box>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 3, minHeight: 180 }}>
            <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 1 }}>批量分析</Typography>
            <Typography sx={{ color: '#666', fontSize: 13, mb: 2 }}>上传多份试卷进行批量质量分析</Typography>
            <Button variant="outlined"
              sx={{ color: '#ff9800', borderColor: '#ff9800', '&:hover': { borderColor: '#ed6c02' } }}>
              上传并分析
            </Button>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ bgcolor: '#1a1a2e', borderRadius: 2, border: '1px solid #2a2a2a', p: 3, minHeight: 180 }}>
            <Typography variant="subtitle1" sx={{ color: '#e0e0e0', fontWeight: 600, mb: 1 }}>IRT 参数预计算</Typography>
            <Typography sx={{ color: '#666', fontSize: 13, mb: 2 }}>批量预计算全部题目的 IRT 参数，提升分析速度</Typography>
            <Button variant="outlined"
              sx={{ color: '#9c27b0', borderColor: '#9c27b0', '&:hover': { borderColor: '#7b1fa2' } }}>
              开始预计算
            </Button>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
