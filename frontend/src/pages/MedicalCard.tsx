import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileHeart } from 'lucide-react';

import { MedicalShareSheet } from '../components/MedicalShareSheet';
import { AppPullToRefresh } from '../components/AppPullToRefresh';
import { CardDocument } from './MedicalCardDocument';
import { medicalCardQuery, medicalCardService } from '../services/medicalCard.service';
import { readinessChecks } from '../utils/medicalReadiness';
import { useHiddenRecords } from '../utils/deferredDelete';
import { usePet } from '../hooks/usePet';
import { LoadError } from '../components/LoadError';
import { EmptyState } from '../components/EmptyState';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { isPetGone } from '../utils/notFound';
import { MedicalCardSkeleton } from '../components/Skeletons';
import './MedicalCard.css';

/** The two ways to hand the card over are on the card from the start; on an empty one they are disabled, and the line
    under them says why. */
const EMPTY_HANDOVER = 'Карта почти пуста. Заполните её, и PDF и ссылка для врача станут доступны';
/** A co-owner reads the card here already, so the link to give away is closed to them: the file is what is left. */
const EMPTY_HANDOVER_COOWNER = 'Карта почти пуста. Заполните её, и PDF станет доступен';

/**
 * A pet's medical card: one document, read from top to bottom.
 *
 * It answers three questions in this order: who this pet is, what asks to be
 * done now, and how far the card is from being complete. Then it becomes the
 * record itself: every block in the order a vet asks in, each with the doors
 * of the owner in its head.
 */
export function MedicalCard() {
  const { id, section } = useParams<{ id: string; section?: string }>();
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const hidden = useHiddenRecords();
  // A card opened by an address of another pet (a link, a notification) makes that pet the chosen one: the bar, the
  // tab and the switcher then say whose card this is.
  const { pets, selectedPetId, selectPet } = usePet();
  useEffect(() => {
    const target = pets.find((p) => p._id === id);
    if (target && target._id !== selectedPetId) selectPet(target);
  }, [id, pets, selectedPetId, selectPet]);

  const query = useQuery({
    ...medicalCardQuery(id!),
    enabled: !!id,
    refetchOnMount: 'always',
  });
  const card = query.data;

  // The address of a part of the card (a link from a notification, the old
  // address of a section) opens the card itself and scrolls to that part.
  useEffect(() => {
    if (!section || !card) return;
    const anchor = document.getElementById(`medcard-${section}`);
    if (anchor) anchor.scrollIntoView({ block: 'start' });
  }, [section, card]);

  const downloadPdf = async () => {
    if (!id || !card || saving) return;
    setSaving(true);
    try {
      if (await medicalCardService.downloadPdf(id, card.pet.name)) showToast.success('Файл сохранён');
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сформировать PDF'));
    } finally {
      setSaving(false);
    }
  };

  if (query.isError) {
    const gone = isPetGone(query.error);
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          {gone ? (
            <EmptyState icon={FileHeart} title="Питомец не найден" description="Возможно, его удалили или у вас нет к нему доступа" actionLabel="К питомцам" onAction={() => navigate('/pets', { replace: true })} />
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
          <MedicalCardSkeleton lines={6} />
        </div>
      </div>
    );
  }

  const checks = readinessChecks(card, id!);
  const doneCount = checks.filter((c) => c.done).length;
  // The two ways to hand the card over: the file, and a link that opens with no sign-in. They
  // stand under the passport, the same place as on the copy a vet opens: the file is downloaded
  // before the visit, and the link is given when the vet asks. On a card that is still nearly
  // empty they stay on the page, disabled, and the line under them says what is missing.
  // The link is the owner's door alone: it opens the card to anyone with the address.
  const canHandOver = doneCount >= 2;
  const isOwner = card.can_edit;

  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <div className="screen-head">
          <h1 className="screen-title display-headline" style={{ fontSize: 'var(--text-display)', fontWeight: 700, margin: 0 }}>Медкарта</h1>
        </div>

        <AppPullToRefresh onRefresh={() => query.refetch()}>
          <CardDocument
            card={card}
            petId={id!}
            hidden={hidden}
            owner
            navigate={(to) => navigate(to)}
            saving={saving}
            onPdf={downloadPdf}
            onShare={isOwner ? () => setShareOpen(true) : undefined}
            handoverBlocked={canHandOver ? undefined : isOwner ? EMPTY_HANDOVER : EMPTY_HANDOVER_COOWNER}
          />
        </AppPullToRefresh>
      </div>

      <MedicalShareSheet visible={shareOpen} petId={id!} petName={card.pet.name} onClose={() => setShareOpen(false)} />
    </div>
  );
}
