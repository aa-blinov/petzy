import { Picker } from 'antd-mobile';
import { dayColumn, type IntakeWhen } from '../utils/intakeWhen';
import { showToast } from '../utils/toast';

const pad = (n: number) => String(n).padStart(2, '0');

const HOURS = Array.from({ length: 24 }, (_, h) => ({ label: pad(h), value: pad(h) }));
const MINUTES = Array.from({ length: 60 }, (_, m) => ({ label: pad(m), value: pad(m) }));

interface IntakeTimePickerProps {
  visible: boolean;
  value: IntakeWhen;
  title?: string;
  onClose: () => void;
  onConfirm: (when: IntakeWhen) => void;
}

/** «Когда дали»: a day of the last week, an hour and a minute. A dose
 *  can't be given in the future, so a time past now is refused. */
export function IntakeTimePicker({ visible, value, title = 'Когда дали', onClose, onConfirm }: IntakeTimePickerProps) {
  const [hh, mm] = value.time.split(':');
  return (
    <Picker
      title={title}
      columns={[dayColumn(value.date), HOURS, MINUTES]}
      visible={visible}
      value={[value.date, hh, mm]}
      onClose={onClose}
      onConfirm={(val) => {
        const [date, hour, minute] = val as string[];
        const when = { date, time: `${hour}:${minute}` };
        const [y, mo, d] = date.split('-').map(Number);
        if (new Date(y, mo - 1, d, Number(hour), Number(minute)) > new Date()) {
          showToast.failure('Время не может быть в будущем');
          return;
        }
        onConfirm(when);
      }}
      cancelText="Отмена"
      confirmText="Готово"
    />
  );
}
