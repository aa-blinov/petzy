import { useState, type ReactNode } from 'react';
import { Button, Dialog } from 'antd-mobile';
import { hapticFeedback } from '../utils/haptic';

interface FormDangerButtonProps {
  /** Button and confirm action text: "Удалить", "Деактивировать". */
  label: string;
  confirmTitle: string;
  confirmContent: ReactNode;
  /** Does the work and leaves the form (toast, navigation). Throwing
      keeps the form open; the caller has shown why. */
  onConfirm: () => Promise<void>;
  disabled?: boolean;
}

/**
 * The destructive action at the foot of an edit form. Cards open their
 * edit form on tap, so this is where delete lives for anyone who never
 * swipes; it asks the same question the swipe does.
 */
export function FormDangerButton({ label, confirmTitle, confirmContent, onConfirm, disabled }: FormDangerButtonProps) {
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [pending, setPending] = useState(false);

  const confirm = async () => {
    setPending(true);
    try {
      await onConfirm();
      setConfirmVisible(false);
    } catch {
      setConfirmVisible(false);
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      <Button
        block
        size="large"
        fill="none"
        color="danger"
        disabled={disabled || pending}
        onClick={() => {
          hapticFeedback('medium');
          setConfirmVisible(true);
        }}
        style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
      >
        {label}
      </Button>
      <Dialog
        visible={confirmVisible}
        title={confirmTitle}
        content={confirmContent}
        onClose={() => setConfirmVisible(false)}
        getContainer={() => document.body}
        actions={[
          { key: 'confirm', text: label, danger: true, disabled: pending, onClick: confirm },
          { key: 'cancel', text: 'Отмена', onClick: () => setConfirmVisible(false) },
        ]}
      />
    </>
  );
}
