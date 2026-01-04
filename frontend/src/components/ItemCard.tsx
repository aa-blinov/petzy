import React from 'react';
import { Card, Button } from 'antd-mobile';

interface ItemCardProps {
  children: React.ReactNode;
  onEdit: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
  style?: React.CSSProperties;
  backgroundColor?: string;
  editText?: string;
  deleteText?: string;
  editTextColor?: string;
  editBorderColor?: string;
  deleteTextColor?: string;
  deleteBorderColor?: string;
}

export function ItemCard({
  children,
  onEdit,
  onDelete,
  style,
  backgroundColor = 'var(--adm-color-background)',
  editText = 'Редактировать',
  deleteText = 'Удалить',
  editTextColor = 'var(--adm-color-text)',
  editBorderColor = 'var(--adm-color-border)',
  deleteTextColor = '#FF453A',
  deleteBorderColor = 'rgba(255, 69, 58, 0.3)',
}: ItemCardProps) {
  return (
    <Card
      style={{
        backgroundColor,
        borderRadius: '12px',
        border: 'none',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        ...style,
      }}
    >
      <div style={{ padding: '16px' }}>
        {children}
        
        <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
          <Button
            size="small"
            fill="outline"
            onClick={(e) => {
              e.stopPropagation();
              onEdit(e);
            }}
            style={{
              flex: 1,
              '--text-color': editTextColor,
              '--border-color': editBorderColor,
            } as React.CSSProperties}
          >
            {editText}
          </Button>
          <Button
            size="small"
            fill="outline"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(e);
            }}
            style={{
              flex: 1,
              '--text-color': deleteTextColor,
              '--border-color': deleteBorderColor,
            } as React.CSSProperties}
          >
            {deleteText}
          </Button>
        </div>
      </div>
    </Card>
  );
}

