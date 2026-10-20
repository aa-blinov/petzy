import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileHeart, Download, Link2, Loader2 } from 'lucide-react';

import { MedicalShareSheet } from '../components/MedicalShareSheet';
import { CardDocument } from './MedicalCardDocument';
import { medicalCardQuery, medicalCardService } from '../services/medicalCard.service';
import { readinessChecks } from '../utils/medicalReadiness';
import { useHiddenRecords } from '../utils/deferredDelete';
import { usePet } from '../hooks/usePet';
import { LoadError } from '../components/LoadError';
import { EmptyState } from '../components/EmptyState';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { httpStatus } from '../services/api';
import { MedicalCardSkeleton } from '../components/Skeletons';
import './MedicalCard.css';

/** The two ways to hand the card over are on the card from the start; on an empty one there is nothing to hand, and the
    line under the heading says so instead of the block appearing out of nowhere later. */
const EMPTY_HANDOVER = 'Карта почти пуста. Заполните её, и здесь появятся PDF и ссылка для врача';
/** A co-owner reads the card here already, so the link to give away is closed to them: the file is what is left. */
const EMPTY_HANDOVER_COOWNER = 'Карта почти пуста. Заполните её, и здесь появится PDF';

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
          <MedicalCardSkeleton lines={6} />
        </div>
      </div>
    );
  }

  const checks = readinessChecks(card, id!);
  const doneCount = checks.filter((c) => c.done).length;
  // The two ways to hand the card over: the file, and a link that opens with
  // no sign-in. They are there from the start: on an empty card the bar is not
  // there yet, and the line at the foot says what is missing instead. The link
  // is the owner's door alone: it opens the card to anyone with the address.
  const canHandOver = doneCount >= 2;
  const isOwner = card.can_edit;
  const photoUrl = pets.find((p) => p._id === id)?.photo_url ?? null;

  return (
    <div className="page-container">
      <div className={`max-width-container safe-area-padding${canHandOver ? ' medcard-page--bar' : ''}`}>
        <div className="screen-head">
          <h1 className="screen-title display-headline" style={{ fontSize: 'var(--text-display)', fontWeight: 700, margin: 0 }}>Медкарта</h1>
        </div>

        <CardDocument
          card={card}
          petId={id!}
          hidden={hidden}
          owner
          navigate={(to) => navigate(to)}
          saving={saving}
          photoUrl={photoUrl}
        />

        {!canHandOver && (
          <p className="medcard__empty medcard__handover-empty">{isOwner ? EMPTY_HANDOVER : EMPTY_HANDOVER_COOWNER}</p>
        )}
      </div>

      {/* The file and the link, always within reach: they are what the card is for. */}
      {canHandOver && (
        <div className="medcard__bar">
          <button type="button" className="medcard__bar-button" onClick={downloadPdf} disabled={saving} aria-busy={saving}>
            {saving ? (
              <Loader2 size={18} strokeWidth={2.2} className="medcard__spin" aria-hidden />
            ) : (
              <Download size={18} strokeWidth={2.2} aria-hidden />
            )}
            Скачать PDF
          </button>
          {isOwner && (
            <button type="button" className="medcard__bar-button" onClick={() => setShareOpen(true)}>
              <Link2 size={18} strokeWidth={2.2} aria-hidden />
              Ссылка для врача
            </button>
          )}
        </div>
      )}

      <MedicalShareSheet visible={shareOpen} petId={id!} petName={card.pet.name} onClose={() => setShareOpen(false)} />
    </div>
  );
}
