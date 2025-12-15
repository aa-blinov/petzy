// Универсальная конфигурация форм для всех типов записей
// Примечание: значения `value` в полях используются как fallback и должны соответствовать
// SettingsModule.DEFAULT_SETTINGS. При создании формы значения берутся из настроек (localStorage).
const FORM_CONFIGS = {
    feeding: {
        title: 'Записать дневную порцию корма',
        endpoint: '/api/feeding',
        fields: [
            { name: 'date', type: 'date', label: 'Дата', required: true, id: 'feeding-date' },
            { name: 'time', type: 'time', label: 'Время', required: true, id: 'feeding-time' },
            { name: 'food_weight', type: 'number', label: 'Вес корма (граммы)', required: true, placeholder: '50', min: 0, step: 0.1, id: 'feeding-food-weight' },
            { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'feeding-comment' }
        ],
        transformData: (formData) => ({
            pet_id: formData.get('pet_id'),
            date: formData.get('date'),
            time: formData.get('time'),
            food_weight: formData.get('food_weight'),
            comment: formData.get('comment') || ''
        }),
        successMessage: (isEdit) => isEdit ? 'Дневная порция обновлена' : 'Дневная порция записана'
    },
    asthma: {
        title: 'Записать приступ астмы',
        endpoint: '/api/asthma',
        fields: [
            { name: 'date', type: 'date', label: 'Дата', required: true, id: 'asthma-date' },
            { name: 'time', type: 'time', label: 'Время', required: true, id: 'asthma-time' },
            { name: 'duration', type: 'select', label: 'Длительность', required: true, options: [
                { value: 'Короткий', text: 'Короткий' },
                { value: 'Длительный', text: 'Длительный' }
            ], value: 'Короткий', id: 'asthma-duration' },
            { name: 'inhalation', type: 'select', label: 'Ингаляция', required: true, options: [
                { value: 'false', text: 'Нет' },
                { value: 'true', text: 'Да' }
            ], value: 'false', id: 'asthma-inhalation' },
            { name: 'reason', type: 'text', label: 'Причина', required: true, placeholder: 'Пил после сна', value: 'Пил', id: 'asthma-reason' },
            { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'asthma-comment' }
        ],
        transformData: (formData) => ({
            pet_id: formData.get('pet_id'),
            date: formData.get('date'),
            time: formData.get('time'),
            duration: formData.get('duration'),
            reason: formData.get('reason'),
            inhalation: formData.get('inhalation') === 'true',
            comment: formData.get('comment') || ''
        }),
        successMessage: (isEdit) => isEdit ? 'Приступ астмы обновлен' : 'Приступ астмы записан'
    },
    defecation: {
        title: 'Записать дефекацию',
        endpoint: '/api/defecation',
        fields: [
            { name: 'date', type: 'date', label: 'Дата', required: true, id: 'defecation-date' },
            { name: 'time', type: 'time', label: 'Время', required: true, id: 'defecation-time' },
            { name: 'stool_type', type: 'select', label: 'Тип стула', required: true, options: [
                { value: 'Обычный', text: 'Обычный' },
                { value: 'Твердый', text: 'Твердый' },
                { value: 'Жидкий', text: 'Жидкий' }
            ], value: 'Обычный', id: 'defecation-stool-type' },
            { name: 'color', type: 'select', label: 'Цвет стула', required: true, options: [
                { value: 'Коричневый', text: 'Коричневый' },
                { value: 'Темно-коричневый', text: 'Темно-коричневый' },
                { value: 'Светло-коричневый', text: 'Светло-коричневый' },
                { value: 'Другой', text: 'Другой' }
            ], value: 'Коричневый', id: 'defecation-color' },
            { name: 'food', type: 'text', label: 'Корм', placeholder: 'Royal Canin Fibre Response', value: 'Royal Canin Fibre Response', id: 'defecation-food' },
            { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'defecation-comment' }
        ],
        transformData: (formData) => ({
            pet_id: formData.get('pet_id'),
            date: formData.get('date'),
            time: formData.get('time'),
            stool_type: formData.get('stool_type'),
            color: formData.get('color'),
            food: formData.get('food') || '',
            comment: formData.get('comment') || ''
        }),
        successMessage: (isEdit) => isEdit ? 'Дефекация обновлена' : 'Дефекация записана'
    },
    litter: {
        title: 'Записать смену лотка',
        endpoint: '/api/litter',
        fields: [
            { name: 'date', type: 'date', label: 'Дата', required: true, id: 'litter-date' },
            { name: 'time', type: 'time', label: 'Время', required: true, id: 'litter-time' },
            { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 3, placeholder: 'Полная замена наполнителя', id: 'litter-comment' }
        ],
        transformData: (formData) => ({
            pet_id: formData.get('pet_id'),
            date: formData.get('date'),
            time: formData.get('time'),
            comment: formData.get('comment') || ''
        }),
        successMessage: (isEdit) => isEdit ? 'Смена лотка обновлена' : 'Смена лотка записана'
    },
    weight: {
        title: 'Записать вес',
        endpoint: '/api/weight',
        fields: [
            { name: 'date', type: 'date', label: 'Дата', required: true, id: 'weight-date' },
            { name: 'time', type: 'time', label: 'Время', required: true, id: 'weight-time' },
            { name: 'weight', type: 'number', label: 'Вес (кг)', required: true, placeholder: '4.5', step: 0.01, min: 0, max: 20, id: 'weight-value' },
            { name: 'food', type: 'text', label: 'Корм', placeholder: 'Royal Canin Fibre Response', value: 'Royal Canin Fibre Response', id: 'weight-food' },
            { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'weight-comment' }
        ],
        transformData: (formData) => ({
            pet_id: formData.get('pet_id'),
            date: formData.get('date'),
            time: formData.get('time'),
            weight: formData.get('weight'),
            food: formData.get('food') || '',
            comment: formData.get('comment') || ''
        }),
        successMessage: (isEdit) => isEdit ? 'Вес обновлен' : 'Вес записан'
    }
};

