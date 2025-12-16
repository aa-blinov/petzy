// Модуль для работы с пользователями (админ-панель)
const UsersModule = {
    isAdmin: false,
    STORAGE_KEY: 'user_is_admin',
    STORAGE_TIMESTAMP_KEY: 'user_is_admin_timestamp',
    CACHE_DURATION: 24 * 60 * 60 * 1000, // 24 часа в миллисекундах

    // Получить статус администратора из localStorage
    getCachedAdminStatus() {
        try {
            const cached = localStorage.getItem(this.STORAGE_KEY);
            const timestamp = localStorage.getItem(this.STORAGE_TIMESTAMP_KEY);
            
            if (cached && timestamp) {
                const cacheAge = Date.now() - parseInt(timestamp, 10);
                // Если кеш свежий (меньше 24 часов), используем его
                if (cacheAge < this.CACHE_DURATION) {
                    return cached === 'true';
                } else {
                    // Кеш устарел, удаляем
                    this.clearAdminCache();
                }
            }
            return null; // Кеша нет или он устарел
        } catch (error) {
            console.error('Error reading admin status from cache:', error);
            return null;
        }
    },

    // Сохранить статус администратора в localStorage
    saveAdminStatus(isAdmin) {
        try {
            localStorage.setItem(this.STORAGE_KEY, isAdmin ? 'true' : 'false');
            localStorage.setItem(this.STORAGE_TIMESTAMP_KEY, Date.now().toString());
            this.isAdmin = isAdmin;
        } catch (error) {
            console.error('Error saving admin status to cache:', error);
        }
    },

    // Очистить кеш статуса администратора
    clearAdminCache() {
        try {
            localStorage.removeItem(this.STORAGE_KEY);
            localStorage.removeItem(this.STORAGE_TIMESTAMP_KEY);
            this.isAdmin = false;
        } catch (error) {
            console.error('Error clearing admin cache:', error);
        }
    },

    // Обновить статус администратора (принудительно)
    async refreshAdminStatus() {
        try {
            const response = await fetch('/api/auth/check-admin', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const result = await response.json();
                const isAdmin = result.isAdmin === true;
                this.saveAdminStatus(isAdmin);
                return isAdmin;
            } else {
                // Если ошибка сервера, считаем что не админ
                this.saveAdminStatus(false);
                return false;
            }
        } catch (error) {
            console.error('Error checking admin status:', error);
            this.saveAdminStatus(false);
            return false;
        }
    },

    // Проверить статус администратора (с кешированием)
    async checkAdminStatus(forceRefresh = false) {
        // Если принудительное обновление, пропускаем кеш
        if (!forceRefresh) {
            const cached = this.getCachedAdminStatus();
            if (cached !== null) {
                // Используем кеш
                this.isAdmin = cached;
                this.updateAdminUI();
                return this.isAdmin;
            }
        }

        // Кеша нет или требуется обновление - делаем запрос
        const isAdmin = await this.refreshAdminStatus();
        this.updateAdminUI();
        return isAdmin;
    },

    // Обновить UI в зависимости от статуса администратора
    updateAdminUI() {
        const adminLink = document.querySelector('.admin-link');
        if (adminLink) {
            adminLink.style.display = this.isAdmin ? 'flex' : 'none';
        }
    },

    // Инициализация: загрузить статус из кеша
    init() {
        const cached = this.getCachedAdminStatus();
        if (cached !== null) {
            this.isAdmin = cached;
            this.updateAdminUI();
        }
        // Асинхронно обновим статус в фоне (без блокировки UI)
        this.checkAdminStatus().catch(error => {
            console.error('Error initializing admin status:', error);
        });
    },

    async loadUsersList() {
        const container = document.getElementById('users-list');
        if (!container) return;
        
        container.innerHTML = '<div class="loading">Загрузка...</div>';
        
        try {
            const response = await fetch('/api/users', {
                credentials: 'include'
            });
            
            if (!response.ok) {
                container.innerHTML = '<div class="error">Ошибка загрузки пользователей</div>';
                return;
            }
            
            const data = await response.json();
            const users = data.users || [];
            
            if (users.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>Нет пользователей</p></div>';
                return;
            }
            
            // Desktop table view
            let html = '<div class="users-table">';
            html += '<div class="table-header">';
            html += '<div>Имя пользователя</div>';
            html += '<div>Полное имя</div>';
            html += '<div>Email</div>';
            html += '<div>Статус</div>';
            html += '<div>Действия</div>';
            html += '</div>';
            
            users.forEach(user => {
                html += `<div class="table-row">`;
                html += `<div>${user.username}</div>`;
                html += `<div>${user.full_name || '-'}</div>`;
                html += `<div>${user.email || '-'}</div>`;
                html += `<div>${user.is_active ? 'Активен' : 'Неактивен'}</div>`;
                html += `<div class="table-actions">`;
                html += `<button class="btn btn-secondary btn-small" onclick="UsersModule.editUser('${user.username}')">Редактировать</button>`;
                if (user.username !== 'admin') {
                    html += `<button class="btn btn-secondary btn-small" onclick="UsersModule.resetUserPassword('${user.username}')">Сбросить пароль</button>`;
                    if (user.is_active) {
                        html += `<button class="btn btn-secondary btn-small" onclick="UsersModule.deactivateUser('${user.username}')">Деактивировать</button>`;
                    } else {
                        html += `<button class="btn btn-primary btn-small" onclick="UsersModule.activateUser('${user.username}')">Активировать</button>`;
                    }
                }
                html += `</div></div>`;
            });
            html += '</div>';
            
            // Mobile card view
            html += '<div class="users-cards">';
            users.forEach(user => {
                html += `<div class="user-card">`;
                html += `<div class="user-card-header">`;
                html += `<div class="user-card-title">`;
                html += `<h4>${user.username}</h4>`;
                html += `<span class="user-status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Активен' : 'Неактивен'}</span>`;
                html += `</div></div>`;
                html += `<div class="user-card-body">`;
                if (user.full_name) {
                    html += `<div class="user-card-field">`;
                    html += `<span class="user-card-label">Полное имя:</span>`;
                    html += `<span class="user-card-value">${user.full_name}</span>`;
                    html += `</div>`;
                }
                if (user.email) {
                    html += `<div class="user-card-field">`;
                    html += `<span class="user-card-label">Email:</span>`;
                    html += `<span class="user-card-value">${user.email}</span>`;
                    html += `</div>`;
                }
                html += `</div>`;
                html += `<div class="user-card-actions">`;
                html += `<button class="btn btn-secondary btn-block" onclick="UsersModule.editUser('${user.username}')">Редактировать</button>`;
                if (user.username !== 'admin') {
                    html += `<button class="btn btn-secondary btn-block" onclick="UsersModule.resetUserPassword('${user.username}')">Сбросить пароль</button>`;
                    if (user.is_active) {
                        html += `<button class="btn btn-secondary btn-block" onclick="UsersModule.deactivateUser('${user.username}')">Деактивировать</button>`;
                    } else {
                        html += `<button class="btn btn-primary btn-block" onclick="UsersModule.activateUser('${user.username}')">Активировать</button>`;
                    }
                }
                html += `</div></div>`;
            });
            html += '</div>';
            
            container.innerHTML = html;
        } catch (error) {
            container.innerHTML = '<div class="error">Ошибка загрузки пользователей</div>';
            console.error('Error:', error);
        }
    },

    resetUserForm() {
        document.getElementById('user-record-username').value = '';
        document.getElementById('user-form-element').reset();
        document.getElementById('user-username').value = '';
        document.getElementById('user-username').disabled = false;
        document.getElementById('user-password').value = '';
        document.getElementById('user-password').required = true;
        document.getElementById('user-password-label').textContent = 'Пароль *';
        document.getElementById('user-full-name').value = '';
        document.getElementById('user-email').value = '';
        document.getElementById('user-form-title').textContent = 'Добавить пользователя';
        document.getElementById('user-submit-btn').textContent = 'Сохранить';
    },

    async editUser(username) {
        try {
            const response = await fetch(`/api/users/${username}`, {
                credentials: 'include'
            });
            const data = await response.json();
            const user = data.user;
            
            document.getElementById('user-record-username').value = user.username;
            document.getElementById('user-username').value = user.username;
            document.getElementById('user-username').disabled = true;
            document.getElementById('user-password').value = '';
            document.getElementById('user-password').required = false;
            document.getElementById('user-password-label').textContent = 'Пароль (оставьте пустым, чтобы не менять)';
            document.getElementById('user-full-name').value = user.full_name || '';
            document.getElementById('user-email').value = user.email || '';
            document.getElementById('user-form-title').textContent = 'Редактировать пользователя';
            document.getElementById('user-submit-btn').textContent = 'Обновить';
            
            if (typeof showScreen === 'function') {
                showScreen('user-form');
            }
        } catch (error) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при загрузке пользователя');
            }
            console.error('Error loading user:', error);
        }
    },

    async resetUserPassword(username) {
        const newPassword = prompt('Введите новый пароль:');
        if (!newPassword) return;
        
        try {
            const response = await fetch(`/api/users/${username}/reset-password`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({password: newPassword})
            });
            
            const result = await response.json();
            if (response.ok) {
                if (typeof showAlert === 'function') {
                    showAlert('success', result.message || 'Пароль изменен');
                }
            } else {
                if (typeof showAlert === 'function') {
                    showAlert('error', result.error || 'Ошибка при изменении пароля');
                }
            }
        } catch (error) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при изменении пароля');
            }
        }
    },

    async deactivateUser(username) {
        if (!confirm(`Вы уверены, что хотите деактивировать пользователя ${username}?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/users/${username}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            
            const result = await response.json();
            if (response.ok) {
                if (typeof showAlert === 'function') {
                    showAlert('success', result.message || 'Пользователь деактивирован');
                }
                this.loadUsersList();
            } else {
                if (typeof showAlert === 'function') {
                    showAlert('error', result.error || 'Ошибка при деактивации');
                }
            }
        } catch (error) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при деактивации');
            }
        }
    },

    async activateUser(username) {
        if (!confirm(`Вы уверены, что хотите активировать пользователя ${username}?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/users/${username}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({is_active: true})
            });
            
            const result = await response.json();
            if (response.ok) {
                if (typeof showAlert === 'function') {
                    showAlert('success', result.message || 'Пользователь активирован');
                }
                this.loadUsersList();
            } else {
                if (typeof showAlert === 'function') {
                    showAlert('error', result.error || 'Ошибка при активации');
                }
            }
        } catch (error) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при активации');
            }
        }
    }
};

// Глобальные функции для обратной совместимости
function checkAdminStatus() {
    return UsersModule.checkAdminStatus();
}

function loadUsersList() {
    return UsersModule.loadUsersList();
}

function resetUserForm() {
    return UsersModule.resetUserForm();
}

function editUser(username) {
    return UsersModule.editUser(username);
}

function resetUserPassword(username) {
    return UsersModule.resetUserPassword(username);
}

function deactivateUser(username) {
    return UsersModule.deactivateUser(username);
}

function activateUser(username) {
    return UsersModule.activateUser(username);
}

// Обновить статус администратора (принудительно, с очисткой кеша)
async function refreshAdminStatus() {
    return await UsersModule.checkAdminStatus(true);
}

