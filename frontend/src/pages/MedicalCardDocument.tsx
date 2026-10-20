import { weightRangeByYear } from '../utils/weightRanges';
import { useState, type ReactNode } from 'react';
import { Popup } from 'antd-mobile';
import { AlertTriangle, CheckCircle2, Clock, Copy, Minus, Plus, ShieldAlert } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { DraggableSheetBody } from '../components/DraggableSheetBody';
import { PetImage } from '../components/PetImage';
import { PARASITE_TARGET_LABELS, medicalRecordsService, type MedicalKind, type MedicalRecord } from '../services/medicalRecords.service';
import { VISIT_CHECKS, VISIT_CHECK_LABELS, type MedicalCard as Card, type MedicalCardCourse, type MedicalCardVaccination, type MedicalClinic, type VisitPrep } from '../services/medicalCard.service';
import { DOCUMENT_CATEGORY_LABELS, type DocumentCategory } from '../services/documents.service';
import { listWords, readinessChecks } from '../utils/medicalReadiness';
import { formatDate, hasLife, weightDelta } from '../utils/medicalCardFormat';
import { pluralRu } from '../utils/relativeTime';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { showUndo } from '../utils/undo';
import './MedicalCard.css';

/**
 * The medical card as one document.
 *
 * The same tree of blocks for the person who keeps the card and for the vet
 * who opens the link: the order a vet asks in, one screen, no modes. The
 * owner's own doors (the «+» of a block, «Изменить») are the only difference
 * between the two copies.
 *
 * The screen answers three questions, in this order: who this pet is, what
 * asks to be done now, and how far the card is from being complete. Only
 * then does it become the record itself.
 */

/** How many records of a kind the document shows before it offers the rest. */
const SHOWN_RECORDS = 4;
/** How many finished courses the document shows. */
const SHOWN_PAST_COURSES = 2;

const STATUS: Record<MedicalCardVaccination['status'], { label: string; Icon: typeof CheckCircle2 }> = {
  valid: { label: 'Действует', Icon: CheckCircle2 },
  soon: { label: 'Скоро истекает', Icon: Clock },
  expired: { label: 'Истекла', Icon: AlertTriangle },
  none: { label: 'Срок не указан', Icon: Minus },
};

const RECORD_STATUS: Record<'overdue' | 'soon' | 'ok', { label: string; Icon: typeof CheckCircle2; tone: MedicalCardVaccination['status'] }> = {
  overdue: { label: 'Просрочено', Icon: AlertTriangle, tone: 'expired' },
  soon: { label: 'Скоро', Icon: Clock, tone: 'soon' },
  ok: { label: 'В срок', Icon: CheckCircle2, tone: 'valid' },
};

/** «1 день», «2 дня», «5 дней». */
function daysWord(n: number): string {
  const last = n % 10;
  const tens = n % 100;
  if (tens >= 11 && tens <= 14) return 'дней';
  if (last === 1) return 'день';
  if (last >= 2 && last <= 4) return 'дня';
  return 'дней';
}

/** After a comma or a colon a line goes on in lowercase: «1 таб, ежедневно в 08:00». An acronym («DEA»), a name
    in capitals, keeps its first letter. */
function lowerFirst(text: string): string {
  if (text.length > 1 && text[0] !== text[0].toLowerCase() && text[1] === text[1].toLowerCase()) return text[0].toLowerCase() + text.slice(1);
  return text;
}

/** The pill of a repeating record: how late, or how soon, in days, not just «просрочено». */
function recordStatusText(status: 'overdue' | 'soon' | 'ok', daysLeft: number | null): string {
  if (status === 'ok' || daysLeft === null) return RECORD_STATUS[status].label;
  const n = Math.abs(daysLeft);
  if (status === 'overdue') return `Просрочено на ${n} ${daysWord(n)}`;
  if (n === 0) return 'Сегодня';
  if (n === 1) return 'Завтра';
  return `Через ${n} ${daysWord(n)}`;
}

/** The pill of a certificate kept as a document. */
function certStatusText(v: MedicalCardVaccination): string {
  if (v.status === 'expired' && v.days_left !== null) {
    const n = Math.abs(v.days_left);
    return `Истекла ${n} ${daysWord(n)} назад`;
  }
  return STATUS[v.status].label;
}

/** Overdue first, then soon, then the rest; a record replaced by a newer one last. The order inside a rank stays as it came. */
function urgencyRank(r: MedicalRecord): number {
  if (r.superseded) return 3;
  if (r.status === 'overdue') return 0;
  if (r.status === 'soon') return 1;
  return 2;
}

/** A few numbers as a line: the trend of the weight, nothing to read off it.
    The line is stretched to the width; the dot at the latest value is its own
    element, so it stays round. */
export function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const y = (v: number) => 36 - ((v - min) / span) * 32;
  const coords = points.map((v, i) => `${(i / (points.length - 1)) * 100},${y(v)}`);
  return (
    <div className="medcard__spark" aria-hidden>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" width="100%" height="100%">
        <polyline points={coords.join(' ')} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <span className="medcard__spark-dot" style={{ top: `${(y(points[points.length - 1]) / 40) * 100}%` }} />
    </div>
  );
}

/** A line of a row and how much it weighs: `key` is what is acted on, `fact` is read for its label,
    `body` is context, `meta` is the rest. One scale for every row of the card. */
