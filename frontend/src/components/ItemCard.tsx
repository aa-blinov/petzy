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
  backgroundColor = 'var(--app-card-background)',
  editText = 'Редактировать',
  deleteText = 'Удалить',
  editTextColor = 'var(--app-text-primary)',
  editBorderColor = 'var(--app-border-color)',
  deleteTextColor = 'var(--app-danger-color)',
  deleteBorderColor = 'var(--app-black-10)',
}: ItemCardProps) {
  return (
    <Card
      style={{
        backgroundColor,
        borderRadius: '12px',
        border: 'none',
        boxShadow: 'var(--app-shadow)',
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

