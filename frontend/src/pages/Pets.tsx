import { useState } from 'react';
import { Button, Dialog, Form, Input, ImageUploader, Toast, ImageViewer, Card } from 'antd-mobile';
import { AddOutline, EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import { petsService, type Pet } from '../services/pets.service';
import { usePet } from '../hooks/usePet';
import { useQueryClient } from '@tanstack/react-query';

export function Pets() {
  const { pets, selectPet, getSelectedPet } = usePet();
  const [showForm, setShowForm] = useState(false);
  const [editingPet, setEditingPet] = useState<Pet | null>(null);
  const [fileList, setFileList] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  
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

  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const handleEditPet = (pet: Pet) => {
    setEditingPet(pet);
    form.setFieldsValue({
      name: pet.name,
      breed: pet.breed || '',
      birth_date: pet.birth_date || '',
      gender: pet.gender || '',
      species: pet.species || '',
    });
    if (pet.photo_url) {
      setFileList([{ url: pet.photo_url }]);
    } else {
      setFileList([]);
    }
    setShowForm(true);
  };

  const handleAddPet = () => {
    setEditingPet(null);
    form.resetFields();
    setFileList([]);
    setShowForm(true);
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
      await petsService.deletePet(pet._id);
      Toast.show({ 
        icon: 'success', 
        content: 'Питомец удален',
        duration: 1500,
      });
      
      await queryClient.invalidateQueries({ queryKey: ['pets'] });
      
      if (getSelectedPet?._id === pet._id) {
        selectPet(null);
      }
      
      // Small delay to let Toast render before unmounting
      setTimeout(() => {
        setDeleteDialog({ visible: false, pet: null });
      }, 100);
    } catch (error: any) {
      console.error('Delete pet error:', error);
      Toast.show({
        icon: 'fail',
        content: error?.response?.data?.error || 'Ошибка при удалении',
        duration: 2000,
      });
      setDeleteDialog({ visible: false, pet: null });
    }
  };

  const handleSubmit = async () => {
    try {
      await form.validateFields();
      const values = form.getFieldsValue();
      setLoading(true);

      const petData = {
        ...values,
        photo_file: fileList[0]?.file,
        photo_url: fileList[0]?.url,
        remove_photo: fileList.length === 0 && editingPet?.photo_url ? true : undefined,
      };

      if (editingPet) {
        await petsService.updatePet(editingPet._id, petData);
        Toast.show({ icon: 'success', content: 'Питомец обновлен' });
      } else {
        await petsService.createPet(petData);
        Toast.show({ icon: 'success', content: 'Питомец добавлен' });
      }

      await queryClient.invalidateQueries({ queryKey: ['pets'] });
      
      setShowForm(false);
      form.resetFields();
      setEditingPet(null);
      setFileList([]);
    } catch (error: any) {
      Toast.show({
        icon: 'fail',
        content: error?.response?.data?.error || 'Ошибка при сохранении',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      backgroundColor: 'var(--app-page-background)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ 
          marginBottom: '16px', 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))'
        }}>
          <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 600, color: 'var(--app-text-color)' }}>Мои питомцы</h2>
          <Button color="primary" fill="none" onClick={handleAddPet}>
            <AddOutline style={{ marginRight: '4px' }} />
            Добавить
          </Button>
        </div>

        {pets.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--adm-color-weak)', padding: '20px' }}>
            Нет питомцев. Добавьте первого!
          </div>
        ) : (
          <div style={{ 
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            marginTop: '8px',
            paddingLeft: 'max(16px, env(safe-area-inset-left))',
            paddingRight: 'max(16px, env(safe-area-inset-right))'
          }}>
            {pets.map(pet => (
              <Card
                key={pet._id}
                style={{
                  borderRadius: '12px',
                  border: 'none',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                }}
              >
                <div style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                    {/* Avatar */}
                    {pet.photo_url ? (
                      <div
                        style={{
                          width: '48px',
                          height: '48px',
                          borderRadius: '50%',
                          overflow: 'hidden',
                          cursor: 'pointer',
                          border: '2px solid var(--adm-color-border)',
                          flexShrink: 0,
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (pet.photo_url) {
                            setImageViewer({ visible: true, image: pet.photo_url });
                          }
                        }}
                      >
                        <img
                          src={pet.photo_url}
                          alt={pet.name}
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
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
                              '--text-color': '#000000',
                              '--border-color': 'rgba(0, 0, 0, 0.3)',
                            } as React.CSSProperties}
                          >
                            <EditSOutline style={{ color: '#000000' }} />
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
        closeOnAction
        onClose={() => setDeleteDialog({ visible: false, pet: null })}
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
            onClick: () => setDeleteDialog({ visible: false, pet: null }),
          },
        ]}
      />

      {/* Pet Form Dialog */}
      <Dialog
        visible={showForm}
        onClose={() => {
          setShowForm(false);
          form.resetFields();
          setEditingPet(null);
        }}
        title={editingPet ? 'Редактировать питомца' : 'Добавить питомца'}
        content={
          <Form
            form={form}
            layout="vertical"
            footer={
              <div style={{ display: 'flex', gap: '8px' }}>
                <Button
                  onClick={() => {
                    setShowForm(false);
                    form.resetFields();
                    setEditingPet(null);
                  }}
                  style={{ flex: 1 }}
                >
                  Отмена
                </Button>
                <Button
                  color="primary"
                  onClick={handleSubmit}
                  loading={loading}
                  style={{ flex: 1 }}
                >
                  {editingPet ? 'Сохранить' : 'Добавить'}
                </Button>
              </div>
            }
          >
            <Form.Item
              name="name"
              label="Имя"
              rules={[{ required: true, message: 'Введите имя питомца' }]}
            >
              <Input placeholder="Имя питомца" />
            </Form.Item>

            <Form.Item name="breed" label="Порода">
              <Input placeholder="Порода (необязательно)" />
            </Form.Item>

            <Form.Item name="birth_date" label="Дата рождения">
              <Input type="date" />
            </Form.Item>
            
            <Form.Item name="gender" label="Пол">
               <Input placeholder="Пол (необязательно)" />
            </Form.Item>

            <Form.Item name="photo" label="Фото">
              <ImageUploader
                value={fileList}
                onChange={setFileList}
                upload={async (file) => {
                  return {
                    url: URL.createObjectURL(file),
                  };
                }}
                maxCount={1}
                deletable={true}
              />
            </Form.Item>
          </Form>
        }
        closeOnAction={false}
        closeOnMaskClick={false}
      />

      {/* Image Viewer */}
      {imageViewer.image && (
        <ImageViewer
          image={imageViewer.image}
          visible={imageViewer.visible}
          onClose={() => {
            // Small delay to prevent race condition
            setTimeout(() => {
              setImageViewer({ visible: false, image: null });
            }, 100);
          }}
        />
      )}
    </div>
  );
}
