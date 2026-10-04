import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Skeleton } from 'antd-mobile';
import { FileHeart } from 'lucide-react';

import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { RecordFab } from '../components/RecordSheet';
import { usePet } from '../hooks/usePet';
import { httpStatus } from '../services/api';
import { DOCUMENT_CATEGORY_LABELS, type DocumentCategory } from '../services/documents.service';
import { medicalCardService, type MedicalCard as Card } from '../services/medicalCard.service';
import { MEDICAL_KIND_LABELS, type MedicalKind } from '../services/medicalRecords.service';
import { useHiddenRecords } from '../utils/deferredDelete';
import { formatDate, hasLife, weightDelta } from '../utils/medicalCardFormat';
import { ClinicRow, CourseRow, ImportantBlock, KindSection, LifeRows, Section, Sparkline } from './MedicalCard';
import './MedicalCard.css';

export type CardSectionKey = 'risks' | 'meds' | 'prevention' | 'weight' | 'visits' | 'documents' | 'clinic' | 'life';

const TITLES: Record<CardSectionKey, string> = {
  risks: 'Риски',
  meds: 'Лекарства',
  prevention: 'Профилактика',
  weight: 'Вес',
  visits: 'Визиты и операции',
  documents: 'Документы',
  clinic: 'Клиника и врачи',
  life: 'Питание и условия',
};

const isSection = (value: string | undefined): value is CardSectionKey => !!value && value in TITLES;

/** One part of the card on its own screen: what the summary's tile opens. The same blocks the card has always had, each
    with its own «Добавить» or «Изменить», so a part is read and put right in one place. */
