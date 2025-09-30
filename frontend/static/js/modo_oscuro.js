class DarkModeManager {
    constructor() {
        this.darkModeKey = 'infojis-dark-mode';
        this.body = document.body;
        this.toggleButton = document.getElementById('darkModeToggle');
        this.iconElement = document.getElementById('darkModeIcon');
        this.mediaQuery = window.matchMedia?.('(prefers-color-scheme: dark)');
        
        this.init();
    }

    init() {
        this.loadDarkModePreference();
        this.toggleButton?.addEventListener('click', () => this.toggleDarkMode());
        this.updateIcon();
        this.setupSystemPreferenceListener();
    }

    toggleDarkMode() {
        const isDarkMode = this.body.classList.toggle('dark');
        this.saveDarkModePreference(isDarkMode);
        this.updateIcon();
        this.showModeChangeNotification(isDarkMode);
    }

    loadDarkModePreference() {
        const savedMode = this.getSavedPreference();
        
        if (savedMode !== null) {
            this.body.classList.toggle('dark', savedMode);
        } else if (this.mediaQuery?.matches) {
            this.body.classList.add('dark');
            this.saveDarkModePreference(true);
        }
    }

    getSavedPreference() {
        try {
            return JSON.parse(localStorage.getItem(this.darkModeKey));
        } catch {
            return null;
        }
    }

    saveDarkModePreference(isDarkMode) {
        try {
            localStorage.setItem(this.darkModeKey, JSON.stringify(isDarkMode));
        } catch (e) {
            console.warn('No se pudo guardar la preferencia de modo oscuro:', e);
        }
    }

    updateIcon() {
        if (!this.iconElement) return;
        
        const isDarkMode = this.body.classList.contains('dark');
        const iconClass = isDarkMode ? 'fas fa-sun' : 'fas fa-moon';
        const ariaLabel = isDarkMode ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
        
        this.iconElement.className = iconClass;
        this.toggleButton?.setAttribute('aria-label', ariaLabel);
    }

    showModeChangeNotification(isDarkMode) {
        const notification = this.createNotification(isDarkMode);
        document.body.appendChild(notification);
        
        // Auto-remove con animación
        setTimeout(() => this.removeNotification(notification), 2000);
    }

    createNotification(isDarkMode) {
        const notification = document.createElement('div');
        const colors = isDarkMode 
            ? { bg: '#2d2d2d', text: '#ffffff', border: '#404040' }
            : { bg: '#ffffff', text: '#333333', border: '#e0e0e0' };
        
        notification.style.cssText = `
            position: fixed; top: 20px; right: 20px; z-index: 9999;
            background: ${colors.bg}; color: ${colors.text};
            border: 1px solid ${colors.border};
            padding: 12px 20px; border-radius: 8px; font-size: 14px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
        `;
        
        notification.innerHTML = `
            <i class="fas fa-${isDarkMode ? 'moon' : 'sun'} me-2"></i>
            Modo ${isDarkMode ? 'oscuro' : 'claro'} activado
        `;
        
        return notification;
    }

    removeNotification(notification) {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => notification.remove(), 300);
    }

    setupSystemPreferenceListener() {
        this.mediaQuery?.addEventListener('change', (e) => {
            // Solo cambiar si no hay preferencia manual guardada
            if (this.getSavedPreference() === null) {
                this.setDarkMode(e.matches);
            }
        });
    }

    // API pública
    isDarkMode() {
        return this.body.classList.contains('dark');
    }

    setDarkMode(enabled) {
        this.body.classList.toggle('dark', enabled);
        this.saveDarkModePreference(enabled);
        this.updateIcon();
    }
}

// Inicialización optimizada
const initDarkMode = () => {
    window.darkModeManager = new DarkModeManager();
};

// Usar el evento más apropiado disponible
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDarkMode);
} else {
    initDarkMode();
}