import { useState, useMemo } from 'react';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate } from 'react-router-dom';
import { Dialog, ImageViewer, PullToRefresh } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import { Pencil, Scale, Trash2, Cat } from 'lucide-react';
import { petsService, type Pet } from '../services/pets.service';
import { healthRecordsService } from '../services/healthRecords.service';
import { usePet } from '../hooks/usePet';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { computePetAge } from '../utils/relativeTime';
import {
  speciesIconMap,
  SPECIES_FALLBACK_ICON,
  speciesGradientMap,
  SPECIES_GRADIENT_FALLBACK,
  genderLabel,
} from '../utils/constants';
import { hapticFeedback } from '../utils/haptic';
import { PetImage } from '../components/PetImage';
import { PetCardSkeleton } from '../components/Skeletons';
import { SwipeableRow, type SwipeAction } from '../components/SwipeableRow';
import { EmptyState } from '../components/EmptyState';
import { UserAvatar } from '../components/UserAvatar';

export function Pets() {
  const navigate = useNavigate();
  const { pets, selectPet, getSelectedPet, isLoading } = usePet();

  const [deleteDialog, setDeleteDialog] = useState<{ visible: boolean; pet: Pet | null }>({
    visible: false,
    pet: null,
  });
  const [imageViewer, setImageViewer] = useState<{ visible: boolean; image: string | null }>({
    visible: false,
    image: null,
  });

  const queryClient = useQueryClient();

  const handleEditPet = (pet: Pet) => navigate(`/pets/${pet._id}/edit`);
  const handleAddPet = () => navigate('/pets/new');
  const handleDeleteClick = (pet: Pet) => setDeleteDialog({ visible: true, pet });

  const confirmDelete = async () => {
    const pet = deleteDialog.pet;
    if (!pet) return;

    try {
      const wasSelected = getSelectedPet?._id === pet._id;
      const currentPetIndex = pets.findIndex(p => p._id === pet._id);

      await petsService.deletePet(pet._id);
      setDeleteDialog(prev => ({ ...prev, visible: false }));

      const updatedPets = await petsService.getPets();
      queryClient.setQueryData(['pets'], updatedPets);

      if (wasSelected && updatedPets.length > 0) {
        const nextPetIndex = currentPetIndex >= updatedPets.length ? updatedPets.length - 1 : currentPetIndex;
        selectPet(updatedPets[nextPetIndex]);
      } else if (updatedPets.length === 0) {
        selectPet(null);
      }

      showToast.success('Питомец удалён');
    } catch (error) {
      console.error('Delete pet error:', error);
      setDeleteDialog(prev => ({ ...prev, visible: false }));
      const errorMessage = getApiErrorMessage(error, 'Не удалось удалить');
      showToast.failure(errorMessage);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{
          marginBottom: 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px',
        }}>
          <h1 className="display-headline" style={{ fontSize: '28px', margin: 0 }}>
            Мои питомцы
          </h1>
          <button
            type="button"
            onClick={handleAddPet}
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
        ) : pets.length === 0 ? (
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

      <Dialog
        visible={deleteDialog.visible}
        title="Удаление питомца"
        content={deleteDialog.pet ? `Вы уверены, что хотите удалить «${deleteDialog.pet.name}»?` : ''}
        onClose={() => setDeleteDialog(prev => ({ ...prev, visible: false }))}
        afterClose={() => setDeleteDialog({ visible: false, pet: null })}
        actions={[
          {
            key: 'delete',
            text: 'Удалить',
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
 * Pet list row — hero photo (or species icon) + headline name + meta chips
 * + a discrete edit pencil. Delete is hidden behind a long-press.
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
  const age = computePetAge(pet.birth_date ?? '');
  const SpeciesIcon = useMemo(() => {
    if (!pet.species) return SPECIES_FALLBACK_ICON;
    const key = pet.species.toLowerCase().trim();
    return speciesIconMap[key] ?? SPECIES_FALLBACK_ICON;
  }, [pet.species]);
  const speciesGradient = useMemo(() => {
    if (!pet.species) return SPECIES_GRADIENT_FALLBACK;
    const key = pet.species.toLowerCase().trim();
    return speciesGradientMap[key] ?? SPECIES_GRADIENT_FALLBACK;
  }, [pet.species]);

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
  // Only the owner can delete a pet (the backend rejects a shared user's
  // attempt outright) — offering the swipe action to everyone just let a
  // shared user discover that the hard way. The legacy app hid the same
  // button behind this exact check.
  const rightAction: SwipeAction | undefined = pet.current_user_is_owner
    ? {
        icon: <Trash2 size={20} strokeWidth={2.4} />,
        label: 'Удалить',
        color: 'var(--app-danger-color)',
        onTrigger: onDelete,
      }
    : undefined;

  return (
    <SwipeableRow leftAction={leftAction} rightAction={rightAction}>
      {/* Editing and deleting are swipe actions. No .tap-ripple here on
          purpose: the card has no tap action, so a press animation would
          promise something that never happens. */}
      <div className="card-soft card-soft--interactive" style={{ padding: '16px' }}>
        <div style={{ display: 'flex', gap: 'var(--spacing-md)' }}>
          {/* Square avatar — image if available, else species icon on
              its gradient tile. Same treatment as PetSummaryCard on the
              dashboard, just without the кормление/вес row below — this
              list is for managing pets, not logging events. */}
          <button
            type="button"
            onClick={() => pet.photo_url && onImageTap(pet.photo_url)}
            disabled={!pet.photo_url}
            aria-label={pet.photo_url ? `Открыть фото ${pet.name}` : undefined}
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
                size={200}
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
                  color: '#FFFFFF',
                  opacity: 0.9,
                }}
              >
                <SpeciesIcon size={40} strokeWidth={1.5} style={{ display: 'block' }} />
              </div>
            )}
          </button>

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
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
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
              {[age, pet.breed, genderLabel(pet.gender)].filter(Boolean).join(', ') || '—'}
            </div>
            {lastWeight && (
              <span
                className="chip"
                style={{
                  alignSelf: 'flex-start',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '12px',
                  // A full pill next to the avatar's soft rounded-square
                  // photo read as two different shape languages in the
                  // same small card — this matches the avatar's corner
                  // instead.
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <Scale size={13} strokeWidth={2.2} style={{ display: 'block' }} />
                {lastWeight.fields?.weight as number} кг
              </span>
            )}
            {/* Nothing indicated a pet was shared anywhere outside its own
                edit form — an owner had no quick way to see at a glance
                which of their pets someone else already has access to.
                Owner-only, like the sharing form itself (PetForm.tsx) —
                a shared (non-owner) user isn't shown who else has access. */}
            {pet.current_user_is_owner && pet.shared_with && pet.shared_with.length > 0 && (
              <span
                className="chip"
                style={{
                  alignSelf: 'flex-start',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '12px',
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
                    <span style={{ marginLeft: '2px' }}>+{pet.shared_with.length - 3}</span>
                  )}
                </div>
                {`Общий доступ${pet.shared_with.length > 1 ? ` (${pet.shared_with.length})` : ''}`}
              </span>
            )}
          </div>
        </div>
      </div>
    </SwipeableRow>
  );
}
