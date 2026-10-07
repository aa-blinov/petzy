import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Skeleton } from 'antd-mobile';
import { AlertTriangle, CheckCircle2, ChevronRight, Clock, Copy, Download, FileHeart, Link2, Minus, ShieldAlert } from 'lucide-react';
import { MedicalShareSheet } from '../components/MedicalShareSheet';
import { RecordFab } from '../components/RecordSheet';
import { MedicalSummary } from '../components/MedicalSummary';
import { MEDICAL_KIND_LABELS, PARASITE_TARGET_LABELS, medicalRecordsService, type MedicalKind, type MedicalRecord } from '../services/medicalRecords.service';
import { useHiddenRecords } from '../utils/deferredDelete';
import { medicalCardService, VISIT_CHECKS, VISIT_CHECK_LABELS, type MedicalCard as Card, type MedicalCardCourse, type MedicalCardVaccination, type MedicalClinic, type VisitPrep } from '../services/medicalCard.service';
import { listWords, missingReadiness, readinessChecks } from '../utils/medicalReadiness';
import { usePet } from '../hooks/usePet';
import { LoadError } from '../components/LoadError';
import { EmptyState } from '../components/EmptyState';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { showUndo } from '../utils/undo';
import { httpStatus } from '../services/api';
import { formatDate, hasLife, weightDelta } from '../utils/medicalCardFormat';
import './MedicalCard.css';

const EMPTY_TEXT: Record<MedicalKind, string> = {
  vaccination: 'Прививок пока нет. Добавьте прививку или сертификат из документов, и срок повтора появится здесь',
  parasite: 'Обработок пока нет. Запишите последнюю, и придёт напоминание, когда пора повторить',
  visit: 'Визитов пока нет. Запишите визит, диагноз и рекомендации врача',
  procedure: 'Операций и процедур пока нет',
};


const STATUS: Record<MedicalCardVaccination['status'], { label: string; Icon: typeof CheckCircle2 }> = {
  valid: { label: 'Действует', Icon: CheckCircle2 },
  soon: { label: 'Скоро истекает', Icon: Clock },
  expired: { label: 'Истекла', Icon: AlertTriangle },
  none: { label: 'Срок не указан', Icon: Minus },
};

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

