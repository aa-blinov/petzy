import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Skeleton } from 'antd-mobile';
import { FileHeart } from 'lucide-react';

import { EmptyState } from '../components/EmptyState';
import { getApiErrorMessage } from '../utils/apiError';
import { medicalShareService } from '../services/medicalShare.service';
import { showToast } from '../utils/toast';
import { OverdueStrip, VetView } from './MedicalCard';
import './MedicalCard.css';

const NO_HIDDEN: ReadonlySet<string> = new Set();
const NO_NAVIGATE = () => undefined;

/**
 * What a vet opens by the link the owner made: the card as the reading mode shows it, and its PDF, with no sign-in and nothing to
 * change. A link that has ended or was taken back says so and tells whom to ask. The page is not offered to search engines.
 */
export function SharedMedicalCard() {
  const { token } = useParams<{ token: string }>();
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
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          <EmptyState heading="h1" icon={FileHeart} title="Ссылка не действует" description="Она закончилась или её отозвали. Попросите владельца питомца прислать новую" />
        </div>
      </div>
    );
  }
  const shared = query.data;
  if (!shared) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding" aria-busy="true">
          <Skeleton.Title animated />
          <Skeleton.Paragraph lineCount={6} animated />
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
  const ends = new Date(shared.expires_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

  const made = new Date(`${card.generated_at.slice(0, 10)}T00:00:00`).toLocaleDateString('ru-RU');

  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <div className="medcard medcard--reading">
          {/* The patient is the title: a page opened from a message names who it is about before anything else. */}
          <h1 className="display-headline" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>{card.pet.name}</h1>
          <VetView
            card={card}
            hidden={NO_HIDDEN}
            saving={saving}
            canPdf
            onPdf={() => void downloadPdf()}
            named={false}
            afterPatient={
              <>
                {/* How old the data is, and until when the page lives, where a vet sees it with what is overdue. */}
                <p className="medcard__stamp medcard__stamp--top">Собрано из записей питомца на {made}. Ссылка действует до {ends}</p>
                <OverdueStrip card={card} petId="" navigate={NO_NAVIGATE} canAct={false} hidden={NO_HIDDEN} />
              </>
            }
          />
        </div>
      </div>
    </div>
  );
}