// Получаем настройки из localStorage
// Используем SettingsModule.DEFAULT_SETTINGS как источник значений по умолчанию
function getFormSettings() {
    try {
        const saved = localStorage.getItem('formDefaults');
        if (saved) {
            const settings = JSON.parse(saved);
            // Ensure backward compatibility
            if (settings.defecation && !settings.defecation.color) {
                settings.defecation.color = 'Коричневый';
            }
            return settings;
        }
    } catch (e) {
        console.error('Error loading settings:', e);
    }
    // Возвращаем значения по умолчанию из SettingsModule
    if (typeof SettingsModule !== 'undefined' && SettingsModule.DEFAULT_SETTINGS) {
        return SettingsModule.DEFAULT_SETTINGS;
    }
    // Fallback, если SettingsModule еще не загружен
    return {
        asthma: {
            duration: 'Короткий',
            inhalation: 'false',
            reason: 'Пил'
        },
        defecation: {
            stool_type: 'Обычный',
            color: 'Коричневый',
            food: 'Royal Canin Fibre Response'
        },
        weight: {
            food: 'Royal Canin Fibre Response'
        }
    };
}

// Универсальная функция для создания формы
function createFormHTML(formType, recordId = null) {
    const config = FORM_CONFIGS[formType];
    if (!config) return '';
    
    // Получаем настройки из localStorage
    const settings = getFormSettings();
    
    // Устанавливаем текущую дату и время по умолчанию
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const dateStr = `${year}-${month}-${day}`;
    const timeStr = now.toTimeString().slice(0, 5);
    
    let html = `<form id="${formType}-form-element" class="inline-form">`;
    html += `<input type="hidden" name="record_id" value="${recordId || ''}">`;
    html += `<input type="hidden" name="pet_id" value="">`;
    
    html += '<div class="form-content">';
    
    // Группируем поля по строкам (date/time всегда вместе)
    let inRow = false;
    config.fields.forEach((field, index) => {
        const isDate = field.name === 'date';
        const isTime = field.name === 'time';
        const nextIsTime = config.fields[index + 1]?.name === 'time';
        
        // Получаем значение из настроек, если доступно
        let fieldValue = field.value;
        
        // Для date/time используем текущие значения
        if (isDate) {
            fieldValue = dateStr;
        } else if (isTime) {
            fieldValue = timeStr;
        } else if (settings[formType] && settings[formType][field.name] !== undefined) {
            // Для остальных полей берем из настроек
            fieldValue = settings[formType][field.name];
        }
        
        // Создаем копию поля с обновленным значением
        const fieldWithSettings = { ...field, value: fieldValue };
        
        if (isDate && nextIsTime) {
            // Начинаем строку с date и time
            if (inRow) html += '</div>';
            html += '<div class="form-row">';
            html += createFieldHTML(fieldWithSettings, true);
            inRow = true;
        } else if (isTime && inRow) {
            // Завершаем строку с time
            html += createFieldHTML(fieldWithSettings, true);
            html += '</div>';
            inRow = false;
        } else {
            // Обычное поле
            if (inRow) {
                html += '</div>';
                inRow = false;
            }
            html += '<div class="form-group">';
            html += createFieldHTML(fieldWithSettings, false);
            html += '</div>';
        }
    });
    if (inRow) html += '</div>';
    
    html += '</div>'; // form-content
    
    html += '<div class="form-actions">';
    html += `<button type="submit" class="btn btn-primary btn-block" id="${formType}-submit-btn">Сохранить</button>`;
    html += '</div>';
    
    html += '</form>';
    return html;
}