/** «С 12.05.2026 по 26.05.2026», «С 12.05.2026», «Начнётся 05.10.2026». */
function coursePeriod(c: MedicalCardCourse): string | null {
  if (c.status === 'planned' && c.started_on) return `Начнётся ${formatDate(c.started_on)}`;
  if (c.started_on && c.ended_on) return `С ${formatDate(c.started_on)} по ${formatDate(c.ended_on)}`;
  if (c.started_on) return `С ${formatDate(c.started_on)}`;
  if (c.ended_on) return `Закончен ${formatDate(c.ended_on)}`;
  return null;
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

/** Allergies, chronic conditions and the notes: what a vet asks first, in the one block with a colour of its own. */
export function ImportantBlock({ card, onEdit, readOnly = false, title = 'Здоровье и аллергии' }: { card: Card; onEdit: () => void; readOnly?: boolean; /** Another name where the screen's h1 is already «Здоровье и аллергии». */ title?: string }) {
  const { profile, pet } = card;
  const hasAllergies = profile.allergies.length > 0;
  const filled = hasAllergies || profile.allergies_none_known || profile.conditions.length > 0 || !!pet.health_notes;
  const ids = [profile.blood_type ? `Группа крови: ${profile.blood_type}` : null, profile.chip_number ? `Чип: ${profile.chip_number}` : null].filter(Boolean);
  // «Не выявлено» is a safe statement: it does not wear the alarm tint.
  const calm = !hasAllergies && profile.allergies_none_known && profile.conditions.length === 0 && !pet.health_notes;
  const copyChip = async () => {
    try {
      await navigator.clipboard.writeText(profile.chip_number ?? '');
      showToast.success('Номер чипа скопирован');
    } catch {
      showToast.failure('Не удалось скопировать, выделите номер вручную');
    }
  };
  return (
    <div className={`medcard__important${filled ? '' : ' medcard__important--empty'}${calm ? ' medcard__important--calm' : ''}`} role="group" aria-labelledby="medcard-important">
      <ShieldAlert className="medcard__important-icon" size={22} strokeWidth={2} aria-hidden />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className="medcard__section-head" style={{ marginBottom: 4 }}>
          <h2 id="medcard-important" className="medcard__important-title" style={{ margin: 0 }}>{title}</h2>
          {!readOnly && (
            <button type="button" className="medcard__link touch-target" onClick={onEdit}>
              {filled ? 'Изменить' : 'Заполнить'}
            </button>
          )}
        </div>
        {!filled && <p className="medcard__important-text">Не указаны. Аллергии и особенности здоровья врач спросит первыми</p>}
        {!hasAllergies && !profile.allergies_none_known && pet.health_notes && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Аллергии</span>
            <span className="medcard__important-text">Не заполнены, смотрите заметки ниже</span>
          </div>
        )}
        {(hasAllergies || profile.allergies_none_known) && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Аллергии</span>
            {hasAllergies ? (
              <ul className="medcard__plain-list">
                {profile.allergies.map((a) => (
                  <li key={`${a.substance}-${a.reaction ?? ''}`}>{a.substance}{a.reaction ? `: ${lowerFirst(a.reaction)}` : ''}</li>
                ))}
              </ul>
            ) : (
              <span className="medcard__important-text">Не выявлено</span>
            )}
          </div>
        )}
        {profile.conditions.length > 0 && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Хронические состояния</span>
            <ul className="medcard__plain-list">
              {profile.conditions.map((c) => (
                <li key={`${c.name}-${c.since_year ?? ''}`}>
                  {c.name}{c.since_year ? ` (с ${c.since_year} года)` : ''}{c.note ? `: ${c.note}` : ''}
                </li>
              ))}
            </ul>
          </div>
        )}
        {pet.health_notes && (
          <div className="medcard__fact">
            <span className="medcard__fact-label">Заметки</span>
            <p className="medcard__important-text">{pet.health_notes}</p>
          </div>
        )}
        {readOnly ? (
          <>
            {profile.blood_type && <p className="medcard__important-text medcard__ids">Группа крови: {profile.blood_type}</p>}
            {profile.chip_number && (
              <button type="button" className="medcard__copy touch-target" onClick={copyChip} aria-label={`Скопировать номер чипа ${profile.chip_number}`}>
                Чип: {profile.chip_number}
                <Copy size={16} strokeWidth={2.2} aria-hidden />
              </button>
            )}
          </>
        ) : (
          ids.length > 0 && <p className="medcard__important-text medcard__ids">{ids.join(', ')}</p>
        )}
      </div>
    </div>
  );
}

/** After a comma or a colon a line goes on in lowercase: «1 таб, ежедневно в 08:00». An acronym («DEA»), a name
    in capitals, keeps its first letter. */
function lowerFirst(text: string): string {
  if (text.length > 1 && text[0] !== text[0].toLowerCase() && text[1] === text[1].toLowerCase()) return text[0].toLowerCase() + text.slice(1);
  return text;
}

