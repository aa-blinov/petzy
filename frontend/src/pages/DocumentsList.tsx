import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Dialog, ImageViewer, PullToRefresh, SearchBar } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import { FileText, Pencil, Trash2, X } from 'lucide-react';

import { usePet } from '../hooks/usePet';
import { useAuth } from '../hooks/useAuth';
import { hapticFeedback } from '../utils/haptic';
import { formatRelativeDateTime, parseRecordDate } from '../utils/relativeTime';
import { formatFileSize } from '../utils/fileSize';
import { showToast } from '../utils/toast';
import {
  documentsService,
  DOCUMENT_CATEGORY_LABELS,
  type DocumentCategory,
  type PetDocument,
} from '../services/documents.service';
import { SwipeableRow } from '../components/SwipeableRow';
import { EmptyState } from '../components/EmptyState';
import { UserAvatar } from '../components/UserAvatar';
import { SkeletonList, MedicationCardSkeleton } from '../components/Skeletons';

/**
 * Category display order — the insertion order of DOCUMENT_CATEGORY_LABELS,
 * so adding a category there is enough; nothing here needs to stay in sync
 * by hand.
 */
const CATEGORY_ORDER = Object.keys(DOCUMENT_CATEGORY_LABELS) as DocumentCategory[];

/**
 * One badge per format this app accepts (see ALLOWED_CONTENT_TYPES in
 * web/documents.py) — always a short text label, never an actual image
 * preview: a cropped 40×40 thumbnail of a real photo (especially a
 * mostly-white infographic or a scanned document) reads as an
 * unrecognisable blur. Every format gets its own colour so the list
 * reads at a glance, uniformly — no format singled out as "the icon
 * one" while the rest get text.
 */
const FORMAT_BADGES: Record<string, { label: string; bg: string; fg: string }> = {
  jpeg: { label: 'JPG', bg: 'var(--app-info-soft)', fg: 'var(--app-info-text)' },
  png: { label: 'PNG', bg: 'var(--app-violet-soft)', fg: 'var(--app-violet-text)' },
  webp: { label: 'WEBP', bg: 'var(--app-success-soft)', fg: 'var(--app-success-text)' },
  heic: { label: 'HEIC', bg: 'var(--app-warning-soft)', fg: 'var(--app-warning-text)' },
  heif: { label: 'HEIF', bg: 'var(--app-warning-soft)', fg: 'var(--app-warning-text)' },
  pdf: { label: 'PDF', bg: 'var(--app-danger-soft)', fg: 'var(--app-danger-text)' },
};
const DEFAULT_FORMAT_BADGE = { label: 'FILE', bg: 'var(--app-accent-soft)', fg: 'var(--app-accent-deep)' };

/** Scans read as film: the page's own text and ground swapped, so the
 *  chip is dark on a light theme and light on a dark one. The label is
 *  the archive's extension (".tar.gz" and ".tgz" share a content type). */
const SCAN_BADGE_COLORS = { bg: 'var(--app-text-color)', fg: 'var(--app-page-background)' };

function scanBadgeLabel(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.tar.gz') || lower.endsWith('.tgz')) return 'TGZ';
  if (lower.endsWith('.dcm')) return 'DCM';
  return lower.split('.').pop()?.toUpperCase().slice(0, 4) || 'ZIP';
}

function formatBadge(doc: PetDocument) {
  if (doc.scan) return { ...SCAN_BADGE_COLORS, label: scanBadgeLabel(doc.original_filename) };
  const subtype = doc.content_type.split('/')[1]?.toLowerCase() ?? '';
  return FORMAT_BADGES[subtype] ?? { ...DEFAULT_FORMAT_BADGE, label: subtype ? subtype.toUpperCase().slice(0, 4) : 'FILE' };
}

/** How many days out "expiring soon" starts — matches the backend's own
 *  DOCUMENT_EXPIRY_REMINDER_DAYS_BEFORE in send_medication_reminders.py,
 *  so the badge that turns orange here is the same window that triggers
 *  a push notification, not two independently-tuned thresholds. */
const EXPIRY_WARNING_DAYS = 14;

