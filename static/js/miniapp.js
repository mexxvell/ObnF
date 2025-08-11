// static/js/miniapp.js

console.log('[INIT] miniapp.js script loaded');

document.addEventListener('DOMContentLoaded', () => {
    console.log('[INIT] DOMContentLoaded event triggered in miniapp.js');
    
    // Инициализация Telegram WebApp
    const tg = window.Telegram?.WebApp;
    if (tg && tg.expand && tg.ready) {
        console.log('[TG] Telegram WebApp API detected');
        try {
            tg.expand();
            tg.ready();
            console.log('[TG] Telegram WebApp API initialized successfully');
        } catch (e) {
            console.error('[TG] Error initializing Telegram WebApp API:', e);
        }
    } else {
        console.warn('[TG] Telegram WebApp API is not available or incomplete');
        // Создаем заглушку только если API полностью отсутствует
        if (!window.Telegram) {
            window.Telegram = {};
        }
        if (!window.Telegram.WebApp) {
            window.Telegram.WebApp = {
                expand: () => console.log('[TG] Mock expand() called'),
                ready: () => console.log('[TG] Mock ready() called'),
                HapticFeedback: {
                    impactOccurred: () => {}
                },
                initDataUnsafe: {
                    user: {
                        id: 123456789,
                        username: "test_user",
                        first_name: "Test",
                        last_name: "User"
                    }
                }
            };
            console.log('[TG] Created mock Telegram WebApp API');
        }
    }
    
    // Проверяем, что Telegram WebApp API доступно
    if (!window.Telegram?.WebApp) {
        console.error('[INIT] Telegram WebApp API is completely unavailable');
        showNotification('Telegram WebApp API недоступен. Попробуйте перезагрузить страницу.', 'error');
        // Скрываем экран загрузки и показываем контент даже при ошибке
        hideLoadingScreen();
        return;
    }

    // Основная логика инициализации
    initializeApp();
});

function hideLoadingScreen() {
    console.log('[INIT] hideLoadingScreen called');
    const loadingScreen = document.getElementById('loading-screen');
    const appContainer = document.getElementById('app-container');
    const frame = document.getElementById('page-frame');
    
    if (loadingScreen) {
        loadingScreen.style.opacity = '0';
        setTimeout(() => {
            loadingScreen.style.display = 'none';
            if (appContainer) {
                appContainer.classList.remove('hidden');
            }
            if (frame) {
                frame.style.display = 'block';
                frame.src = '/miniapp/home';
            }
        }, 500);
    }
}