function createFieldHTML(field, isHalf = false) {
    let html = '';
    const wrapperClass = isHalf ? 'form-group form-group-half' : '';
    
    html += `<div class="${wrapperClass || 'form-group'}">`;
    html += `<label for="${field.id}">${field.label}${field.required ? ' *' : ''}</label>`;
    
    if (field.type === 'select') {
        html += `<select name="${field.name}" ${field.required ? 'required' : ''} id="${field.id}">`;
        field.options.forEach(opt => {
            // Выбираем первое значение по умолчанию, если не указано field.value
            const isDefault = field.value ? (field.value === opt.value) : (opt === field.options[0]);
            const selected = isDefault ? 'selected' : '';
            html += `<option value="${opt.value}" ${selected}>${opt.text}</option>`;
        });
        html += `</select>`;
    } else if (field.type === 'textarea') {
        html += `<textarea name="${field.name}" ${field.required ? 'required' : ''} placeholder="${field.placeholder || ''}" rows="${field.rows || 2}" id="${field.id}"></textarea>`;
    } else {
        const attrs = [];
        if (field.required) attrs.push('required');
        if (field.placeholder) attrs.push(`placeholder="${field.placeholder}"`);
        if (field.value) attrs.push(`value="${field.value}"`);
        if (field.min !== undefined) attrs.push(`min="${field.min}"`);
        if (field.max !== undefined) attrs.push(`max="${field.max}"`);
        if (field.step !== undefined) attrs.push(`step="${field.step}"`);
        
        html += `<input type="${field.type}" name="${field.name}" id="${field.id}" ${attrs.join(' ')}>`;
    }
    
    html += '</div>';
    return html;
}

// Функция для заполнения формы данными записи
function populateForm(formType, recordData, recordId) {
    const config = FORM_CONFIGS[formType];
    if (!config) return;
    
    const container = document.getElementById(`${formType}-form-container`);
    if (!container) return;
    
    // Парсим дату и время
    const [datePart, timePart] = recordData.date_time.split(' ');
    
    // Создаем форму с recordId
    container.innerHTML = createFormHTML(formType, recordId);
    const form = document.getElementById(`${formType}-form-element`);
    
    if (!form) return;
    
    // Заполняем поля
    config.fields.forEach(field => {
        const element = document.getElementById(field.id);
        if (!element) return;
        
        if (field.name === 'date') {
            element.value = datePart;
        } else if (field.name === 'time') {
            element.value = timePart;
        } else {
            let value = recordData[field.name];
            if (value === '-' || value === null || value === undefined) {
                value = field.value || '';
            }
            
            // Специальная обработка для asthma.inhalation
            if (field.name === 'inhalation' && typeof value === 'string') {
                // Преобразуем "Да"/"Нет" в "true"/"false"
                if (value === 'Да') value = 'true';
                else if (value === 'Нет') value = 'false';
            }
            
            if (field.type === 'select') {
                element.value = value;
            } else {
                element.value = value;
            }
        }
    });
    
    // Обновляем текст кнопки
    const submitBtn = document.getElementById(`${formType}-submit-btn`);
    if (submitBtn) {
        submitBtn.textContent = 'Обновить';
    }
    
    // Привязываем обработчик
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        handleFormSubmit(formType, form);
    });
}

// Универсальный обработчик отправки формы
async function handleFormSubmit(formType, formElement) {
    const config = FORM_CONFIGS[formType];
    if (!config) {
        showAlert('error', 'Неизвестный тип формы');
        return;
    }
    
    const formData = new FormData(formElement);
    const recordId = formData.get('record_id');
    const petId = getSelectedPetId();
    
    if (!petId) {
        showAlert('error', 'Выберите животное в меню навигации');
        return;
    }
    
    formData.set('pet_id', petId);
    const data = config.transformData(formData);
    
    try {
        const url = recordId ? `${config.endpoint}/${recordId}` : config.endpoint;
        const method = recordId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        if (response.ok) {
            showAlert('success', result.message || config.successMessage(!!recordId));
            formElement.reset();
            formElement.querySelector('[name="record_id"]').value = '';
            resetFormDefaults();
            setTimeout(() => {
                showScreen('main-menu');
                if (recordId) {
                    showScreen('history');
                    showHistoryTab(formType);
                }
            }, 150);
        } else {
            showAlert('error', result.error || 'Ошибка при сохранении');
        }
    } catch (error) {
        showAlert('error', 'Ошибка при сохранении');
    }
}

