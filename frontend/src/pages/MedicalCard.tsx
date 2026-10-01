import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Skeleton } from 'antd-mobile';
import { AlertTriangle, CheckCircle2, ChevronRight, Clock, Copy, Download, FileHeart, Minus, ShieldAlert } from 'lucide-react';
import { MEDICAL_KIND_LABELS, PARASITE_TARGET_LABELS, medicalRecordsService, type MedicalKind, type MedicalRecord } from '../services/medicalRecords.service';
import { useHiddenRecords } from '../utils/deferredDelete';
import { medicalCardService, type MedicalCard as Card, type MedicalCardCourse, type MedicalCardVaccination } from '../services/medicalCard.service';
import { usePet } from '../hooks/usePet';
import { readinessChecks } from '../utils/medicalReadiness';
import { PetImage } from '../components/PetImage';
import { LoadError } from '../components/LoadError';
import { EmptyState } from '../components/EmptyState';
import { getSpecies } from '../utils/species';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { httpStatus } from '../services/api';
import { DOCUMENT_CATEGORY_LABELS, type DocumentCategory } from '../services/documents.service';
import './MedicalCard.css';

const EMPTY_TEXT: Record<MedicalKind, string> = {
  vaccination: 'Прививок пока нет. Добавьте прививку или сертификат из документов, и срок повтора появится здесь.',
  parasite: 'Обработок пока нет. Запишите последнюю, и придёт напоминание, когда пора повторить.',
  visit: 'Визитов пока нет. Запишите визит, диагноз и рекомендации врача.',
  procedure: 'Операций и процедур пока нет.',
};

const formatDate = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('ru-RU');

const STATUS: Record<MedicalCardVaccination['status'], { label: string; Icon: typeof CheckCircle2 }> = {
  valid: { label: 'Действует', Icon: CheckCircle2 },
  soon: { label: 'Скоро истекает', Icon: Clock },
  expired: { label: 'Истекла', Icon: AlertTriangle },
  none: { label: 'Срок не указан', Icon: Minus },
};

/** A few numbers as a line: the trend of the weight, nothing to read off it.
    The line is stretched to the width; the dot at the latest value is its own
    element, so it stays round. */
