// Модуль для работы с питомцами
const PetsModule = {
    selectedPetId: null,
    selectedPetName: null,

    init() {
        this.selectedPetId = this.getSelectedPetId();
        this.selectedPetName = localStorage.getItem('selectedPetName');
        this.updatePetSwitcher();
    },

    getSelectedPetId() {
        return localStorage.getItem('selectedPetId');
    },

    setSelectedPet(petId, petName) {
        localStorage.setItem('selectedPetId', petId);
        localStorage.setItem('selectedPetName', petName);
        this.selectedPetId = petId;
        this.selectedPetName = petName;
        this.updatePetSwitcher();
        // Reload current screen data if needed
        const activeScreen = document.querySelector('.screen.active');
        if (activeScreen && activeScreen.id === 'history') {
            const currentTab = document.querySelector('.tab-btn.active');
            if (currentTab) {
                const tabType = currentTab.getAttribute('data-tab');
                if (tabType && typeof showHistoryTab === 'function') {
                    showHistoryTab(tabType);
                }
            }
        }
    },

    clearSelectedPet() {
        localStorage.removeItem('selectedPetId');
        localStorage.removeItem('selectedPetName');
        this.selectedPetId = null;
        this.selectedPetName = null;
        this.updatePetSwitcher();
    },

    async loadPets() {
        try {
            const response = await fetch('/api/pets', {
                credentials: 'include'
            });
            const data = await response.json();
            return data.pets || [];
        } catch (error) {
            console.error('Error loading pets:', error);
            return [];
        }
    },

    async renderPetsList() {
        const container = document.getElementById('pets-list');
        if (!container) return;
        
        container.innerHTML = '<div class="loading">Загрузка...</div>';
        
        const pets = await this.loadPets();
        
        if (pets.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>У вас пока нет животных. Создайте первое!</p></div>';
            return;
        }
        
        let html = '<div class="pets-grid">';
        pets.forEach(pet => {
            const photo = pet.photo_url ? pet.photo_url + '?t=' + new Date().getTime() : '';
            const isOwner = pet.current_user_is_owner || false;
            html += `
                <div class="pet-card">
                    <div class="pet-card-content" onclick="PetsModule.selectPet('${pet._id}', '${pet.name}')">
                        ${photo ? `<img src="${photo}" alt="${pet.name}" class="pet-photo">` : '<div class="pet-photo-placeholder">🐱</div>'}
                        <div class="pet-info">
                            <h3>${pet.name}</h3>
                            ${pet.breed ? `<p>${pet.breed}</p>` : ''}
                            ${pet.gender ? `<p>${pet.gender}</p>` : ''}
                        </div>
                    </div>
                    <div class="pet-card-actions">
                        <button class="btn btn-primary btn-small" onclick="event.stopPropagation(); PetsModule.editPet('${pet._id}')">Редактировать</button>
                        ${isOwner ? `<button class="btn btn-secondary btn-small" onclick="event.stopPropagation(); PetsModule.deletePet('${pet._id}', '${pet.name}')">Удалить</button>` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    },

    selectPet(petId, petName) {
        this.setSelectedPet(petId, petName);
        this.updatePetSwitcher();
        
        const activeScreen = document.querySelector('.screen.active');
        const isInForm = activeScreen && (
            activeScreen.id === 'asthma-form' || 
            activeScreen.id === 'defecation-form' ||
            activeScreen.id === 'litter-form' ||
            activeScreen.id === 'weight-form' ||
            activeScreen.id === 'feeding-form' ||
            activeScreen.id === 'pet-form' ||
            activeScreen.id === 'user-form'
        );
        const isInHistory = activeScreen && activeScreen.id === 'history';
        const isInAdminPanel = activeScreen && activeScreen.id === 'admin-panel';
        const isInPetSelector = activeScreen && activeScreen.id === 'pet-selector';
        const isInPetSharing = activeScreen && activeScreen.id === 'pet-sharing';
        
        if (isInForm) {
            // Stay in the form
        } else if (isInHistory && typeof showHistoryTab === 'function') {
            const currentTab = document.querySelector('.tab-btn.active');
            if (currentTab) {
                const tabType = currentTab.getAttribute('data-tab');
                if (tabType) {
                    showHistoryTab(tabType);
                }
            }
        } else if (isInAdminPanel || isInPetSelector || isInPetSharing) {
            // Stay in current screen
        } else if (typeof showScreen === 'function') {
            showScreen('main-menu');
        }
    },

    updatePetSwitcher() {
        const switcher = document.getElementById('pet-switcher');
        const switcherName = document.getElementById('pet-switcher-name');
        
        if (switcher && switcherName) {
            switcher.style.display = 'block';
            if (this.selectedPetId && this.selectedPetName) {
                switcherName.textContent = this.selectedPetName;
            } else {
                switcherName.textContent = 'Выбрать животное';
            }
        }

        // Обновляем состояние карточек действий в дашборде
        const actionCards = document.querySelectorAll('.action-cards .action-card');
        const hasPet = !!this.selectedPetId;
        actionCards.forEach(card => {
            if (hasPet) {
                card.classList.remove('action-card-disabled');
            } else {
                card.classList.add('action-card-disabled');
            }
        });
    },

    async showPetSwitcherMenu() {
        const menu = document.getElementById('pet-switcher-menu');
        const list = document.getElementById('pet-switcher-list');
        
        if (!menu || !list) return;
        
        if (menu.style.display === 'block') {
            this.hidePetSwitcherMenu();
            return;
        }
        
        menu.style.display = 'block';
        list.innerHTML = '<div class="loading">Загрузка...</div>';
        
        const pets = await this.loadPets();
        let html = '';
        
        pets.forEach(pet => {
            const isSelected = pet._id === this.selectedPetId;
            html += `
                <button class="pet-switcher-item ${isSelected ? 'active' : ''}" 
                        onclick="PetsModule.selectPet('${pet._id}', '${pet.name}'); PetsModule.hidePetSwitcherMenu();">
                    ${pet.name}
                </button>
            `;
        });
        
        list.innerHTML = html;
    },

    hidePetSwitcherMenu() {
        const menu = document.getElementById('pet-switcher-menu');
        if (menu) {
            menu.style.display = 'none';
        }
    },

    async checkAndSelectPet() {
        const savedPetId = this.getSelectedPetId();
        if (savedPetId) {
            try {
                const response = await fetch(`/api/pets/${savedPetId}`, {
                    credentials: 'include'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.setSelectedPet(savedPetId, data.pet.name);
                    this.updatePetSwitcher();
                    return true;
                } else if (response.status === 403) {
                    // 403 (FORBIDDEN) - нормальная ситуация: нет доступа к питомцу
                    // Очищаем сохранённый petId, так как доступа больше нет
                    this.clearSelectedPet();
                    this.updatePetSwitcher();
                    return false;
                } else {
                    // Другие ошибки (404, 500 и т.д.) - логируем
                    console.warn(`Error loading pet ${savedPetId}: ${response.status}`);
                    this.clearSelectedPet();
                    this.updatePetSwitcher();
                    return false;
                }
            } catch (error) {
                // Ошибка сети - логируем только реальные ошибки
                console.error('Error checking pet:', error);
                this.clearSelectedPet();
                this.updatePetSwitcher();
                return false;
            }
        }
        
        this.updatePetSwitcher();
        return false;
    },

    async deletePet(petId, petName) {
        if (!confirm(`Удалить питомца «${petName}»? Это действие нельзя отменить.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/pets/${petId}`, {
                method: 'DELETE',
                credentials: 'include'
            });

            const result = await response.json();
            if (response.ok) {
                if (typeof showAlert === 'function') {
                    showAlert('success', result.message || 'Питомец удален');
                }

                // Если удалён выбранный сейчас питомец — очищаем выбор
                if (this.selectedPetId === petId) {
                    this.clearSelectedPet();
                }

                // Обновляем список питомцев
                await this.renderPetsList();
            } else {
                if (typeof showAlert === 'function') {
                    showAlert('error', result.error || 'Ошибка при удалении питомца');
                }
            }
        } catch (error) {
            console.error('Error deleting pet:', error);
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при удалении питомца');
            }
        }
    },

    async editPet(petId) {
        try {
            const response = await fetch(`/api/pets/${petId}`, {
                credentials: 'include'
            });
            const data = await response.json();
            const pet = data.pet;
            
            document.getElementById('pet-record-id').value = pet._id;
            document.getElementById('pet-name').value = pet.name || '';
            document.getElementById('pet-breed').value = pet.breed || '';
            document.getElementById('pet-birth-date').value = pet.birth_date || '';
            document.getElementById('pet-gender').value = pet.gender || '';
            document.getElementById('pet-form-title').textContent = 'Редактировать питомца';
            document.getElementById('pet-submit-btn').textContent = 'Обновить';
            
            const photoCurrent = document.getElementById('pet-photo-current');
            const photoCurrentImg = document.getElementById('pet-photo-current-img');
            if (pet.photo_url) {
                photoCurrentImg.src = pet.photo_url + '?t=' + new Date().getTime();
                photoCurrent.style.display = 'block';
            } else {
                photoCurrent.style.display = 'none';
            }
            
            const accessSection = document.getElementById('pet-access-section');
            if (pet.current_user_is_owner) {
                accessSection.style.display = 'block';
                await this.loadPetAccessInForm(petId);
            } else {
                accessSection.style.display = 'none';
            }
            
            if (typeof showScreen === 'function') {
                showScreen('pet-form');
            }
        } catch (error) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при загрузке питомца');
            }
            console.error('Error loading pet:', error);
        }
    },

    async loadPetAccessInForm(petId) {
        try {
            const response = await fetch(`/api/pets/${petId}`, {
                credentials: 'include'
            });
            const data = await response.json();
            const pet = data.pet;
            
            const sharedList = document.getElementById('pet-shared-with-list');
            const sharedWith = pet.shared_with || [];
            if (sharedWith.length === 0) {
                sharedList.innerHTML = '<div class="empty-state"><p>Нет пользователей с доступом</p></div>';
            } else {
                let html = '<div class="shared-users-list">';
                sharedWith.forEach(username => {
                    html += `
                        <div class="shared-user-item">
                            <div class="shared-user-name">${username}</div>
                            <div class="shared-user-actions">
                                <button class="btn btn-secondary btn-block" onclick="PetsModule.unsharePetFromForm('${petId}', '${username}')">Убрать доступ</button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                sharedList.innerHTML = html;
            }
        } catch (error) {
            console.error('Error loading pet access:', error);
        }
    },

    async sharePetFromForm() {
        const petId = document.getElementById('pet-record-id').value;
        const usernameInput = document.getElementById('share-username-input');
        const username = usernameInput.value.trim();
        
        if (!username) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Введите имя пользователя');
            }
            return;
        }
        
        if (!petId) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Сначала сохраните питомца');
            }
            return;
        }
        
        try {
            const response = await fetch(`/api/pets/${petId}/share`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({username: username})
            });
            
            const result = await response.json();
            if (response.ok) {
                if (typeof showAlert === 'function') {
                    showAlert('success', result.message || 'Доступ предоставлен');
                }
                usernameInput.value = '';
                await this.loadPetAccessInForm(petId);
            } else {
                if (typeof showAlert === 'function') {
                    showAlert('error', result.error || 'Ошибка при предоставлении доступа');
                }
            }
        } catch (error) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при предоставлении доступа');
            }
        }
    },

    async unsharePetFromForm(petId, username) {
        if (!confirm(`Убрать доступ у пользователя ${username}?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/pets/${petId}/share/${username}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            
            const result = await response.json();
            if (response.ok) {
                if (typeof showAlert === 'function') {
                    showAlert('success', result.message || 'Доступ убран');
                }
                await this.loadPetAccessInForm(petId);
            } else {
                if (typeof showAlert === 'function') {
                    showAlert('error', result.error || 'Ошибка при удалении доступа');
                }
            }
        } catch (error) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при удалении доступа');
            }
        }
    },

    showPetSharing(petId, petName) {
        this.setSelectedPet(petId, petName);
        if (typeof loadPetSharing === 'function') {
            loadPetSharing();
        }
    },

    resetPetForm() {
        document.getElementById('pet-form-element').reset();
        document.getElementById('pet-record-id').value = '';
        document.getElementById('pet-form-title').textContent = 'Добавить питомца';
        document.getElementById('pet-submit-btn').textContent = 'Сохранить';
        const preview = document.getElementById('pet-photo-preview');
        const previewImg = document.getElementById('pet-photo-preview-img');
        if (preview) {
            preview.style.display = 'none';
            if (previewImg) {
                previewImg.src = '';
            }
        }
        const photoCurrent = document.getElementById('pet-photo-current');
        if (photoCurrent) {
            photoCurrent.style.display = 'none';
        }
        document.getElementById('pet-access-section').style.display = 'none';
    }
};

// Глобальные функции для обратной совместимости
function getSelectedPetId() {
    return PetsModule.getSelectedPetId();
}

function setSelectedPet(petId, petName) {
    return PetsModule.setSelectedPet(petId, petName);
}

function selectPet(petId, petName) {
    return PetsModule.selectPet(petId, petName);
}

function showPetSwitcherMenu() {
    return PetsModule.showPetSwitcherMenu();
}

function hidePetSwitcherMenu() {
    return PetsModule.hidePetSwitcherMenu();
}

function resetPetForm() {
    return PetsModule.resetPetForm();
}

function sharePetFromForm() {
    return PetsModule.sharePetFromForm();
}

function editPet(petId) {
    return PetsModule.editPet(petId);
}

function showPetSharing(petId, petName) {
    return PetsModule.showPetSharing(petId, petName);
}

function unsharePetFromForm(petId, username) {
    return PetsModule.unsharePetFromForm(petId, username);
}

async function renderPetsList() {
    return await PetsModule.renderPetsList();
}

