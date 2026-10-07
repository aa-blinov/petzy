import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Popup, Skeleton } from 'antd-mobile';
import { FileHeart } from 'lucide-react';

import { DraggableSheetBody } from '../components/DraggableSheetBody';
import { EmptyState } from '../components/EmptyState';
import { Fab } from '../components/Fab';
import { LoadError } from '../components/LoadError';
import { usePet } from '../hooks/usePet';
import { httpStatus } from '../services/api';
import { DOCUMENT_CATEGORY_LABELS, type DocumentCategory } from '../services/documents.service';
import { medicalCardService, type MedicalCard as Card } from '../services/medicalCard.service';
import { MEDICAL_KIND_LABELS, type MedicalKind } from '../services/medicalRecords.service';
import { useHiddenRecords } from '../utils/deferredDelete';
import { formatDate, hasLife, weightDelta } from '../utils/medicalCardFormat';
import { pluralRu } from '../utils/relativeTime';
import { ClinicRow, CourseRow, ImportantBlock, KindSection, LifeRows, Section, Sparkline } from './MedicalCard';
import './MedicalCard.css';

export type CardSectionKey = 'risks' | 'meds' | 'prevention' | 'weight' | 'visits' | 'documents' | 'clinic' | 'life';

const TITLES: Record<CardSectionKey, string> = {
  risks: 'Здоровье и аллергии',
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
      return <ImportantBlock card={card} onEdit={() => navigate(`${profileTo}?section=allergies`)} title="Аллергии и состояния" />;
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
          {/* What is missing is said, and where to put it is the one door of this screen, the round «+» below. The list of
              missing kinds used to be a block of buttons of its own: the same two forms as the sheet under «+», one screen
              over. */}
          {empty.length > 0 && (
            <p className="medcard__empty">
              {empty.length > 1
                ? 'Визитов и операций пока нет. «+» внизу откроет запись'
                : `${MEDICAL_KIND_LABELS[empty[0]].section} пока нет. «+» внизу откроет запись`}
            </p>
          )}
        </>
      );
    }
    case 'weight': {
      if (!card.weight) {
        return (
          <Section id="medcard-weight" title="Сейчас" action={{ label: 'Записать вес', onClick: () => navigate('/form/weight') }}>
            <p className="medcard__empty">Вес не записан. Врач считает по нему дозы</p>
          </Section>
        );
      }
      const { series, latest } = card.weight;
      const values = series.map((p) => p.value);
      const range = Math.min(...values) === Math.max(...values) ? null : `${Math.min(...values).toLocaleString('ru-RU')}–${Math.max(...values).toLocaleString('ru-RU')} кг`;
      // The latest is the headline; what came before it is a short list, newest first, so the line has dates and values to read by.
      const before = series.slice(0, -1).slice(-4).reverse();
      return (
        <>
          <Section id="medcard-weight" title="Сейчас" action={{ label: 'Записать вес', onClick: () => navigate('/form/weight') }} secondary={{ label: 'История', onClick: () => navigate('/history') }}>
            <div className="medcard__weight">
              <div className="medcard__weight-now">
                <span className="medcard__weight-value">{latest.value.toLocaleString('ru-RU')} кг</span>
                <span className="medcard__weight-date">{formatDate(latest.date)}</span>
              </div>
              {weightDelta(series) && <div className="medcard__row-sub medcard__row-sub--meta">{weightDelta(series)}</div>}
              <Sparkline points={values} />
              {series.length > 1 && (
                <div className="medcard__row-sub medcard__row-sub--meta">
                  {series.length} {pluralRu(series.length, 'замер', 'замера', 'замеров')} с {formatDate(series[0].date)}
                  {range ? `, диапазон ${range}` : ''}
                </div>
              )}
            </div>
          </Section>
          {before.length > 0 && (
            <Section id="medcard-weight-before" title="Раньше">
              <ul className="medcard__list">
                {before.map((p) => (
                  <li key={`${p.date}-${p.value}`} className="medcard__row">
                    <div className="medcard__row-main">
                      <div className="medcard__row-title">{p.value.toLocaleString('ru-RU')} кг</div>
                      <div className="medcard__row-sub">{formatDate(p.date)}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </>
      );
    }
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
          title={card.profile.clinics.length > 1 ? 'Клиники' : 'Клиника'}
          titleHidden
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

/** What the round «+» of this section adds: only its own entries. The card keeps the full sheet, because there it is asked
    which thing of the whole diary to write about, and on one part of the card half of that list is somebody else's. */
const SECTION_ADDS: Record<CardSectionKey, { label: string; to: (petId: string) => string }[]> = {
  risks: [{ label: 'Аллергии и состояния', to: (id) => `/pets/${id}/medical-profile?section=allergies` }],
  meds: [{ label: 'Лекарство', to: () => '/medications/new' }],
  prevention: [
    { label: 'Прививка', to: (id) => `/pets/${id}/medical-records/new?kind=vaccination` },
    { label: 'Обработка от паразитов', to: (id) => `/pets/${id}/medical-records/new?kind=parasite` },
  ],
  weight: [{ label: 'Замер веса', to: () => '/form/weight' }],
  visits: [
    { label: 'Визит', to: (id) => `/pets/${id}/medical-records/new?kind=visit` },
    { label: 'Операция', to: (id) => `/pets/${id}/medical-records/new?kind=procedure` },
  ],
  documents: [{ label: 'Документ', to: () => '/documents/new' }],
  clinic: [{ label: 'Клиника и врачи', to: (id) => `/pets/${id}/medical-profile?section=clinic` }],
  life: [{ label: 'Питание и условия', to: (id) => `/pets/${id}/medical-profile?section=life` }],
};

/** Where the block of the section already carries its own «Добавить», «Записать вес» or «Указать», the round «+» only
    repeats that door. It stays where the block has no door of its own, and where it asks between two kinds. «Профилактика»
    and «Визиты» ask between two kinds, and their blocks carry no door at all, so one «+» opens the whole screen. */
const SECTION_OPENS_ITSELF: ReadonlySet<CardSectionKey> = new Set(['risks', 'meds', 'weight', 'clinic', 'life']);

/** The round «+» of one part of the card: where there is one thing to add it opens the screen, where there are two
    it asks which, in the same sheet the card uses. */
function SectionFab({ section, petId, navigate }: { section: CardSectionKey; petId: string; navigate: (to: string) => void }) {
  const [open, setOpen] = useState(false);
  const adds = SECTION_ADDS[section];
  if (SECTION_OPENS_ITSELF.has(section)) return null;
  if (adds.length === 1) return <Fab label={`Добавить: ${adds[0].label}`} onClick={() => navigate(adds[0].to(petId))} />;
  return (
    <>
      <Fab label="Добавить" popup onClick={() => setOpen(true)} />
      <Popup visible={open} onMaskClick={() => setOpen(false)} position="bottom" bodyStyle={{ background: 'transparent' }}>
        <DraggableSheetBody visible={open} onClose={() => setOpen(false)} label="Что добавить">
          <ul className="medcard__list">
            {adds.map((add) => (
              <li key={add.label} className="medcard__row" style={{ padding: 0 }}>
                <button
                  type="button"
                  className="medcard__row-button medcard__todo-row"
                  onClick={() => {
                    setOpen(false);
                    navigate(add.to(petId));
                  }}
                >
                  <span className="medcard__row-title">{add.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </DraggableSheetBody>
      </Popup>
    </>
  );
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
            {/* No switcher in the bar here: the way to another pet is the list, said once under the name. */}
            {pets.length > 1 && (
              <button type="button" className="medcard__link touch-target" onClick={() => navigate('/pets')}>
                Все питомцы
              </button>
            )}
          </div>
          <SectionBody section={section} card={card} petId={id!} hidden={hidden} navigate={navigate} />
        </div>
      </div>
      <SectionFab section={section} petId={id!} navigate={navigate} />
    </div>
  );
}