function Sparkline({ points }: { points: number[] }) {
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
function CourseRow({ course }: { course: MedicalCardCourse }) {
  const lines: (RowLine | null)[] = [
    { text: [course.dose_text, course.schedule_text].filter(Boolean).join(', '), tier: 'key' },
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
function ImportantBlock({ card, onEdit, readOnly = false }: { card: Card; onEdit: () => void; readOnly?: boolean }) {
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
          <h2 id="medcard-important" className="medcard__important-title" style={{ margin: 0 }}>Здоровье и аллергии</h2>
          {!readOnly && (
            <button type="button" className="medcard__link touch-target" onClick={onEdit}>
              {filled ? 'Изменить' : 'Заполнить'}
            </button>
          )}
        </div>
        {!filled && <p className="medcard__important-text">Не указаны. Аллергии и особенности здоровья врач спросит первыми.</p>}
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
                  <li key={`${a.substance}-${a.reaction ?? ''}`}>{a.substance}{a.reaction ? `: ${a.reaction}` : ''}</li>
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

const RECORD_STATUS: Record<'overdue' | 'soon' | 'ok', { label: string; Icon: typeof CheckCircle2; tone: MedicalCardVaccination['status'] }> = {
  overdue: { label: 'Просрочено', Icon: AlertTriangle, tone: 'expired' },
  soon: { label: 'Скоро', Icon: Clock, tone: 'soon' },
  ok: { label: 'В срок', Icon: CheckCircle2, tone: 'valid' },
};

/** One record of the card: what, when, and (for a vaccination or a treatment) when it is due again. */
function RecordRow({ record, onOpen, onRepeat }: { record: MedicalRecord; onOpen: () => void; onRepeat?: () => void }) {
  const repeating = record.kind === 'vaccination' || record.kind === 'parasite';
  const status = record.status !== 'none' ? RECORD_STATUS[record.status] : null;
  const lines: (RowLine | null)[] = [
    {
      text: [repeating ? `Сделано ${formatDate(record.date)}` : formatDate(record.date), record.target ? PARASITE_TARGET_LABELS[record.target].toLowerCase() : null, record.batch ? `серия ${record.batch}` : null]
        .filter(Boolean)
        .join(', '),
      tier: 'body',
    },
    record.next_due && repeating && !record.superseded ? { label: 'Следующая', text: formatDate(record.next_due), tier: 'key' } : null,
    record.diagnosis ? { label: 'Диагноз', text: record.diagnosis, tier: 'fact' } : null,
    record.recommendations ? { label: 'Рекомендации', text: record.recommendations, tier: 'fact' } : null,
    { text: [record.clinic, record.vet ? `врач ${record.vet}` : null].filter(Boolean).join(', '), tier: 'meta' },
    record.note ? { label: 'Заметка', text: record.note, tier: 'meta' } : null,
    record.documents.length ? { label: 'Документы', text: record.documents.map((d) => d.title).join(', '), tier: 'meta' } : null,
    record.superseded ? { text: 'Есть более новая запись', tier: 'meta' } : null,
  ];
  return (
    <li className={`medcard__row medcard__row--stack${record.superseded ? ' medcard__row--history' : ''}`}>
      <button type="button" className="medcard__row-button" onClick={onOpen} aria-label={`${record.title}, открыть запись`}>
        <span className="medcard__row-top">
          <span className="medcard__row-main">
            <span className="medcard__row-title" style={{ display: 'block' }}>{record.title}</span>
            <RowLines lines={lines.filter((l): l is RowLine => !!l && !!l.text)} />
          </span>
          {status && (
            <span className={`medcard__status medcard__status--${status.tone}`}>
              <status.Icon size={13} strokeWidth={2.4} aria-hidden />
              {status.label}
            </span>
          )}
        </span>
      </button>
      {onRepeat && !record.superseded && (
        <button type="button" className="medcard__row-action" onClick={onRepeat}>
          Записать снова
        </button>
      )}
    </li>
  );
}

function Section({ id, title, action, children }: { id: string; title: string; action?: { label: string; onClick: () => void }; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id}>
      <div className="medcard__section-head">
        <h2 id={id} className="medcard__section-title">{title}</h2>
        {action && (
          <button type="button" className="medcard__link touch-target" onClick={action.onClick}>
            {action.label}
          </button>
        )}
      </div>
      <div className="card-soft" style={{ overflow: 'hidden' }}>{children}</div>
    </section>
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
      <p className="medcard__ready" role="status">
        <CheckCircle2 size={18} strokeWidth={2.2} aria-hidden />
        Главное для врача заполнено
      </p>
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

/** The records of one kind. The card brings the latest ten; «Показать все» asks for the rest. */
function KindSection({ kind, card, petId, hidden, navigate }: { kind: MedicalKind; card: Card; petId: string; hidden: ReadonlySet<string>; navigate: (to: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const total = card.record_counts[kind];
  const all = useQuery({
    queryKey: ['medical-records', petId, kind],
    queryFn: () => medicalRecordsService.list(petId, kind),
    enabled: expanded,
    staleTime: 0,
  });
  const source = expanded && all.data ? all.data : card.records[kind];
  const rows = source.filter((r) => !hidden.has(r._id));
  const legacy = kind === 'vaccination' ? card.vaccinations : [];
  const repeating = kind === 'vaccination' || kind === 'parasite';
  const more = total > source.length;
  // An empty kind says nothing here: the block of missing items, or the group of what can be added, already does.
  if (rows.length === 0 && legacy.length === 0 && !expanded) return null;
  return (
    <Section
      id={`medcard-${kind}`}
      title={MEDICAL_KIND_LABELS[kind].section}
      action={{ label: 'Добавить', onClick: () => navigate(`/pets/${petId}/medical-records/new?kind=${kind}`) }}
    >
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
            />
          ))}
          {legacy.map((v) => {
            const { label, Icon } = STATUS[v.status];
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
                    {label}
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
              Показаны последние {source.length} из {total}.{' '}
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

type Mode = 'vet' | 'fill';
const MODE_KEY = 'medcard-mode';

/** The mode the person chose on this device, if any: the default depends on how much is filled in. */
function readMode(): Mode | null {
  try {
    const v = localStorage.getItem(MODE_KEY);
    return v === 'vet' || v === 'fill' ? v : null;
  } catch {
    return null;
  }
}

function saveMode(mode: Mode) {
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {
    /* a private window keeps no choice: the default applies next time */
  }
}

function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  return (
    <div className="medcard__modes" role="group" aria-label="Режим медкарты">
      {([['vet', 'Врачу'], ['fill', 'Заполнить']] as const).map(([value, label]) => (
        <button key={value} type="button" className="medcard__mode" aria-pressed={mode === value} onClick={() => onChange(value)}>
          {label}
        </button>
      ))}
    </div>
  );
}

/** What a vet reads at the counter, in the order they ask: allergies, what is due, what is taken now and the
    weight, the clinic, the last visits. Nothing here edits; the history and the forms are in the other mode. */
function VetView({ card, hidden, saving, onPdf, onAll }: { card: Card; hidden: ReadonlySet<string>; saving: boolean; onPdf: () => void; onAll: () => void }) {
  const clinic = card.profile.clinic;
  const due = (['vaccination', 'parasite'] as const).flatMap((kind) => card.records[kind].filter((r) => !r.superseded && !hidden.has(r._id)));
  const visits = card.records.visit.filter((r) => !hidden.has(r._id)).slice(0, 3);
  const hasClinic = !!(clinic.name || clinic.vet || clinic.phone);
  return (
    <>
      <ImportantBlock card={card} onEdit={() => undefined} readOnly />

      <Section id="medcard-vet-due" title="Прививки и обработки">
        {due.length === 0 && card.vaccinations.length === 0 ? (
          <p className="medcard__empty">Не указаны.</p>
        ) : (
          <ul className="medcard__list">
            {due.map((r) => {
              const status = r.status !== 'none' ? RECORD_STATUS[r.status] : null;
              return (
                <li key={r._id} className="medcard__row">
                  <div className="medcard__row-main">
                    <div className="medcard__row-title">{r.title}</div>
                    <div className="medcard__row-sub">
                      Сделано {formatDate(r.date)}{r.next_due ? `, следующая ${formatDate(r.next_due)}` : ''}
                    </div>
                  </div>
                  {status && (
                    <span className={`medcard__status medcard__status--${status.tone}`}>
                      <status.Icon size={13} strokeWidth={2.4} aria-hidden />
                      {status.label}
                    </span>
                  )}
                </li>
              );
            })}
            {card.vaccinations.map((v) => {
              const { label, Icon } = STATUS[v.status];
              return (
                <li key={v.id} className="medcard__row">
                  <div className="medcard__row-main">
                    <div className="medcard__row-title">{v.title}</div>
                    <div className="medcard__row-sub">Сертификат{v.expires_at ? `, до ${formatDate(v.expires_at)}` : ''}</div>
                  </div>
                  <span className={`medcard__status medcard__status--${v.status}`}>
                    <Icon size={13} strokeWidth={2.4} aria-hidden />
                    {label}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section id="medcard-vet-now" title="Сейчас">
        <ul className="medcard__list">
          {card.medications.map((c) => (
            <CourseRow key={c.id} course={c} />
          ))}
          {card.medications.length === 0 && (
            <li className="medcard__row">
              <div className="medcard__row-main">
                <div className="medcard__row-title">Лекарства</div>
                <div className="medcard__row-sub">Сейчас ничего не принимает</div>
              </div>
            </li>
          )}
          <li className="medcard__row">
            <div className="medcard__row-main">
              <div className="medcard__row-title">Вес</div>
              <div className="medcard__row-sub">
                {card.weight ? `${card.weight.latest.value.toLocaleString('ru-RU')} кг, ${formatDate(card.weight.latest.date)}` : 'Не указан'}
              </div>
            </div>
          </li>
          <li className="medcard__row">
            <div className="medcard__row-main">
              <div className="medcard__row-title">{hasClinic ? clinic.name || 'Клиника' : 'Клиника'}</div>
              {!hasClinic && <div className="medcard__row-sub">Не указана</div>}
              {clinic.vet && <div className="medcard__row-sub">Врач: {clinic.vet}</div>}
            </div>
            {clinic.phone && (
              <a className="medcard__call touch-target" href={`tel:${clinic.phone.replace(/[^\d+]/g, '')}`}>
                {clinic.phone}
              </a>
            )}
          </li>
        </ul>
      </Section>

      {visits.length > 0 && (
        <Section id="medcard-vet-visits" title="Последние визиты">
          <ul className="medcard__list">
            {visits.map((r) => (
              <li key={r._id} className="medcard__row medcard__row--stack">
                <div className="medcard__row-title">{r.title}, {formatDate(r.date)}</div>
                {r.diagnosis && <div className="medcard__row-sub">Диагноз: {r.diagnosis}</div>}
                {r.recommendations && <div className="medcard__row-sub">Рекомендации: {r.recommendations}</div>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <div className="medcard__actions">
        <Button block color="primary" size="large" loading={saving} disabled={saving} onClick={onPdf}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <Download size={18} strokeWidth={2.2} aria-hidden />
            Скачать PDF для врача
          </span>
        </Button>
        <button type="button" className="medcard__link touch-target" style={{ alignSelf: 'center' }} onClick={onAll}>
          Вся история и правка
        </button>
      </div>
    </>
  );
}

/** A pet's medical card: everything a vet asks for, on one page, from the
    pet's own records. Read-only; each section leads to where it is edited. */
export function MedicalCard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { pets } = usePet();
  const hidden = useHiddenRecords();
  const pet = pets.find((p) => p._id === id);
  const [saving, setSaving] = useState(false);
  const [chosen, setChosen] = useState<Mode | null>(readMode);

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
      await medicalCardService.downloadPdf(id, card.pet.name);
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

  const SpeciesIcon = getSpecies(pet?.species).icon;
  const checks = readinessChecks(card, id!);
  const doneCount = checks.filter((c) => c.done).length;
  const complete = doneCount === checks.length;
  const importantFilled = card.profile.allergies.length > 0 || card.profile.allergies_none_known || card.profile.conditions.length > 0 || !!card.pet.health_notes;
  // The kinds of record that are only optional: a visit or an operation is not owed, so they wait in one group.
  const optionalEmpty = (['visit', 'procedure'] as MedicalKind[]).filter((kind) => card.record_counts[kind] === 0);
  // Everyone with access to the pet may fill the card in (the profile and the records are the family's): the choice on this device, else by how much is filled in.
  const mode: Mode = chosen ?? (complete ? 'vet' : 'fill');
  const chooseMode = (next: Mode) => {
    setChosen(next);
    saveMode(next);
  };
  const facts = [card.pet.species, card.pet.breed, card.pet.age_text, card.pet.gender, card.pet.neutered_text].filter(Boolean).join(', ');

  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <div className={`medcard${mode === 'vet' ? ' medcard--reading' : ''}`}>
          <h1 className="display-headline" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Медкарта</h1>

          <div className="card-soft medcard__head">
            <div className="medcard__avatar" aria-hidden={!pet?.photo_url}>
              {pet?.photo_url ? (
                <PetImage src={pet.photo_url} alt={card.pet.name} size={72} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 0 }} />
              ) : (
                <SpeciesIcon size={36} strokeWidth={1.6} aria-hidden />
              )}
            </div>
            <div style={{ minWidth: 0 }}>
              <p className="medcard__name">{card.pet.name}</p>
              <p className="medcard__facts">{facts || 'Данные о питомце не заполнены'}</p>
            </div>
          </div>

          <ModeSwitch mode={mode} onChange={chooseMode} />

          {mode === 'vet' ? (
            <VetView card={card} hidden={hidden} saving={saving} onPdf={downloadPdf} onAll={() => chooseMode('fill')} />
          ) : (
            <>
          <ReadinessBlock card={card} petId={id!} navigate={navigate} />

          {/* A PDF of an empty card helps nobody: it is offered once two of the five are there. */}
          {doneCount >= 2 && (
            <div className="medcard__actions">
              <Button block fill="outline" color="primary" size="large" loading={saving} disabled={saving} onClick={downloadPdf}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <Download size={18} strokeWidth={2.2} aria-hidden />
                  Скачать PDF для врача
                </span>
              </Button>
              <p className="medcard__hint">Первая страница для приёма, дальше история.</p>
            </div>
          )}

          {importantFilled && <ImportantBlock card={card} onEdit={() => navigate(`/pets/${id}/medical-profile`)} />}

          {(card.profile.clinic.name || card.profile.clinic.vet || card.profile.clinic.phone) && (
            <Section id="medcard-clinic" title="Клиника" action={{ label: 'Изменить', onClick: () => navigate(`/pets/${id}/medical-profile`) }}>
              <div className="medcard__row">
                <div className="medcard__row-main">
                  {card.profile.clinic.name && <div className="medcard__row-title">{card.profile.clinic.name}</div>}
                  {card.profile.clinic.vet && <div className="medcard__row-sub">Врач: {card.profile.clinic.vet}</div>}
                  {card.profile.clinic.phone && (
                    <div className="medcard__row-sub">
                      <a className="medcard__tel" href={`tel:${card.profile.clinic.phone.replace(/[^\d+]/g, '')}`}>{card.profile.clinic.phone}</a>
                    </div>
                  )}
                </div>
              </div>
            </Section>
          )}

          <Section id="medcard-medications" title="Лекарства сейчас" action={{ label: card.medications.length ? 'Все лекарства' : 'Добавить', onClick: () => navigate(card.medications.length ? '/medications' : '/medications/new') }}>
            {card.medications.length === 0 ? (
              <p className="medcard__empty">Сейчас ничего не принимает.</p>
            ) : (
              <ul className="medcard__list">
                {card.medications.map((c) => (
                  <CourseRow key={c.id} course={c} />
                ))}
              </ul>
            )}
          </Section>

          {(['vaccination', 'parasite', 'visit', 'procedure'] as MedicalKind[]).map((kind) => (
            <KindSection key={kind} kind={kind} card={card} petId={id!} hidden={hidden} navigate={navigate} />
          ))}

          {optionalEmpty.length > 0 && (
            <Section id="medcard-optional" title="Ещё можно добавить">
              <ul className="medcard__list">
                {optionalEmpty.map((kind) => (
                  <li key={kind} className="medcard__row" style={{ padding: 0 }}>
                    <button type="button" className="medcard__row-button medcard__todo-row" onClick={() => navigate(`/pets/${id}/medical-records/new?kind=${kind}`)}>
                      <span className="medcard__row-title">{MEDICAL_KIND_LABELS[kind].section}</span>
                      <ChevronRight size={18} strokeWidth={2.2} aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {card.past_courses.length > 0 && (
            <Section id="medcard-past-courses" title="Прошлые курсы">
              <ul className="medcard__list">
                {card.past_courses.map((c) => (
                  <CourseRow key={c.id} course={c} />
                ))}
              </ul>
              {card.past_courses_total > card.past_courses.length && (
                <p className="medcard__more">Показаны последние {card.past_courses.length} из {card.past_courses_total}. Все курсы есть в PDF.</p>
              )}
            </Section>
          )}

          {card.weight && (
            <Section id="medcard-weight" title="Вес" action={{ label: 'История', onClick: () => navigate('/history') }}>
              <div className="medcard__weight">
                <div className="medcard__weight-now">
                  <span className="medcard__weight-value">{card.weight.latest.value.toLocaleString('ru-RU')} кг</span>
                  <span className="medcard__weight-date">{formatDate(card.weight.latest.date)}</span>
                </div>
                <Sparkline points={card.weight.series.map((p) => p.value)} />
              </div>
            </Section>
          )}

          {card.documents.length > 0 && (
            <Section id="medcard-documents" title="Последние результаты" action={{ label: 'Все документы', onClick: () => navigate('/documents') }}>
              <ul className="medcard__list">
                {card.documents.map((d) => (
                  <li key={d.id} className="medcard__row">
                    <div className="medcard__row-main">
                      <div className="medcard__row-title">{d.title}</div>
                      <div className="medcard__row-sub">{DOCUMENT_CATEGORY_LABELS[d.category as DocumentCategory] ?? 'Документ'}, {formatDate(d.added)}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </Section>
          )}

            </>
          )}

          <p className="medcard__stamp">Собрано из записей питомца на {formatDate(card.generated_at)}</p>
        </div>
      </div>
    </div>
  );
}
