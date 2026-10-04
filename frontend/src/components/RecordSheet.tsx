import { createElement, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Popup } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import { Bug, FileText, HeartPulse, Pill, Scale, Scissors, Stethoscope, Syringe, TriangleAlert, type LucideIcon } from 'lucide-react';

import { DraggableSheetBody } from './DraggableSheetBody';
import './RecordSheet.css';

interface Choice {
  label: string;
  icon: LucideIcon;
  to: string;
}

/**
 * «Что записать?»: one door to every kind of entry of a pet's card, from wherever the card is open. The person says what
 * happened, and the form that fits it opens, short, with what can be guessed already in it. Grouped by where the entry lands:
 * the card's own records, the doctor's data, and the diary and lists elsewhere in the app.
 */
export function RecordSheet({ visible, petId, petName, onClose, onChoose }: { visible: boolean; petId: string; petName?: string; onClose: () => void; onChoose: (to: string) => void }) {
  const card = `/pets/${petId}/medical-records/new`;
  const profile = `/pets/${petId}/medical-profile`;
  const groups: { title: string; items: Choice[] }[] = [
    {
      title: 'В медкарту',
      items: [
        { label: 'Прививка', icon: Syringe, to: `${card}?kind=vaccination` },
        { label: 'Обработка от паразитов', icon: Bug, to: `${card}?kind=parasite` },
        { label: 'Визит к врачу', icon: Stethoscope, to: `${card}?kind=visit` },
        { label: 'Операция или процедура', icon: Scissors, to: `${card}?kind=procedure` },
      ],
    },
    {
      title: 'Данные для врача',
      items: [
        { label: 'Аллергия', icon: TriangleAlert, to: `${profile}?section=allergies` },
        { label: 'Хроническое состояние', icon: HeartPulse, to: `${profile}?section=conditions` },
      ],
    },
    {
      title: 'Рядом с картой',
      items: [
        { label: 'Лекарство', icon: Pill, to: '/medications/new' },
        { label: 'Вес', icon: Scale, to: '/form/weight' },
        { label: 'Анализ или документ', icon: FileText, to: '/documents/new' },
      ],
    },
  ];

  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="85vh" label="Что записать">
        <h2 className="recsheet__title">Что записать?</h2>
        {petName && <p className="recsheet__pet">{petName}</p>}
        {groups.map((group) => (
          <section key={group.title} className="recsheet__group" aria-label={group.title}>
            <h3 className="recsheet__group-title">{group.title}</h3>
            <div className="recsheet__grid">
              {group.items.map((item) => (
                <button key={item.label} type="button" className="recsheet__tile tap-feedback" onClick={() => onChoose(item.to)}>
                  <span className="recsheet__icon" aria-hidden>
                    {createElement(item.icon, { size: 20, strokeWidth: 2 })}
                  </span>
                  <span className="recsheet__label">{item.label}</span>
                </button>
              ))}
            </div>
          </section>
        ))}
      </DraggableSheetBody>
    </Popup>
  );
}

/** The round «+» of the medical card and the sheet it opens: the same on every screen of the card that edits. In a portal,
    as the feed's is, so that no page-level containing block moves it. */
export function RecordFab({ petId, petName }: { petId: string; petName?: string }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  return (
    <>
      {createPortal(
        <button type="button" className="app-fab" aria-label="Записать в медкарту" aria-haspopup="dialog" onClick={() => setOpen(true)}>
          <AddOutline fontSize={28} aria-hidden />
        </button>,
        document.body,
      )}
      <RecordSheet
        visible={open}
        petId={petId}
        petName={petName}
        onClose={() => setOpen(false)}
        onChoose={(to) => {
          setOpen(false);
          navigate(to);
        }}
      />
    </>
  );
}
