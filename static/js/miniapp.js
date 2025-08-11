// miniapp.js — основной скрипт для Telegram WebApp

(function() {
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
        
        // Проверяем, что это внутренняя ссылка
        if (target && target.href && target.href.includes(window.location.host)) {
            e.preventDefault();
            
            // Открываем ссылку в iframe
            const frame = document.getElementById('page-frame');
            if (frame) {
                frame.src = target.href;
                
                // Обновляем историю браузера
                if (!target.href.includes('#')) {
                    window.history.pushState({}, '', target.href);
                }
                
                // Закрываем боковое меню при переходе
                document.getElementById('side-menu').classList.add('hidden');
            }
        }
        // Для внешних ссылок открываем в том же окне
        else if (target && target.href && !target.target) {
            e.preventDefault();
            window.location.href = target.href;
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
    
document.addEventListener('DOMContentLoaded', () => {
    // Элементы интерфейса
    const loadingScreen = document.getElementById('loading-screen');
    const appContainer = document.getElementById('app-container');
    const frame = document.getElementById('page-frame');
    
    // Скрываем основной контент до завершения инициализации
    if (frame) {
        frame.style.display = 'none';
    }
    
    // Таймаут для инициализации (максимум 10 секунд)
    const INIT_TIMEOUT = 10000;
    let initTimeoutId;
    let progressInterval;
    
    // ОБЪЕДИНЕННАЯ функция завершения инициализации (ОПРЕДЕЛЕНА ПЕРВОЙ!)
    const completeInitialization = (success = true) => {
        clearTimeout(initTimeoutId);
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        
        console.log('Completing initialization with success:', success);
// Плавно скрываем экран загрузки
if (loadingScreen) {
    loadingScreen.style.opacity = '0';
    setTimeout(() => {
        console.log('Hiding loading screen');
        if (loadingScreen) {
            loadingScreen.style.display = 'none';
        }
        if (appContainer) {
            console.log('Showing app container');
            appContainer.classList.remove('hidden');
        }
        if (frame && success) {
            console.log('Showing frame');
            frame.style.display = 'block';
        }
    }, 500);
}
        
        if (success) {
            // Настраиваем интерфейс
            setupBottomMenu();
            setupSideMenu();
            setupLinkHandlers();
            setupNavigation();
            setupIframeHandler();
            setupErrorHandlers();
            
            // Запускаем опрос уведомлений
            pollNotifications();
            pollInterval = setInterval(pollNotifications, 8000);
            
            // Устанавливаем активную вкладку
            const activeTab = getActiveTabFromUrl();
            setActiveTab(activeTab);
            
            // Загружаем содержимое активной вкладки
            loadActiveTabContent(activeTab);
        } else {
            // Показываем уведомление об ошибке
            showNotification('Не удалось инициализировать приложение. Проверьте соединение и перезагрузите страницу.', 'error');
            
            // Все равно показываем приложение, чтобы пользователь мог перезагрузить
            if (appContainer) {
                appContainer.classList.remove('hidden');
            }
            
            // Показываем сообщение об ошибке в основном контенте
            if (frame) {
                frame.style.display = 'block';
                frame.src = 'about:blank';
                frame.onload = function() {
                    const errorContent = `
                        <div style="padding: 20px; text-align: center; color: #ff6b6b;">
                            <h2>Ошибка инициализации</h2>
                            <p>Не удалось загрузить приложение. Пожалуйста, перезагрузите страницу.</p>
                            <button onclick="location.reload()" style="margin-top: 20px; padding: 10px 20px; background: #ff6b6b; color: white; border: none; border-radius: 8px; cursor: pointer;">
                                Перезагрузить
                            </button>
                        </div>
                    `;
                    frame.contentDocument.open();
                    frame.contentDocument.write(errorContent);
                    frame.contentDocument.close();
                };
            }
        }
    };
    
    // Обновление прогресс-бара
    const progressBar = document.getElementById('loading-progress-bar');
    let progress = 0;
	let retryCount = 0;
	const MAX_RETRIES = 3;

    const updateProgress = (value) => {
        progress = Math.min(Math.max(progress, value), 100);
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
    };

    // Проверяем, доступен ли Telegram WebApp API
    const checkTelegramApi = () => {
        return new Promise((resolve) => {
            const maxAttempts = 50;
            let attempts = 0;
            
            const check = () => {
                attempts++;
                if (window.Telegram && window.Telegram.WebApp) {
                    console.log('Telegram WebApp API загружен');
                    resolve(true);
                } else if (attempts >= maxAttempts) {
                    console.warn('Telegram WebApp API не загрузился');
                    resolve(false);
                } else {
                    setTimeout(check, 100);
                }
            };
            
            check();
        });
    };
    
    // Инициализация сессии с проверкой Telegram API
    const initSessionWithCheck = async () => {
        // Сначала проверяем доступность Telegram API
        const isTelegramAvailable = await checkTelegramApi();
        
        if (!isTelegramAvailable) {
            throw new Error('Telegram WebApp API недоступен');
        }
        
        try {
            const tg = window.Telegram.WebApp;
            tg.expand();
            tg.ready();
            
            const user = tg.initDataUnsafe?.user || null;
            if (!user) {
                console.error("User data not available from Telegram");
                throw new Error("User data not available");
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
            
            let response;
try {
    response = await fetch('/miniapp/init', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });
} catch (fetchError) {
    if (retryCount < MAX_RETRIES) {
        retryCount++;
        console.log(`Retry ${retryCount}/${MAX_RETRIES} for init...`);
        updateProgress(progress + 10); // +10% за retry
        return initSessionWithCheck(); // Рекурсивный retry
    }
    throw fetchError;
}

if (!response.ok) {
    throw new Error(`Server responded with status ${response.status}`);
}

	const data = await response.json();
            if (data.success) {
                console.log('Session initialized');
                // Обновляем информацию о пользователе
                const userMini = document.getElementById('user-mini');
                if (userMini) {
                    userMini.textContent = user.first_name || 'Пользователь';
                }
                return true;
            } else {
                throw new Error(data.error || 'Session initialization failed');
            }
        } catch (error) {
            console.error('Error initializing session:', error);
            throw error;
        }
    };
    
    // Добавляем функцию для загрузки содержимого вкладки
    function loadActiveTabContent(tabName) {
        if (!frame) return;
        
        switch (tabName) {
            case 'home':
                frame.src = '/miniapp/home';
                break;
            case 'nlo':
                frame.src = '/miniapp/nlo';
                break;
            case 'pred':
                frame.src = '/miniapp/predictions';
                break;
            case 'profile':
                frame.src = '/miniapp/profile';
                break;
            case 'support':
                frame.src = '/miniapp/support';
                break;
            default:
                frame.src = '/miniapp/home';
        }
        
        // Добавляем небольшую задержку перед показом
        setTimeout(() => {
            if (frame) {
                frame.style.opacity = '1';
                frame.style.transition = 'opacity 0.3s ease';
            }
        }, 300);
    }
    
    // Устанавливаем таймаут для инициализации
    initTimeoutId = setTimeout(() => {
        console.error('Инициализация сессии превысила лимит времени');
        completeInitialization(false);
    }, INIT_TIMEOUT);
    
    // Имитация прогресса загрузки
progressInterval = setInterval(() => {
    if (progress < 100) {
        updateProgress(progress + 2);
    }
}, 300);
    
    // Запускаем инициализацию
    initSessionWithCheck()
        .then(() => {
            console.log('Инициализация сессии завершена успешно');
            completeInitialization(true);
        })
        .catch(error => {
            console.error('Ошибка инициализации сессии:', error);
            completeInitialization(false);
        });
    
    // Очистка при разгрузке
    window.addEventListener('beforeunload', () => {
        if (pollInterval) {
            clearInterval(pollInterval);
        }
        clearTimeout(initTimeoutId);
        if (progressInterval) {
            clearInterval(progressInterval);
        }
    });
});