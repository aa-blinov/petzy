import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileHeart } from 'lucide-react';

import { CardDocument } from './MedicalCardDocument';
import { EmptyState } from '../components/EmptyState';
import { getApiErrorMessage } from '../utils/apiError';
import { httpStatus } from '../services/api';
import { formatShareEnd, medicalShareService } from '../services/medicalShare.service';
import { showToast } from '../utils/toast';
import { MedicalCardSkeleton } from '../components/Skeletons';
import './MedicalCard.css';

const NO_HIDDEN: ReadonlySet<string> = new Set();

/**
 * What a vet opens by the link the owner made: the card as it is, and its PDF, with no sign-in and nothing to
 * change. A link that has ended or was taken back says so and tells whom to ask. The page is not offered to search engines.
 *
 * The person who made the link is often the owner, and they open it on their own phone to show it to a vet. The copy itself
 * stays a copy (no header, no tabs, nothing to change), but the server names the pet when the visitor is signed in and may
 * see it, and then the page offers the way back into the app. Without a session there is no button: the link opens the card
 * and nothing else.
 */
export function SharedMedicalCard() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const query = useQuery({ queryKey: ['shared-medical-card', token], queryFn: () => medicalShareService.open(token!), enabled: !!token, retry: false, staleTime: 0, gcTime: 0 });

  useEffect(() => {
    const meta = document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex, nofollow, noarchive';
    document.head.appendChild(meta);
    return () => {
      meta.remove();
    };
  }, []);

  if (query.isError) {
    // Two things look the same from a phone: a link that stopped working and a connection that did not come through.
    // Telling them apart matters: the first asks the owner for a new link, the second only asks to try again.
    const dead = [403, 404].includes(httpStatus(query.error) ?? 0);
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          {dead ? (
            <EmptyState heading="h1" icon={FileHeart} title="Ссылка не действует" description="Она закончилась или её отозвали. Попросите владельца питомца прислать новую" />
          ) : (
            <EmptyState
              heading="h1"
              icon={FileHeart}
              title="Не удалось загрузить карту"
              description="Похоже, нет связи. Это не значит, что ссылка не действует: попробуйте ещё раз"
              actionLabel="Повторить"
              onAction={() => void query.refetch()}
            />
          )}
        </div>
      </div>
    );
  }
  const shared = query.data;
  if (!shared) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding" aria-busy="true">
          <MedicalCardSkeleton lines={6} />
        </div>
      </div>
    );
  }

  const { card } = shared;
  const downloadPdf = async () => {
    if (saving) return;
    setSaving(true);
    try {
      if (await medicalShareService.downloadPdf(token!, card.pet.name)) showToast.success('PDF сохранён');
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сформировать PDF'));
    } finally {
      setSaving(false);
    }
  };
  const ends = formatShareEnd(shared.expires_at);

  const made = new Date(`${card.generated_at.slice(0, 10)}T00:00:00`).toLocaleDateString('ru-RU');

  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        {/* The patient is the title: a page opened from a message names who it is about before anything else.
            And what the page is, once, over the name: the copy has no bar to name the pet, so the name
            stands in the title, and the kind of document says itself above it. */}
        <div className="screen-head" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-accent-deep)', marginBottom: 'var(--spacing-xs)' }}>
            Медкарта
          </div>
          <h1 className="screen-title display-headline" style={{ fontSize: 'var(--text-display)', fontWeight: 700, margin: 0 }}>{card.pet.name}</h1>
        </div>
        <CardDocument
          card={card}
          petId={shared.pet_id ?? ''}
          hidden={NO_HIDDEN}
          owner={false}
          shared
          navigate={() => undefined}
          onPdf={() => void downloadPdf()}
          saving={saving}
          afterPassport={
            <>
              {/* How old the data is, and until when the page lives, where a vet sees it with what is overdue. */}
              <p className="medcard__stamp medcard__stamp--top">Собрано из записей питомца на {made}. Ссылка действует до {ends}</p>
            </>
          }
        />
        {/* What this page is, once, at the end: a copy. The way back into the app is only for the person who has a session. */}
        <p className="medcard__hint">
          {shared.pet_id
            ? 'Это копия медкарты питомца на момент отправки ссылки. В приложении она живая: там пишут и смотрят'
            : 'Это копия медкарты питомца на момент отправки ссылки. Вернуться в приложение из неё нельзя'}
        </p>
        {shared.pet_id && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-lg)' }}>
            <button type="button" className="medcard__link medcard__back touch-target" onClick={() => navigate(`/pets/${shared.pet_id}/medical-card`)}>
              Медицинская карта
            </button>
          </div>
        )}
        {/* Once, at the very bottom, in the visitor's own words: what the page is and where it must not go. */}
        <p className="medcard__hint" data-testid="share-private">
          Это личные данные питомца. Не пересылайте ссылку
        </p>
      </div>
    </div>
  );
}
