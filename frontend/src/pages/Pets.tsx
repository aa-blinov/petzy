import { useState } from 'react';
import { Card, Button, List, Dialog, Form, Input, DatePicker, ImageUploader, Toast } from 'antd-mobile';
import { AddOutline, EditSOutline } from 'antd-mobile-icons';
import { petsService, type Pet, type PetCreate } from '../services/pets.service';
import { usePet } from '../hooks/usePet';
import { useQueryClient } from '@tanstack/react-query';

export function Pets() {
  const { pets, selectPet, getSelectedPet } = usePet();
  const [showForm, setShowForm] = useState(false);
  const [editingPet, setEditingPet] = useState<Pet | null>(null);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const handleAddPet = () => {
    setEditingPet(null);
    form.resetFields();
    setShowForm(true);
  };

  const handleEditPet = (pet: Pet) => {
    setEditingPet(pet);
    form.setFieldsValue({
      name: pet.name,
      breed: pet.breed || '',
      birth_date: pet.birth_date ? new Date(pet.birth_date) : null,
      gender: pet.gender || '',
    });
    setShowForm(true);
  };

  const handleDeletePet = async (pet: Pet) => {
    const result = await Dialog.confirm({
      content: `Вы уверены, что хотите удалить "${pet.name}"?`,
    });

    if (result) {
      try {
        await petsService.deletePet(pet._id);
        Toast.show({ icon: 'success', content: 'Питомец удален' });
        
        // Invalidate pets cache to refresh the list
        queryClient.invalidateQueries({ queryKey: ['pets'] });
        
        // If deleted pet was selected, clear selection
        if (getSelectedPet?._id === pet._id) {
          selectPet(null);
        }
      } catch (error: any) {
        Toast.show({
          icon: 'fail',
          content: error?.response?.data?.error || 'Ошибка при удалении',
        });
      }
    }
  };

  const handleSubmit = async () => {
    try {
      await form.validateFields();
      const values = form.getFieldsValue();
      setLoading(true);

      const petData: PetCreate = {
        name: values.name,
        breed: values.breed || '',
        birth_date: values.birth_date
          ? new Date(values.birth_date).toISOString().split('T')[0]
          : '',
        gender: values.gender || '',
      };

      // Handle photo upload if present
      if (values.photo && values.photo.length > 0) {
        petData.photo_file = values.photo[0].originFileObj;
      }

      if (editingPet) {
        // Update existing pet
        await petsService.updatePet(editingPet._id, petData);
        Toast.show({ icon: 'success', content: 'Питомец обновлен' });
      } else {
        // Create new pet
        const newPet = await petsService.createPet(petData);
        Toast.show({ icon: 'success', content: 'Питомец добавлен' });
        
        // Auto-select newly created pet
        selectPet(newPet);
      }

      // Invalidate pets cache to refresh the list
      queryClient.invalidateQueries({ queryKey: ['pets'] });

      setShowForm(false);
      form.resetFields();
      setEditingPet(null);
    } catch (error: any) {
      if (error?.errorFields) {
        // Form validation error
        return;
      }
      Toast.show({
        icon: 'fail',
        content: error?.response?.data?.error || 'Ошибка при сохранении',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
        paddingBottom: 'calc(env(safe-area-inset-bottom) + 84px)',
        minHeight: '100vh',
        backgroundColor: 'var(--app-page-background)',
      }}
    >
      <div style={{ padding: '16px' }}>
        <Card
          title="Мои питомцы"
          extra={
            <Button
              size="small"
              color="primary"
              fill="none"
              onClick={handleAddPet}
            >
              <AddOutline /> Добавить
            </Button>
          }
        >
          {pets.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--adm-color-weak)' }}>
              <p>У вас пока нет питомцев</p>
              <Button
                color="primary"
                onClick={handleAddPet}
                style={{ marginTop: '16px' }}
              >
                Добавить первого питомца
              </Button>
            </div>
          ) : (
            <List>
              {pets.map((pet) => (
                <List.Item
                  key={pet._id}
                  prefix={
                    pet.photo_url ? (
                      <img
                        src={pet.photo_url}
                        alt={pet.name}
                        style={{
                          width: '48px',
                          height: '48px',
                          borderRadius: '50%',
                          objectFit: 'cover',
                        }}
                      />
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
                          fontSize: '20px',
                        }}
                      >
                        🐱
                      </div>
                    )
                  }
                  description={
                    <div>
                      {pet.breed && <div>{pet.breed}</div>}
                      {pet.birth_date && (
                        <div style={{ fontSize: '12px', color: 'var(--adm-color-weak)' }}>
                          Дата рождения: {pet.birth_date}
                        </div>
                      )}
                    </div>
                  }
                  extra={
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <Button
                        size="small"
                        fill="none"
                        onClick={() => handleEditPet(pet)}
                      >
                        <EditSOutline />
                      </Button>
                      <Button
                        size="small"
                        color="danger"
                        fill="none"
                        onClick={() => handleDeletePet(pet)}
                      >
                        Удалить
                      </Button>
                    </div>
                  }
                >
                  {pet.name}
                </List.Item>
              ))}
            </List>
          )}
        </Card>
      </div>

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
              <DatePicker max={new Date()}>
                {(value) =>
                  value ? value.toLocaleDateString('ru-RU') : 'Выберите дату'
                }
              </DatePicker>
            </Form.Item>

            <Form.Item name="gender" label="Пол">
              <Input placeholder="Мальчик / Девочка" />
            </Form.Item>

            <Form.Item name="photo" label="Фото">
              <ImageUploader
                maxCount={1}
                upload={async (file) => {
                  // Return a mock result - actual upload happens on form submit
                  return {
                    url: URL.createObjectURL(file),
                  };
                }}
              />
            </Form.Item>
          </Form>
        }
      />
    </div>
  );
}

