import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, ImageViewer, PullToRefresh } from 'antd-mobile';
import { Pencil, Scale, Trash2, Cat, LogOut, FileHeart, Palette } from 'lucide-react';
import { type Pet } from '../services/pets.service';
import { healthRecordsService } from '../services/healthRecords.service';
import { usePet } from '../hooks/usePet';
import { useDeletePet, useLeavePet } from '../hooks/useDeletePet';
import { PendingInvites } from '../components/PendingInvites';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { computePetAge } from '../utils/relativeTime';
import { genderLabel } from '../utils/constants';
import { getSpecies, speciesLabel } from '../utils/species';
import { hapticFeedback } from '../utils/haptic';
import { PetImage } from '../components/PetImage';
import { PetCardSkeleton } from '../components/Skeletons';
import { CardChevron } from '../components/CardChevron';
import { SwipeableRow, type SwipeAction } from '../components/SwipeableRow';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { UserAvatar } from '../components/UserAvatar';
import { Fab } from '../components/Fab';
import { formatAmount } from '../utils/stock';
import { PetDeleteSummary } from '../components/PetDeleteSummary';
import { useHiddenRecords } from '../utils/deferredDelete';

export function Pets() {
  const navigate = useNavigate();
  const { pets, isLoading, isError, refetchPets } = usePet();

  const [deleteDialog, setDeleteDialog] = useState<{ visible: boolean; pet: Pet | null }>({
    visible: false,
    pet: null,
  });
  const [imageViewer, setImageViewer] = useState<{ visible: boolean; image: string | null }>({
    visible: false,
    image: null,
  });

  const queryClient = useQueryClient();

  // A pet deleted a moment ago is already out of the list while «Отменить»
  // is still on offer. With it was the last one, the empty state would come
  // up under the bar and answer «no pets» about a deletion nobody has agreed
  // to yet, so the empty state waits until the bar is gone.
  const hiddenRecords = useHiddenRecords();

  const handleEditPet = (pet: Pet) => navigate(`/pets/${pet._id}/edit`);
  const handleAddPet = () => navigate('/pets/new');
  const handleDeleteClick = (pet: Pet) => setDeleteDialog({ visible: true, pet });

  const deletePet = useDeletePet();
  const leavePet = useLeavePet();
  // The same row action and question: the owner deletes the pet, anyone
  // else only stops seeing it.
  const confirmDelete = async () => {
    const pet = deleteDialog.pet;
    if (!pet) return;
    setDeleteDialog(prev => ({ ...prev, visible: false }));
    const remove = pet.current_user_is_owner ? deletePet : leavePet;
    await remove(pet).catch(() => undefined);
  };
  const leaving = !!deleteDialog.pet && !deleteDialog.pet.current_user_is_owner;

  return (
    <div className="page-container fab-page">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{
          marginBottom: 'var(--spacing-lg)',
          minHeight: '40px',
        }}>
          <h1 className="display-headline" style={{ fontSize: 'var(--text-display)', margin: 0 }}>
            Мои питомцы
          </h1>
        </div>

        <div className="safe-area-padding">
          <PendingInvites />
        </div>

        {isLoading ? (
          <div className="safe-area-padding" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-md)',
            marginTop: 'var(--spacing-sm)',
          }}>
            <PetCardSkeleton />
            <PetCardSkeleton />
          </div>
        ) : isError ? (
          <LoadError what="питомцев" onRetry={refetchPets} />
        ) : pets.length === 0 && hiddenRecords.size === 0 ? (
          <EmptyState
            icon={Cat}
            title="Здесь будут ваши питомцы"
            description="Добавьте первого, и Petzy будет считать кормления, следить за весом и напоминать о лекарствах"
            actionLabel="Добавить питомца"
            onAction={handleAddPet}
          />
        ) : (
          <PullToRefresh
            onRefresh={async () => {
              hapticFeedback('medium');
              await queryClient.invalidateQueries({ queryKey: ['pets'] });
              await queryClient.refetchQueries({ queryKey: ['pets'] });
            }}
            headHeight={48}
          >
            <div className="safe-area-padding" style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--spacing-md)',
              marginTop: 'var(--spacing-sm)',
            }}>
              {pets.map((pet) => (
                <PetCard
                  key={pet._id}
                  pet={pet}
                  onEdit={() => handleEditPet(pet)}
                  onDelete={() => handleDeleteClick(pet)}
                  onImageTap={(url) => setImageViewer({ visible: true, image: url })}
                />
              ))}
            </div>
          </PullToRefresh>
        )}
      </div>

      {/* A pet is added from the bottom right, as everything else in the app. */}
      <Fab label="Добавить питомца" onClick={handleAddPet} />

      <Dialog
        visible={deleteDialog.visible}
        title={leaving ? 'Выйти из доступа' : 'Удаление питомца'}
        content={
          !deleteDialog.pet
            ? ''
            : leaving
              ? `Больше не видеть «${deleteDialog.pet.name}»? Его записи останутся у владельца, он сможет пригласить вас снова`
              : <PetDeleteSummary pet={deleteDialog.pet} />
        }
        onClose={() => setDeleteDialog(prev => ({ ...prev, visible: false }))}
        afterClose={() => setDeleteDialog({ visible: false, pet: null })}
        actions={[
          {
            key: 'delete',
            text: leaving ? 'Выйти' : 'Удалить',
            danger: true,
            onClick: confirmDelete,
          },
          {
            key: 'cancel',
            text: 'Отмена',
            onClick: () => setDeleteDialog(prev => ({ ...prev, visible: false })),
          },
        ]}
      />

      <ImageViewer
        image={imageViewer.image || ''}
        visible={imageViewer.visible}
        onClose={() => setImageViewer(prev => ({ ...prev, visible: false }))}
        afterClose={() => setImageViewer({ visible: false, image: null })}
      />
    </div>
  );
}


