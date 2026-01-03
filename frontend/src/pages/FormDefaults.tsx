import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Input, Picker, Form, Toast } from 'antd-mobile';
import { DEFAULT_FORM_SETTINGS, getFormSettings, type FormSettings } from '../utils/formsConfig';

export function FormDefaults() {
  const navigate = useNavigate();
  const mountedRef = useRef(true);
  const [formSettings, setFormSettings] = useState<FormSettings>(DEFAULT_FORM_SETTINGS);
  const [visiblePicker, setVisiblePicker] = useState<string | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const settings = getFormSettings();
    setFormSettings(settings);
  }, []);

  const handleSave = useCallback(() => {
    try {
      localStorage.setItem('formDefaults', JSON.stringify(formSettings));
      Toast.show({
        icon: 'success',
        content: 'Настройки успешно сохранены',
        duration: 1000,
      });
      setTimeout(() => {
        if (mountedRef.current) {
          navigate('/settings');
        }
      }, 1000);
    } catch (err) {
      Toast.show({
        icon: 'fail',
        content: 'Ошибка при сохранении настроек',
      });
      console.error('Error saving settings:', err);
    }
  }, [formSettings, navigate]);

  const handleReset = useCallback(() => {
    const confirmed = window.confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?');
    if (confirmed) {
      try {
        setFormSettings(DEFAULT_FORM_SETTINGS);
        localStorage.setItem('formDefaults', JSON.stringify(DEFAULT_FORM_SETTINGS));
        Toast.show({
          icon: 'success',
          content: 'Настройки сброшены',
          duration: 1000,
        });
      } catch (err) {
        Toast.show({
          icon: 'fail',
          content: 'Ошибка при сбросе настроек',
        });
      }
    }
  }, []);

  const updateFormSetting = useCallback((formType: keyof FormSettings, field: string, value: string) => {
    setFormSettings(prev => ({
      ...prev,
      [formType]: {
        ...(prev[formType] || {}),
        [field]: value
      }
    }));
  }, []);

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: 'var(--app-page-background)',
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px', paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>Значения по умолчанию</h2>
        </div>

        {/* Form Defaults Section */}
        <Form layout="horizontal" mode="card">
          <Form.Header>Приступ астмы</Form.Header>
          <Form.Item label="Длительность" onClick={() => setVisiblePicker('asthma_duration')} arrow>
            {formSettings.asthma?.duration || 'Короткий'}
          </Form.Item>
          <Form.Item label="Ингаляция" onClick={() => setVisiblePicker('asthma_inhalation')} arrow>
            {formSettings.asthma?.inhalation === 'true' ? 'Да' : 'Нет'}
          </Form.Item>
          <Form.Item label="Причина">
            <Input
              value={formSettings.asthma?.reason || ''}
              onChange={(val) => updateFormSetting('asthma', 'reason', val)}
              placeholder="Пил"
            />
          </Form.Item>

          <Form.Header>Дефекация</Form.Header>
          <Form.Item label="Тип стула" onClick={() => setVisiblePicker('defecation_stool_type')} arrow>
            {formSettings.defecation?.stool_type || 'Обычный'}
          </Form.Item>
          <Form.Item label="Цвет стула" onClick={() => setVisiblePicker('defecation_color')} arrow>
            {formSettings.defecation?.color || 'Коричневый'}
          </Form.Item>
          <Form.Item label="Корм">
            <Input
              value={formSettings.defecation?.food || ''}
              onChange={(val) => updateFormSetting('defecation', 'food', val)}
              placeholder="Royal Canin Fibre Response"
            />
          </Form.Item>

          <Form.Header>Вес</Form.Header>
          <Form.Item label="Корм">
            <Input
              value={formSettings.weight?.food || ''}
              onChange={(val) => updateFormSetting('weight', 'food', val)}
              placeholder="Royal Canin Fibre Response"
            />
          </Form.Item>

          <Form.Header>Закапывание глаз</Form.Header>
          <Form.Item label="Тип капель" onClick={() => setVisiblePicker('eye_drops_type')} arrow>
            {formSettings.eye_drops?.drops_type || 'Обычные'}
          </Form.Item>

          <Form.Header>Чистка зубов</Form.Header>
          <Form.Item label="Способ чистки" onClick={() => setVisiblePicker('tooth_brushing_type')} arrow>
            {formSettings.tooth_brushing?.brushing_type || 'Щетка'}
          </Form.Item>

          <Form.Header>Чистка ушей</Form.Header>
          <Form.Item label="Способ чистки" onClick={() => setVisiblePicker('ear_cleaning_type')} arrow>
            {formSettings.ear_cleaning?.cleaning_type || 'Салфетка/Марля'}
          </Form.Item>
        </Form>

        {/* Pickers */}
        <Picker
          columns={[[
            { label: 'Короткий', value: 'Короткий' },
            { label: 'Средний', value: 'Средний' },
            { label: 'Длинный', value: 'Длинный' },
          ]]}
          visible={visiblePicker === 'asthma_duration'}
          onClose={() => setVisiblePicker(null)}
          value={[formSettings.asthma?.duration || 'Короткий']}
          onConfirm={(val) => {
            updateFormSetting('asthma', 'duration', val[0] as string || 'Короткий');
            setVisiblePicker(null);
          }}
          cancelText="Отмена"
          confirmText="Сохранить"
        />

        <Picker
          columns={[[
            { label: 'Нет', value: 'false' },
            { label: 'Да', value: 'true' },
          ]]}
          visible={visiblePicker === 'asthma_inhalation'}
          onClose={() => setVisiblePicker(null)}
          value={[formSettings.asthma?.inhalation || 'false']}
          onConfirm={(val) => {
            updateFormSetting('asthma', 'inhalation', val[0] as string || 'false');
            setVisiblePicker(null);
          }}
          cancelText="Отмена"
          confirmText="Сохранить"
        />

        <Picker
          columns={[[
            { label: 'Обычный', value: 'Обычный' },
            { label: 'Твердый', value: 'Твердый' },
            { label: 'Жидкий', value: 'Жидкий' },
          ]]}
          visible={visiblePicker === 'defecation_stool_type'}
          onClose={() => setVisiblePicker(null)}
          value={[formSettings.defecation?.stool_type || 'Обычный']}
          onConfirm={(val) => {
            updateFormSetting('defecation', 'stool_type', val[0] as string || 'Обычный');
            setVisiblePicker(null);
          }}
          cancelText="Отмена"
          confirmText="Сохранить"
        />

        <Picker
          columns={[[
            { label: 'Коричневый', value: 'Коричневый' },
            { label: 'Темно-коричневый', value: 'Темно-коричневый' },
            { label: 'Светло-коричневый', value: 'Светло-коричневый' },
            { label: 'Другой', value: 'Другой' },
          ]]}
          visible={visiblePicker === 'defecation_color'}
          onClose={() => setVisiblePicker(null)}
          value={[formSettings.defecation?.color || 'Коричневый']}
          onConfirm={(val) => {
            updateFormSetting('defecation', 'color', val[0] as string || 'Коричневый');
            setVisiblePicker(null);
          }}
          cancelText="Отмена"
          confirmText="Сохранить"
        />

        <Picker
          columns={[[
            { label: 'Обычные', value: 'Обычные' },
            { label: 'Гелевые', value: 'Гелевые' },
          ]]}
          visible={visiblePicker === 'eye_drops_type'}
          onClose={() => setVisiblePicker(null)}
          value={[formSettings.eye_drops?.drops_type || 'Обычные']}
          onConfirm={(val) => {
            updateFormSetting('eye_drops', 'drops_type', val[0] as string || 'Обычные');
            setVisiblePicker(null);
          }}
          cancelText="Отмена"
          confirmText="Сохранить"
        />

        <Picker
          columns={[[
            { label: 'Щетка', value: 'Щетка' },
            { label: 'Марля', value: 'Марля' },
            { label: 'Игрушка', value: 'Игрушка' },
          ]]}
          visible={visiblePicker === 'tooth_brushing_type'}
          onClose={() => setVisiblePicker(null)}
          value={[formSettings.tooth_brushing?.brushing_type || 'Щетка']}
          onConfirm={(val) => {
            updateFormSetting('tooth_brushing', 'brushing_type', val[0] as string || 'Щетка');
            setVisiblePicker(null);
          }}
          cancelText="Отмена"
          confirmText="Сохранить"
        />

        <Picker
          columns={[[
            { label: 'Салфетка/Марля', value: 'Салфетка/Марля' },
            { label: 'Капли', value: 'Капли' },
          ]]}
          visible={visiblePicker === 'ear_cleaning_type'}
          onClose={() => setVisiblePicker(null)}
          value={[formSettings.ear_cleaning?.cleaning_type || 'Салфетка/Марля']}
          onConfirm={(val) => {
            updateFormSetting('ear_cleaning', 'cleaning_type', val[0] as string || 'Салфетка/Марля');
            setVisiblePicker(null);
          }}
          cancelText="Отмена"
          confirmText="Сохранить"
        />

        {/* Action Buttons */}
        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Button block color="primary" size="large" onClick={handleSave}>
            Сохранить
          </Button>
          <Button block color="default" size="large" onClick={handleReset}>
            Сбросить к значениям по умолчанию
          </Button>
        </div>
      </div>
    </div>
  );
}