/** «1 день», «2 дня», «5 дней». */
function daysWord(n: number): string {
  const last = n % 10;
  const tens = n % 100;
  if (tens >= 11 && tens <= 14) return 'дней';
  if (last === 1) return 'день';
  if (last >= 2 && last <= 4) return 'дня';
  return 'дней';
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

/** «+0,3 кг с 05.09.2026»: how the latest weight differs from the one before it. */

/** Overdue first, then soon, then the rest; a record replaced by a newer one last. The order inside a rank stays as it came. */
function urgencyRank(r: MedicalRecord): number {
  if (r.superseded) return 3;
  if (r.status === 'overdue') return 0;
  if (r.status === 'soon') return 1;
  return 2;
}

/** The pill of a certificate kept as a document. */
function certStatusText(v: MedicalCardVaccination): string {
  if (v.status === 'expired' && v.days_left !== null) {
    const n = Math.abs(v.days_left);
    return `Истекла ${n} ${daysWord(n)} назад`;
  }
  return STATUS[v.status].label;
}

const RECORD_STATUS: Record<'overdue' | 'soon' | 'ok', { label: string; Icon: typeof CheckCircle2; tone: MedicalCardVaccination['status'] }> = {
  overdue: { label: 'Просрочено', Icon: AlertTriangle, tone: 'expired' },
  soon: { label: 'Скоро', Icon: Clock, tone: 'soon' },
  ok: { label: 'В срок', Icon: CheckCircle2, tone: 'valid' },
};

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
  const navigate = useNavigate();
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
      {record.documents.map((d) => (
        // Attached files are one tap from the record, not only a name in a line of text.
        <button key={d.id} type="button" className="medcard__row-action medcard__row-action--quiet" onClick={() => navigate(`/documents?open=${d.id}`)}>
          Открыть документ: {d.title}
        </button>
      ))}
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

export function Section({ id, title, titleHidden = false, action, secondary, children }: { id: string; title: string; /** On a screen whose h1 already says it: the heading stays for screen readers and is not drawn twice. */ titleHidden?: boolean; action?: { label: string; onClick: () => void }; /** A second, quieter door beside the first («История» next to «Записать вес»). */ secondary?: { label: string; onClick: () => void }; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id}>
      <div className="medcard__section-head">
        <h2 id={id} className={titleHidden ? 'sr-only' : 'medcard__section-title'}>{title}</h2>
        {(action || secondary) && (
          <span className="medcard__section-actions">
            {secondary && (
              <button type="button" className="medcard__link medcard__link--quiet touch-target" onClick={secondary.onClick}>
                {secondary.label}
              </button>
            )}
            {action && (
              <button type="button" className="medcard__link touch-target" onClick={action.onClick}>
                {action.label}
              </button>
            )}
          </span>
        )}
      </div>
      <div className="card-soft" style={{ overflow: 'hidden' }}>{children}</div>
    </section>
  );
}

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

/** What is overdue, the most overdue first: repeating records, and certificates in the documents that have expired. */
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

/** The one line that matters most, under the mode switch in both modes: what is overdue and, where the card can be
    edited, the way to put it right. */
export function OverdueStrip({ card, petId, navigate, canAct, hidden }: { card: Card; petId: string; navigate: (to: string) => void; canAct: boolean; hidden: ReadonlySet<string> }) {
  const items = overdueItems(card, hidden);
  if (items.length === 0) return null;
  const [first, ...others] = items;
  const to = first.recordId
    ? `/pets/${petId}/medical-records/new?kind=${first.kind}&from=${first.recordId}`
    : first.certId
      ? `/pets/${petId}/medical-records/new?kind=vaccination&renew=${first.certId}`
      : `/pets/${petId}/medical-records/new?kind=vaccination`;
  const label = first.kind === 'parasite' ? 'Записать повторную обработку' : first.recordId ? 'Записать повторную прививку' : 'Записать прививку';
  return (
    <div className="medcard__alert" role="status">
      <AlertTriangle size={20} strokeWidth={2.2} aria-hidden className="medcard__alert-icon" />
      <div className="medcard__alert-body">
        <p className="medcard__alert-text">
          <b>{first.title}</b>: {first.text}
          {others.length > 0 ? `. И ещё ${others.length}` : ''}
        </p>
        {canAct ? (
          <Button block size="large" color="danger" fill="outline" onClick={() => navigate(to)}>
            {label}
          </Button>
        ) : (
          // A copy a vet reads: there is nothing to press here, so the strip says who can put it right.
          <p className="medcard__alert-text">Обновить сможет тот, у кого есть доступ к питомцу, в приложении</p>
        )}
      </div>
    </div>
  );
}