/**
 * Pet list row: photo (or species icon), name, meta chips. Tap opens the
 * edit form, swipe edits or deletes.
 */
function PetCard({
  pet,
  onEdit,
  onDelete,
  onImageTap,
}: {
  pet: Pet;
  onEdit: () => void;
  onDelete: () => void;
  onImageTap: (url: string) => void;
}) {
  const navigate = useNavigate();
  const { selectPet } = usePet();
  const age = computePetAge(pet.birth_date ?? '');
  const { icon: SpeciesIcon, gradient: speciesGradient } = getSpecies(pet.species);

  // Most recent weight for the chip — uses the same endpoint as the dashboard.
  const weights = useQuery({
    queryKey: ['pet-summary', 'weight', pet._id],
    queryFn: () => healthRecordsService.getList('weight', pet._id, 1, 1),
    enabled: !!pet._id,
    staleTime: 30_000,
  });
  const lastWeight = weights.data?.items?.[0];

  // Swipe left → delete, swipe right → edit. Matches HistoryItem / MedicationsList.
  const leftAction: SwipeAction = {
    icon: <Pencil size={20} strokeWidth={2.4} />,
    label: 'Изменить',
    color: 'var(--app-accent)',
    onTrigger: onEdit,
  };
  // Only the owner can delete a pet (the backend refuses anyone else);
  // someone it's shared with gets «Выйти» in the same place instead.
  const rightAction: SwipeAction = pet.current_user_is_owner
    ? {
        icon: <Trash2 size={20} strokeWidth={2.4} />,
        label: 'Удалить',
        color: 'var(--app-danger-color)',
        onTrigger: onDelete,
      }
    : {
        icon: <LogOut size={20} strokeWidth={2.4} />,
        label: 'Выйти',
        color: 'var(--app-danger-color)',
        onTrigger: onDelete,
      };

  const Avatar = pet.photo_url ? 'button' : 'div';

  return (
    <SwipeableRow leftAction={leftAction} rightAction={rightAction} itemLabel={pet.name}>
      {/* Tap opens the edit form; swiping is the shortcut to edit or
          delete. The photo opens on its own tap. A button, not a div with
          a click: the card was unreachable with a keyboard and read as
          plain text by a screen reader. */}
      <button
        type="button"
        className="card-soft card-soft--interactive"
        aria-label={`Изменить питомца ${pet.name}`}
        style={{ padding: '16px', cursor: 'pointer', width: '100%', font: 'inherit', color: 'inherit', textAlign: 'left' }}
        onClick={onEdit}
      >
        <div style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
          {/* Square avatar — image if available, else species icon on
              its gradient tile. Same treatment as PetSummaryCard on the
              dashboard, just without the кормление/вес row below — this
              list is for managing pets, not logging events. */}
          <Avatar
            // With a photo the avatar is a button of its own that opens the photo, not the edit form. Without one it is
            // only a picture: a button that does nothing and has no name is what a screen reader read as «кнопка».
            {...(pet.photo_url
              ? {
                  type: 'button' as const,
                  onClick: (e: React.MouseEvent) => {
                    e.stopPropagation();
                    onImageTap(pet.photo_url as string);
                  },
                  'aria-label': `Открыть фото ${pet.name}`,
                }
              : { 'aria-hidden': true })}
            style={{
              position: 'relative',
              flexShrink: 0,
              width: '96px',
              height: '96px',
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
              padding: 0,
              border: 'none',
              background: 'none',
              cursor: pet.photo_url ? 'pointer' : 'default',
            }}
          >
            <div
              style={{
                position: 'absolute',
                inset: 0,
                backgroundColor: 'var(--tile-brown)',
                backgroundImage: pet.photo_url ? undefined : speciesGradient,
              }}
            />
            {pet.photo_url ? (
              <PetImage
                src={pet.photo_url}
                alt={pet.name}
                size={96}
                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 0, cursor: 'pointer' }}
              />
            ) : (
              <div
                aria-hidden
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--app-text-on-dark)',
                  opacity: 0.9,
                }}
              >
                <SpeciesIcon size={40} strokeWidth={1.5} style={{ display: 'block' }} />
              </div>
            )}
          </Avatar>

          {/* Right column — name, age/breed/gender summary, weight chip.
              Stretched to the avatar's full height and spread with
              space-between instead of a tight centered cluster, so the
              card doesn't read as a compact block floating in a much
              taller photo frame. */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div
              className="display-headline"
              style={{
                fontSize: 'var(--text-xl)',
                fontWeight: 700,
                // Two lines before a cut: «Александр Македонский…» is still a name.
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                overflowWrap: 'anywhere',
              }}
            >
              {pet.name}
            </div>
            <div
              style={{
                fontSize: 'var(--text-sm)',
                color: 'var(--app-text-secondary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {/* Nothing known yet: at least what animal it is, not a lone dash. */}
              {[age, pet.breed, genderLabel(pet.gender)].filter(Boolean).join(', ') || speciesLabel(pet.species) || 'Возраст и порода не указаны'}
            </div>
            {/* Every chip of the pet on a line that wraps: two to a row where they fit, not one under another. */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-sm)', alignItems: 'flex-start' }}>
            {lastWeight && (
              <span
                className="chip"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: 'var(--text-xs)',
                  // A full pill next to the avatar's soft rounded-square
                  // photo read as two different shape languages in the
                  // same small card — this matches the avatar's corner
                  // instead.
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <Scale size={13} strokeWidth={2.2} style={{ display: 'block' }} />
                {formatAmount(Number(lastWeight.fields?.weight))} кг
              </span>
            )}
              <button
                type="button"
                className="chip touch-target"
                onClick={(e) => {
                  e.stopPropagation(); // the card itself opens the edit form
                  navigate(`/pets/${pet._id}/medical-card`);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <FileHeart size={13} strokeWidth={2.2} style={{ display: 'block' }} aria-hidden />
                Медкарта
              </button>
              {/* The look is the owner's to set, and it is set for the pet that is selected: choose it, then open the settings. */}
              {pet.current_user_is_owner && (
                <button
                  type="button"
                  className="chip touch-target"
                  aria-label={`Оформление: ${pet.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    selectPet(pet);
                    navigate('/pet-look');
                  }}
                  style={{
                      display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  <Palette size={13} strokeWidth={2.2} style={{ display: 'block' }} aria-hidden />
                  Оформление
                </button>
              )}
            {/* Nothing indicated a pet was shared anywhere outside its own
                edit form — an owner had no quick way to see at a glance
                which of their pets someone else already has access to.
                Owner-only, like the sharing form itself (PetForm.tsx) —
                a shared (non-owner) user isn't shown who else has access. */}
            {/* A pet someone shared with me: whose it is, since only its owner can change it or delete it. */}
            {pet.current_user_is_owner === false && pet.owner && (
              <span
                className="chip"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: 'var(--text-xs)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <UserAvatar username={pet.owner} size={16} />
                {`Владелец: ${pet.owner}`}
              </span>
            )}
            {pet.current_user_is_owner && pet.shared_with && pet.shared_with.length > 0 && (
              <span
                className="chip"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: 'var(--text-xs)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <div style={{ display: 'flex' }}>
                  {pet.shared_with.slice(0, 3).map((username, i) => (
                    <UserAvatar
                      key={username}
                      username={username}
                      size={16}
                      style={i > 0 ? { marginLeft: -4, border: '1.5px solid var(--app-card-background)' } : undefined}
                    />
                  ))}
                  {pet.shared_with.length > 3 && (
                    <span style={{ marginLeft: 'var(--spacing-xs)' }}>+{pet.shared_with.length - 3}</span>
                  )}
                </div>
                {`Общий доступ${pet.shared_with.length > 1 ? ` (${pet.shared_with.length})` : ''}`}
              </span>
            )}
            </div>
          </div>
          <span style={{ alignSelf: 'center' }}><CardChevron /></span>
        </div>
      </button>
    </SwipeableRow>
  );
}