function describeExpiry(expiresAt: string): { text: string; color: string; bg: string } | null {
  const expiryDate = parseRecordDate(expiresAt);
  if (!expiryDate) return null;

  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startOfExpiry = new Date(expiryDate.getFullYear(), expiryDate.getMonth(), expiryDate.getDate());
  const daysUntil = Math.round((startOfExpiry.getTime() - startOfToday.getTime()) / 86_400_000);
  const formatted = expiryDate.toLocaleDateString('ru-RU');

  if (daysUntil < 0) {
    return { text: `Истёк ${formatted}`, color: 'var(--app-danger-text)', bg: 'var(--app-danger-soft)' };
  }
  if (daysUntil <= EXPIRY_WARNING_DAYS) {
    return { text: `Истекает ${formatted}`, color: 'var(--app-warning-text)', bg: 'var(--app-warning-soft)' };
  }
  return { text: `До ${formatted}`, color: 'var(--app-text-tertiary)', bg: 'var(--app-accent-soft)' };
}

export function DocumentsList() {
  const { selectedPetId } = usePet();
  const { username: currentUsername } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState('');
  const [deleteDialog, setDeleteDialog] = useState<{ visible: boolean; document: PetDocument | null }>({
    visible: false,
    document: null,
  });
  const [imageViewer, setImageViewer] = useState<{ visible: boolean; image: string | null }>({
    visible: false,
    image: null,
  });
  // Non-image documents (PDFs) open in an in-app viewer rather than a new
  // tab or a same-tab navigation — window.open is unreliable here (a popup
  // blocker can silently swallow it, and installed as a PWA there is often
  // no browser chrome to open a tab in at all), and navigating away loses
  // the whole SPA. An <iframe> keeps the user on this screen and works
  // everywhere a browser can render a PDF at all.
  const [fileViewer, setFileViewer] = useState<{ visible: boolean; url: string | null; title: string }>({
    visible: false,
    url: null,
    title: '',
  });

  // Esc closes whichever viewer is open. Needed most for the image
  // viewer: it has no close button of its own and normally relies on
  // tapping the image to dismiss — which does nothing when the "image"
  // is a format the browser can't decode (HEIC, most places outside
  // Safari) and never actually renders, leaving no tap target at all.
  useEffect(() => {
    if (!imageViewer.visible && !fileViewer.visible) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setImageViewer((prev) => (prev.visible ? { ...prev, visible: false } : prev));
      setFileViewer((prev) => (prev.visible ? { ...prev, visible: false } : prev));
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [imageViewer.visible, fileViewer.visible]);

  const {
    data: documents = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['documents', selectedPetId],
    queryFn: () => documentsService.getList(selectedPetId!).then((res) => res.documents),
    enabled: !!selectedPetId,
  });

  const searchedDocuments = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return documents;
    return documents.filter((doc) => doc.title.toLowerCase().includes(q));
  }, [documents, searchQuery]);

  // Sections replace the old category filter — with the handful of
  // documents a pet typically has, always showing every category beats
  // hiding them behind a filter sheet the user has to open first.
  // Categories with no matching documents (right now, or under the
  // current search) are skipped rather than shown as empty sections.
  const groupedDocuments = useMemo(() => {
    const byCategory = new Map<DocumentCategory, PetDocument[]>();
    for (const doc of searchedDocuments) {
      const list = byCategory.get(doc.category);
      if (list) list.push(doc);
      else byCategory.set(doc.category, [doc]);
    }
    return CATEGORY_ORDER
      .map((category) => [category, byCategory.get(category) ?? []] as const)
      .filter(([, docs]) => docs.length > 0);
  }, [searchedDocuments]);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      showToast.success('Документ удалён');
    },
  });

  const handleDelete = (doc: PetDocument) => {
    hapticFeedback('light');
    setDeleteDialog({ visible: true, document: doc });
  };

  const handleOpen = (doc: PetDocument) => {
    hapticFeedback('light');
    const url = documentsService.getFileUrl(doc._id);
    if (doc.scan) {
      // An archive has nothing to preview: the server answers with a
      // short-lived link to the file in storage, sent as a download, so
      // the app stays where it is.
      window.location.assign(url);
      showToast.info('Скачиваем архив');
      return;
    }
    if (doc.content_type.startsWith('image/')) {
      setImageViewer({ visible: true, image: url });
    } else {
      setFileViewer({ visible: true, url, title: doc.title });
    }
  };

  if (!selectedPetId) {
    return (
      <div style={{ minHeight: '100vh', padding: 'var(--spacing-lg)' }}>
        <p>Выберите питомца в меню навигации, чтобы посмотреть документы</p>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div
          className="safe-area-padding"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 'var(--spacing-lg)',
            minHeight: '40px',
          }}
        >
          <h1 className="display-headline" style={{ fontSize: '28px', margin: 0 }}>
            Документы
          </h1>
          <button
            type="button"
            className="touch-target"
            onClick={() => navigate('/documents/new')}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--app-accent-deep)',
              fontWeight: 600,
              fontSize: 'var(--text-sm)',
              cursor: 'pointer',
              padding: '8px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <AddOutline style={{ fontSize: 20 }} />
            Добавить
          </button>
        </div>

        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-md)' }}>
          <SearchBar
            placeholder="Поиск по названию"
            value={searchQuery}
            onChange={setSearchQuery}
            onClear={() => setSearchQuery('')}
          />
        </div>

        {isLoading ? (
          <SkeletonList count={3} render={() => <MedicationCardSkeleton />} />
        ) : documents.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Здесь будут документы питомца"
            description="Справки о прививках, анализы, снимки МРТ и КТ, страховка в одном месте"
            actionLabel="Добавить документ"
            onAction={() => navigate('/documents/new')}
          />
        ) : searchedDocuments.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Ничего не найдено"
            description="Попробуйте изменить запрос"
          />
        ) : (
          <PullToRefresh
            onRefresh={async () => {
              hapticFeedback('medium');
              await refetch();
            }}
            headHeight={48}
          >
            <div
              className="safe-area-padding"
              style={{ marginTop: 'var(--spacing-sm)' }}
            >
              {groupedDocuments.map(([category, docs]) => (
                <div key={category} style={{ marginBottom: 'var(--spacing-lg)' }}>
                  <h2 className="section-header" style={{ marginBottom: '10px', paddingLeft: 4 }}>
                    {DOCUMENT_CATEGORY_LABELS[category]}
                  </h2>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
                    {docs.map((doc) => {
                      // Preview reflects the file's actual format — the
                      // category already reads from the section header above.
                      const badge = formatBadge(doc);
                      const expiry = doc.expires_at ? describeExpiry(doc.expires_at) : null;
                      return (
                        <SwipeableRow
                          key={doc._id}
                          itemLabel={doc.title}
                          openAction={{ label: doc.scan ? 'Скачать' : 'Открыть', onTrigger: () => handleOpen(doc) }}
                          leftAction={{
                            icon: <Pencil size={20} strokeWidth={2.4} />,
                            label: 'Изменить',
                            color: 'var(--app-accent)',
                            onTrigger: () => navigate(`/documents/${doc._id}/edit`),
                          }}
                          rightAction={{
                            icon: <Trash2 size={20} strokeWidth={2.4} />,
                            label: 'Удалить',
                            color: 'var(--app-danger-color)',
                            onTrigger: () => handleDelete(doc),
                          }}
                        >
                          <Card
                            className="card-soft card-soft--interactive"
                            style={{ borderRadius: 'var(--radius-md)', border: 'none', padding: 0, cursor: 'pointer' }}
                            onClick={() => handleOpen(doc)}
                          >
                            <div style={{ padding: 'var(--spacing-lg)', display: 'flex', gap: 'var(--spacing-md)' }}>
                              <div
                                aria-hidden
                                style={{
                                  width: 40,
                                  height: 40,
                                  borderRadius: 12,
                                  background: badge.bg,
                                  color: badge.fg,
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  flexShrink: 0,
                                  fontSize: 10,
                                  fontWeight: 700,
                                  letterSpacing: '0.02em',
                                }}
                              >
                                {badge.label}
                              </div>
                              <div style={{ minWidth: 0, flex: 1 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', flexWrap: 'wrap' }}>
                                  <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 600 }}>{doc.title}</h3>
                                  {expiry && (
                                    <span
                                      style={{
                                        fontSize: 'var(--text-xs)',
                                        fontWeight: 600,
                                        color: expiry.color,
                                        background: expiry.bg,
                                        padding: '2px 8px',
                                        borderRadius: 'var(--radius-sm)',
                                        whiteSpace: 'nowrap',
                                      }}
                                    >
                                      {expiry.text}
                                    </span>
                                  )}
                                </div>
                                <p
                                  style={{
                                    margin: '2px 0 0',
                                    fontSize: 'var(--text-sm)',
                                    color: 'var(--app-text-secondary)',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                >
                                  {doc.original_filename}
                                </p>
                                <p
                                  style={{
                                    margin: '4px 0 0',
                                    fontSize: 'var(--text-xs)',
                                    color: 'var(--app-text-tertiary)',
                                    fontVariantNumeric: 'tabular-nums',
                                  }}
                                >
                                  {formatRelativeDateTime(doc.created_at)}
                                  {doc.file_size > 0 && ` · ${formatFileSize(doc.file_size)}`}
                                </p>
                                {doc.username && doc.username !== currentUsername && (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      navigate(`/users/${doc.username}`);
                                    }}
                                    style={{
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: '6px',
                                      marginTop: '4px',
                                      background: 'none',
                                      border: 'none',
                                      padding: 0,
                                      cursor: 'pointer',
                                      font: 'inherit',
                                      fontSize: 'var(--text-xs)',
                                      color: 'var(--app-text-tertiary)',
                                    }}
                                  >
                                    <UserAvatar username={doc.username} size={16} />
                                    Добавил(а) {doc.username}
                                  </button>
                                )}
                              </div>
                            </div>
                          </Card>
                        </SwipeableRow>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </PullToRefresh>
        )}
      </div>

      <ImageViewer
        image={imageViewer.image || ''}
        visible={imageViewer.visible}
        onClose={() => setImageViewer((prev) => ({ ...prev, visible: false }))}
        afterClose={() => setImageViewer({ visible: false, image: null })}
      />

      {/* ImageViewer ships no close button of its own — dismissing relies
          on tapping the image, which is exactly what doesn't work for a
          format the browser can't decode (HEIC, outside Safari): nothing
          ever renders, so there's no tap target and the viewer is stuck
          open. A explicit close button doesn't depend on the image
          having loaded. Portalled to <body> at a higher z-index than
          antd's own mask (1000) for the same reason as the file viewer
          below — RouteTransition's stacking context would otherwise
          bury it under the Navbar. */}
      {imageViewer.visible && createPortal(
        <button
          type="button"
          onClick={() => {
            hapticFeedback('light');
            setImageViewer((prev) => ({ ...prev, visible: false }));
          }}
          className="touch-target"
          aria-label="Закрыть"
          style={{
            position: 'fixed',
            top: 'calc(env(safe-area-inset-top) + var(--spacing-md))',
            right: 'var(--spacing-md)',
            zIndex: 1001,
            background: 'rgba(0, 0, 0, 0.5)',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '50%',
            width: 36,
            height: 36,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
        >
          <X size={20} strokeWidth={2.4} />
        </button>,
        document.body,
      )}

      {fileViewer.visible && createPortal(
        <div
          style={{
            position: 'fixed',
            inset: 0,
            // The page content sits inside RouteTransition, whose slide
            // animation transforms it — that opens a new stacking
            // context while it runs, so a z-index here would
            // only ever compete within it and never actually beat the
            // Navbar's fixed z-index:1000 sitting outside it. Portalling
            // to <body> escapes that context entirely, same as antd-mobile's
            // own ImageViewer/Dialog/Popup already do for this exact reason.
            zIndex: 1001,
            background: 'var(--app-page-background)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 'var(--spacing-md)',
              padding: 'var(--spacing-md) var(--spacing-lg)',
              paddingTop: 'calc(env(safe-area-inset-top) + var(--spacing-md))',
              flexShrink: 0,
            }}
          >
            <h3
              style={{
                margin: 0,
                fontSize: 'var(--text-md)',
                fontWeight: 600,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {fileViewer.title}
            </h3>
            <button
              type="button"
              onClick={() => {
                hapticFeedback('light');
                setFileViewer({ visible: false, url: null, title: '' });
              }}
              className="touch-target"
              aria-label="Закрыть"
              style={{
                background: 'var(--app-accent-soft)',
                color: 'var(--app-text-color)',
                border: 'none',
                borderRadius: '50%',
                width: 32,
                height: 32,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              <X size={18} strokeWidth={2.4} />
            </button>
          </div>
          {fileViewer.url && (
            <iframe
              src={fileViewer.url}
              title={fileViewer.title}
              style={{ flex: 1, width: '100%', border: 'none' }}
            />
          )}
        </div>,
        document.body,
      )}

      <Dialog
        visible={deleteDialog.visible}
        title="Удаление документа"
        content={deleteDialog.document && <span>Удалить документ «{deleteDialog.document.title}»?</span>}
        onClose={() => setDeleteDialog((prev) => ({ ...prev, visible: false }))}
        afterClose={() => setDeleteDialog({ visible: false, document: null })}
        actions={[
          {
            key: 'delete',
            text: 'Удалить',
            danger: true,
            onClick: () => {
              if (deleteDialog.document) deleteMutation.mutate(deleteDialog.document._id);
              setDeleteDialog((prev) => ({ ...prev, visible: false }));
            },
          },
          {
            key: 'cancel',
            text: 'Отмена',
            onClick: () => setDeleteDialog((prev) => ({ ...prev, visible: false })),
          },
        ]}
      />
    </div>
  );
}