function SectionBody({ section, card, petId, hidden, navigate }: { section: CardSectionKey; card: Card; petId: string; hidden: ReadonlySet<string>; navigate: (to: string) => void }) {
  const profileTo = `/pets/${petId}/medical-profile`;
  switch (section) {
    case 'risks':
      return <ImportantBlock card={card} onEdit={() => navigate(profileTo)} />;
    case 'meds':
      return (
        <>
          <Section
            id="medcard-medications"
            title="Сейчас"
            action={{ label: card.medications.length ? 'Все лекарства' : 'Добавить', onClick: () => navigate(card.medications.length ? '/medications' : '/medications/new') }}
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
          </Section>
          {card.past_courses.length > 0 && (
            <Section id="medcard-past-courses" title="Прошлые курсы">
              <ul className="medcard__list">
                {card.past_courses.map((c) => (
                  <CourseRow key={c.id} course={c} />
                ))}
              </ul>
              {card.past_courses_total > card.past_courses.length && (
                <p className="medcard__more">{card.past_courses.length === 1 ? `Показан последний курс из ${card.past_courses_total}` : `Показаны последние ${card.past_courses.length} из ${card.past_courses_total}`}</p>
              )}
            </Section>
          )}
        </>
      );
    case 'prevention':
      return (
        <>
          <KindSection kind="vaccination" card={card} petId={petId} hidden={hidden} navigate={navigate} />
          <KindSection kind="parasite" card={card} petId={petId} hidden={hidden} navigate={navigate} />
          {card.record_counts.vaccination + card.record_counts.parasite + card.vaccinations.length === 0 && (
            <p className="medcard__empty">Прививок и обработок пока нет. «+» внизу откроет запись, срок повтора появится здесь</p>
          )}
        </>
      );
    case 'visits': {
      const empty = (['visit', 'procedure'] as MedicalKind[]).filter((kind) => card.record_counts[kind] === 0);
      return (
        <>
          <KindSection kind="visit" card={card} petId={petId} hidden={hidden} navigate={navigate} />
          <KindSection kind="procedure" card={card} petId={petId} hidden={hidden} navigate={navigate} />
          {empty.length > 0 && (
            <Section id="medcard-optional" title={empty.length > 1 ? 'Ещё можно добавить' : MEDICAL_KIND_LABELS[empty[0]].section}>
              <ul className="medcard__list">
                {empty.map((kind) => (
                  <li key={kind} className="medcard__row" style={{ padding: 0 }}>
                    <button type="button" className="medcard__row-button medcard__todo-row" onClick={() => navigate(`/pets/${petId}/medical-records/new?kind=${kind}`)}>
                      <span className="medcard__row-title">{MEDICAL_KIND_LABELS[kind].section}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </>
      );
    }
    case 'weight':
      return card.weight ? (
        <Section id="medcard-weight" title="Сейчас" action={{ label: 'Записать вес', onClick: () => navigate('/form/weight') }} secondary={{ label: 'История', onClick: () => navigate('/history') }}>
          <div className="medcard__weight">
            <div className="medcard__weight-now">
              <span className="medcard__weight-value">{card.weight.latest.value.toLocaleString('ru-RU')} кг</span>
              <span className="medcard__weight-date">{formatDate(card.weight.latest.date)}</span>
            </div>
            {weightDelta(card.weight.series) && <div className="medcard__row-sub medcard__row-sub--meta">{weightDelta(card.weight.series)}</div>}
            <Sparkline points={card.weight.series.map((p) => p.value)} />
          </div>
        </Section>
      ) : (
        <Section id="medcard-weight" title="Сейчас" action={{ label: 'Записать вес', onClick: () => navigate('/form/weight') }}>
          <p className="medcard__empty">Вес не записан. Врач считает по нему дозы</p>
        </Section>
      );
    case 'documents':
      return (
        <Section id="medcard-documents" title="Последние результаты" action={{ label: 'Все документы', onClick: () => navigate('/documents') }}>
          {card.documents.length === 0 ? (
            <p className="medcard__empty">Анализов и заключений пока нет. Добавьте их в документы, и они появятся здесь</p>
          ) : (
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
          )}
        </Section>
      );
    case 'clinic':
      return (
        <Section
          id="medcard-clinic"
          title={card.profile.clinics.length > 1 ? 'Клиники и врачи' : 'Клиника'}
          action={{ label: card.profile.clinics.length ? 'Изменить' : 'Указать', onClick: () => navigate(`${profileTo}?section=clinic`) }}
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
        </Section>
      );
    case 'life':
      return (
        <Section id="medcard-life" title="Сейчас" action={{ label: hasLife(card.profile) ? 'Изменить' : 'Указать', onClick: () => navigate(`${profileTo}?section=life`) }}>
          {hasLife(card.profile) ? (
            <ul className="medcard__list">
              <LifeRows profile={card.profile} />
            </ul>
          ) : (
            <p className="medcard__empty">Чем кормят и где живёт: помогает врачу, когда причина не ясна</p>
          )}
        </Section>
      );
  }
}

export function MedicalCardSection() {
  const { id, section } = useParams<{ id: string; section: string }>();
  const navigate = useNavigate();
  const hidden = useHiddenRecords();
  const { pets, selectedPetId, selectPet } = usePet();
  // The same as the card itself: the address of another pet makes that pet the chosen one.
  useEffect(() => {
    const target = pets.find((p) => p._id === id);
    if (target && target._id !== selectedPetId) selectPet(target);
  }, [id, pets, selectedPetId, selectPet]);

  const query = useQuery({ queryKey: ['medical-card', id], queryFn: () => medicalCardService.get(id!), enabled: !!id, staleTime: 0, refetchOnMount: 'always' });

  if (!isSection(section)) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          <EmptyState icon={FileHeart} title="Такого раздела нет" description="Вернитесь в медкарту и выберите раздел" actionLabel="В медкарту" onAction={() => navigate(`/pets/${id}/medical-card`, { replace: true })} />
        </div>
      </div>
    );
  }
  if (query.isError) {
    const gone = [403, 404].includes(httpStatus(query.error) ?? 0);
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          {gone ? <EmptyState icon={FileHeart} title="Питомец не найден" description="Возможно, его удалили или закрыли вам доступ" actionLabel="К питомцам" onAction={() => navigate('/pets', { replace: true })} /> : <LoadError what="раздел" onRetry={() => query.refetch()} />}
        </div>
      </div>
    );
  }
  const card = query.data;
  if (!card) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding" aria-busy="true">
          <Skeleton.Title animated />
          <Skeleton.Paragraph lineCount={5} animated />
        </div>
      </div>
    );
  }
  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <div className="medcard medcard--entering">
          <div className="medcard__header">
            <h1 className="display-headline" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>{TITLES[section]}</h1>
            <p className="medcard__hint">{card.pet.name}</p>
          </div>
          <SectionBody section={section} card={card} petId={id!} hidden={hidden} navigate={navigate} />
        </div>
      </div>
      <RecordFab petId={id!} petName={card.pet.name} />
    </div>
  );
}
