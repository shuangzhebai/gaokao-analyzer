import { Box, Typography, Chip, Collapse, List, ListItemButton, ListItemText } from '@mui/material';
import { useState } from 'react';
import type { QuestionType } from '../../types/question';

interface QuestionTreeProps {
  types: QuestionType[];
  selectedTypeId?: number;
  onSelect: (typeId: number | undefined) => void;
}

function TypeNode({ node, selectedTypeId, onSelect, depth = 0 }: {
  node: QuestionType;
  selectedTypeId?: number;
  onSelect: (typeId: number | undefined) => void;
  depth: number;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = node.id === selectedTypeId;

  return (
    <>
      <ListItemButton
        sx={{ pl: 2 + depth * 2, py: 0.5 }}
        selected={isSelected}
        onClick={() => {
          if (hasChildren) setOpen(!open);
          onSelect(node.id);
        }}
      >
        <ListItemText
          primary={node.name_cn}
          primaryTypographyProps={{
            fontSize: depth === 0 ? 14 : 13,
            fontWeight: depth === 0 ? 600 : 400,
            color: isSelected ? '#00d4ff' : '#e0e0e0',
          }}
        />
        {hasChildren && (
          <Chip label={`${node.children!.length}`} size="small"
            sx={{ height: 20, fontSize: 11, color: '#999', bgcolor: '#2a2a2a' }} />
        )}
      </ListItemButton>
      {hasChildren && (
        <Collapse in={open}>
          <List disablePadding>
            {node.children!.map((child) => (
              <TypeNode key={child.id} node={child} selectedTypeId={selectedTypeId}
                onSelect={onSelect} depth={depth + 1} />
            ))}
          </List>
        </Collapse>
      )}
    </>
  );
}

export default function QuestionTree({ types, selectedTypeId, onSelect }: QuestionTreeProps) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ color: '#999', px: 2, py: 1, fontSize: 12, textTransform: 'uppercase' }}>
        题型分类
      </Typography>
      <ListItemButton
        sx={{ pl: 2, py: 0.5 }}
        selected={selectedTypeId === undefined}
        onClick={() => onSelect(undefined)}
      >
        <ListItemText primary="全部题目" primaryTypographyProps={{ fontSize: 13, color: selectedTypeId === undefined ? '#00d4ff' : '#e0e0e0' }} />
      </ListItemButton>
      <List disablePadding>
        {types.map((t) => (
          <TypeNode key={t.id} node={t} selectedTypeId={selectedTypeId} onSelect={onSelect} depth={0} />
        ))}
      </List>
    </Box>
  );
}