async function initializeApp() {
    console.log('[INIT] Starting application initialization');
    
    // Элементы интерфейса
    const loadingScreen = document.getElementById('loading-screen');
    const appContainer = document.getElementById('app-container');
    const frame = document.getElementById('page-frame');
    
    // Скрываем основной контент до завершения инициализации
    if (frame) {
        frame.style.display = 'none';
        console.log('[INIT] Frame hidden for initialization');
    }
    
    // Таймаут для инициализации (максимум 10 секунд)
    const INIT_TIMEOUT = 10000;
    let initTimeoutId;
    let progressInterval;
    
    // ОБЪЕДИНЕННАЯ функция завершения инициализации
    const completeInitialization = (success = true, errorMessage = null) => {
        console.log('[INIT] Completing initialization with success:', success, 'Error:', errorMessage);
        clearTimeout(initTimeoutId);
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        
        // Плавно скрываем экран загрузки
        if (loadingScreen) {
            loadingScreen.style.opacity = '0';
            setTimeout(() => {
                console.log('[INIT] Hiding loading screen');
                if (loadingScreen) {
                    loadingScreen.style.display = 'none';
                }
                if (appContainer) {
                    console.log('[INIT] Showing app container');
                    appContainer.classList.remove('hidden');
                }
                if (frame && success) {
                    console.log('[INIT] Showing frame');
                    frame.style.display = 'block';
                    
                    // Добавляем класс ready для плавного появления iframe
                    frame.classList.add('ready');
                }
            }, 500);
        }

        // Если инициализация успешна, скрываем сообщение об ошибке
        if (success && frame) {
            try {
                if (frame.contentDocument) {
                    const errorDiv = frame.contentDocument.querySelector('.error-message');
                    if (errorDiv) {
                        errorDiv.style.display = 'none';
                    }
                }
            } catch (e) {
                console.warn('[INIT] Could not hide error message in iframe:', e);
            }
        }

        // В случае успеха также убираем сообщение об ошибке, если оно было показано
        if (success && frame) {
            // Очищаем содержимое iframe от сообщения об ошибке
            try {
                if (frame.contentDocument) {
                    frame.contentDocument.body.innerHTML = '';
                }
            } catch (e) {
                console.warn('[INIT] Could not clear iframe content:', e);
            }
        }
            
        if (success) {
            // Настраиваем интерфейс
            console.log('[INIT] Setting up UI components');
            setupBottomMenu();
            setupSideMenu();
            setupLinkHandlers();
            setupNavigation();
            setupIframeHandler();
            setupErrorHandlers();
            
            // Запускаем опрос уведомлений
            console.log('[INIT] Starting notifications polling');
            pollNotifications();
            pollInterval = setInterval(pollNotifications, 8000);
            
            // Устанавливаем активную вкладку
            const activeTab = getActiveTabFromUrl();
            console.log('[INIT] Active tab:', activeTab);
            setActiveTab(activeTab);
            
            // Загружаем содержимое активной вкладки
            loadActiveTabContent(activeTab);
        } else {
            // Показываем уведомление об ошибке
            console.error('[INIT] Initialization failed:', errorMessage);
            const message = errorMessage || 'Не удалось инициализировать приложение. Проверьте соединение и перезагрузите страницу.';
            showNotification(message, 'error');
            
            // Все равно показываем приложение, чтобы пользователь мог перезагрузить
            if (appContainer) {
                console.log('[INIT] Showing app container despite error');
                appContainer.classList.remove('hidden');
            }
            
            // Показываем сообщение об ошибке в основном контенте
            if (frame) {
                frame.style.display = 'block';
                frame.src = '/miniapp/home'; // Вместо about:blank загружаем главную страницу
                frame.onload = function() {
                    // Добавляем обработчик для кнопки перезагрузки
                    try {
                        const reloadBtn = frame.contentDocument.querySelector('button[onclick="location.reload()"]');
                        if (reloadBtn) {
                            reloadBtn.addEventListener('click', function(e) {
                                e.preventDefault();
                                location.reload();
                            });
                        }
                    } catch (e) {
                        console.warn('[INIT] Could not add reload button handler:', e);
                    }
                };
            }
        }
    };
    
    // Обновление прогресс-бара
    const progressBar = document.getElementById('loading-progress-bar');
    let progress = 0;

    const updateProgress = (value) => {
        progress = Math.min(Math.max(progress, value), 100);
        console.log(`[PROGRESS] Updating progress to ${progress}%`);
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
    };

    // Проверяем, доступен ли Telegram WebApp API
    const checkTelegramApi = () => {
        return new Promise((resolve) => {
            const maxAttempts = 20;
            let attempts = 0;
            
            const check = () => {
                attempts++;
                if (window.Telegram && window.Telegram.WebApp) {
                    console.log('[TG] Telegram WebApp API загружен после попытки', attempts);
                    resolve(true);
                } else if (attempts >= maxAttempts) {
                    console.warn('[TG] Telegram WebApp API не загрузился после', maxAttempts, 'попыток');
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
        console.log('[SESSION] Starting session initialization');
        
        // Сначала проверяем доступность Telegram API
        const isTelegramAvailable = await checkTelegramApi();
        
        if (!isTelegramAvailable) {
            console.error('[SESSION] Telegram WebApp API недоступен');
            throw new Error('Telegram WebApp API недоступен');
        }
        
        try {
            const tg = window.Telegram.WebApp;
            console.log('[SESSION] Telegram WebApp object:', tg);
            
            // Проверяем наличие необходимых методов
            if (!tg.expand || !tg.ready) {
                console.error('[SESSION] Required Telegram WebApp methods are missing');
                throw new Error('Required Telegram WebApp methods are missing');
            }
            
            tg.expand();
            tg.ready();
            console.log('[SESSION] Telegram WebApp expanded and ready');
            
            const user = tg.initDataUnsafe?.user || null;
            console.log('[SESSION] User data from Telegram:', user);
            
            if (!user) {
                console.error("[SESSION] User data not available from Telegram");
                throw new Error("User data not available");
            }
            
            console.log('[SESSION] User ', {
                id: user.id,
                username: user.username,
                firstName: user.first_name,
                lastName: user.last_name
            });
            
            // Сохраняем реферальный параметр
            const urlParams = new URLSearchParams(window.location.search);
            const ref = urlParams.get('ref');
            
            // Отправляем данные на сервер
            console.log('[SESSION] Sending init request to /miniapp/init');
            const payload = {
                user_id: user.id,
                username: user.username || "",
                display_name: `${user.first_name} ${user.last_name || ""}`,
                ref: ref
            };
            
            console.log('[SESSION] Payload:', payload);
            
            let response;
            try {
                response = await fetch('/miniapp/init', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });
            } catch (networkError) {
                console.error('[SESSION] Network error:', networkError);
                throw new Error('Network error: Unable to connect to server');
            }
            
            console.log('[SESSION] Init response status:', response.status);
            if (!response.ok) {
                const errorText = await response.text();
                console.error('[SESSION] Server error response:', errorText);
                throw new Error(`Server error ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            console.log('[SESSION] Init response ', data);

            if (data.success) {
                console.log('[SESSION] Session initialized successfully');
                // Обновляем информацию о пользователе
                const userMini = document.getElementById('user-mini');
                if (userMini) {
                    userMini.textContent = user.first_name || 'Пользователь';
                }
                
                // Добавляем класс к iframe для плавного появления
                if (frame) {
                    frame.classList.add('ready');
                }
                
                return true;
            } else {
                console.error('[SESSION] Session initialization failed:', data.error);
                throw new Error(data.error || 'Session initialization failed');
            }
        } catch (error) {
            console.error('[SESSION] Error initializing session:', error);
            throw error;
        }
    };
    
    // Добавляем функцию для загрузки содержимого вкладки
    function loadActiveTabContent(tabName) {
        console.log('[TAB] Loading active tab content:', tabName);
        if (!frame) {
            console.error('[TAB] Frame element not found');
            return;
        }
        
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
                console.warn('[TAB] Unknown tab name:', tabName);
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
        console.error('[INIT] Инициализация сессии превысила лимит времени');
        completeInitialization(false, 'Превышено время ожидания инициализации. Попробуйте перезагрузить страницу.');
    }, INIT_TIMEOUT);
    
    // Имитация прогресса загрузки
    progressInterval = setInterval(() => {
        if (progress < 90) { // Останавливаем на 90%, чтобы не дойти до 100% до завершения
            updateProgress(progress + 2);
        }
    }, 300);
    
    // Запускаем инициализацию
    try {
        const result = await initSessionWithCheck();
        updateProgress(100); // Устанавливаем 100% при успешной инициализации
        console.log('[INIT] Инициализация сессии завершена успешно');
        completeInitialization(true);
    } catch (error) {
        console.error('[INIT] Ошибка инициализации сессии:', error);
        completeInitialization(false, error.message);
    }
    
    // Очистка при разгрузке
    window.addEventListener('beforeunload', () => {
        if (pollInterval) {
            clearInterval(pollInterval);
        }
        clearTimeout(initTimeoutId);
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        console.log('[INIT] Cleanup completed');
    });
    
    // Установка активной вкладки
    function setActiveTab(tabName) {
        console.log('[TAB] Setting active tab:', tabName);
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
        console.log('[TAB] Getting active tab from URL:', path);
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
        console.log('[MENU] Setting up bottom menu');
        // Обработчик клика на нижнюю панель
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tg = window.Telegram?.WebApp;
                if (tg?.HapticFeedback) {
                    tg.HapticFeedback.impactOccurred('light');
                }
                const tab = btn.dataset.tab;
                const frame = document.getElementById('page-frame');
                
                console.log('[MENU] Bottom menu item clicked:', tab);
                
                // Обновляем URL без перезагрузки
                let newUrl = '';
                switch (tab) {
                    case 'home':
                        newUrl = '/miniapp/home';
                        break;
                    case 'nlo':
                        newUrl = '/miniapp/nlo';
                        break;
                    case 'pred':
                        newUrl = '/miniapp/predictions';
                        break;
                    case 'profile':
                        newUrl = '/miniapp/profile';
                        break;
                    case 'support':
                        newUrl = '/miniapp/support';
                        break;
                    default:
                        newUrl = '/miniapp/home'; // По умолчанию главная страница
                        break;
                }
                
                // Проверяем, существует ли iframe
                if (!frame) {
                    console.error('[IFRAME] Frame element not found');
                    showNotification('Ошибка: iframe не найден', 'error');
                    return;
                }
                
                // Задержка перед загрузкой нового содержимого
                frame.style.opacity = '0.7';
                frame.style.transform = 'scale(0.98)';
                
                setTimeout(() => {
                    frame.src = newUrl;
                    frame.onload = function() {
                        frame.style.opacity = '1';
                        frame.style.transform = 'scale(1)';
                        
                        // Обновляем активную вкладку
                        setActiveTab(tab);
                    };
                    
                    frame.onerror = function() {
                        console.error('[IFRAME] Error loading content for:', newUrl);
                        showNotification('Ошибка загрузки страницы. Проверьте соединение.', 'error');
                    };
                }, 100);
            });
        });
    }
    
    // Настройка бокового меню
    function setupSideMenu() {
        console.log('[MENU] Setting up side menu');
        const burger = document.getElementById('burger');
        const sideMenu = document.getElementById('side-menu');
        const closeBtn = document.getElementById('close-burger');
        
        if (burger && sideMenu && closeBtn) {
            burger.addEventListener('click', () => {
                const tg = window.Telegram?.WebApp;
                if (tg?.HapticFeedback) {
                    tg.HapticFeedback.impactOccurred('medium');
                }
                console.log('[MENU] Burger menu clicked');
                sideMenu.classList.toggle('hidden');
            });
            
            closeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const tg = window.Telegram?.WebApp;
                if (tg?.HapticFeedback) {
                    tg.HapticFeedback.impactOccurred('light');
                }
                console.log('[MENU] Close burger clicked');
                sideMenu.classList.add('hidden');
            });
            
            // Закрытие меню при клике вне его области
            document.addEventListener('click', (e) => {
                if (!sideMenu.contains(e.target) && 
                    !burger.contains(e.target) && 
                    !sideMenu.classList.contains('hidden')) {
                    console.log('[MENU] Closing menu by clicking outside');
                    sideMenu.classList.add('hidden');
                }
            });
        } else {
            console.warn('[MENU] Some menu elements not found');
        }
    }
    
    // Обработчик кликов по ссылкам
    function setupLinkHandlers() {
        console.log('[LINKS] Setting up link handlers');
        document.addEventListener('click', (e) => {
            let target = e.target;
            while (target && !target.href) {
                target = target.parentElement;
            }
            
            // Проверяем, что это внутренняя ссылка
            if (target && target.href && target.href.includes(window.location.host)) {
                e.preventDefault();
                
                console.log('[LINKS] Internal link clicked:', target.href);
                
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
                console.log('[LINKS] External link clicked, opening in same window:', target.href);
                window.location.href = target.href;
            }
        });
    }
    
    // Обработчик навигации
    function setupNavigation() {
        console.log('[NAV] Setting up navigation');
        window.addEventListener('popstate', () => {
            console.log('[NAV] Popstate event triggered');
            const frame = document.getElementById('page-frame');
            if (frame) {
                frame.src = window.location.pathname;
            }
        });
    }
    
    // Обработчик iframe загрузки
    function setupIframeHandler() {
        console.log('[IFRAME] Setting up iframe handler');
        const frame = document.getElementById('page-frame');
        if (frame) {
            frame.onload = function() {
                console.log('[IFRAME] Frame loaded:', frame.src);
                try {
                    // Обновляем активную вкладку на основе содержимого iframe
                    const src = frame.src;
                    if (src.includes('/miniapp/home')) {
                        setActiveTab('home');
                        
                        // Добавляем обработчик для кнопок "Детали" после загрузки страницы
                        setTimeout(() => {
                            try {
                                const detailsButtons = frame.contentDocument.querySelectorAll('.details-btn, .match-detail-btn');
                                console.log('[MATCH] Found details buttons:', detailsButtons.length);
                                detailsButtons.forEach(btn => {
                                    // Удаляем предыдущие обработчики, если есть
                                    const clone = btn.cloneNode(true);
                                    btn.parentNode.replaceChild(clone, btn);
                                    
                                    clone.addEventListener('click', (e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        
                                        console.log('[MATCH] Details button clicked:', clone);
                                        
                                        // Пытаемся найти ID матча разными способами
                                        let matchId = null;
                                        
                                        // 1. Проверяем атрибут data-match-id кнопки
                                        if (clone.dataset.matchId) {
                                            matchId = clone.dataset.matchId;
                                            console.log('[MATCH] Found match ID from button data-match-id:', matchId);
                                        }
                                        // 2. Проверяем родительский элемент .match-card
                                        else if (clone.closest('.match-card')?.dataset.matchId) {
                                            matchId = clone.closest('.match-card').dataset.matchId;
                                            console.log('[MATCH] Found match ID from .match-card data-match-id:', matchId);
                                        }
                                        // 3. Проверяем родительский элемент tr (для таблицы)
                                        else if (clone.closest('tr')?.dataset.matchId) {
                                            matchId = clone.closest('tr').dataset.matchId;
                                            console.log('[MATCH] Found match ID from tr data-match-id:', matchId);
                                        }
                                        // 4. Проверяем атрибут href (если кнопка является ссылкой)
                                        else if (clone.href && /\/match\/(\d+)/.test(clone.href)) {
                                            matchId = clone.href.match(/\/match\/(\d+)/)[1];
                                            console.log('[MATCH] Found match ID from href:', matchId);
                                        }
                                        // 5. Проверяем скрытое поле в форме
                                        else {
                                            const hiddenInput = clone.closest('form, .match-card')?.querySelector('input[name="match_id"]');
                                            if (hiddenInput && hiddenInput.value) {
                                                matchId = hiddenInput.value;
                                                console.log('[MATCH] Found match ID from hidden input:', matchId);
                                            }
                                        }
                                        
                                        if (matchId) {
                                            console.log('[MATCH] Opening details for match ID:', matchId);
                                            // Загружаем страницу матча
                                            document.getElementById('page-frame').src = `/miniapp/match/${matchId}`;
                                            
                                            // Закрываем боковое меню, если открыто
                                            document.getElementById('side-menu')?.classList.add('hidden');
                                        } else {
                                            console.error('[MATCH] Match ID not found after all attempts');
                                            showNotification('Ошибка: не удалось определить матч. Пожалуйста, обновите страницу и попробуйте снова.', 'error');
                                        }
                                    });
                                });
                            } catch (iframeError) {
                                console.error('[IFRAME] Error adding details button handlers:', iframeError);
                            }
                        }, 500);
                    } else if (src.includes('/miniapp/nlo')) {
                        setActiveTab('nlo');
                        
                        // Настройка вкладок НЛО 8x8
                        setTimeout(() => {
                            try {
                                if (!frame.contentDocument) {
                                    console.warn('[IFRAME] Cannot access iframe contentDocument');
                                    return;
                                }
                                
                                const nloTabs = frame.contentDocument.querySelectorAll('.nlo-tab');
                                const nloTabContents = frame.contentDocument.querySelectorAll('.nlo-tab-content');
                                
                                console.log('[NLO] Found NLO tabs:', nloTabs.length);
                                
                                nloTabs.forEach(tab => {
                                    // Удаляем предыдущие обработчики
                                    const clone = tab.cloneNode(true);
                                    tab.parentNode.replaceChild(clone, tab);
                                    
                                    clone.addEventListener('click', (e) => {
                                        e.preventDefault();
                                        console.log('[NLO] Tab clicked:', clone.dataset.tab);
                                        
                                        // Удаляем активный класс со всех вкладок
                                        nloTabs.forEach(t => t.classList.remove('active'));
                                        nloTabContents.forEach(c => c.classList.remove('active'));
                                        
                                        // Добавляем активный класс текущей вкладке
                                        clone.classList.add('active');
                                        const tabName = clone.dataset.tab;
                                        const content = frame.contentDocument.querySelector(`.nlo-tab-content[data-tab-content="${tabName}"]`);
                                        if (content) {
                                            content.classList.add('active');
                                        }
                                        
                                        // Если это вкладка турнирной таблицы, загружаем данные
                                        if (tabName === 'standings') {
                                            loadStandingsTable(frame);
                                        }
                                        
                                        // Если это вкладка трансляций, загружаем данные
                                        if (tabName === 'streams') {
                                            loadStreamsTable(frame);
                                        }
                                    });
                                });
                                
                                // Проверяем активную вкладку при загрузке
                                const activeTab = frame.contentDocument.querySelector('.nlo-tab.active');
                                if (activeTab && activeTab.dataset.tab === 'standings') {
                                    loadStandingsTable(frame);
                                }
                                if (activeTab && activeTab.dataset.tab === 'streams') {
                                    loadStreamsTable(frame);
                                }
                            } catch (iframeError) {
                                console.error('[IFRAME] Error setting up NLO tabs:', iframeError);
                            }
                        }, 500);
                    } else if (src.includes('/miniapp/predictions') || 
                               src.includes('/miniapp/pred')) {
                        setActiveTab('pred');
                    } else if (src.includes('/miniapp/profile')) {
                        setActiveTab('profile');
                    } else if (src.includes('/miniapp/support')) {
                        setActiveTab('support');
                    }
                } catch (e) {
                    console.error('[IFRAME] Error updating tab state:', e);
                }
            };
                
            frame.onerror = function() {
                console.error('[IFRAME] Frame failed to load:', frame.src);
                showNotification('Ошибка загрузки страницы. Проверьте соединение.', 'error');
            };
        }
    }

    // Функция загрузки турнирной таблицы
    function loadStandingsTable(frame) {
        console.log('[STANDINGS] Loading standings table');
        const tableBody = frame.contentDocument.getElementById('standings-table-body');
        if (!tableBody) {
            console.error('[STANDINGS] Table body not found');
            return;
        }
        
        tableBody.innerHTML = '<tr><td colspan="7" class="loading-text">Загрузка таблицы...</td></tr>';
        
        fetch('/miniapp/standings-data')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('[STANDINGS] Data received:', data);
                if (!Array.isArray(data) || data.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="7">Турнирная таблица пуста</td></tr>';
                    return;
                }
                
                let html = '';
                data.forEach((row, index) => {
                    html += `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${row.team}</td>
                            <td>${row.played}</td>
                            <td>${row.won}</td>
                            <td>${row.drawn}</td>
                            <td>${row.lost}</td>
                            <td>${row.points}</td>
                        </tr>
                    `;
                });
                
                tableBody.innerHTML = html;
            })
            .catch(error => {
                console.error('[STANDINGS] Error loading standings:', error);
                tableBody.innerHTML = '<tr><td colspan="7" class="error">Ошибка загрузки таблицы</td></tr>';
            });
    }

    // Функция загрузки трансляций
    function loadStreamsTable(frame) {
        console.log('[STREAMS] Loading streams table');
        const streamsContainer = frame.contentDocument.getElementById('streams-container');
        if (!streamsContainer) {
            console.error('[STREAMS] Streams container not found');
            return;
        }
        
        streamsContainer.innerHTML = '<p class="loading-text">Загрузка трансляций...</p>';
        
        fetch('/miniapp/nlo/streams')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.text(); // Получаем HTML
            })
            .then(html => {
                console.log('[STREAMS] HTML received');
                streamsContainer.innerHTML = html;
            })
            .catch(error => {
                console.error('[STREAMS] Error loading streams:', error);
                streamsContainer.innerHTML = '<p class="error">Ошибка загрузки трансляций</p>';
            });
    }
    
    // Показ уведомлений
    function showNotification(message, type = 'info') {
        console.log(`[NOTIF] Showing notification (${type}):`, message);
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
        console.log('[ERROR] Setting up error handlers');
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
            console.log('[NOTIF] Polling notifications');
            const response = await fetch('/miniapp/notifications');
            const data = await response.json();
            
            if (data.length > 0) {
                // Показываем последнее уведомление
                const latest = data[0];
                console.log('[NOTIF] New live notification:', latest);
                showLiveBanner(latest);
            }
        } catch (error) {
            console.error('[NOTIF] Error polling notifications:', error);
        }
    }
    
    function showLiveBanner(note) {
        console.log('[BANNER] Showing live banner:', note);
        const banner = document.getElementById('live-banner');
        if (!banner) {
            console.error('[BANNER] Banner element not found');
            return;
        }
        
        banner.innerHTML = `
            <div class="banner-inner">
                <div class="logos">${note.team1} — ${note.team2}</div>
                <div class="score">${note.score1}:${note.score2}</div>
            </div>
        `;
        
        banner.classList.add('pulse');
        
        // Обработчик клика на баннер
        banner.onclick = function() {
            console.log('[BANNER] Banner clicked, loading match page');
            document.getElementById('page-frame').src = `/miniapp/match/${note.id}`;
            hideLiveBanner();
        };
        
        // Автоматическое скрытие через 10 секунд
        setTimeout(hideLiveBanner, 10000);
    }
    
    function hideLiveBanner() {
        console.log('[BANNER] Hiding live banner');
        const banner = document.getElementById('live-banner');
        if (banner) {
            banner.classList.remove('pulse');
            setTimeout(() => {
                banner.style.opacity = '0';
                setTimeout(() => banner.style.display = 'none', 300);
            }, 300);
        }
    }
}

// Добавим обработчик ошибок загрузки скрипта
window.addEventListener('error', function(e) {
    console.error('[WINDOW] Script loading error:', e);
});