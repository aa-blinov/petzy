// Модуль для работы с историей записей
const HistoryModule = {
    currentHistoryType: 'asthma',
    selectedExportType: null,

    // Конфигурация типов записей для истории
    typeConfig: {
        feeding: {
            endpoint: 'feeding',
            dataKey: 'feedings',
            displayName: 'Дневные порции',
            renderDetails: (item) => {
                let html = `<span><strong>Вес корма:</strong> ${item.food_weight} г</span>`;
                if (item.comment && item.comment !== '-') {
                    html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
                }
                return html;
            }
        },
        asthma: {
            endpoint: 'asthma',
            dataKey: 'attacks',
            displayName: 'Приступы астмы',
            renderDetails: (item) => {
                let html = `<span><strong>Длительность:</strong> ${item.duration}</span>`;
                html += `<span><strong>Причина:</strong> ${item.reason}</span>`;
                html += `<span><strong>Ингаляция:</strong> ${item.inhalation}</span>`;
                if (item.comment && item.comment !== '-') {
                    html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
                }
                return html;
            }
        },
        defecation: {
            endpoint: 'defecation',
            dataKey: 'defecations',
            displayName: 'Дефекации',
            renderDetails: (item) => {
                let html = `<span><strong>Тип стула:</strong> ${item.stool_type}</span>`;
                if (item.color) {
                    html += `<span><strong>Цвет стула:</strong> ${item.color}</span>`;
                }
                if (item.food && item.food !== '-') {
                    html += `<span><strong>Корм:</strong> ${item.food}</span>`;
                }
                if (item.comment && item.comment !== '-') {
                    html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
                }
                return html;
            }
        },
        litter: {
            endpoint: 'litter',
            dataKey: 'litter_changes',
            displayName: 'Смена лотка',
            renderDetails: (item) => {
                let html = '';
                if (item.comment && item.comment !== '-') {
                    html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
                }
                return html;
            }
        },
        weight: {
            endpoint: 'weight',
            dataKey: 'weights',
            displayName: 'Вес',
            renderDetails: (item) => {
                let html = `<span><strong>Вес:</strong> ${item.weight} кг</span>`;
                if (item.food && item.food !== '-') {
                    html += `<span><strong>Корм:</strong> ${item.food}</span>`;
                }
                if (item.comment && item.comment !== '-') {
                    html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
                }
                return html;
            }
        }
    },

    formatDateTime(dateTimeStr) {
        if (!dateTimeStr) return '';
        const parts = dateTimeStr.split(' ');
        if (parts.length !== 2) return dateTimeStr;
        const [datePart, timePart] = parts;
        const dateParts = datePart.split('-');
        if (dateParts.length !== 3) return dateTimeStr;
        const [year, month, day] = dateParts;
        return `${day}.${month}.${year} ${timePart}`;
    },

    showHistoryTab(type) {
        this.currentHistoryType = type;
        const config = this.typeConfig[type];
        if (!config) return;
        
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            const isMatch = btn.textContent.includes(config.displayName);
            if (isMatch) {
                btn.classList.add('active');
            }
        });
        
        const content = document.getElementById('history-content');
        const petId = typeof getSelectedPetId === 'function' ? getSelectedPetId() : null;
        
        if (!petId) {
            content.innerHTML = '<div class="empty-state"><p>Выберите животное в меню навигации для просмотра истории</p></div>';
            return;
        }
        
        content.innerHTML = '<div class="loading">Загрузка...</div>';
        
        const endpoint = `/api/${config.endpoint}?pet_id=${petId}`;
        
        fetch(endpoint, { credentials: 'include' })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Ошибка загрузки данных');
                    }).catch(() => {
                        throw new Error('Ошибка загрузки данных');
                    });
                }
                return response.json();
            })
            .then(data => {
                const items = data[config.dataKey] || [];
                
                if (!items || items.length === 0) {
                    content.innerHTML = '<p class="no-data">Нет записей</p>';
                    return;
                }
                
                let html = '<div class="history-list">';
                items.forEach(item => {
                    html += `<div class="history-item history-item-${type}" data-id="${item._id}">`;
                    html += `<div class="history-date">${this.formatDateTime(item.date_time)}</div>`;
                    const username = item.username || '-';
                    html += `<div class="history-user"><strong>Пользователь:</strong> ${username}</div>`;
                    html += `<div class="history-details">${config.renderDetails(item)}</div>`;
                    html += `<div class="history-actions">`;
                    html += `<button class="btn btn-secondary btn-small" onclick="editRecord('${type}', '${item._id}')">Редактировать</button>`;
                    html += `<button class="btn btn-secondary btn-small" onclick="deleteRecord('${type}', '${item._id}')">Удалить</button>`;
                    html += `</div></div>`;
                });
                html += '</div>';
                content.innerHTML = html;
            })
            .catch(error => {
                content.innerHTML = '<p class="error">Ошибка загрузки данных</p>';
                console.error('Error:', error);
            });
    },

    showExportMenu() {
        this.selectedExportType = null;
        document.getElementById('export-type-selection').style.display = 'block';
        document.getElementById('export-format-selection').style.display = 'none';
        document.getElementById('export-back-btn').style.display = 'none';
        document.getElementById('export-cancel-btn').style.display = 'block';
        document.getElementById('export-menu-title').textContent = 'Выберите тип данных:';
        document.getElementById('export-menu').style.display = 'flex';
    },

    hideExportMenu() {
        document.getElementById('export-menu').style.display = 'none';
        this.selectedExportType = null;
    },

    selectExportType(type) {
        this.selectedExportType = type;
        const config = this.typeConfig[type];
        if (!config) return;
        
        document.getElementById('export-type-selection').style.display = 'none';
        document.getElementById('export-format-selection').style.display = 'block';
        document.getElementById('export-back-btn').style.display = 'block';
        document.getElementById('export-cancel-btn').style.display = 'none';
        document.getElementById('export-menu-title').textContent = `Выберите формат (${config.displayName}):`;
    },

    backToExportType() {
        this.selectedExportType = null;
        document.getElementById('export-type-selection').style.display = 'block';
        document.getElementById('export-format-selection').style.display = 'none';
        document.getElementById('export-back-btn').style.display = 'none';
        document.getElementById('export-cancel-btn').style.display = 'block';
        document.getElementById('export-menu-title').textContent = 'Выберите тип данных:';
    },

    async exportData(format) {
        if (!this.selectedExportType) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Выберите тип данных');
            }
            return;
        }
        
        const petId = typeof getSelectedPetId === 'function' ? getSelectedPetId() : null;
        if (!petId) {
            if (typeof showAlert === 'function') {
                showAlert('error', 'Выберите животное');
            }
            return;
        }
        
        const config = this.typeConfig[this.selectedExportType];
        const url = `/api/export/${config.endpoint}/${format}?pet_id=${petId}`;
        
        try {
            const response = await fetch(url, {
                method: 'GET',
                credentials: 'include'
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Ошибка при выгрузке' }));
                if (typeof showAlert === 'function') {
                    showAlert('error', errorData.error || 'Ошибка при выгрузке');
                }
                return;
            }
            
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = '';
            if (contentDisposition) {
                const rfc5987Match = contentDisposition.match(/filename\*=UTF-8''(.+)/);
                if (rfc5987Match) {
                    filename = decodeURIComponent(rfc5987Match[1]);
                } else {
                    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                    if (filenameMatch) {
                        filename = filenameMatch[1];
                    }
                }
            }
            
            if (!filename) {
                filename = `${this.selectedExportType}_${new Date().toISOString().slice(0, 10)}.${format}`;
            }
            
            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = filename;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(blobUrl);
            
            this.hideExportMenu();
            if (typeof showAlert === 'function') {
                showAlert('success', 'Файл выгружен');
            }
        } catch (error) {
            console.error('Export error:', error);
            if (typeof showAlert === 'function') {
                showAlert('error', 'Ошибка при выгрузке файла');
            }
        }
    }
};

// Глобальные функции для обратной совместимости
function showHistoryTab(type) {
    return HistoryModule.showHistoryTab(type);
}

function showExportMenu() {
    return HistoryModule.showExportMenu();
}

function hideExportMenu() {
    return HistoryModule.hideExportMenu();
}

function selectExportType(type) {
    return HistoryModule.selectExportType(type);
}

function backToExportType() {
    return HistoryModule.backToExportType();
}

function exportData(format) {
    return HistoryModule.exportData(format);
}

function formatDateTime(dateTimeStr) {
    return HistoryModule.formatDateTime(dateTimeStr);
}

