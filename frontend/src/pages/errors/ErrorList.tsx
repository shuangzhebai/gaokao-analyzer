import { Box, Typography, Chip, IconButton } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import DeleteIcon from '@mui/icons-material/Delete';
import type { ErrorRecord } from '../../types/error';

interface ErrorListProps {
  records: ErrorRecord[];
  total: number;
  page: number;
  onPageChange: (page: number) => void;
  onSelect: (record: ErrorRecord) => void;
  onDelete: (id: number) => void;
  onMarkMastered: (id: number) => void;
}

const REASON_LABELS: Record<string, { label: string; color: string }> = {
  concept: { label: '概念不清', color: '#f44336' },
  careless: { label: '粗心大意', color: '#ff9800' },
  calculation: { label: '计算错误', color: '#2196f3' },
  strategy: { label: '策略失误', color: '#9c27b0' },
  other: { label: '其他', color: '#999' },
};

export default function ErrorList({ records, total, page, onPageChange, onSelect, onDelete, onMarkMastered }: ErrorListProps) {
  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 60, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    {
      field: 'error_reason', headerName: '原因', width: 100, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => {
        const info = REASON_LABELS[params.value as string] || REASON_LABELS.other;
        return <Chip label={info.label} size="small" sx={{ color: info.color, borderColor: info.color, fontSize: 11 }} variant="outlined" />;
      },
    },
    { field: 'attempt_count', headerName: '错次', width: 60, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    {
      field: 'is_mastered', headerName: '状态', width: 80, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      renderCell: (params: GridRenderCellParams) => (
        <Chip label={params.value ? '已掌握' : '未掌握'} size="small"
          sx={{ color: params.value ? '#4caf50' : '#f44336', borderColor: params.value ? '#4caf50' : '#f44336', fontSize: 11 }} variant="outlined" />
      ),
    },
    { field: 'question_score', headerName: '分值', width: 60, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    { field: 'created_at', headerName: '录入时间', width: 160, headerClassName: 'header-theme', cellClassName: 'cell-theme' },
    {
      field: 'actions', headerName: '操作', width: 120, headerClassName: 'header-theme', cellClassName: 'cell-theme',
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Chip label="详情" size="small" onClick={() => onSelect(params.row)}
            sx={{ color: '#00d4ff', borderColor: '#00d4ff', fontSize: 11, cursor: 'pointer' }} variant="outlined" />
          {!params.row.is_mastered && (
            <Chip label="掌握" size="small" onClick={() => onMarkMastered(params.row.id)}
              sx={{ color: '#4caf50', borderColor: '#4caf50', fontSize: 11, cursor: 'pointer' }} variant="outlined" />
          )}
          <IconButton size="small" onClick={() => onDelete(params.row.id)} sx={{ color: '#f44336' }}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ];

  return (
    <Box sx={{ height: 400 }}>
      <DataGrid
        rows={records}
        columns={columns}
        rowCount={total}
        paginationMode="server"
        pageSizeOptions={[20]}
        paginationModel={{ page: page - 1, pageSize: 20 }}
        onPaginationModelChange={(m) => onPageChange(m.page + 1)}
        disableRowSelectionOnClick
        getRowId={(row) => row.id}
        sx={{
          border: 'none', bgcolor: 'transparent',
          '& .header-theme': { bgcolor: '#12121e', color: '#999', fontWeight: 600, fontSize: 12 },
          '& .cell-theme': { color: '#e0e0e0', fontSize: 13 },
          '& .MuiDataGrid-cell': { borderColor: '#2a2a2a' },
          '& .MuiTablePagination-root': { color: '#999' },
        }}
      />
    </Box>
  );
}
