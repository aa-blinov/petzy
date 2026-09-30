import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Skeleton } from 'antd-mobile';
import { AlertTriangle, CheckCircle2, Clock, Download, FileHeart, Minus, ShieldAlert } from 'lucide-react';
import { medicalCardService, type MedicalCard as Card, type MedicalCardVaccination } from '../services/medicalCard.service';
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

/** A pet's medical card: everything a vet asks for, on one page, from the
    pet's own records. Read-only; each section leads to where it is edited. */
export function MedicalCard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { pets } = usePet();
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
  const editPet = () => navigate(`/pets/${id}/edit`);

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
          </div>

          {card.pet.health_notes ? (
            <div className="medcard__important" role="group" aria-labelledby="medcard-important">
              <ShieldAlert className="medcard__important-icon" size={22} strokeWidth={2} aria-hidden />
              <div style={{ minWidth: 0 }}>
                <h2 id="medcard-important" className="medcard__important-title">Здоровье и аллергии</h2>
                <p className="medcard__important-text">{card.pet.health_notes}</p>
              </div>
            </div>
          ) : (
            <div className="medcard__important medcard__important--empty" role="group" aria-labelledby="medcard-important">
              <ShieldAlert className="medcard__important-icon" size={22} strokeWidth={2} aria-hidden />
              <div style={{ minWidth: 0 }}>
                <h2 id="medcard-important" className="medcard__important-title">Здоровье и аллергии</h2>
                <p className="medcard__important-text">Не указаны. Аллергии и особенности здоровья врач спросит первыми.</p>
                {card.can_edit && (
                  <button type="button" className="medcard__link touch-target" onClick={editPet} style={{ paddingLeft: 0 }}>
                    Добавить в карточке питомца
                  </button>
                )}
              </div>
            </div>
          )}

          <Section id="medcard-vaccinations" title="Прививки" action={{ label: 'Добавить', onClick: () => navigate('/documents/new?category=vaccination') }}>
            {card.vaccinations.length === 0 ? (
              <p className="medcard__empty">Прививок пока нет. Добавьте сертификат, и срок действия появится здесь.</p>
            ) : (
              <ul className="medcard__list">
                {card.vaccinations.map((v) => {
                  const { label, Icon } = STATUS[v.status];
                  return (
                    <li key={v.id} className="medcard__row">
                      <div className="medcard__row-main">
                        <div className="medcard__row-title">{v.title}</div>
                        {v.expires_at && <div className="medcard__row-sub">до {formatDate(v.expires_at)}</div>}
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

          <Section id="medcard-medications" title="Лекарства сейчас" action={{ label: card.medications.length ? 'Все лекарства' : 'Добавить', onClick: () => navigate(card.medications.length ? '/medications' : '/medications/new') }}>
            {card.medications.length === 0 ? (
              <p className="medcard__empty">Сейчас ничего не принимает.</p>
            ) : (
              <ul className="medcard__list">
                {card.medications.map((m) => (
                  <li key={m.id} className="medcard__row">
                    <div className="medcard__row-main">
                      <div className="medcard__row-title">{m.name}{m.strength ? `, ${m.strength}` : ''}</div>
                      <div className="medcard__row-sub">
                        {[m.dose_text, m.schedule_text].filter(Boolean).join(', ')}
                        {m.comment ? `. ${m.comment}` : ''}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>

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