/** What a vet looks for first, and whether the card has it. Each gap is a row that opens the
    place to fill it; when nothing is missing the block says so in one line, so the owner knows
    the card is good enough to show. */
function ReadinessBlock({ card, petId, navigate }: { card: Card; petId: string; navigate: (to: string) => void }) {
  const checks = readinessChecks(card, petId);
  const missing = checks.filter((c) => !c.done);
  if (missing.length === 0) {
    return (
      <div className="medcard__ready-box">
        <p className="medcard__ready" role="status">
          <CheckCircle2 size={18} strokeWidth={2.2} aria-hidden />
          Главное для врача заполнено
        </p>
      </div>
    );
  }
  // The order is the order a vet asks in. One step is the next one; the others wait below it as a short list.
  const [next, ...rest] = missing;
  return (
    <section className="medcard__todos" aria-labelledby="medcard-readiness">
      <h2 id="medcard-readiness" className="medcard__todos-title">
        Заполнено {checks.length - missing.length} из {checks.length}
      </h2>
      <p className="medcard__todos-next">{next.label}</p>
      <p className="medcard__todos-hint">{next.hint}</p>
      <Button block color="primary" size="large" onClick={() => navigate(next.to)}>
        {next.action}
      </Button>
      {rest.length > 0 && (
        <ul className="medcard__todos-rest" aria-label="Потом">
          {rest.map((c) => (
            <li key={c.key}>
              <button type="button" className="medcard__todos-row tap-feedback" onClick={() => navigate(c.to)}>
                {c.label}
                <ChevronRight size={18} strokeWidth={2.2} aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** The records of one kind. The card brings the latest ten; «Показать все» asks for the rest.
    No door of its own: the round «+» on this screen already opens the very form a «Добавить» here would,
    and two ways to the same record on one screen is one too many. */
export function KindSection({ kind, card, petId, hidden, navigate }: { kind: MedicalKind; card: Card; petId: string; hidden: ReadonlySet<string>; navigate: (to: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();
  const total = card.record_counts[kind];
  // The repeat date taken off the record, and given back by «Отменить».
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
  const all = useQuery({
    queryKey: ['medical-records', petId, kind],
    queryFn: () => medicalRecordsService.list(petId, kind),
    enabled: expanded,
    staleTime: 0,
  });
  const source = expanded && all.data ? all.data : card.records[kind];
  const rows = source.filter((r) => !hidden.has(r._id)).sort((a, b) => urgencyRank(a) - urgencyRank(b));
  const legacy = kind === 'vaccination' ? card.vaccinations : [];
  const repeating = kind === 'vaccination' || kind === 'parasite';
  const more = total > source.length;
  // An empty kind says nothing here: the block of missing items, or the group of what can be added, already does.
  if (rows.length === 0 && legacy.length === 0 && !expanded) return null;
  return (
    <Section id={`medcard-${kind}`} title={MEDICAL_KIND_LABELS[kind].section}>
      {rows.length === 0 && legacy.length === 0 ? (
        <p className="medcard__empty">{EMPTY_TEXT[kind]}</p>
      ) : (
        <ul className="medcard__list">
          {rows.map((r) => (
            <RecordRow
              key={r._id}
              record={r}
              onOpen={() => navigate(`/pets/${petId}/medical-records/${r._id}`)}
              onRepeat={repeating ? () => navigate(`/pets/${petId}/medical-records/new?kind=${kind}&from=${r._id}`) : undefined}
              onStop={repeating ? () => void stopTracking(r) : undefined}
            />
          ))}
          {legacy.map((v) => {
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
                <button type="button" className="medcard__row-action touch-target" onClick={() => navigate(`/pets/${petId}/medical-records/new?kind=vaccination&doc=${v.id}`)}>
                  Оформить как запись
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {(more || (expanded && total > card.records[kind].length)) && (
        <div className="medcard__more">
          {more ? (
            <>
              {source.length === 1 ? `Показана последняя запись из ${total}` : `Показаны последние ${source.length} из ${total}`}{' '}
              <button type="button" className="medcard__link touch-target" style={{ padding: 0 }} disabled={all.isFetching} onClick={() => setExpanded(true)}>
                {all.isFetching ? 'Загружаем…' : 'Показать все'}
              </button>
            </>
          ) : (
            <button type="button" className="medcard__link touch-target" style={{ padding: 0 }} onClick={() => setExpanded(false)}>
              Свернуть до последних {card.records[kind].length}
            </button>
          )}
        </div>
      )}
    </Section>
  );
}

/** The two ways to hand the card over are on the card from the start; on an empty one there is nothing to hand, and the
    line under the heading says so instead of the block appearing out of nowhere later. */
const EMPTY_HANDOVER = 'Карта почти пуста. Заполните её, и здесь появятся PDF и ссылка для врача';
/** The file is worth having before the appointment, where the connection is often gone. */
const PDF_HINT = 'Скачайте заранее: на приёме может не быть связи';

type Mode = 'vet' | 'fill';
function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  return (
    <div className="medcard__modes" role="group" aria-label="Режим медкарты">
      {([['fill', 'Записи'], ['vet', 'Врачу']] as const).map(([value, label]) => (
        <button key={value} type="button" className="medcard__mode" aria-pressed={mode === value} onClick={() => onChange(value)}>
          {label}
        </button>
      ))}
    </div>
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
        <div className="medcard__row-sub medcard__row-sub--key" style={{ color: 'var(--app-danger-text)' }}>
          Изменилось: {changed.join(', ')}
        </div>
      )}
      {normal.length > 0 && <div className="medcard__row-sub medcard__row-sub--meta">Как обычно: {normal.join(', ')}</div>}
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

/** What a vet reads at the counter, in the order they ask: allergies, what is due, what is taken now and the
    weight, the clinic, the last visits. Nothing here edits; the history and the forms are in the other mode. */
/** Who this is about, in the first line a vet reads: a record read at the counter, or shown from a screenshot, names its patient.
    The weight comes with it and with the day it was taken: it is what the doses are counted from, and an old one is seen as old. */
function PatientLine({ pet, weight, named = true }: { pet: Card['pet']; weight: Card['weight']; named?: boolean }) {
  // Lowercase after the name: «Лабрадор, Мальчик» in the middle of a line reads as an artifact.
  const facts = [pet.species, pet.breed, pet.age_text, pet.gender, pet.neutered_text].filter(Boolean).join(', ').toLowerCase();
  const delta = weight ? weightDelta(weight.series) : null;
  return (
    <div className="medcard__patient">
      <p>
        {named && <strong>{pet.name}</strong>}
        {named && facts ? ', ' : ''}
        {facts}
      </p>
      <p>
        {weight ? `Вес ${weight.latest.value.toLocaleString('ru-RU')} кг на ${formatDate(weight.latest.date)}` : 'Вес не указан'}
        {delta ? `, ${delta[0].toLowerCase()}${delta.slice(1)}` : ''}
      </p>
    </div>
  );
}

export function VetView({ card, hidden, saving, canPdf, onPdf, onAll, onShare, afterPatient, named = true }: { card: Card; hidden: ReadonlySet<string>; saving: boolean; canPdf: boolean; onPdf: () => void; /** The way back to the records: only where there are some (not on the page a vet opens by a link). */ onAll?: () => void; /** A link to the card for a vet: only the owner's side offers it. */ onShare?: () => void; /** Under the patient line: what the page of a link says about its date and its end, and what is overdue. */ afterPatient?: ReactNode; /** Without the pet's name in the first line, where the page already carries it as its title. */ named?: boolean }) {
  const due = (['vaccination', 'parasite'] as const)
    .flatMap((kind) => card.records[kind].filter((r) => !r.superseded && !hidden.has(r._id)))
    .sort((a, b) => urgencyRank(a) - urgencyRank(b));
  const visits = card.records.visit.filter((r) => !hidden.has(r._id)).slice(0, 3);
  // An operation does not wait for the full card: a vet asks about the neutering first.
  const procedures = card.records.procedure.filter((r) => !hidden.has(r._id)).slice(0, 3);
  // A card opened by a link has no way back into the app, so the file is offered there and then, right under the date.
  const byLink = !onShare;
  const missing = missingReadiness(card);
  const handover = canPdf ? (
    <div className="medcard__topactions">
      <div className="medcard__topbuttons">
        <Button block fill="outline" color="primary" size="large" loading={saving} disabled={saving} onClick={onPdf}>
          <Download size={18} strokeWidth={2.2} aria-hidden style={{ verticalAlign: 'middle', marginRight: 'var(--spacing-sm)' }} />
          Скачать PDF
        </Button>
        {onShare && (
          <Button block fill="outline" color="primary" size="large" onClick={onShare}>
            <Link2 size={18} strokeWidth={2.2} aria-hidden style={{ verticalAlign: 'middle', marginRight: 'var(--spacing-sm)' }} />
            Ссылка для врача
          </Button>
        )}
      </div>
      {(byLink || onAll) && <p className="medcard__hint">{PDF_HINT}</p>}
    </div>
  ) : onShare ? (
    <p className="medcard__hint">{EMPTY_HANDOVER}</p>
  ) : null;
  return (
    <>
      <PatientLine pet={card.pet} weight={card.weight} named={named} />
      {afterPatient}

      {/* On the page a vet opens by a link the file comes before everything that is read: it is what they take away with them. */}
      {byLink && handover}

      <ImportantBlock card={card} onEdit={() => undefined} readOnly />

      {/* What the card does not have, in one line: a vet reads the empty parts as missing, not as «all is well». */}
      {missing.length > 0 && (
        <p className="medcard__empty" role="note">
          Не заполнено: {listWords(missing)}
        </p>
      )}

      {/* The owner hands the card over, so the file and the link come right after what could harm, the first thing a vet reads. */}
      {onShare && handover}

      <Section id="medcard-vet-meds" title="Лекарства">
        {card.medications.length === 0 ? (
          <p className="medcard__empty">Сейчас ничего не принимает</p>
        ) : (
          <ul className="medcard__list">
            {card.medications.map((c) => (
              <CourseRow key={c.id} course={c} />
            ))}
          </ul>
        )}
      </Section>

      {card.visit_prep && (
        <Section id="medcard-vet-prep" title="На приём">
          <ul className="medcard__list">
            <PrepRows prep={card.visit_prep} />
          </ul>
        </Section>
      )}

      <Section id="medcard-vet-due" title="Прививки и обработки">
        {due.length === 0 && card.vaccinations.length === 0 ? (
          <p className="medcard__empty">Не указаны</p>
        ) : (
          <ul className="medcard__list">
            {due.map((r) => (
              <li key={r._id} className="medcard__row medcard__row--stack">
                <div className="medcard__row-title">{r.title}</div>
                <RowLines lines={recordLines(r).filter((l) => l.tier === 'body' || l.tier === 'key')} />
                <RecordPill record={r} />
              </li>
            ))}
            {card.vaccinations.map((v) => {
              const { Icon } = STATUS[v.status];
              return (
                <li key={v.id} className="medcard__row medcard__row--stack">
                  <div className="medcard__row-main">
                    <div className="medcard__row-title">{v.title}</div>
                    <div className="medcard__row-sub">Сертификат{v.expires_at ? `, до ${formatDate(v.expires_at)}` : ''}</div>
                  </div>
                  <span className={`medcard__status medcard__status--${v.status}`}>
                    <Icon size={13} strokeWidth={2.4} aria-hidden />
                    {certStatusText(v)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section id="medcard-vet-clinic" title={card.profile.clinics.length > 1 ? 'Клиники и врачи' : 'Клиника'}>
        {card.profile.clinics.length === 0 ? (
          <p className="medcard__empty">Не указана</p>
        ) : (
          <ul className="medcard__list">
            {card.profile.clinics.map((c, i) => (
              <ClinicRow key={`${c.name ?? ''}-${i}`} clinic={c} />
            ))}
          </ul>
        )}
      </Section>

      {hasLife(card.profile) && (
        <Section id="medcard-vet-life" title="Питание и условия">
          <ul className="medcard__list">
            <LifeRows profile={card.profile} />
          </ul>
        </Section>
      )}

      {visits.length > 0 && (
        <Section id="medcard-vet-visits" title="Последние визиты">
          <ul className="medcard__list">
            {visits.map((r) => (
              <li key={r._id} className="medcard__row medcard__row--stack">
                <div className="medcard__row-title">{r.title}</div>
                <RowLines lines={recordLines(r).filter((l) => l.tier === 'body' || l.tier === 'fact')} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {procedures.length > 0 && (
        <Section id="medcard-vet-procedures" title="Операции и процедуры">
          <ul className="medcard__list">
            {procedures.map((r) => (
              <li key={r._id} className="medcard__row medcard__row--stack">
                <div className="medcard__row-title">{r.title}</div>
                <RowLines lines={recordLines(r).filter((l) => l.tier === 'body' || l.tier === 'fact')} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {card.past_courses.length > 0 && (
        <Section id="medcard-vet-past" title="Прошлые курсы">
          <ul className="medcard__list">
            {card.past_courses.slice(0, 3).map((c) => (
              <CourseRow key={c.id} course={c} />
            ))}
          </ul>
        </Section>
      )}

      {onAll && (
        <div className="medcard__actions">
          <button type="button" className="medcard__link touch-target" style={{ alignSelf: 'center' }} onClick={onAll}>
            К записям
          </button>
        </div>
      )}
    </>
  );
}

/** A pet's medical card: everything a vet asks for, on one page, from the
    pet's own records. Read-only; each section leads to where it is edited. */
export function MedicalCard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const hidden = useHiddenRecords();
  const [saving, setSaving] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  // A link may ask for the reading mode (the links screen sends «Открыть медкарту» that way); the working mode is the default.
  const linkMode = useSearchParams()[0].get('mode');
  const [chosen, setChosen] = useState<Mode | null>(linkMode === 'vet' ? 'vet' : null);
  // A card opened by an address of another pet (a link, a notification) makes that pet the chosen one: the bar, the
  // tab and the switcher then say whose card this is.
  const { pets, selectedPetId, selectPet } = usePet();
  useEffect(() => {
    const target = pets.find((p) => p._id === id);
    if (target && target._id !== selectedPetId) selectPet(target);
  }, [id, pets, selectedPetId, selectPet]);

  const query = useQuery({
    queryKey: ['medical-card', id],
    queryFn: () => medicalCardService.get(id!),
    enabled: !!id,
    // Built from records that change elsewhere: always asked again on opening.
    staleTime: 0,
    refetchOnMount: 'always',
  });
  const card: Card | undefined = query.data;

  const downloadPdf = async () => {
    if (!id || !card || saving) return;
    setSaving(true);
    try {
      if (await medicalCardService.downloadPdf(id, card.pet.name)) showToast.success('PDF сохранён');
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сформировать PDF'));
    } finally {
      setSaving(false);
    }
  };

  if (query.isError) {
    const gone = [403, 404].includes(httpStatus(query.error) ?? 0);
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          {gone ? (
            <EmptyState icon={FileHeart} title="Питомец не найден" description="Возможно, его удалили или закрыли вам доступ" actionLabel="К питомцам" onAction={() => navigate('/pets', { replace: true })} />
          ) : (
            <LoadError what="медкарту" onRetry={() => query.refetch()} />
          )}
        </div>
      </div>
    );
  }

  if (!card) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding" aria-busy="true">
          <Skeleton.Title animated />
          <Skeleton.Paragraph lineCount={6} animated />
        </div>
      </div>
    );
  }

  const checks = readinessChecks(card, id!);
  const doneCount = checks.filter((c) => c.done).length;
  // Everyone with access to the pet may fill the card in, so the card opens as the working mode every time: the reading
  // mode is entered on purpose (or by a link that asks for it), and is not remembered, so that nobody who comes back to
  // record a visit finds a view with no «+».
  const mode: Mode = chosen ?? 'fill';
  const chooseMode = setChosen;
  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <div className={`medcard${mode === 'vet' ? ' medcard--reading' : ' medcard--entering'}`}>
          {/* The title stays in both modes: switching the mode changes what is below, not where the person is. */}
          <h1 className="display-headline" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Медкарта</h1>

          <ModeSwitch mode={mode} onChange={chooseMode} />

          <OverdueStrip card={card} petId={id!} navigate={navigate} canAct={mode === 'fill'} hidden={hidden} />

          {mode === 'vet' ? (
            <VetView card={card} hidden={hidden} saving={saving} canPdf={doneCount >= 2} onPdf={downloadPdf} onAll={() => chooseMode('fill')} onShare={() => setShareOpen(true)} />
          ) : (
            <>
          <ReadinessBlock card={card} petId={id!} navigate={navigate} />


          <MedicalSummary card={card} petId={id!} hidden={hidden} navigate={navigate} />

          <Section
            id="medcard-prep"
            title="К приёму"
            action={{ label: card.visit_prep ? 'Изменить' : 'Добавить', onClick: () => navigate(`/pets/${id}/visit-prep`) }}
          >
            {card.visit_prep ? (
              <ul className="medcard__list">
                <PrepRows prep={card.visit_prep} />
              </ul>
            ) : (
              <p className="medcard__empty">Что беспокоит и что изменилось: врач увидит это первой строкой</p>
            )}
          </Section>

          {/* Two ways to hand the card over, below the tiles so that they stay high: the file, and a link that opens with no
              sign-in. The block is there from the start: on an empty card it says what is missing instead of appearing
              out of nowhere later, when two of the five are done. */}
          <section aria-labelledby="medcard-forvet">
            <div className="medcard__section-head">
              <h2 id="medcard-forvet" className="medcard__section-title">Для врача</h2>
            </div>
            {doneCount >= 2 ? (
              <div className="medcard__forvet">
                <Button block fill="outline" color="primary" size="large" loading={saving} disabled={saving} onClick={downloadPdf}>
                  <Download size={18} strokeWidth={2.2} aria-hidden style={{ verticalAlign: 'middle', marginRight: 'var(--spacing-sm)' }} />
                  Скачать PDF
                </Button>
                <Button block fill="outline" color="primary" size="large" onClick={() => setShareOpen(true)}>
                  <Link2 size={18} strokeWidth={2.2} aria-hidden style={{ verticalAlign: 'middle', marginRight: 'var(--spacing-sm)' }} />
                  Ссылка для врача
                </Button>
              </div>
            ) : (
              <p className="medcard__empty">{EMPTY_HANDOVER}</p>
            )}
          </section>

            </>
          )}

        </div>
      </div>
      {/* The same round «+» as the feed's, in the mode that edits; the reading mode has nothing to add to. */}
      {mode === 'fill' && <RecordFab petId={id!} petName={pets.find((p) => p._id === id)?.name} />}
      <MedicalShareSheet visible={shareOpen} petId={id!} petName={card.pet.name} onClose={() => setShareOpen(false)} />
    </div>
  );
}
