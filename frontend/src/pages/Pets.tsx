import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Dialog, ImageViewer, Card, Toast } from 'antd-mobile';
import { AddOutline, EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import { petsService, type Pet } from '../services/pets.service';
import { usePet } from '../hooks/usePet';
import { useQueryClient } from '@tanstack/react-query';
import { PetImage } from '../components/PetImage';

export function Pets() {
  const navigate = useNavigate();
  const { pets, selectPet, getSelectedPet } = usePet();

  // State for Delete Confirmation Dialog
  const [deleteDialog, setDeleteDialog] = useState<{ visible: boolean; pet: Pet | null }>({
    visible: false,
    pet: null
  });

  // State for Image Viewer
  const [imageViewer, setImageViewer] = useState<{ visible: boolean; image: string | null }>({
    visible: false,
    image: null,
  });

  const queryClient = useQueryClient();

  const handleEditPet = (pet: Pet) => {
    navigate(`/pets/${pet._id}/edit`);
  };

  const handleAddPet = () => {
    navigate('/pets/new');
  };

  // Just open the dialog via state
  const handleDeleteClick = (pet: Pet) => {
    setDeleteDialog({ visible: true, pet });
  };

  // Actual delete logic
  const confirmDelete = async () => {
    const pet = deleteDialog.pet;
    if (!pet) return;

    try {
      const wasSelected = getSelectedPet?._id === pet._id;
      const currentPetIndex = pets.findIndex(p => p._id === pet._id);

      // Delete the pet
      await petsService.deletePet(pet._id);

      // Close dialog first
      setDeleteDialog(prev => ({ ...prev, visible: false }));

      // Fetch fresh data directly
      const updatedPets = await petsService.getPets();

      // Update the cache
      queryClient.setQueryData(['pets'], updatedPets);

      // If the deleted pet was selected, select another pet from the fresh list
      if (wasSelected && updatedPets.length > 0) {
        // Try to select the pet at the same index, or the previous one if we deleted the last pet
        const nextPetIndex = currentPetIndex >= updatedPets.length ? updatedPets.length - 1 : currentPetIndex;
        selectPet(updatedPets[nextPetIndex]);
      } else if (updatedPets.length === 0) {
        // No pets left, clear selection
        selectPet(null);
      }

      Toast.show({
        icon: 'success',
        content: 'Питомец удален'
      });
    } catch (error: any) {
      console.error('Delete pet error:', error);
      // Close dialog on error
      setDeleteDialog(prev => ({ ...prev, visible: false }));

      const errorMessage = error?.response?.data?.error || 'Ошибка при удалении';
      Toast.show({
        icon: 'fail',
        content: errorMessage
      });
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
          minHeight: '40px'
        }}>
          <h2 style={{ margin: 0, fontSize: 'var(--text-xxl)', fontWeight: 600, color: 'var(--app-text-color)' }}>Мои питомцы</h2>
          <Button color="primary" fill="none" onClick={handleAddPet}>
            <AddOutline style={{ marginRight: 'var(--spacing-xs)' }} />
            Добавить
          </Button>
        </div>

        {pets.length === 0 ? (
          <div className="safe-area-padding" style={{
            textAlign: 'center',
            color: 'var(--adm-color-weak)',
            padding: 'var(--spacing-xl)',
          }}>
            <p style={{ marginBottom: 'var(--spacing-lg)' }}>
              Нет питомцев. Добавьте первого!
            </p>
            <Button color="primary" onClick={handleAddPet}>
              <AddOutline /> &nbsp;Добавить питомца
            </Button>
          </div>
        ) : (
          <div className="safe-area-padding" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-md)',
            marginTop: 'var(--spacing-sm)',
          }}>
            {pets.map(pet => (
              <Card
                key={pet._id}
                style={{
                  borderRadius: '12px',
                  border: 'none',
                  boxShadow: 'var(--app-shadow)',
                }}
              >
                <div style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                    {/* Avatar */}
                    {pet.photo_url ? (
                      <div
                        style={{
                          cursor: 'pointer',
                          flexShrink: 0,
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (pet.photo_url) {
                            setImageViewer({ visible: true, image: pet.photo_url });
                          }
                        }}
                      >
                        <PetImage
                          src={pet.photo_url}
                          alt={pet.name}
                          size={48}
                          style={{
                            borderRadius: '50%',
                            border: '2px solid var(--adm-color-border)',
                          }}
                        />
                      </div>
                    ) : (
                      <div
                        style={{
                          width: '48px',
                          height: '48px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--adm-color-border)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '24px',
                          flexShrink: 0,
                        }}
                      >
                        🐱
                      </div>
                    )}

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                        <span style={{ fontWeight: 600, fontSize: '16px' }}>{pet.name}</span>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <Button
                            size="mini"
                            fill="outline"
                            onClick={() => handleEditPet(pet)}
                            style={{
                              '--text-color': 'var(--app-text-primary)',
                              '--border-color': 'var(--app-border-color)',
                            } as React.CSSProperties}
                          >
                            <EditSOutline style={{ color: 'var(--app-text-primary)', fontSize: '16px' }} />
                          </Button>
                          <Button
                            size="mini"
                            color="danger"
                            fill="outline"
                            onClick={() => handleDeleteClick(pet)}
                          >
                            <DeleteOutline />
                          </Button>
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {pet.breed && <span>{pet.breed}</span>}
                        {pet.birth_date && (
                          <span style={{ fontSize: '12px', color: 'var(--adm-color-weak)' }}>Дата рождения: {pet.birth_date}</span>
                        )}
                        {pet.gender && (
                          <span style={{ fontSize: '12px', color: 'var(--adm-color-weak)' }}>Пол: {pet.gender}</span>
                        )}
                        {pet.species && (
                          <span style={{ fontSize: '12px', color: 'var(--adm-color-weak)' }}>Вид: {pet.species}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Declarative Delete Dialog */}
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

      {/* Image Viewer */}
      <ImageViewer
        image={imageViewer.image || ''}
        visible={imageViewer.visible}
        onClose={() => setImageViewer(prev => ({ ...prev, visible: false }))}
        afterClose={() => setImageViewer({ visible: false, image: null })}
      />
    </div>
  );
}
