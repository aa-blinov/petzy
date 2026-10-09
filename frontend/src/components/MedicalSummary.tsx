import { createElement } from 'react';
import { Building2, Bug, FileText, Pill, Scale, ShieldAlert, Stethoscope, Utensils, type LucideIcon } from 'lucide-react';

import type { MedicalCard as Card } from '../services/medicalCard.service';
import type { MedicalRecord } from '../services/medicalRecords.service';
import './MedicalSummary.css';

type Tone = 'bad' | 'warn' | 'ok' | 'none';

interface Tile {
  key: string;
  label: string;
  icon: LucideIcon;
  value: string;
  note?: { text: string; tone: Tone };
  /** A second door on the tile, beside it (not inside it): goes straight to the form or the edit, one tap. */
  quick?: { label: string; to: (petId: string) => string };
}

const formatDate = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('ru-RU');

/** «2 аллергии»: the noun after a number, in the Russian forms. */
function plural(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  const form = mod10 === 1 && mod100 !== 11 ? forms[0] : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? forms[1] : forms[2];
  return `${n} ${form}`;
}

/** The prevention of a pet: the records of the two kinds that come due, and the certificates kept only as documents. */
function prevention(card: Card, hidden: ReadonlySet<string>): { overdue: number; soon: number; total: number } {
  const live = (list: MedicalRecord[]) => list.filter((r) => !r.superseded && !hidden.has(r._id));
  const records = [...live(card.records.vaccination), ...live(card.records.parasite)];
  const overdueIds = new Set((card.overdue_records ?? records.filter((r) => r.status === 'overdue')).filter((r) => !r.superseded && !hidden.has(r._id)).map((r) => r._id));
  const expiredCerts = card.vaccinations.filter((v) => v.status === 'expired').length;
  return {
    overdue: overdueIds.size + expiredCerts,
    soon: records.filter((r) => r.status === 'soon').length + card.vaccinations.filter((v) => v.status === 'soon').length,
    total: card.record_counts.vaccination + card.record_counts.parasite + card.vaccinations.length,
  };
}

function tilesOf(card: Card, hidden: ReadonlySet<string>): Tile[] {
  const { profile, pet } = card;
  const allergies = profile.allergies.length;
  const conditions = profile.conditions.length;
  const risksFilled = allergies > 0 || profile.allergies_none_known || conditions > 0 || !!pet.health_notes;
  const risks: string[] = [];
  if (allergies > 0) risks.push(plural(allergies, ['аллергия', 'аллергии', 'аллергий']));
  else if (profile.allergies_none_known) risks.push('Аллергий нет');
  if (conditions > 0) risks.push(plural(conditions, ['состояние', 'состояния', 'состояний']));

  const prev = prevention(card, hidden);
  const visits = card.record_counts.visit;
  const procedures = card.record_counts.procedure;
  const lastVisit = card.records.visit[0];
  const clinic = profile.clinics.find((c) => c.name)?.name;
  const life = profile.diet || profile.living || profile.reproduction;
  const latestDoc = card.documents[0];

  return [
    {
      key: 'risks',
      label: 'Здоровье и аллергии',
      icon: ShieldAlert,
      value: risks.length ? risks.join(', ') : 'Не заполнено',
      note: risksFilled ? undefined : { text: 'Врач спросит первым', tone: 'warn' },
      quick: { label: 'Изменить', to: (petId) => `/pets/${petId}/medical-profile?section=allergies` },
    },
    {
      key: 'meds',
      label: 'Лекарства',
      icon: Pill,
      value: card.medications.length ? `${card.medications.length} сейчас` : 'Ничего не принимает',
    },
    {
      key: 'prevention',
      label: 'Профилактика',
      icon: Bug,
      value: prev.total === 0 ? 'Нет записей' : prev.overdue > 0 ? `${prev.overdue} просрочено` : prev.soon > 0 ? `${prev.soon} скоро` : 'Всё в срок',
      note: prev.overdue > 0 ? { text: 'Нужно повторить', tone: 'bad' } : prev.soon > 0 ? { text: 'Скоро срок', tone: 'warn' } : prev.total > 0 ? { text: 'В порядке', tone: 'ok' } : undefined,
    },
    {
      key: 'weight',
      label: 'Вес',
      icon: Scale,
      value: card.weight ? `${card.weight.latest.value.toLocaleString('ru-RU')} кг` : 'Не записан',
      note: card.weight ? { text: formatDate(card.weight.latest.date), tone: 'none' } : undefined,
      quick: { label: 'Записать', to: () => '/form/weight' },
    },
    {
      key: 'visits',
      label: 'Визиты и операции',
      icon: Stethoscope,
      value: visits + procedures === 0 ? 'Нет записей' : lastVisit ? `Визит ${formatDate(lastVisit.date)}` : plural(procedures, ['операция', 'операции', 'операций']),
      note: visits + procedures > 0 ? { text: `Всего ${visits + procedures}`, tone: 'none' } : undefined,
    },
    {
      key: 'documents',
      label: 'Документы',
      icon: FileText,
      value: latestDoc ? latestDoc.title : 'Нет документов',
      note: latestDoc ? { text: formatDate(latestDoc.added), tone: 'none' } : undefined,
    },
    {
      key: 'clinic',
      label: 'Клиника и врачи',
      icon: Building2,
      value: clinic ?? 'Не указана',
      note: profile.clinics.length > 1 ? { text: `Ещё ${profile.clinics.length - 1}`, tone: 'none' } : undefined,
    },
    {
      key: 'life',
      label: 'Питание и условия',
      icon: Utensils,
      value: life ?? 'Не указано',
    },
  ];
}

/**
 * The card at a glance: one tile for each part a vet asks about, in the order they ask, each saying what is there and
 * whether it needs attention. A tile opens that part on its own screen (MedicalCardSection), where it is read and put right.
 * It replaces what used to be one page of every section in a row.
 */
export function MedicalSummary({ card, petId, hidden, navigate }: { card: Card; petId: string; hidden: ReadonlySet<string>; navigate: (to: string) => void }) {
  const tiles = tilesOf(card, hidden);
  return (
    <section className="medsum" aria-label="Разделы медкарты">
      <ul className="medsum__grid">
        {tiles.map((tile) => (
          <li key={tile.key} className={tile.quick ? 'medsum__item medsum__item--quick' : undefined}>
            <button
              type="button"
              className="medsum__tile tap-feedback"
              aria-label={`${tile.label}: ${tile.value}${tile.note ? `, ${tile.note.text}` : ''}`}
              onClick={() => navigate(`/pets/${petId}/medical-card/${tile.key}`)}
            >
              <span className="medsum__label">
                {createElement(tile.icon, { size: 16, strokeWidth: 2, 'aria-hidden': true })}
                {tile.label}
              </span>
              <span className="medsum__value">{tile.value}</span>
              {tile.note && <span className={`medsum__note medsum__note--${tile.note.tone}`}>{tile.note.text}</span>}
            </button>
            {tile.quick && (
              <button type="button" className="medsum__quick" onClick={() => navigate(tile.quick!.to(petId))}>
                {tile.quick.label}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
