// Модуль для работы с историей записей
const HistoryModule = {
    currentHistoryType: 'asthma',
    selectedExportType: null,
    pagination: {
        currentPage: 1,
        pageSize: 100,
        total: 0,
        hasMore: false
    },

    // Конфигурация типов записей для истории
    typeConfig: {
        feeding: {
            endpoint: 'feeding',
            dataKey: 'feedings',
            displayName: 'Дневные порции',
            color: 'brown',
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
            color: 'red',
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
            color: 'green',
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
            color: 'purple',
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
            color: 'orange',
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
        },
        'eye_drops': {
            endpoint: 'eye_drops',
            dataKey: 'eye_drops',
            displayName: 'Глаза',
            color: 'teal',
            renderDetails: (item) => {
                let html = `<span><strong>Тип капель:</strong> ${item.drops_type}</span>`;
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

    showHistoryTab(type, resetPagination = true) {
        this.currentHistoryType = type;
        const config = this.typeConfig[type];
        if (!config) return;
        
        // Reset pagination if starting fresh
        if (resetPagination) {
            this.pagination.currentPage = 1;
            this.pagination.total = 0;
            this.pagination.hasMore = false;
        }
        
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            const dataTab = btn.getAttribute('data-tab');
            if (dataTab === type) {
                btn.classList.add('active');
            }
        });
        
        const content = document.getElementById('history-content');
        const petId = typeof getSelectedPetId === 'function' ? getSelectedPetId() : null;
        
        if (!petId) {
            content.innerHTML = '<div class="empty-state"><p>Выберите животное в меню навигации для просмотра истории</p></div>';
            return;
        }
        
        // Show loading only on first page
        if (this.pagination.currentPage === 1) {
            content.innerHTML = '<div class="loading">Загрузка...</div>';
        }
        
        const endpoint = `/api/${config.endpoint}?pet_id=${petId}&page=${this.pagination.currentPage}&page_size=${this.pagination.pageSize}`;
        
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
                
                // Update pagination state
                this.pagination.total = data.total || 0;
                this.pagination.hasMore = (this.pagination.currentPage * this.pagination.pageSize) < this.pagination.total;
                
                if (this.pagination.currentPage === 1 && (!items || items.length === 0)) {
                    content.innerHTML = '<p class="no-data">Нет записей</p>';
                    return;
                }
                
                // Get existing list or create new one
                let listContainer = content.querySelector('.history-list');
                if (!listContainer) {
                    listContainer = document.createElement('div');
                    listContainer.className = 'history-list';
                    content.innerHTML = '';
                    content.appendChild(listContainer);
                }
                
                // Append new items
                items.forEach(item => {
                    const itemElement = document.createElement('div');
                    itemElement.className = 'history-item';
                    itemElement.setAttribute('data-color', config.color);
                    itemElement.setAttribute('data-id', item._id);
                    itemElement.innerHTML = `
                        <div class="history-date">${this.formatDateTime(item.date_time)}</div>
                        <div class="history-user"><strong>Пользователь:</strong> ${item.username || '-'}</div>
                        <div class="history-details">${config.renderDetails(item)}</div>
                        <div class="history-actions">
                            <button class="btn btn-secondary btn-small" onclick="editRecord('${type}', '${item._id}')">Редактировать</button>
                            <button class="btn btn-secondary btn-small" onclick="deleteRecord('${type}', '${item._id}')">Удалить</button>
                        </div>
                    `;
                    listContainer.appendChild(itemElement);
                });
                
                // Update or create pagination controls
                this.updatePaginationControls(content, type);
            })
            .catch(error => {
                if (this.pagination.currentPage === 1) {
                    content.innerHTML = '<p class="error">Ошибка загрузки данных</p>';
                }
                console.error('Error:', error);
            });
    },

    loadMoreHistory() {
        if (!this.pagination.hasMore) return;
        
        this.pagination.currentPage++;
        this.showHistoryTab(this.currentHistoryType, false);
    },

    updatePaginationControls(container, type) {
        // Remove existing pagination controls
        const existingControls = container.querySelector('.history-pagination');
        if (existingControls) {
            existingControls.remove();
        }
        
        // Add pagination controls if there are more records
        if (this.pagination.hasMore) {
            const controls = document.createElement('div');
            controls.className = 'history-pagination';
            controls.innerHTML = `
                <div class="pagination-info">
                    Показано ${Math.min(this.pagination.currentPage * this.pagination.pageSize, this.pagination.total)} из ${this.pagination.total} записей
                </div>
                <button class="btn btn-primary btn-block" onclick="HistoryModule.loadMoreHistory()">
                    Загрузить еще
                </button>
            `;
            container.appendChild(controls);
        } else if (this.pagination.total > 0) {
            // Show total count if all records loaded
            const controls = document.createElement('div');
            controls.className = 'history-pagination';
            controls.innerHTML = `
                <div class="pagination-info">
                    Всего записей: ${this.pagination.total}
                </div>
            `;
            container.appendChild(controls);
        }
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
                    showAlert('error', errorData.error || errorData);
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

