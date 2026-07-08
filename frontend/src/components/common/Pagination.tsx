import { Box, Typography, IconButton } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

export default function Pagination({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange: (p: number) => void }) {
  if (totalPages <= 1) return null;
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1, mt: 2 }}>
      <IconButton size="small" disabled={page <= 1} onClick={() => onPageChange(page - 1)} sx={{ color: '#a0a0b0' }}>
        <ChevronLeftIcon />
      </IconButton>
      <Typography variant="body2" sx={{ color: '#a0a0b0' }}>
        {page} / {totalPages}
      </Typography>
      <IconButton size="small" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} sx={{ color: '#a0a0b0' }}>
        <ChevronRightIcon />
      </IconButton>
    </Box>
  );
}
