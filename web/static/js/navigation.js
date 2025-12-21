// Модуль для навигации между экранами
const NavigationModule = {
    showScreen(screenId) {
        // Экраны, которые требуют выбранного питомца
        const petRequiredScreens = [
            'feeding-form',
            'asthma-form',
            'defecation-form',
            'litter-form',
            'weight-form',
            'eye-drops-form',
            'tooth-brushing-form',
            'ear-cleaning-form',
            'history'
        ];

        // Если для экрана нужен питомец, но он не выбран – блокируем переход
        if (petRequiredScreens.includes(screenId)) {
            const petId = typeof getSelectedPetId === 'function' ? getSelectedPetId() : null;
            if (!petId) {
                if (typeof showAlert === 'function') {
                    showAlert('error', 'Сначала выберите животное в меню навигации');
                }
                return;
            }
        }

        // Hide all screens
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        
        // Show selected screen
        const screen = document.getElementById(screenId);
        if (screen) {
            screen.classList.add('active');
            window.scrollTo(0, 0);
            
            // Генерируем формы динамически для типов записей
            const formTypes = ['feeding', 'asthma', 'defecation', 'litter', 'weight', 'eye_drops', 'tooth_brushing', 'ear_cleaning'];
            const formType = formTypes.find(type => {
                let expectedScreenId;
                if (type === 'eye_drops') {
                    expectedScreenId = 'eye-drops-form';
                } else if (type === 'tooth_brushing') {
                    expectedScreenId = 'tooth-brushing-form';
                } else if (type === 'ear_cleaning') {
                    expectedScreenId = 'ear-cleaning-form';
                } else {
                    expectedScreenId = `${type}-form`;
                }
                return screenId === expectedScreenId;
            });
            
            if (formType) {
                let containerIdSuffix = formType;
                if (formType === 'eye_drops') {
                    containerIdSuffix = 'eye-drops';
                } else if (formType === 'tooth_brushing') {
                    containerIdSuffix = 'tooth-brushing';
                } else if (formType === 'ear_cleaning') {
                    containerIdSuffix = 'ear-cleaning';
                }
                const container = document.getElementById(`${containerIdSuffix}-form-container`);
                if (container) {
                    const formElement = document.getElementById(`${formType}-form-element`);
                    const recordId = formElement ? formElement.querySelector('[name="record_id"]')?.value : null;
                    
                    // Создаем форму (уже с настройками из localStorage)
                    if (typeof createFormHTML === 'function') {
                        container.innerHTML = createFormHTML(formType, recordId);
                        
                        // Привязываем обработчик
                        const newForm = document.getElementById(`${formType}-form-element`);
                        if (newForm && typeof handleFormSubmit === 'function') {
                            newForm.addEventListener('submit', (e) => {
                                e.preventDefault();
                                handleFormSubmit(formType, newForm);
                            });
                        }
                        
                        // Сбрасываем значения по умолчанию только для новых записей
                        if (!recordId && typeof resetFormDefaults === 'function') {
                            resetFormDefaults();
                        }
                    }
                }
            } else if (screenId === 'settings') {
                if (typeof loadSettingsForm === 'function') {
                    loadSettingsForm();
                }
                // Инициализировать UI настроек тайлов
                if (typeof TilesManager !== 'undefined') {
                    TilesManager.initTilesSettingsUI();
                }
            } else if (screenId === 'pet-selector') {
                if (typeof PetsModule !== 'undefined' && PetsModule.renderPetsList) {
                    PetsModule.renderPetsList();
                }
            } else if (screenId === 'pet-form') {
                const recordId = document.getElementById('pet-record-id')?.value;
                if (!recordId && typeof resetPetForm === 'function') {
                    resetPetForm();
                }
            } else if (screenId === 'admin-panel') {
                if (typeof UsersModule !== 'undefined' && UsersModule.loadUsersList) {
                    UsersModule.loadUsersList();
                }
            } else if (screenId === 'user-form') {
                const recordUsername = document.getElementById('user-record-username')?.value;
                if (!recordUsername && typeof resetUserForm === 'function') {
                    resetUserForm();
                }
            } else if (screenId === 'pet-sharing') {
                if (typeof loadPetSharing === 'function') {
                    loadPetSharing();
                }
            } else if (screenId === 'history') {
                if (typeof showHistoryTab === 'function') {
                    showHistoryTab('feeding');
                }
            }
            
            // При переходе на любой экран кроме settings очищаем ресурсы drag and drop
            if (screenId !== 'settings' && typeof TilesManager !== 'undefined' && TilesManager.cleanup) {
                TilesManager.cleanup();
            }
        }
    }
};

// Глобальная функция для обратной совместимости
function showScreen(screenId) {
    return NavigationModule.showScreen(screenId);
}

