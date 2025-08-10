// miniapp.js — основной скрипт для Telegram WebApp

(function() {
    // Инициализация Telegram WebApp
    const tg = window.Telegram.WebApp;
    tg.expand();
    tg.ready();
    
    // Инициализация сессии
    async function initSession() {
        try {
            const user = tg.initDataUnsafe?.user || null;
            if (!user) {
                console.error("User data not available from Telegram");
                return;
            }
            
            // Сохраняем реферальный параметр
            const urlParams = new URLSearchParams(window.location.search);
            const ref = urlParams.get('ref');
            
            // Отправляем данные на сервер
            const payload = {
                user_id: user.id,
                username: user.username || "",
                display_name: `${user.first_name} ${user.last_name || ""}`,
                ref: ref
            };
            
            const response = await fetch('/miniapp/init', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            if (data.success) {
                console.log('Session initialized');
                // Обновляем информацию о пользователе
                document.getElementById('user-mini').textContent = user.first_name || 'Пользователь';
            } else {
                console.error('Session init failed:', data.error);
            }
        } catch (error) {
            console.error('Error initializing session:', error);
        }
    }
    
    // Установка активной вкладки
    function setActiveTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
    }
    
    // Получение активной вкладки из URL
    function getActiveTabFromUrl() {
        const path = window.location.pathname.split('/').pop();
        const tabMap = {
            'home': 'home',
            'nlo': 'nlo',
            'pred': 'pred',
            'predictions': 'pred',
            'profile': 'profile',
            'support': 'support'
        };
        return tabMap[path] || 'home';
    }
    
    // Настройка нижнего меню
    function setupBottomMenu() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                tg.HapticFeedback.impactOccurred('light');
                const tab = btn.dataset.tab;
                const frame = document.getElementById('page-frame');
                
                // Обновляем URL без перезагрузки
                if (tab === 'home') {
                    frame.src = '/miniapp/home';
                    window.history.pushState({}, '', '/miniapp');
                } else if (tab === 'nlo') {
                    frame.src = '/miniapp/nlo';
                } else if (tab === 'pred') {
                    frame.src = '/miniapp/predictions';
                } else if (tab === 'profile') {
                    frame.src = '/miniapp/profile';
                } else if (tab === 'support') {
                    frame.src = '/miniapp/support';
                }
                
                setActiveTab(tab);
            });
        });
    }
    
    // Настройка бокового меню
    function setupSideMenu() {
        const burger = document.getElementById('burger');
        const sideMenu = document.getElementById('side-menu');
        const closeBtn = document.getElementById('close-burger');
        
        if (burger && sideMenu && closeBtn) {
            burger.addEventListener('click', () => {
                tg.HapticFeedback.impactOccurred('medium');
                sideMenu.classList.toggle('hidden');
            });
            
            closeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                tg.HapticFeedback.impactOccurred('light');
                sideMenu.classList.add('hidden');
            });
            
            // Закрытие меню при клике вне его области
            document.addEventListener('click', (e) => {
                if (!sideMenu.contains(e.target) && 
                    !burger.contains(e.target) && 
                    !sideMenu.classList.contains('hidden')) {
                    sideMenu.classList.add('hidden');
                }
            });
        }
    }
    
    // Обработчик кликов по ссылкам
    function setupLinkHandlers() {
        document.addEventListener('click', (e) => {
            let target = e.target;
            while (target && !target.href) {
                target = target.parentElement;
            }
            
            if (target && target.href && !target.target) {
                e.preventDefault();
                const frame = document.getElementById('page-frame');
                if (frame) {
                    frame.src = target.href;
                    
                    // Обновляем историю браузера
                    if (!target.href.includes('#')) {
                        window.history.pushState({}, '', target.href);
                    }
                }
            }
        });
    }
    
    // Обработчик навигации
    function setupNavigation() {
        window.addEventListener('popstate', () => {
            const frame = document.getElementById('page-frame');
            if (frame) {
                frame.src = window.location.pathname;
            }
        });
    }
    
    // Обработчик iframe загрузки
    function setupIframeHandler() {
        const frame = document.getElementById('page-frame');
        if (frame) {
            frame.onload = function() {
                try {
                    // Обновляем активную вкладку на основе содержимого iframe
                    const src = frame.src;
                    if (src.includes('/miniapp/home')) {
                        setActiveTab('home');
                    } else if (src.includes('/miniapp/nlo')) {
                        setActiveTab('nlo');
                    } else if (src.includes('/miniapp/predictions') || 
                               src.includes('/miniapp/pred')) {
                        setActiveTab('pred');
                    } else if (src.includes('/miniapp/profile')) {
                        setActiveTab('profile');
                    } else if (src.includes('/miniapp/support')) {
                        setActiveTab('support');
                    }
                } catch (e) {
                    console.error('Error updating tab state:', e);
                }
            };
        }
    }
    
    // Показ уведомлений
    function showNotification(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type} show`;
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-message">${message}</span>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Удаляем уведомление через 3 секунды
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    }
    
    // Обработчик ошибок
    function setupErrorHandlers() {
        window.onerror = function(message, source, lineno, colno, error) {
            console.error('Global error:', {
                message,
                source,
                lineno,
                colno,
                error
            });
            return true;
        };
        
        // Обработка необработанных промисов
        window.addEventListener('unhandledrejection', event => {
            console.error('Unhandled promise rejection:', event.reason);
            event.preventDefault();
        });
    }
    
    // Опрос уведомлений
    let pollInterval = null;
    
    async function pollNotifications() {
        try {
            const response = await fetch('/miniapp/notifications');
            const data = await response.json();
            
            if (data.length > 0) {
                // Показываем последнее уведомление
                const latest = data[0];
                showLiveBanner(latest);
            }
        } catch (error) {
            console.error('Error polling notifications:', error);
        }
    }
    
    function showLiveBanner(note) {
        const banner = document.getElementById('live-banner');
        if (!banner) return;
        
        banner.innerHTML = `
            <div class="banner-inner">
                <div class="logos">${note.team1} — ${note.team2}</div>
                <div class="score">${note.score1}:${note.score2}</div>
            </div>
        `;
        
        banner.classList.add('pulse');
        
        // Обработчик клика на баннер
        banner.onclick = function() {
            document.getElementById('page-frame').src = `/miniapp/match/${note.id}`;
            hideLiveBanner();
        };
        
        // Автоматическое скрытие через 10 секунд
        setTimeout(hideLiveBanner, 10000);
    }
    
    function hideLiveBanner() {
        const banner = document.getElementById('live-banner');
        if (banner) {
            banner.classList.remove('pulse');
            setTimeout(() => {
                banner.style.opacity = '0';
                setTimeout(() => banner.style.display = 'none', 300);
            }, 300);
        }
    }
    
    // Инициализация приложения
    document.addEventListener('DOMContentLoaded', () => {
        initSession();
        setupBottomMenu();
        setupSideMenu();
        setupLinkHandlers();
        setupNavigation();
        setupIframeHandler();
        setupErrorHandlers();
        
        // Запускаем опрос уведомлений каждые 8 секунд
        pollNotifications();
        pollInterval = setInterval(pollNotifications, 8000);
        
        // Устанавливаем активную вкладку
        const activeTab = getActiveTabFromUrl();
        setActiveTab(activeTab);
    });
    
    // Очистка при разгрузке
    window.addEventListener('beforeunload', () => {
        if (pollInterval) {
            clearInterval(pollInterval);
        }
    });
})();