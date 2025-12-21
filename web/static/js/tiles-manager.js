// Модуль для управления тайлами дашборда (порядок и видимость)
const TilesManager = {
    // Конфигурация всех тайлов
    tilesConfig: [
        { id: 'feeding', title: 'Дневная порция корма', subtitle: 'Записать порцию', color: 'brown', screen: 'feeding-form' },
        { id: 'weight', title: 'Вес', subtitle: 'Записать вес', color: 'orange', screen: 'weight-form' },
        { id: 'asthma', title: 'Приступ астмы', subtitle: 'Записать приступ', color: 'red', screen: 'asthma-form' },
        { id: 'defecation', title: 'Дефекация', subtitle: 'Записать дефекацию', color: 'green', screen: 'defecation-form' },
        { id: 'litter', title: 'Смена лотка', subtitle: 'Записать смену лотка', color: 'purple', screen: 'litter-form' },
        { id: 'eye_drops', title: 'Закапывание глаз', subtitle: 'Записать капли', color: 'teal', screen: 'eye-drops-form' },
        { id: 'tooth_brushing', title: 'Чистка зубов', subtitle: 'Записать чистку', color: 'cyan', screen: 'tooth-brushing-form' },
        { id: 'ear_cleaning', title: 'Чистка ушей', subtitle: 'Записать чистку', color: 'yellow', screen: 'ear-cleaning-form' },
        { id: 'history', title: 'История', subtitle: 'Просмотр записей', color: 'blue', screen: 'history' },
        { id: 'admin', title: 'Админ-панель', subtitle: 'Управление пользователями', color: 'pink', screen: 'admin-panel', isAdmin: true }
    ],

    // Получить настройки тайлов из localStorage
    getTilesSettings() {
        try {
            const saved = localStorage.getItem('tilesSettings');
            if (saved) {
                const parsed = JSON.parse(saved);
                // Убеждаемся, что все тайлы из конфига присутствуют в настройках
                const defaultOrder = this.tilesConfig.map(tile => tile.id);
                const defaultVisible = this.tilesConfig.reduce((acc, tile) => {
                    if (acc[tile.id] === undefined) {
                        acc[tile.id] = true;
                    }
                    return acc;
                }, parsed.visible || {});
                
                // Добавляем отсутствующие тайлы в конец порядка
                const missingTiles = defaultOrder.filter(id => !parsed.order.includes(id));
                parsed.order = [...parsed.order, ...missingTiles];
                
                return {
                    order: parsed.order,
                    visible: defaultVisible
                };
            }
        } catch (e) {
            console.error('Error loading tiles settings:', e);
        }
        // Возвращаем настройки по умолчанию (все видимы, порядок по умолчанию)
        return {
            order: this.tilesConfig.map(tile => tile.id),
            visible: this.tilesConfig.reduce((acc, tile) => {
                acc[tile.id] = true;
                return acc;
            }, {})
        };
    },

    // Сохранить настройки тайлов в localStorage
    saveTilesSettings(settings) {
        try {
            localStorage.setItem('tilesSettings', JSON.stringify(settings));
        } catch (e) {
            console.error('Error saving tiles settings:', e);
        }
    },

    // Применить настройки тайлов к дашборду
    applyTilesSettings() {
        const settings = this.getTilesSettings();
        const container = document.getElementById('action-cards-container');
        if (!container) return;

        // Очищаем контейнер
        container.innerHTML = '';

        // Создаем тайлы в нужном порядке
        settings.order.forEach(tileId => {
            const tileConfig = this.tilesConfig.find(t => t.id === tileId);
            if (!tileConfig) return;

            // Пропускаем админ-панель, если пользователь не админ
            if (tileConfig.isAdmin) {
                // Проверяем статус администратора через UsersModule
                if (typeof UsersModule === 'undefined' || !UsersModule.isAdmin) {
                    return;
                }
            }

            // Пропускаем скрытые тайлы
            if (!settings.visible[tileId]) return;

            const tile = document.createElement('div');
            tile.className = `card action-card${tileConfig.isAdmin ? ' admin-link' : ''}`;
            tile.setAttribute('data-tile-id', tileId);
            tile.setAttribute('data-color', tileConfig.color);
            tile.onclick = () => showScreen(tileConfig.screen);
            tile.innerHTML = `
                <h3>${tileConfig.title}</h3>
                <p>${tileConfig.subtitle}</p>
            `;
            // Для админ-панели устанавливаем display в зависимости от статуса
            if (tileConfig.isAdmin) {
                if (typeof UsersModule !== 'undefined' && UsersModule.isAdmin) {
                    tile.style.display = 'flex';
                } else {
                    tile.style.display = 'none';
                }
            }
            container.appendChild(tile);
        });
    },

    // Инициализировать настройки тайлов в UI настроек
    initTilesSettingsUI() {
        const container = document.getElementById('tiles-settings-list');
        if (!container) return;

        const settings = this.getTilesSettings();
        container.innerHTML = '';

        // Создаем элементы для каждого тайла
        settings.order.forEach(tileId => {
            const tileConfig = this.tilesConfig.find(t => t.id === tileId);
            if (!tileConfig) return;

            // Пропускаем админ-панель в настройках, если пользователь не админ
            if (tileConfig.isAdmin) {
                if (typeof UsersModule === 'undefined' || !UsersModule.isAdmin) {
                    return;
                }
            }

            const item = document.createElement('div');
            item.className = 'tile-settings-item';
            item.setAttribute('data-tile-id', tileId);
            item.innerHTML = `
                <div class="tile-settings-drag-handle" data-drag-handle="true">☰</div>
                <div class="tile-settings-content">
                    <div class="tile-settings-info">
                        <strong>${tileConfig.title}</strong>
                        <span class="tile-settings-subtitle">${tileConfig.subtitle}</span>
                    </div>
                    <label class="tile-settings-toggle">
                        <input type="checkbox" ${settings.visible[tileId] ? 'checked' : ''} 
                               onchange="TilesManager.toggleTileVisibility('${tileId}', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            `;
            container.appendChild(item);
        });

        // Добавляем обработчики drag and drop
        this.initDragAndDrop();
    },

    // Инициализировать drag and drop (с поддержкой touch для мобильных)
    initDragAndDrop() {
        const container = document.getElementById('tiles-settings-list');
        if (!container) return;

        // Используем IIFE для изоляции состояния и предотвращения утечек памяти
        const dragState = (() => {
            let draggedElement = null;
            let touchStartY = 0;
            let touchStartX = 0;
            let touchCurrentY = 0;
            let isDragging = false;
            let touchTarget = null;
            let rafId = null;
            let pendingY = null;
            let scrollInterval = null;
            let currentScrollY = 0;
            let isInScrollZone = false;
            
            return {
                get draggedElement() { return draggedElement; },
                set draggedElement(val) { draggedElement = val; },
                get touchStartY() { return touchStartY; },
                set touchStartY(val) { touchStartY = val; },
                get touchStartX() { return touchStartX; },
                set touchStartX(val) { touchStartX = val; },
                get touchCurrentY() { return touchCurrentY; },
                set touchCurrentY(val) { touchCurrentY = val; },
                get isDragging() { return isDragging; },
                set isDragging(val) { isDragging = val; },
                get touchTarget() { return touchTarget; },
                set touchTarget(val) { touchTarget = val; },
                get rafId() { return rafId; },
                set rafId(val) { rafId = val; },
                get pendingY() { return pendingY; },
                set pendingY(val) { pendingY = val; },
                get scrollInterval() { return scrollInterval; },
                set scrollInterval(val) { scrollInterval = val; },
                get currentScrollY() { return currentScrollY; },
                set currentScrollY(val) { currentScrollY = val; },
                get isInScrollZone() { return isInScrollZone; },
                set isInScrollZone(val) { isInScrollZone = val; },
                clearAll() {
                    draggedElement = null;
                    touchStartY = 0;
                    touchStartX = 0;
                    touchCurrentY = 0;
                    isDragging = false;
                    touchTarget = null;
                    if (rafId !== null) {
                        cancelAnimationFrame(rafId);
                        rafId = null;
                    }
                    if (scrollInterval !== null) {
                        clearInterval(scrollInterval);
                        scrollInterval = null;
                    }
                    isInScrollZone = false;
                    currentScrollY = 0;
                    pendingY = null;
                }
            };
        })();

        // Функция для очистки визуальных эффектов
        const clearIndicators = () => {
            Array.from(container.children).forEach(el => {
                if (el.classList.contains('tile-settings-item')) {
                    el.classList.remove('drag-over-top', 'drag-over-bottom');
                }
            });
        };

        // Функция для определения элемента под курсором/пальцем
        const getElementAtPosition = (y) => {
            const items = Array.from(container.children);
            for (const item of items) {
                if (!item.classList.contains('tile-settings-item') || item.classList.contains('dragging')) {
                    continue;
                }
                const rect = item.getBoundingClientRect();
                if (y >= rect.top && y <= rect.bottom) {
                    return item;
                }
            }
            return null;
        };

        // Функция для автоскролла страницы при перетаскивании к краю экрана
        const handleAutoScroll = (y) => {
            if (!dragState.draggedElement) {
                stopAutoScroll();
                return;
            }
            
            dragState.currentScrollY = y;
            
            const scrollThreshold = 100;
            const viewportHeight = window.innerHeight;
            
            const inTopZone = y < scrollThreshold;
            const inBottomZone = y > viewportHeight - scrollThreshold;
            const shouldScroll = inTopZone || inBottomZone;
            
            if (shouldScroll && !dragState.isInScrollZone) {
                dragState.isInScrollZone = true;
                startAutoScroll();
            } else if (!shouldScroll && dragState.isInScrollZone) {
                stopAutoScroll();
            }
        };
        
        // Запуск автоскролла (интервал создается один раз)
        const startAutoScroll = () => {
            if (dragState.scrollInterval !== null) return;
            
            const scrollSpeed = 15;
            const scrollThreshold = 100;
            const viewportHeight = window.innerHeight;
            
            dragState.scrollInterval = setInterval(() => {
                if (!dragState.draggedElement) {
                    stopAutoScroll();
                    return;
                }
                
                const y = dragState.currentScrollY;
                
                // Скролл вверх
                if (y < scrollThreshold) {
                    const distanceFromTop = y;
                    const speed = Math.max(5, scrollSpeed * (1 - distanceFromTop / scrollThreshold));
                    
                    if (window.scrollY > 0) {
                        window.scrollBy(0, -speed);
                    } else {
                        stopAutoScroll();
                    }
                }
                // Скролл вниз
                else if (y > viewportHeight - scrollThreshold) {
                    const distanceFromBottom = viewportHeight - y;
                    const speed = Math.max(5, scrollSpeed * (1 - distanceFromBottom / scrollThreshold));
                    const maxScroll = document.documentElement.scrollHeight - viewportHeight;
                    
                    if (window.scrollY < maxScroll) {
                        window.scrollBy(0, speed);
                    } else {
                        stopAutoScroll();
                    }
                }
                // Вышли из зоны скролла
                else {
                    stopAutoScroll();
                }
            }, 16);
        };
        
        // Остановка автоскролла
        const stopAutoScroll = () => {
            if (dragState.scrollInterval !== null) {
                clearInterval(dragState.scrollInterval);
                dragState.scrollInterval = null;
            }
            dragState.isInScrollZone = false;
        };

        // Оптимизированное обновление индикаторов с троттлингом
        const updateDragIndicator = (() => {
            let lastUpdate = 0;
            const UPDATE_INTERVAL = 16; // ~60fps
            
            return (y) => {
                if (!dragState.draggedElement) return;
                
                const now = performance.now();
                dragState.pendingY = y;
                
                // Обрабатываем автоскролл
                handleAutoScroll(y);
                
                // Троттлинг через requestAnimationFrame
                if (dragState.rafId === null) {
                    dragState.rafId = requestAnimationFrame(() => {
                        if (dragState.pendingY !== null && dragState.draggedElement) {
                            clearIndicators();
                            const targetItem = getElementAtPosition(dragState.pendingY);
                            
                            if (targetItem && targetItem !== dragState.draggedElement) {
                                const rect = targetItem.getBoundingClientRect();
                                const midpoint = rect.top + rect.height / 2;
                                
                                if (dragState.pendingY < midpoint) {
                                    targetItem.classList.add('drag-over-top');
                                } else {
                                    const nextSibling = targetItem.nextElementSibling;
                                    if (nextSibling && nextSibling !== dragState.draggedElement) {
                                        nextSibling.classList.add('drag-over-top');
                                    } else {
                                        targetItem.classList.add('drag-over-bottom');
                                    }
                                }
                            }
                        }
                        dragState.rafId = null;
                        dragState.pendingY = null;
                    });
                }
            };
        })();

        // Функция для завершения перетаскивания
        const finishDrag = (y, isTouch = false) => {
            if (!dragState.draggedElement) return;
            if (isTouch && !dragState.isDragging) return;
            
            // Проверка границ контейнера
            const containerRect = container.getBoundingClientRect();
            if (y < containerRect.top - 50 || y > containerRect.bottom + 50) {
                // Отмена перетаскивания при выходе за пределы
                clearIndicators();
                if (dragState.draggedElement) {
                    dragState.draggedElement.classList.remove('dragging');
                }
                dragState.clearAll();
                return;
            }
            
            const targetItem = getElementAtPosition(y);
            if (targetItem && targetItem !== dragState.draggedElement) {
                const rect = targetItem.getBoundingClientRect();
                const midpoint = rect.top + rect.height / 2;
                
                if (y < midpoint) {
                    container.insertBefore(dragState.draggedElement, targetItem);
                } else {
                    container.insertBefore(dragState.draggedElement, targetItem.nextSibling);
                }
                
                this.saveTilesOrder();
            }
            
            clearIndicators();
            if (dragState.draggedElement) {
                dragState.draggedElement.classList.remove('dragging');
            }
            dragState.clearAll();
        };

        // Обработчики событий для каждого элемента
        container.querySelectorAll('.tile-settings-item').forEach(item => {
            const dragHandle = item.querySelector('.tile-settings-drag-handle');
            if (!dragHandle) return;
            
            // Desktop: HTML5 drag and drop
            dragHandle.setAttribute('draggable', 'true');
            
            dragHandle.addEventListener('dragstart', (e) => {
                dragState.draggedElement = item;
                item.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/html', item.innerHTML);
            });

            dragHandle.addEventListener('dragend', () => {
                stopAutoScroll();
                item.classList.remove('dragging');
                dragState.clearAll();
                clearIndicators();
            });

            // Обработчики для контейнера (для drag&drop)
            container.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                updateDragIndicator(e.clientY);
            });

            container.addEventListener('dragleave', (e) => {
                if (!container.contains(e.relatedTarget)) {
                    clearIndicators();
                }
            });

            container.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                finishDrag(e.clientY, false);
            });

            // Mobile: Touch events
            dragHandle.addEventListener('touchstart', (e) => {
                const touch = e.touches[0];
                const target = e.target;
                
                if (!target.closest('.tile-settings-drag-handle')) {
                    return;
                }
                
                dragState.draggedElement = item;
                dragState.touchStartY = touch.clientY;
                dragState.touchStartX = touch.clientX;
                dragState.touchCurrentY = dragState.touchStartY;
                dragState.touchTarget = target;
                dragState.isDragging = false;
            }, { passive: true });

            item.addEventListener('touchmove', (e) => {
                if (!dragState.draggedElement || dragState.draggedElement !== item) {
                    return;
                }
                
                const touch = e.touches[0];
                const currentY = touch.clientY;
                const currentX = touch.clientX;
                const deltaY = currentY - dragState.touchStartY;
                const deltaX = currentX - dragState.touchStartX;
                const absDeltaY = Math.abs(deltaY);
                const absDeltaX = Math.abs(deltaX);
                
                if (!dragState.isDragging) {
                    const isVerticalDrag = absDeltaY > 10 && absDeltaY > absDeltaX;
                    const isSmallHorizontal = absDeltaX < 20 && absDeltaY > 5;
                    
                    if (isVerticalDrag || isSmallHorizontal) {
                        dragState.isDragging = true;
                        item.classList.add('dragging');
                        dragState.touchCurrentY = currentY;
                        if (e.cancelable) {
                            e.preventDefault();
                        }
                    } else if (absDeltaY > 30 || absDeltaX > 40) {
                        dragState.clearAll();
                        return;
                    }
                }
                
                if (dragState.isDragging) {
                    dragState.touchCurrentY = currentY;
                    updateDragIndicator(dragState.touchCurrentY);
                    if (e.cancelable) {
                        e.preventDefault();
                    }
                }
            }, { passive: false });

            item.addEventListener('touchend', (e) => {
                if (!dragState.draggedElement || dragState.draggedElement !== item) {
                    dragState.clearAll();
                    return;
                }
                
                if (dragState.isDragging) {
                    finishDrag(dragState.touchCurrentY, true);
                    if (e.cancelable) {
                        e.preventDefault();
                    }
                }
                
                stopAutoScroll();
                dragState.clearAll();
            });

            item.addEventListener('touchcancel', () => {
                if (dragState.draggedElement === item) {
                    clearIndicators();
                    if (dragState.draggedElement) {
                        dragState.draggedElement.classList.remove('dragging');
                    }
                    dragState.clearAll();
                }
            });
        });
        
        // Очистка при уничтожении компонента
        const cleanup = () => {
            dragState.clearAll();
            clearIndicators();
        };
        
        // Сохраняем cleanup для внешнего вызова
        this._cleanupDragAndDrop = cleanup;
    },

    // Функция для очистки ресурсов
    cleanup() {
        if (this._cleanupDragAndDrop) {
            this._cleanupDragAndDrop();
            this._cleanupDragAndDrop = null;
        }
    },

    // Сохранить порядок тайлов
    saveTilesOrder() {
        const container = document.getElementById('tiles-settings-list');
        if (!container) return;

        const order = Array.from(container.querySelectorAll('.tile-settings-item')).map(item => 
            item.getAttribute('data-tile-id')
        );

        const settings = this.getTilesSettings();
        settings.order = order;
        this.saveTilesSettings(settings);
    },

    // Переключить видимость тайла
    toggleTileVisibility(tileId, visible) {
        const settings = this.getTilesSettings();
        settings.visible[tileId] = visible;
        this.saveTilesSettings(settings);
    },

    // Сохранить настройки тайлов из формы
    saveTilesSettingsFromForm() {
        const container = document.getElementById('tiles-settings-list');
        if (!container) return;

        const order = Array.from(container.querySelectorAll('.tile-settings-item')).map(item => 
            item.getAttribute('data-tile-id')
        );

        const visible = {};
        container.querySelectorAll('.tile-settings-item').forEach(item => {
            const tileId = item.getAttribute('data-tile-id');
            const checkbox = item.querySelector('input[type="checkbox"]');
            visible[tileId] = checkbox ? checkbox.checked : true;
        });

        this.saveTilesSettings({ order, visible });
    },

    // Сбросить настройки тайлов к значениям по умолчанию
    resetTilesSettings() {
        // Удаляем сохраненные настройки тайлов
        try {
            localStorage.removeItem('tilesSettings');
        } catch (e) {
            console.error('Error resetting tiles settings:', e);
        }
        
        // Переинициализируем UI тайлов с настройками по умолчанию
        this.initTilesSettingsUI();
        
        // Применяем настройки к дашборду
        this.applyTilesSettings();
    }
};
