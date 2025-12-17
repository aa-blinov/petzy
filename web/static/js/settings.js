// Модуль для работы с настройками
const SettingsModule = {
    DEFAULT_SETTINGS: {
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
        },
        'eye-drops': {
            drops_type: 'Обычные'
        }
    },

    loadSettings() {
        const saved = localStorage.getItem('formDefaults');
        if (saved) {
            try {
                const settings = JSON.parse(saved);
                // Ensure backward compatibility - add color if missing
                if (settings.defecation && !settings.defecation.color) {
                    settings.defecation.color = 'Коричневый';
                }
                return settings;
            } catch (e) {
                console.error('Error loading settings:', e);
            }
        }
        return this.DEFAULT_SETTINGS;
    },

    saveSettings(settings) {
        localStorage.setItem('formDefaults', JSON.stringify(settings));
    },

    getSettings() {
        return this.loadSettings();
    },

    loadSettingsForm() {
        const settings = this.getSettings();
        document.getElementById('default-asthma-duration').value = settings.asthma.duration;
        document.getElementById('default-asthma-inhalation').value = settings.asthma.inhalation;
        document.getElementById('default-asthma-reason').value = settings.asthma.reason;
        document.getElementById('default-defecation-stool-type').value = settings.defecation.stool_type;
        document.getElementById('default-defecation-color').value = settings.defecation.color || 'Коричневый';
        document.getElementById('default-defecation-food').value = settings.defecation.food;
        document.getElementById('default-weight-food').value = settings.weight.food;
        document.getElementById('default-eye-drops-type').value = settings['eye-drops']?.drops_type || 'Обычные';
    },

    resetSettingsToDefaults() {
        if (confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?')) {
            this.saveSettings(this.DEFAULT_SETTINGS);
            this.loadSettingsForm();
            if (typeof showAlert === 'function') {
                showAlert('success', 'Настройки сброшены к значениям по умолчанию');
            }
        }
    }
};

// Глобальные функции для обратной совместимости
const DEFAULT_SETTINGS = SettingsModule.DEFAULT_SETTINGS;

function loadSettings() {
    return SettingsModule.loadSettings();
}

function saveSettings(settings) {
    return SettingsModule.saveSettings(settings);
}

function getSettings() {
    return SettingsModule.getSettings();
}

function loadSettingsForm() {
    return SettingsModule.loadSettingsForm();
}

function resetSettingsToDefaults() {
    return SettingsModule.resetSettingsToDefaults();
}

