import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Skeleton } from 'antd-mobile';
import { AlertTriangle, CheckCircle2, Clock, Download, FileHeart, Minus, ShieldAlert } from 'lucide-react';
import { MEDICAL_KIND_LABELS, PARASITE_TARGET_LABELS, medicalRecordsService, type MedicalKind, type MedicalRecord } from '../services/medicalRecords.service';
import { useHiddenRecords } from '../utils/deferredDelete';
import { medicalCardService, type MedicalCard as Card, type MedicalCardCourse, type MedicalCardVaccination } from '../services/medicalCard.service';
import { usePet } from '../hooks/usePet';
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

/** One course: what, how much and when, what for, who prescribed it, how it went. */
function CourseRow({ course }: { course: MedicalCardCourse }) {
  const lines = [
    [course.dose_text, course.schedule_text].filter(Boolean).join(', '),
    course.purpose ? `От чего: ${course.purpose}` : null,
    course.prescribed_by ? `Назначил: ${course.prescribed_by}` : null,
    course.comment,
    coursePeriod(course),
    course.given || course.skipped ? `Дано доз: ${course.given}${course.skipped ? `, пропущено ${course.skipped}` : ''}` : null,
  ].filter(Boolean) as string[];
  return (
    <li className="medcard__row">
      <div className="medcard__row-main">
        <div className="medcard__row-title">{course.name}{course.strength ? `, ${course.strength}` : ''}</div>
        {lines.map((line) => (
          <div key={line} className="medcard__row-sub">{line}</div>
        ))}
      </div>
      {course.status === 'planned' && <span className="medcard__status medcard__status--none">Ещё не началась</span>}
    </li>
  );
}

/** Allergies, chronic conditions and the notes: what a vet asks first, in the one block with a colour of its own. */
function ImportantBlock({ card, onEdit }: { card: Card; onEdit: () => void }) {
  const { profile, pet } = card;
  const hasAllergies = profile.allergies.length > 0;
  const filled = hasAllergies || profile.allergies_none_known || profile.conditions.length > 0 || !!pet.health_notes;
  const ids = [profile.blood_type ? `Группа крови: ${profile.blood_type}` : null, profile.chip_number ? `Чип: ${profile.chip_number}` : null].filter(Boolean);
  return (
    <div className={`medcard__important${filled ? '' : ' medcard__important--empty'}`} role="group" aria-labelledby="medcard-important">
      <ShieldAlert className="medcard__important-icon" size={22} strokeWidth={2} aria-hidden />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className="medcard__section-head" style={{ marginBottom: 4 }}>
          <h2 id="medcard-important" className="medcard__important-title" style={{ margin: 0 }}>Здоровье и аллергии</h2>
          <button type="button" className="medcard__link touch-target" onClick={onEdit}>
            {filled ? 'Изменить' : 'Заполнить'}
          </button>
        </div>
        {!filled && <p className="medcard__important-text">Не указаны. Аллергии и особенности здоровья врач спросит первыми.</p>}
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
        {ids.length > 0 && <p className="medcard__important-text medcard__ids">{ids.join(', ')}</p>}
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
  const lines = [
    [repeating ? `Сделано ${formatDate(record.date)}` : formatDate(record.date), record.target ? PARASITE_TARGET_LABELS[record.target].toLowerCase() : null, record.batch ? `серия ${record.batch}` : null]
      .filter(Boolean)
      .join(', '),
    record.next_due && repeating && !record.superseded ? `Следующая: ${formatDate(record.next_due)}` : null,
    [record.clinic, record.vet ? `врач ${record.vet}` : null].filter(Boolean).join(', ') || null,
    record.diagnosis ? `Диагноз: ${record.diagnosis}` : null,
    record.recommendations ? `Рекомендации: ${record.recommendations}` : null,
    record.note ? `Заметка: ${record.note}` : null,
    record.documents.length ? `Документы: ${record.documents.map((d) => d.title).join(', ')}` : null,
    record.superseded ? 'Есть более новая запись' : null,
  ].filter(Boolean) as string[];
  return (
    <li className={`medcard__row medcard__row--stack${record.superseded ? ' medcard__row--history' : ''}`}>
      <button type="button" className="medcard__row-button" onClick={onOpen} aria-label={`${record.title}, открыть запись`}>
        <span className="medcard__row-top">
          <span className="medcard__row-main">
            <span className="medcard__row-title" style={{ display: 'block' }}>{record.title}</span>
            {lines.map((line) => (
              <span key={line} className="medcard__row-sub" style={{ display: 'block' }}>{line}</span>
            ))}
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
        <button type="button" className="medcard__row-action touch-target" onClick={onRepeat}>
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

/** A pet's medical card: everything a vet asks for, on one page, from the
    pet's own records. Read-only; each section leads to where it is edited. */
export function MedicalCard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { pets } = usePet();
  const hidden = useHiddenRecords();
  const pet = pets.find((p) => p._id === id);
  const [saving, setSaving] = useState(false);

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
  const facts = [card.pet.species, card.pet.breed, card.pet.age_text, card.pet.gender, card.pet.neutered_text].filter(Boolean).join(', ');

  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <div className="medcard">
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

          <div className="medcard__actions">
            <Button block color="primary" size="large" loading={saving} disabled={saving} onClick={downloadPdf}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Download size={18} strokeWidth={2.2} aria-hidden />
                Скачать PDF для врача
              </span>
            </Button>
            <p className="medcard__hint">На первой странице то, что нужно на приёме, дальше вся история без сокращений.</p>
          </div>

          <ImportantBlock card={card} onEdit={() => navigate(`/pets/${id}/medical-profile`)} />

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

          <Section id="medcard-weight" title="Вес" action={{ label: card.weight ? 'История' : 'Записать', onClick: () => navigate(card.weight ? '/history' : '/form/weight') }}>
            {card.weight ? (
              <div className="medcard__weight">
                <div className="medcard__weight-now">
                  <span className="medcard__weight-value">{card.weight.latest.value.toLocaleString('ru-RU')} кг</span>
                  <span className="medcard__weight-date">{formatDate(card.weight.latest.date)}</span>
                </div>
                <Sparkline points={card.weight.series.map((p) => p.value)} />
              </div>
            ) : (
              <p className="medcard__empty">Замеров нет.</p>
            )}
          </Section>

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

          <p className="medcard__stamp">Собрано из записей питомца на {formatDate(card.generated_at)}</p>
        </div>
      </div>
    </div>
  );
}