type Tier = 'key' | 'fact' | 'body' | 'meta';
interface RowLine {
  text: string;
  tier: Tier;
  label?: string;
}

const lineClass = (tier: Tier) => `medcard__row-sub medcard__row-sub--${tier}`;

function RowLines({ lines }: { lines: RowLine[] }) {
  return (
    <>
      {lines.map((line) => (
        <span key={`${line.label ?? ''}${line.text}`} className={lineClass(line.tier)} style={{ display: 'block' }}>
          {line.label && <b className="medcard__row-label">{line.label}: </b>}
          {line.text}
        </span>
      ))}
    </>
  );
}

/** What a record says, in tiers: the same lines in the whole card and in the reading mode (which only reads them bigger). */
function recordLines(record: MedicalRecord): RowLine[] {
  const repeating = record.kind === 'vaccination' || record.kind === 'parasite';
  const lines: (RowLine | null)[] = [
    {
      text: [repeating ? `Сделано ${formatDate(record.date)}` : formatDate(record.date), record.target ? PARASITE_TARGET_LABELS[record.target].toLowerCase() : null, record.batch ? `серия ${record.batch}` : null]
        .filter(Boolean)
        .join(', '),
      tier: 'body',
    },
    record.next_due && repeating && !record.superseded ? { label: 'Следующая', text: formatDate(record.next_due), tier: 'key' } : null,
    record.complaint ? { label: 'Жалоба', text: record.complaint, tier: 'fact' } : null,
    record.diagnosis ? { label: 'Диагноз', text: record.diagnosis, tier: 'fact' } : null,
    record.recommendations ? { label: 'Рекомендации', text: record.recommendations, tier: 'fact' } : null,
    { text: [record.clinic, record.vet ? `врач ${record.vet}` : null].filter(Boolean).join(', '), tier: 'meta' },
    record.note ? { label: 'Заметка', text: record.note, tier: 'meta' } : null,
    // What it is against: the same line of the card for any brand of it, so a change of brand reads as a repeat.
    record.kind === 'vaccination' && record.protects_label ? { label: 'Защита', text: record.protects_label, tier: 'meta' } : null,
    record.documents.length > 0 ? { label: 'Прикреплено', text: record.documents.map((d) => d.title).join(', '), tier: 'meta' } : null,
    record.superseded ? { text: 'Есть более новая запись', tier: 'meta' } : null,
  ];
  return lines.filter((l): l is RowLine => !!l && !!l.text);
}

/** The pill of a repeating record: a word and an icon, and how many days. */
function RecordPill({ record }: { record: MedicalRecord }) {
  if (record.status === 'none') {
    // A vaccination or a treatment with no repeat date is not watched: say so, so that nobody counts on a reminder.
    if (record.superseded || (record.kind !== 'vaccination' && record.kind !== 'parasite')) return null;
    return (
      <span className="medcard__status medcard__status--none">
        <Minus size={13} strokeWidth={2.4} aria-hidden />
        Без напоминания
      </span>
    );
  }
  const status = RECORD_STATUS[record.status];
  return (
    <span className={`medcard__status medcard__status--${status.tone}`}>
      <status.Icon size={13} strokeWidth={2.4} aria-hidden />
      {recordStatusText(record.status, record.days_left)}
    </span>
  );
}

/** What a screen reader says for the row: the title and what the eye takes from the pill, not only «открыть запись». */
function recordAriaLabel(record: MedicalRecord): string {
  const parts = [record.title];
  if (record.status !== 'none') parts.push(recordStatusText(record.status, record.days_left));
  else if (!record.superseded && (record.kind === 'vaccination' || record.kind === 'parasite')) parts.push('без напоминания');
  if (record.next_due && !record.superseded && (record.kind === 'vaccination' || record.kind === 'parasite')) parts.push(`следующая ${formatDate(record.next_due)}`);
  else parts.push(formatDate(record.date));
  parts.push('открыть запись');
  return parts.join(', ');
}

/** One record of the card: what, when, and (for a vaccination or a treatment) when it is due again. */
function RecordRow({ record, onOpen, onRepeat, onStop }: { record: MedicalRecord; onOpen: () => void; onRepeat?: () => void; onStop?: () => void }) {
  const repeating = record.kind === 'vaccination' || record.kind === 'parasite';
  return (
    <li className={`medcard__row medcard__row--stack${record.superseded ? ' medcard__row--history' : ''}`}>
      <button type="button" className="medcard__row-button" onClick={onOpen} aria-label={recordAriaLabel(record)}>
        <span className="medcard__row-top">
          <span className="medcard__row-main">
            <span className="medcard__row-title" style={{ display: 'block' }}>{record.title}</span>
            <RowLines lines={recordLines(record)} />
            <RecordPill record={record} />
          </span>
        </span>
      </button>
      {/* Only where a repeat is asked for: a vaccination in its term has nothing to repeat yet (the «+» does it in two taps). */}
      {repeating && onRepeat && !record.superseded && (record.status === 'overdue' || record.status === 'soon') && (
        <button type="button" className="medcard__row-action" onClick={onRepeat}>
          {record.kind === 'parasite' ? 'Записать повторную обработку' : 'Записать повторную прививку'}
        </button>
      )}
      {onStop && record.status === 'overdue' && !record.superseded && (
        // Not done any more (the vaccine was dropped, the pet is too old): the record stays in the history, and the card and
        // the reminders stop counting it as overdue.
        <button type="button" className="medcard__row-action medcard__row-action--quiet" onClick={onStop}>
          Больше не делаем
        </button>
      )}
    </li>
  );
}

