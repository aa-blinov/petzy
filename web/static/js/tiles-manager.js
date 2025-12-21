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
        { id: 'ear_cleaning', title: 'Чистка ушей', subtitle: 'Записать чистку', color: 'purple', screen: 'ear-cleaning-form' },
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
            // draggable устанавливается только на иконке перетаскивания
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

        let draggedElement = null;
        let touchStartY = 0;
        let touchStartX = 0;
        let touchCurrentY = 0;
        let isDragging = false;
        let touchTarget = null;
        let rafId = null; // Для requestAnimationFrame
        let pendingY = null; // Сохраняем последнюю позицию для обновления
        let scrollInterval = null; // Для автоскролла
        let currentScrollY = 0; // Текущая координата Y для автоскролла
        let isInScrollZone = false; // Флаг, что мы в зоне скролла

        // Функция для очистки визуальных эффектов
        const clearIndicators = () => {
            // Используем children для оптимизации (быстрее чем querySelectorAll)
            Array.from(container.children).forEach(el => {
                if (el.classList.contains('tile-settings-item')) {
                    el.classList.remove('drag-over-top', 'drag-over-bottom');
                }
            });
        };

        // Функция для определения элемента под курсором/пальцем
        const getElementAtPosition = (y) => {
            // Используем children для оптимизации (быстрее чем querySelectorAll)
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
            if (!draggedElement) {
                stopAutoScroll();
                return;
            }
            
            // Обновляем текущую координату
            currentScrollY = y;
            
            const scrollThreshold = 100; // Расстояние от края viewport для начала скролла
            const viewportHeight = window.innerHeight;
            
            // Проверяем, находимся ли мы в зоне скролла
            const inTopZone = y < scrollThreshold;
            const inBottomZone = y > viewportHeight - scrollThreshold;
            const shouldScroll = inTopZone || inBottomZone;
            
            // Если вошли в зону скролла и интервал еще не запущен
            if (shouldScroll && !isInScrollZone) {
                isInScrollZone = true;
                startAutoScroll();
            }
            // Если вышли из зоны скролла
            else if (!shouldScroll && isInScrollZone) {
                stopAutoScroll();
            }
        };
        
        // Запуск автоскролла (интервал создается один раз)
        const startAutoScroll = () => {
            if (scrollInterval !== null) return; // Уже запущен
            
            const scrollSpeed = 15; // Базовая скорость скролла
            const scrollThreshold = 100;
            const viewportHeight = window.innerHeight;
            
            scrollInterval = setInterval(() => {
                if (!draggedElement) {
                    stopAutoScroll();
                    return;
                }
                
                // Используем актуальную координату
                const y = currentScrollY;
                
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
            }, 16); // ~60fps
        };
        
        // Остановка автоскролла
        const stopAutoScroll = () => {
            if (scrollInterval !== null) {
                clearInterval(scrollInterval);
                scrollInterval = null;
            }
            isInScrollZone = false;
        };

        // Функция для обновления индикаторов при перетаскивании (с requestAnimationFrame для поддержки 60/120Hz)
        const updateDragIndicator = (y) => {
            if (!draggedElement) return;
            
            // Сохраняем последнюю позицию
            pendingY = y;
            
            // Обрабатываем автоскролл
            handleAutoScroll(y);
            
            // Если уже есть pending requestAnimationFrame, не создаем новый
            // requestAnimationFrame автоматически синхронизируется с частотой дисплея
            if (rafId === null) {
                rafId = requestAnimationFrame(() => {
                    if (pendingY !== null && draggedElement) {
                        clearIndicators();
                        const targetItem = getElementAtPosition(pendingY);
                        
                        if (targetItem && targetItem !== draggedElement) {
                            const rect = targetItem.getBoundingClientRect();
                            const midpoint = rect.top + rect.height / 2;
                            
                            if (pendingY < midpoint) {
                                targetItem.classList.add('drag-over-top');
                            } else {
                                const nextSibling = targetItem.nextElementSibling;
                                if (nextSibling && nextSibling !== draggedElement) {
                                    nextSibling.classList.add('drag-over-top');
                                } else {
                                    targetItem.classList.add('drag-over-bottom');
                                }
                            }
                        }
                    }
                    rafId = null;
                    pendingY = null;
                });
            }
        };

        // Функция для завершения перетаскивания
        const finishDrag = (y, isTouch = false) => {
            if (!draggedElement) return;
            // Для touch событий проверяем isDragging, для mouse - нет
            if (isTouch && !isDragging) return;
            
            const targetItem = getElementAtPosition(y);
            if (targetItem && targetItem !== draggedElement) {
                const rect = targetItem.getBoundingClientRect();
                const midpoint = rect.top + rect.height / 2;
                
                if (y < midpoint) {
                    container.insertBefore(draggedElement, targetItem);
                } else {
                    container.insertBefore(draggedElement, targetItem.nextSibling);
                }
                
                this.saveTilesOrder();
            }
            
            clearIndicators();
            if (draggedElement) {
                draggedElement.classList.remove('dragging');
            }
            draggedElement = null;
            isDragging = false;
            touchTarget = null;
        };

        container.querySelectorAll('.tile-settings-item').forEach(item => {
            const dragHandle = item.querySelector('.tile-settings-drag-handle');
            if (!dragHandle) return;
            
            // Desktop: HTML5 drag and drop - только на иконке перетаскивания
            dragHandle.setAttribute('draggable', 'true');
            dragHandle.addEventListener('dragstart', (e) => {
                draggedElement = item;
                item.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/html', item.innerHTML);
            });

            dragHandle.addEventListener('dragend', () => {
                // Останавливаем автоскролл
                stopAutoScroll();
                // Отменяем pending requestAnimationFrame
                if (rafId !== null) {
                    cancelAnimationFrame(rafId);
                    rafId = null;
                }
                item.classList.remove('dragging');
                draggedElement = null;
                clearIndicators();
            });

            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                updateDragIndicator(e.clientY);
                // Автоскролл для desktop тоже
                handleAutoScroll(e.clientY);
            });

            item.addEventListener('dragleave', () => {
                // Не очищаем здесь, чтобы индикатор оставался видимым
            });

            item.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                finishDrag(e.clientY, false); // false = mouse event
            });

            // Mobile: Touch events - только на иконке перетаскивания
            dragHandle.addEventListener('touchstart', (e) => {
                const touch = e.touches[0];
                const target = e.target;
                
                // Проверяем, что касание именно на иконке перетаскивания
                if (!target.closest('.tile-settings-drag-handle')) {
                    return;
                }
                
                // Сохраняем начальные данные, но не блокируем прокрутку пока
                draggedElement = item;
                touchStartY = touch.clientY;
                touchStartX = touch.clientX;
                touchCurrentY = touchStartY;
                touchTarget = target;
                isDragging = false;
                
                // НЕ вызываем preventDefault здесь - позволяем прокрутке работать
            }, { passive: true });

            item.addEventListener('touchmove', (e) => {
                // Если перетаскивание не началось или элемент не тот, не обрабатываем
                // Это позволяет скроллу работать нормально
                if (!draggedElement || draggedElement !== item) {
                    return; // Не блокируем скролл - просто выходим
                }
                
                const touch = e.touches[0];
                const currentY = touch.clientY;
                const currentX = touch.clientX;
                const deltaY = currentY - touchStartY;
                const deltaX = currentX - touchStartX;
                const absDeltaY = Math.abs(deltaY);
                const absDeltaX = Math.abs(deltaX);
                
                // Если перетаскивание еще не началось, проверяем, нужно ли его начать
                if (!isDragging) {
                    // Начинаем перетаскивание если:
                    // 1. Вертикальное перемещение больше 10px (уменьшено для более быстрого отклика)
                    // 2. Вертикальное перемещение больше горизонтального (чтобы отличить от скролла)
                    // ИЛИ горизонтальное перемещение очень маленькое (менее 20px) - это точно перетаскивание
                    const isVerticalDrag = absDeltaY > 10 && absDeltaY > absDeltaX;
                    const isSmallHorizontal = absDeltaX < 20 && absDeltaY > 5;
                    
                    if (isVerticalDrag || isSmallHorizontal) {
                        isDragging = true;
                        item.classList.add('dragging');
                        touchCurrentY = currentY;
                        // Только теперь блокируем прокрутку, если событие можно отменить
                        if (e.cancelable) {
                            e.preventDefault();
                        }
                    } else if (absDeltaY > 30 || absDeltaX > 40) {
                        // Если перемещение большое, но не соответствует условиям перетаскивания,
                        // это скорее всего скролл - сбрасываем состояние
                        draggedElement = null;
                        touchTarget = null;
                        isDragging = false;
                        touchStartY = 0;
                        touchStartX = 0;
                        touchCurrentY = 0;
                        // НЕ вызываем preventDefault - позволяем скроллу работать
                        return;
                    }
                    // Если перемещение маленькое (меньше порогов), просто ждем дальше
                    // Не сбрасываем состояние, чтобы дать возможность начать перетаскивание
                }
                
                // Если перетаскивание активно, обновляем позицию и блокируем скролл
                if (isDragging) {
                    touchCurrentY = currentY;
                    // requestAnimationFrame автоматически синхронизируется с частотой дисплея (60/120Hz)
                    updateDragIndicator(touchCurrentY);
                    // Блокируем прокрутку только во время активного перетаскивания
                    if (e.cancelable) {
                        e.preventDefault();
                    }
                }
            }, { passive: false });

            item.addEventListener('touchend', (e) => {
                // Если перетаскивание не началось или элемент не тот, просто сбрасываем состояние
                if (!draggedElement || draggedElement !== item) {
                    // Сбрасываем на всякий случай
                    draggedElement = null;
                    touchTarget = null;
                    isDragging = false;
                    return;
                }
                
                const wasDragging = isDragging;
                
                if (wasDragging) {
                    finishDrag(touchCurrentY, true); // true = touch event
                    // Предотвращаем действие по умолчанию только если событие можно отменить
                    if (e.cancelable) {
                        e.preventDefault();
                    }
                }
                
                // Останавливаем автоскролл
                stopAutoScroll();
                
                // Отменяем pending requestAnimationFrame
                if (rafId !== null) {
                    cancelAnimationFrame(rafId);
                    rafId = null;
                }
                
                // Полностью сбрасываем состояние сразу (не ждем задержку)
                draggedElement = null;
                touchTarget = null;
                isDragging = false;
                touchStartY = 0;
                touchStartX = 0;
                touchCurrentY = 0;
            });

            item.addEventListener('touchcancel', () => {
                if (draggedElement === item) {
                    // Останавливаем автоскролл
                    stopAutoScroll();
                    // Отменяем pending requestAnimationFrame
                    if (rafId !== null) {
                        cancelAnimationFrame(rafId);
                        rafId = null;
                    }
                    clearIndicators();
                    if (draggedElement) {
                        draggedElement.classList.remove('dragging');
                    }
                    // Полностью сбрасываем состояние
                    draggedElement = null;
                    isDragging = false;
                    touchTarget = null;
                    touchStartY = 0;
                    touchStartX = 0;
                    touchCurrentY = 0;
                }
            });
        });
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
        // Применить изменения сразу (опционально, можно убрать для применения только при сохранении)
        // this.applyTilesSettings();
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
    }
};

