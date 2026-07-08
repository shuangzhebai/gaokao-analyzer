import { Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button } from '@mui/material';

export default function ConfirmDialog({ open, title, message, onConfirm, onCancel }: {
  open: boolean; title: string; message: string; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <Dialog open={open} onClose={onCancel} slotProps={{ paper: { sx: { bgcolor: '#1a1a2e' } } }}>
      <DialogTitle sx={{ color: '#e0e0e0' }}>{title}</DialogTitle>
      <DialogContent><DialogContentText sx={{ color: '#a0a0b0' }}>{message}</DialogContentText></DialogContent>
      <DialogActions>
        <Button onClick={onCancel} sx={{ color: '#a0a0b0' }}>取消</Button>
        <Button onClick={onConfirm} color="error" variant="contained">确认</Button>
      </DialogActions>
    </Dialog>
  );
}