/** One course: what, how much and when, what for, who prescribed it, how it went. */
export function CourseRow({ course }: { course: MedicalCardCourse }) {
  const lines: (RowLine | null)[] = [
    { text: [course.dose_text, course.schedule_text ? lowerFirst(course.schedule_text) : null].filter(Boolean).join(', '), tier: 'key' },
    course.purpose ? { label: 'От чего', text: course.purpose, tier: 'fact' } : null,
    course.prescribed_by ? { label: 'Назначил', text: course.prescribed_by, tier: 'body' } : null,
    course.comment ? { text: course.comment, tier: 'body' } : null,
    coursePeriod(course) ? { text: coursePeriod(course)!, tier: 'meta' } : null,
    course.given || course.skipped ? { text: `Дано доз: ${course.given}${course.skipped ? `, пропущено ${course.skipped}` : ''}`, tier: 'meta' } : null,
  ];
  return (
    <li className="medcard__row">
      <div className="medcard__row-main">
        <div className="medcard__row-title">{course.name}{course.strength ? `, ${course.strength}` : ''}</div>
        <RowLines lines={lines.filter((l): l is RowLine => !!l && !!l.text)} />
      </div>
      {course.status === 'planned' && <span className="medcard__status medcard__status--none">Ещё не началась</span>}
    </li>
  );
}

/** «С 12.05.2026 по 26.05.2026», «С 12.05.2026», «Начнётся 05.10.2026». */
function coursePeriod(c: MedicalCardCourse): string | null {
  if (c.status === 'planned' && c.started_on) return `Начнётся ${formatDate(c.started_on)}`;
  if (c.started_on && c.ended_on) return `С ${formatDate(c.started_on)} по ${formatDate(c.ended_on)}`;
  if (c.started_on) return `С ${formatDate(c.started_on)}`;
  if (c.ended_on) return `Закончен ${formatDate(c.ended_on)}`;
  return null;
}

/** A clinic: its name, the doctors seen there with what they do, and the phone as a button that calls. */
export function ClinicRow({ clinic }: { clinic: MedicalClinic }) {
  const doctors = clinic.doctors.map((d) => (d.specialty ? `${d.name}, ${lowerFirst(d.specialty)}` : d.name));
  return (
    <li className="medcard__row medcard__row--stack">
      <div className="medcard__row-main">
        <div className="medcard__row-title">{clinic.name || 'Клиника'}</div>
        {doctors.map((line) => (
          <div key={line} className="medcard__row-sub">
            {doctors.length === 1 ? 'Врач: ' : ''}
            {line}
          </div>
        ))}
      </div>
      {clinic.phone && (clinic.phone.replace(/\D/g, '').length >= 5 ? (
        <a className="medcard__call touch-target" href={`tel:${clinic.phone.replace(/[^\d+]/g, '')}`}>
          Позвонить {clinic.phone}
        </a>
      ) : (
        // Not a number to dial («регистратура», a note): said as it was written, not a button that calls nobody.
        <div className="medcard__row-sub">Телефон: {clinic.phone}</div>
      ))}
    </li>
  );
}

/** What is kept about the way of life: the food, the home, and when it matters the reproductive state. */
export function LifeRows({ profile }: { profile: Card['profile'] }) {
  const rows = [
    ['Питание', profile.diet],
    ['Условия жизни', profile.living],
    ['Репродуктивный статус', profile.reproduction],
  ].filter((row): row is [string, string] => !!row[1]);
  return (
    <>
      {rows.map(([label, value]) => (
        <li key={label} className="medcard__row medcard__row--stack">
          <div className="medcard__row-title">{label}</div>
          <div className="medcard__row-sub">{value}</div>
        </li>
      ))}
    </>
  );
}

/** What the household wants to tell the vet this time: the complaint, and what is not as usual. */
function PrepRows({ prep }: { prep: VisitPrep }) {
  const changed = VISIT_CHECKS.filter((k) => prep.checks[k] === 'changed').map((k) => VISIT_CHECK_LABELS[k].toLowerCase());
  const normal = VISIT_CHECKS.filter((k) => prep.checks[k] === 'normal').map((k) => VISIT_CHECK_LABELS[k].toLowerCase());
  return (
    <li className="medcard__row medcard__row--stack">
      {prep.complaint && <div className="medcard__row-title">{prep.complaint}</div>}
      {changed.length > 0 && (
        <div className="medcard__row-sub medcard__row-sub--changed">Изменилось: {changed.join(', ')}</div>
      )}
      {normal.length > 0 && <div className="medcard__row-sub medcard__row-sub--meta">Как обычно: {normal.join(', ')}</div>}
    </li>
  );
}

/**
 * The passport: who this card is about. The weight comes with it and with the
 * day it was taken: it is what the doses are counted from, and an old one is
 * seen as old.
 */
