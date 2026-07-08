import { Box, Typography, Button } from '@mui/material';
import InboxIcon from '@mui/icons-material/Inbox';

export default function EmptyState({ message = '暂无数据', actionLabel, onAction }: {
  message?: string; actionLabel?: string; onAction?: () => void;
}) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8 }}>
      <InboxIcon sx={{ fontSize: 64, color: '#444', mb: 2 }} />
      <Typography variant="body1" sx={{ color: '#a0a0b0', mb: 2 }}>{message}</Typography>
      {actionLabel && onAction && (
        <Button variant="outlined" onClick={onAction}>{actionLabel}</Button>
      )}
    </Box>
  );
}
