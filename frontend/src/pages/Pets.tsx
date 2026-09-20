import { useState, useMemo } from 'react';
import { showToast } from '../utils/toast';
import { useNavigate } from 'react-router-dom';
import { Dialog, ImageViewer, PullToRefresh } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import { Pencil, Scale, Trash2, Cat } from 'lucide-react';
import { petsService, type Pet } from '../services/pets.service';
import { healthRecordsService } from '../services/healthRecords.service';
import { usePet } from '../hooks/usePet';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { computePetAge } from '../utils/relativeTime';
import { speciesIconMap, SPECIES_FALLBACK_ICON, genderLabel } from '../utils/constants';
import { hapticFeedback } from '../utils/haptic';
import { PetImage } from '../components/PetImage';
import { PetCardSkeleton } from '../components/Skeletons';
import { SwipeableRow, type SwipeAction } from '../components/SwipeableRow';
import { EmptyState } from '../components/EmptyState';

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

      showToast.success('Питомец удален');
    } catch (error: any) {
      console.error('Delete pet error:', error);
      setDeleteDialog(prev => ({ ...prev, visible: false }));
      const errorMessage = error?.response?.data?.error || 'Ошибка при удалении';
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
            description="Добавьте первого — Petzy будет считать кормления, вес и напомнит о лекарствах."
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
              {pets.map((pet, index) => (
                <div
                  key={pet._id}
                  className={`motion-enter motion-stagger-${Math.min(index + 1, 4)}`}
                >
                  <PetCard
                    pet={pet}
                    onEdit={() => handleEditPet(pet)}
                    onDelete={() => handleDeleteClick(pet)}
                    onImageTap={(url) => setImageViewer({ visible: true, image: url })}
                  />
                </div>
              ))}
            </div>
          </PullToRefresh>
        )}
      </div>

      <Dialog
        visible={deleteDialog.visible}
        title="Удаление питомца"
        content={deleteDialog.pet ? `Вы уверены, что хотите удалить "${deleteDialog.pet.name}"?` : ''}
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

  // Most recent weight for the chip — uses the same endpoint as the dashboard.
  const weights = useQuery({
    queryKey: ['pet-summary', 'weight', pet._id],
    queryFn: () => healthRecordsService.getList('weight', pet._id, 1, 1),
    enabled: !!pet._id,
    staleTime: 30_000,
  });
  const lastWeight = weights.data?.weights?.[0];

  // Swipe left → delete, swipe right → edit. Matches HistoryItem / MedicationsList.
  const leftAction: SwipeAction = {
    icon: <Pencil size={20} strokeWidth={2.4} />,
    label: 'Изменить',
    color: 'var(--app-accent)',
    onTrigger: onEdit,
  };
  const rightAction: SwipeAction = {
    icon: <Trash2 size={20} strokeWidth={2.4} />,
    label: 'Удалить',
    color: 'var(--app-danger-color)',
    onTrigger: onDelete,
  };

  return (
    <SwipeableRow leftAction={leftAction} rightAction={rightAction}>
      {/* Editing and deleting are swipe actions. No .tap-ripple here on
          purpose: the card has no tap action, so a press animation would
          promise something that never happens. */}
      <div className="card-soft card-soft--interactive" style={{ overflow: 'hidden' }}>
        {/* Hero photo / species icon (compact, ~120px) */}
        <button
          type="button"
          onClick={() => pet.photo_url && onImageTap(pet.photo_url)}
          disabled={!pet.photo_url}
          aria-label={pet.photo_url ? `Открыть фото ${pet.name}` : undefined}
          style={{
            position: 'relative',
            width: '100%',
            height: '120px',
            padding: 0,
            border: 'none',
            background: 'none',
            cursor: pet.photo_url ? 'pointer' : 'default',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundColor: 'var(--tile-brown)',
              backgroundImage: pet.photo_url
                ? undefined
                : 'linear-gradient(135deg, #E8946A 0%, #C46A3F 100%)',
            }}
          />
          {pet.photo_url ? (
            <PetImage
              src={pet.photo_url}
              alt={pet.name}
              size={120}
              style={{ width: '100%', height: '100%', borderRadius: 0, cursor: 'pointer' }}
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
              <SpeciesIcon size={64} strokeWidth={1.5} style={{ display: 'block' }} />
            </div>
          )}
        </button>

        {/* Body — name + meta chips.
            Every card is the same height regardless of how full the
            profile is. Three things used to vary it: the chip row was
            rendered only when some metadata existed, it could wrap onto
            a second line, and a long name could wrap too — so a list of
            pets came out as a stepped column. The row is now always
            present (with a stand-in when empty), kept to one line, and
            the name is clipped rather than wrapped. */}
        <div style={{ padding: '14px 16px' }}>
          <div
            className="display-headline"
            style={{
              fontSize: '20px',
              fontWeight: 700,
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {pet.name}
          </div>
          <div
            style={{
              marginTop: 8,
              display: 'flex',
              flexWrap: 'nowrap',
              gap: 6,
              overflow: 'hidden',
            }}
          >
            {pet.breed || age || pet.gender || lastWeight ? (
              <>
                {pet.breed && <span className="chip">{pet.breed}</span>}
                {age && <span className="chip">{age}</span>}
                {pet.gender && <span className="chip">{genderLabel(pet.gender)}</span>}
                {lastWeight && (
                  <span className="chip">
                    <Scale size={14} strokeWidth={2.2} style={{ display: 'block' }} />
                    {lastWeight.weight} кг
                  </span>
                )}
              </>
            ) : (
              <span className="chip chip--muted">Профиль не заполнен</span>
            )}
          </div>
        </div>
      </div>
    </SwipeableRow>
  );
}