function Passport({ pet, weight, chip, bloodType, photoUrl, canCopy }: { pet: Card['pet']; weight: Card['weight']; chip: string | null; bloodType: string | null; photoUrl?: string | null; canCopy: boolean }) {
  const facts = [pet.species, pet.breed, pet.age_text, pet.gender, pet.neutered_text].filter(Boolean).join(', ');
  const delta = weight ? weightDelta(weight.series) : null;
  const copyChip = async () => {
    try {
      await navigator.clipboard.writeText(chip ?? '');
      showToast.success('Номер чипа скопирован');
    } catch {
      showToast.failure('Не удалось скопировать, выделите номер вручную');
    }
  };
  return (
    <div className="medcard__passport">
      <div className="medcard__avatar">
        {photoUrl ? (
          <PetImage src={photoUrl} alt="" size={56} className="medcard__avatar-img" />
        ) : (
          <span aria-hidden>{pet.name.slice(0, 1).toUpperCase()}</span>
        )}
      </div>
      <div className="medcard__passport-body">
        <div className="medcard__pet-name">{pet.name}</div>
        {facts && <div className="medcard__pet-facts">{facts}</div>}
        <div className="medcard__pet-line">
          {weight ? (
            <>
              <span className="medcard__weight-chip">{weight.latest.value.toLocaleString('ru-RU')} кг</span>
              <span className="medcard__pet-dim">{formatDate(weight.latest.date)}</span>
            </>
          ) : (
            <span className="medcard__pet-dim">Вес не указан</span>
          )}
        </div>
        {weight && delta && <div className="medcard__pet-dim">{delta}</div>}
        {(chip || bloodType) && (
          <div className="medcard__pet-line">
            {chip &&
              (canCopy ? (
                <button type="button" className="medcard__copy touch-target" onClick={copyChip} aria-label={`Скопировать номер чипа ${chip}`}>
                  Чип: {chip}
                  <Copy size={14} strokeWidth={2.2} aria-hidden />
                </button>
              ) : (
                <span className="medcard__pet-dim">Чип: {chip}</span>
              ))}
            {bloodType && <span className="medcard__pet-dim">Группа крови: {bloodType}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

/** What is overdue, the most overdue first: repeating records, and certificates in the documents that have expired. */
interface OverdueItem {
  id: string;
  title: string;
  text: string;
  kind: 'vaccination' | 'parasite';
  /** The record to record again, none for a certificate kept as a document. */
  recordId: string | null;
  /** The expired certificate this is about, when there is no record. */
  certId?: string;
  days: number;
}

function overdueItems(card: Card, hidden: ReadonlySet<string>): OverdueItem[] {
  const items: OverdueItem[] = [];
  // From every record (the server's own list), not only the latest ten of a kind that the card shows.
  const overdue = card.overdue_records ?? (['vaccination', 'parasite'] as const).flatMap((kind) => card.records[kind]);
  for (const r of overdue) {
    if ((r.kind === 'vaccination' || r.kind === 'parasite') && r.status === 'overdue' && !r.superseded && !hidden.has(r._id)) {
      items.push({ id: r._id, title: r.title, text: recordStatusText('overdue', r.days_left).toLowerCase(), kind: r.kind, recordId: r._id, days: r.days_left ?? 0 });
    }
  }
  for (const v of card.vaccinations) {
    if (v.status === 'expired') items.push({ id: v.id, title: v.title, text: certStatusText(v).toLowerCase(), kind: 'vaccination', recordId: null, certId: v.id, days: v.days_left ?? 0 });
  }
  return items.sort((a, b) => a.days - b.days);
}

/**
 * The one thing that asks to be done now: what is overdue, and the door that
 * puts it right. Nothing else on the card is louder than this.
 */
function AttentionZone({ items, canAct, shared, petId }: { items: OverdueItem[]; canAct: boolean; shared: boolean; petId: string }) {
  if (items.length === 0) return null;
  return (
    <section className="medcard__attention" aria-labelledby="medcard-attention" role="status">
      <h2 id="medcard-attention" className="medcard__zone-title">
        Требует внимания
      </h2>
      <ul className="medcard__attention-list">
        {items.map((item) => {
          const action = item.recordId
            ? item.kind === 'parasite'
              ? 'Записать повторную обработку'
              : 'Записать повторную прививку'
            : 'Оформить как запись';
          const to = item.recordId
            ? `/pets/${petId}/medical-records/new?kind=${item.kind}&from=${item.recordId}`
            : `/pets/${petId}/medical-records/new?kind=vaccination&doc=${item.certId}`;
          return (
            <li key={item.id} className="medcard__attention-item">
              <AlertTriangle size={20} strokeWidth={2.2} aria-hidden className="medcard__attention-icon" />
              <div className="medcard__attention-body">
                <div className="medcard__attention-title">{item.title}</div>
                <div className="medcard__attention-text">{item.text}</div>
                {canAct ? (
                  <a className="medcard__attention-link" href={to}>
                    {action}
                  </a>
                ) : (
                  // Nobody pressed this on the vet's copy, so it says who can put it right.
                  <p className="medcard__attention-note">
                    {shared ? 'Обновить сможет тот, у кого есть доступ к питомцу, в приложении' : 'Обновить сможет владелец питомца'}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * How far the card is from being complete. Both states are one line: when
 * everything is there the card says so, and when something is missing it says
 * what and offers the first step.
 */
function ReadinessBlock({ card, petId, canAct, navigate }: { card: Card; petId: string; canAct: boolean; navigate: (to: string) => void }) {
  const checks = readinessChecks(card, petId);
  const missing = checks.filter((c) => !c.done);
  const done = checks.length - missing.length;
  if (missing.length === 0) {
    return (
      <section className="medcard__ready medcard__ready--done" aria-labelledby="medcard-ready">
        <div className="medcard__ready-top">
          <span className="medcard__ready-label" id="medcard-ready">
            <CheckCircle2 size={18} strokeWidth={2.2} aria-hidden />
            Готовность к приёму
          </span>
          <span className="medcard__ready-count">{done} из {checks.length}</span>
        </div>
        <div className="medcard__ready-dots" aria-hidden>
          {checks.map((c) => (
            <span key={c.key} className="medcard__ready-dot medcard__ready-dot--on" />
          ))}
        </div>
        <p className="medcard__ready-hint">Главное для врача заполнено</p>
      </section>
    );
  }
  const next = missing[0];
  return (
    <section className="medcard__ready" aria-labelledby="medcard-ready">
      <div className="medcard__ready-top">
        <span className="medcard__ready-label" id="medcard-ready">
          Готовность к приёму
        </span>
        <span className="medcard__ready-count">{done} из {checks.length}</span>
      </div>
      <div className="medcard__ready-dots" aria-hidden>
        {checks.map((c) => (
          <span key={c.key} className={`medcard__ready-dot${c.done ? ' medcard__ready-dot--on' : ''}`} />
        ))}
      </div>
      <p className="medcard__ready-hint">Не хватает: {listWords(missing.map((c) => c.label.toLowerCase()))}</p>
      {canAct && (
        <button type="button" className="medcard__link medcard__ready-action touch-target" onClick={() => navigate(next.to)}>
          {next.action}
        </button>
      )}
    </section>
  );
}

/** A block of the document: its name, the round «+» of the owner, and the quiet doors under the block. */
function DocSection({
  id,
  title,
  links,
  add,
  children,
}: {
  id: string;
  title: string;
  /** The quiet doors of the owner under the block («Изменить», «Все лекарства»). */
  links?: { label: string; onClick: () => void }[];
  /** The round «+» of the owner: what this block is about is added here. */
  add?: { label: string; onClick: () => void };
  children: ReactNode;
}) {
  return (
    <section className="medcard__section" id={id} aria-labelledby={`${id}-title`}>
      <div className="medcard__section-head">
        <h2 id={`${id}-title`} className="medcard__section-title">
          {title}
        </h2>
        {add && (
          <button type="button" className="medcard__add touch-target" onClick={add.onClick} aria-label={`Добавить: ${add.label}`}>
            <Plus size={18} strokeWidth={2.4} aria-hidden />
          </button>
        )}
      </div>
      <div className="card-soft medcard__block">
        {children}
        {links && links.length > 0 && (
          <div className="medcard__block-links">
            {links.map((link) => (
              <button key={link.label} type="button" className="medcard__link medcard__link--quiet touch-target" onClick={link.onClick}>
                {link.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/** The sheet that asks which of the two kinds to write about. */
function KindSheet({ visible, onClose, title, options, onPick }: { visible: boolean; onClose: () => void; title: string; options: { label: string; to: string }[]; onPick: (to: string) => void }) {
  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} label={title}>
        <ul className="medcard__list">
          {options.map((option) => (
            <li key={option.label} className="medcard__row" style={{ padding: 0 }}>
              <button type="button" className="medcard__row-button medcard__todo-row" onClick={() => onPick(option.to)}>
                <span className="medcard__row-title">{option.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </DraggableSheetBody>
    </Popup>
  );
}

/**
 * The rest of the records of a kind, in a sheet over the document: the whole
 * history of one block without leaving the card.
 */
function RecordsSheet({
  visible,
  onClose,
  petId,
  kinds,
  hidden,
  onOpen,
  onRepeat,
}: {
  visible: boolean;
  onClose: () => void;
  petId: string;
  kinds: MedicalKind[];
  hidden: ReadonlySet<string>;
  onOpen: (id: string) => void;
  /** The repeat of this record, as a new record of the same kind. */
  onRepeat: (record: MedicalRecord) => void;
}) {
  const queryClient = useQueryClient();
  const all = useQuery({
    queryKey: ['medical-records', petId, kinds.join('-')],
    queryFn: async () => {
      const lists = await Promise.all(kinds.map((kind) => medicalRecordsService.list(petId, kind)));
      return lists.flat();
    },
    enabled: visible,
    staleTime: 0,
  });
  const stopTracking = async (r: MedicalRecord) => {
    const input = {
      date: r.date, title: r.title, next_due: null as string | null, clinic: r.clinic, vet: r.vet, note: r.note, batch: r.batch, target: r.target,
      complaint: r.complaint, diagnosis: r.diagnosis, recommendations: r.recommendations, document_ids: r.documents.map((d) => d.id),
    };
    const refresh = () => queryClient.invalidateQueries({ queryKey: ['medical-card', petId] });
    try {
      await medicalRecordsService.update(r._id, input);
      await refresh();
      showUndo({
        message: `«${r.title}»: больше не напоминаем и не считаем просроченной`,
        onUndo: async () => {
          await medicalRecordsService.update(r._id, { ...input, next_due: r.next_due });
          await refresh();
        },
      });
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
    }
  };
  const records = (all.data ?? []).filter((r) => !hidden.has(r._id)).sort((a, b) => urgencyRank(a) - urgencyRank(b));
  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} label="Все записи">
        {all.isError ? (
          <p className="medcard__empty">Не удалось загрузить записи</p>
        ) : all.isFetching && !all.data ? (
          <p className="medcard__empty">Загружаем записи</p>
        ) : records.length === 0 ? (
          <p className="medcard__empty">Записей пока нет</p>
        ) : (
          <ul className="medcard__list medcard__list--sheet">
            {records.map((r) => (
              <RecordRow
                key={r._id}
                record={r}
                onOpen={() => onOpen(r._id)}
                onRepeat={r.kind === 'vaccination' || r.kind === 'parasite' ? () => onRepeat(r) : undefined}
                onStop={r.kind === 'vaccination' || r.kind === 'parasite' ? () => void stopTracking(r) : undefined}
              />
            ))}
          </ul>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}

/** The measurements of the weight, in a sheet: the chart is the trend, this is the numbers. */
function WeightSheet({ visible, onClose, series }: { visible: boolean; onClose: () => void; series: { date: string; value: number }[] }) {
  const before = series.slice(0, -1).slice(-6).reverse();
  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} label="Замеры веса">
        {before.length === 0 ? (
          <p className="medcard__empty">Замеров пока нет</p>
        ) : (
          <ul className="medcard__list medcard__list--sheet">
            {before.map((p) => (
              <li key={`${p.date}-${p.value}`} className="medcard__row">
                <div className="medcard__row-main">
                  <div className="medcard__row-title">{p.value.toLocaleString('ru-RU')} кг</div>
                  <div className="medcard__row-sub">{formatDate(p.date)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}

/** What the document is made of, in the order a vet asks in. */
export interface CardDocumentProps {
  card: Card;
  /** The pet this card is about: where the doors of the owner go. */
  petId: string;
  hidden: ReadonlySet<string>;
  /** The owner may change what is on the card: the «+» of a block and «Изменить». */
  owner: boolean;
  /** Where a door goes. The guest's copy has nowhere to go, and says so instead. */
  navigate: (to: string) => void;
  /** The file: the owner's copy has it in the bar at the foot, the guest's under the date. */
  onPdf?: () => void;
  saving?: boolean;
  /** Under the passport: what the page is and how fresh it is. */
  afterPassport?: ReactNode;
  /** The pet's photo, when the app knows it. */
  photoUrl?: string | null;
  /** The copy opened by a link: it says who may put right what is overdue. */
  shared?: boolean;
}

export function CardDocument({ card, petId, hidden, owner, navigate, onPdf, saving, afterPassport, photoUrl, shared }: CardDocumentProps) {
  const [kindSheet, setKindSheet] = useState<null | { title: string; options: { label: string; to: string }[] }>(null);
  const [recordsSheet, setRecordsSheet] = useState<null | MedicalKind[]>(null);
  const [weightSheet, setWeightSheet] = useState(false);
  const items = overdueItems(card, hidden);
  // A co-owner may fill the card in too; only a guest by a link may not.
  const canAct = owner || card.can_edit;

  const prevention = [...card.records.vaccination, ...card.records.parasite].filter((r) => !hidden.has(r._id)).sort((a, b) => urgencyRank(a) - urgencyRank(b));
  const visits = [...card.records.visit, ...card.records.procedure].filter((r) => !hidden.has(r._id)).sort((a, b) => urgencyRank(a) - urgencyRank(b));
  const weight = card.weight;
  const openRecord = (id: string) => {
    setRecordsSheet(null);
    navigate(`/pets/${petId}/medical-records/${id}`);
  };
  const repeatRecord = (record: MedicalRecord) => {
    setRecordsSheet(null);
    navigate(`/pets/${petId}/medical-records/new?kind=${record.kind}&from=${record._id}`);
  };
  const addTo = (to: string) => {
    setKindSheet(null);
    navigate(to);
  };

  const preventionShown = prevention.slice(0, SHOWN_RECORDS);
  const visitsShown = visits.slice(0, SHOWN_RECORDS);
  const profileTo = `/pets/${petId}/medical-profile`;

  return (
    <div className="medcard medcard--document">
      <Passport pet={card.pet} weight={weight} chip={card.profile.chip_number ?? null} bloodType={card.profile.blood_type ?? null} photoUrl={photoUrl} canCopy={owner} />

      {afterPassport}

      {/* The file, on the copy opened by a link: it is what the visitor takes away with them. */}
      {onPdf && !owner && (
        <div className="medcard__topactions">
          <button type="button" className="medcard__pdf-button" onClick={onPdf} disabled={saving}>
            Скачать PDF
          </button>
          <p className="medcard__hint">Скачать заранее: на приёме может не быть связи</p>
        </div>
      )}

      <AttentionZone items={items} canAct={canAct} shared={!!shared} petId={petId} />

      <ReadinessBlock card={card} petId={petId} canAct={canAct} navigate={navigate} />

      {/* What could harm comes first: allergies and conditions are read before anything else on the card. */}
      <DocSection
        id="medcard-risks"
        title="Здоровье и аллергии"
        links={owner ? [{ label: 'Изменить', onClick: () => navigate(`${profileTo}?section=allergies`) }] : undefined}
      >
        <RisksBlock card={card} />
      </DocSection>

      <DocSection
        id="medcard-prep"
        title="К приёму"
        links={owner ? [{ label: card.visit_prep ? 'Изменить' : 'Добавить', onClick: () => navigate(`/pets/${petId}/visit-prep`) }] : undefined}
      >
        {card.visit_prep ? (
          <ul className="medcard__list">
            <PrepRows prep={card.visit_prep} />
          </ul>
        ) : (
          <p className="medcard__empty">Что беспокоит и что изменилось: врач увидит это первой строкой</p>
        )}
      </DocSection>

      <DocSection
        id="medcard-meds"
        title="Лекарства"
        links={owner ? [{ label: 'Все лекарства', onClick: () => navigate('/medications') }] : undefined}
        add={owner ? { label: 'лекарство', onClick: () => navigate('/medications/new') } : undefined}
      >
        {card.medications.length === 0 ? (
          <p className="medcard__empty">Сейчас ничего не принимает</p>
        ) : (
          <ul className="medcard__list">
            {card.medications.map((c) => (
              <CourseRow key={c.id} course={c} />
            ))}
          </ul>
        )}
        {card.past_courses.length > 0 && (
          <div className="medcard__past">
            <div className="medcard__past-title">Прошлые курсы</div>
            <ul className="medcard__list">
              {card.past_courses.slice(0, SHOWN_PAST_COURSES).map((c) => (
                <CourseRow key={c.id} course={c} />
              ))}
            </ul>
            {card.past_courses_total > SHOWN_PAST_COURSES && (
              <p className="medcard__more">
                Показаны последние {SHOWN_PAST_COURSES} из {card.past_courses_total}
              </p>
            )}
          </div>
        )}
      </DocSection>

      <DocSection
        id="medcard-weight"
        title="Вес"
        add={owner ? { label: 'замер веса', onClick: () => navigate('/form/weight') } : undefined}
        links={weight && weight.series.length > 1 ? [{ label: 'Все замеры', onClick: () => setWeightSheet(true) }] : undefined}
      >
        {!weight ? (
          <p className="medcard__empty">Вес не записан. Врач считает по нему дозы</p>
        ) : (
          <div className="medcard__weight">
            <div className="medcard__weight-now">
              <span className="medcard__weight-value">{weight.latest.value.toLocaleString('ru-RU')} кг</span>
              <span className="medcard__weight-date">{formatDate(weight.latest.date)}</span>
            </div>
            {weightDelta(weight.series) && <div className="medcard__row-sub medcard__row-sub--meta">{weightDelta(weight.series)}</div>}
            {weight.series.length > 1 && <Sparkline points={weight.series.map((w) => w.value)} />}
            {weight.series.length > 1 && (
              <div className="medcard__row-sub medcard__row-sub--meta">
                {weight.series.length} {pluralRu(weight.series.length, 'замер', 'замера', 'замеров')} с {formatDate(weight.series[0].date)}
                {(() => {
                  const values = weight.series.map((w) => w.value);
                  const min = Math.min(...values), max = Math.max(...values);
                  return min === max ? '' : `, диапазон от ${min.toLocaleString('ru-RU')} до ${max.toLocaleString('ru-RU')} кг`;
                })()}
              </div>
            )}
            {weight.series.length > 1 && new Set(weight.series.map((w) => w.date.slice(0, 4))).size > 1 && (
              <div className="medcard__row-sub medcard__row-sub--meta">По годам: {weightRangeByYear(weight.series)}</div>
            )}
          </div>
        )}
      </DocSection>

      <DocSection
        id="medcard-prevention"
        title="Прививки и обработки"
        links={prevention.length > SHOWN_RECORDS ? [{ label: `Показать все ${prevention.length}`, onClick: () => setRecordsSheet(['vaccination', 'parasite']) }] : undefined}
        add={
          owner
            ? {
                label: 'прививку или обработку',
                onClick: () =>
                  setKindSheet({
                    title: 'Что добавить',
                    options: [
                      { label: 'Прививка', to: `/pets/${petId}/medical-records/new?kind=vaccination` },
                      { label: 'Обработка от паразитов', to: `/pets/${petId}/medical-records/new?kind=parasite` },
                    ],
                  }),
              }
            : undefined
        }
      >
        {preventionShown.length === 0 && card.vaccinations.length === 0 ? (
          <p className="medcard__empty">Прививок и обработок пока нет</p>
        ) : (
          <ul className="medcard__list">
            {preventionShown.map((r) => (
              <RecordRow key={r._id} record={r} onOpen={() => navigate(`/pets/${petId}/medical-records/${r._id}`)} />
            ))}
            {card.vaccinations.map((v) => {
              const { Icon } = STATUS[v.status];
              return (
                <li key={v.id} className="medcard__row medcard__row--stack">
                  <span className="medcard__row-top">
                    <span className="medcard__row-main">
                      <span className="medcard__row-title" style={{ display: 'block' }}>{v.title}</span>
                      <span className="medcard__row-sub" style={{ display: 'block' }}>
                        Сертификат в документах{v.expires_at ? `, до ${formatDate(v.expires_at)}` : ''}
                      </span>
                    </span>
                    <span className={`medcard__status medcard__status--${v.status}`}>
                      <Icon size={13} strokeWidth={2.4} aria-hidden />
                      {certStatusText(v)}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </DocSection>

      <DocSection
        id="medcard-visits"
        title="Визиты и операции"
        links={visits.length > SHOWN_RECORDS ? [{ label: `Показать все ${visits.length}`, onClick: () => setRecordsSheet(['visit', 'procedure']) }] : undefined}
        add={
          owner
            ? {
                label: 'визит или операцию',
                onClick: () =>
                  setKindSheet({
                    title: 'Что добавить',
                    options: [
                      { label: 'Визит', to: `/pets/${petId}/medical-records/new?kind=visit` },
                      { label: 'Операция', to: `/pets/${petId}/medical-records/new?kind=procedure` },
                    ],
                  }),
              }
            : undefined
        }
      >
        {visitsShown.length === 0 ? (
          <p className="medcard__empty">Визитов и операций пока нет</p>
        ) : (
          <ul className="medcard__list">
            {visitsShown.map((r) => (
              <RecordRow key={r._id} record={r} onOpen={() => navigate(`/pets/${petId}/medical-records/${r._id}`)} />
            ))}
          </ul>
        )}
      </DocSection>

      <DocSection
        id="medcard-documents"
        title="Анализы и заключения"
        links={owner ? [{ label: 'Все документы', onClick: () => navigate('/documents') }] : undefined}
        add={owner ? { label: 'документ', onClick: () => navigate('/documents/new') } : undefined}
      >
        {card.documents.length === 0 ? (
          <p className="medcard__empty">Анализов и заключений пока нет</p>
        ) : (
          <ul className="medcard__list">
            {card.documents.map((d) => (
              <li key={d.id} className="medcard__row">
                <div className="medcard__row-main">
                  <div className="medcard__row-title">{d.title}</div>
                  <div className="medcard__row-sub">
                    {DOCUMENT_CATEGORY_LABELS[d.category as DocumentCategory] ?? 'Документ'}, {formatDate(d.added)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </DocSection>

      <DocSection
        id="medcard-clinic"
        title="Клиника и врачи"
        links={owner && card.profile.clinics.length > 0 ? [{ label: 'Изменить', onClick: () => navigate(`${profileTo}?section=clinic`) }] : undefined}
        add={owner ? { label: 'клинику и врачей', onClick: () => navigate(`${profileTo}?section=clinic`) } : undefined}
      >
        {card.profile.clinics.length === 0 ? (
          <p className="medcard__empty">Клиника не указана. Её телефон врач увидит в карте</p>
        ) : (
          <ul className="medcard__list">
            {card.profile.clinics.map((c, i) => (
              <ClinicRow key={`${c.name ?? ''}-${i}`} clinic={c} />
            ))}
          </ul>
        )}
      </DocSection>

      <DocSection
        id="medcard-life"
        title="Питание и условия"
        links={owner && hasLife(card.profile) ? [{ label: 'Изменить', onClick: () => navigate(`${profileTo}?section=life`) }] : undefined}
        add={owner ? { label: 'питание и условия', onClick: () => navigate(`${profileTo}?section=life`) } : undefined}
      >
        {hasLife(card.profile) ? (
          <ul className="medcard__list">
            <LifeRows profile={card.profile} />
          </ul>
        ) : (
          <p className="medcard__empty">Чем кормят и где живёт: помогает врачу, когда причина не ясна</p>
        )}
      </DocSection>

      {kindSheet && <KindSheet visible title={kindSheet.title} options={kindSheet.options} onClose={() => setKindSheet(null)} onPick={addTo} />}
      {recordsSheet && (
        <RecordsSheet
          visible
          petId={petId}
          kinds={recordsSheet}
          hidden={hidden}
          onClose={() => setRecordsSheet(null)}
          onOpen={openRecord}
          onRepeat={repeatRecord}
        />
      )}
      {weightSheet && weight && <WeightSheet visible series={weight.series} onClose={() => setWeightSheet(false)} />}
    </div>
  );
}

/** Allergies, chronic conditions and the notes: what a vet asks first. */
function RisksBlock({ card }: { card: Card }) {
  const { profile, pet } = card;
  const hasAllergies = profile.allergies.length > 0;
  const filled = hasAllergies || profile.allergies_none_known || profile.conditions.length > 0 || !!pet.health_notes;
  const calm = !hasAllergies && profile.allergies_none_known && profile.conditions.length === 0 && !pet.health_notes;
  return (
    <div className={`medcard__risks${filled ? '' : ' medcard__risks--empty'}${calm ? ' medcard__risks--calm' : ''}`}>
      <ShieldAlert className="medcard__risks-icon" size={22} strokeWidth={2} aria-hidden />
      <div className="medcard__risks-body">
        {!filled && <p className="medcard__risks-text">Не указаны. Аллергии и особенности здоровья врач спросит первыми</p>}
        {!hasAllergies && !profile.allergies_none_known && pet.health_notes && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Аллергии</span>
            <span className="medcard__risks-text">Не заполнены, смотрите заметки ниже</span>
          </div>
        )}
        {(hasAllergies || profile.allergies_none_known) && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Аллергии</span>
            {hasAllergies ? (
              <ul className="medcard__plain-list">
                {profile.allergies.map((a) => (
                  <li key={`${a.substance}-${a.reaction ?? ''}`}>
                    {a.substance}
                    {a.reaction ? `: ${lowerFirst(a.reaction)}` : ''}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="medcard__risks-text">Не выявлено</span>
            )}
          </div>
        )}
        {profile.conditions.length > 0 && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Хронические состояния</span>
            <ul className="medcard__plain-list">
              {profile.conditions.map((c) => (
                <li key={`${c.name}-${c.since_year ?? ''}`}>
                  {c.name}
                  {c.since_year ? ` (с ${c.since_year} года)` : ''}
                  {c.note ? `: ${c.note}` : ''}
                </li>
              ))}
            </ul>
          </div>
        )}
        {pet.health_notes && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Заметки</span>
            <p className="medcard__risks-text">{pet.health_notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}
