/**
 * НЛО — Футбольная Лига
 * Основной JavaScript для Telegram Web App
 * Версия: 1.0 (исправленная)
 */

document.addEventListener('DOMContentLoaded', () => {
    // Инициализация Telegram WebApp
    if (window.Telegram && Telegram.WebApp) {
        Telegram.WebApp.expand();
        Telegram.WebApp.setHeaderColor('#000000');
        Telegram.WebApp.setBackgroundColor('#0f172a');
    }

    // Глобальные переменные
    const app = {
        userId: null,
        currentPage: 'splash',
        userData: null,
        matches: [],
        achievements: {}  // Данные об ачивках
    };

    // Получаем OWNER_TELEGRAM_ID из скрытого элемента (переданного из бэкенда)
    const ownerTelegramId = document.getElementById('owner-telegram-id')?.dataset.value || '';

    // Загрузка данных пользователя
    const loadUserData = async () => {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            app.userId = urlParams.get('user_id') || '123456';
            console.log(`Загрузка данных для пользователя: ${app.userId}`);
            
            const response = await fetch(`/api/profile?user_id=${app.userId}`);
            if (!response.ok) {
                throw new Error(`Ошибка загрузки профиля: ${response.status}`);
            }
            
            app.userData = await response.json();
            console.log('Данные профиля загружены:', app.userData);
            return true;
        } catch (error) {
            console.error('Ошибка загрузки данных:', error);
            showNotification('Ошибка загрузки данных. Попробуйте позже.', 'error');
            return false;
        }
    };

    // Загрузка матчей
    const loadMatches = async () => {
        try {
            console.log('Загрузка матчей...');
            const response = await fetch('/api/matches');
            if (!response.ok) {
                throw new Error(`Ошибка загрузки матчей: ${response.status}`);
            }
            
            const data = await response.json();
            app.matches = data.matches || [];
            console.log('Матчи загружены:', app.matches);
            return true;
        } catch (error) {
            console.error('Ошибка загрузки матчей:', error);
            showNotification('Ошибка загрузки матчей. Проверьте подключение.', 'error');
            return false;
        }
    };

    // Загрузка данных об ачивках (ИСПРАВЛЕНО!)
    const loadAchievements = async () => {
        try {
            console.log('Загрузка данных об ачивках...');
            
            // ИСПОЛЬЗУЕМ ОТНОСИТЕЛЬНЫЙ ПУТЬ И УБЕЖДАЕМСЯ, ЧТО ФАЙЛ В ПАПКЕ static
            const response = await fetch('/achievements.json');
            
            if (!response.ok) {
                throw new Error(`Ошибка загрузки ачивок: ${response.status}`);
            }
            
            app.achievements = await response.json();
            console.log('Данные об ачивках загружены');
            return true;
        } catch (error) {
            console.error('Ошибка загрузки ачивок:', error);
            
            // Создаем минимальные данные об ачивках
            app.achievements = {
                "bets_made": {
                    "title": "Новичок прогноза",
                    "description": "Сделайте 10 ставок",
                    "bronze_threshold": 10,
                    "silver_threshold": 100,
                    "gold_threshold": 1000,
                    "image_paths": {
                        "bronze": "bets_bronze.png",
                        "silver": "bets_silver.png",
                        "gold": "bets_gold.png"
                    }
                },
                "exact_scores": {
                    "title": "Точный счёт",
                    "description": "Угадайте точный счёт матча",
                    "bronze_threshold": 1,
                    "silver_threshold": 10,
                    "gold_threshold": 50,
                    "image_paths": {
                        "bronze": "exact_bronze.png",
                        "silver": "exact_silver.png",
                        "gold": "exact_gold.png"
                    }
                }
                // Другие базовые ачивки...
            };
            
            console.warn('Используются минимальные данные об ачивках');
            return true;
        }
    };

    // Инициализация приложения
    const initApp = async () => {
        console.log('Инициализация приложения...');
        showPage('splash');
        
        try {
            // Загружаем данные
            await loadUserData();
            await loadMatches();
            await loadAchievements();
            
            // Рендерим данные
            renderProfile();
            renderMatches();
            
            // Проверяем, является ли пользователь владельцем
            initAdminPanel();
            
            // Переходим к основному экрану
            console.log('Переключение на основной экран');
            setTimeout(() => {
                showPage('main');
            }, 500); // Небольшая задержка для анимации загрузки
        } catch (error) {
            console.error('Критическая ошибка инициализации:', error);
            showNotification('Ошибка загрузки данных. Попробуйте позже.', 'error');
            // Даже при ошибках показываем интерфейс
            setTimeout(() => {
                showPage('main');
            }, 500);
        }
    };

    // Отображение страницы
    const showPage = (pageId) => {
        console.log(`Показ страницы: ${pageId}`);
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });
        
        const newPage = document.getElementById(pageId);
        if (newPage) {
            newPage.classList.add('active');
            app.currentPage = pageId;
            
            // Анимация для профиля
            if (pageId === 'profile') {
                animateProgressBar();
            }
        } else {
            console.error(`Страница не найдена: ${pageId}`);
            showPage('main'); // Возвращаемся на главную
        }
    };

    // Анимация прогресс-бара
    const animateProgressBar = () => {
        const progressBar = document.getElementById('xp-progress');
        if (!progressBar) return;
        
        const width = progressBar.style.width;
        progressBar.style.width = '0%';
        
        setTimeout(() => {
            progressBar.style.transition = 'width 1s ease-out';
            progressBar.style.width = width;
        }, 10);
    };

    // Рендер профиля
    const renderProfile = () => {
        try {
            console.log('Рендер профиля...');
            if (!app.userData) {
                console.warn('Данные профиля отсутствуют');
                return;
            }
            
            // Обновляем данные профиля
            const usernameEl = document.getElementById('profile-username');
            if (usernameEl) {
                usernameEl.textContent = app.userData.display_name || app.userData.username || `Игрок ${app.userId}`;
            }
            
            const creditsEl = document.getElementById('profile-credits');
            if (creditsEl) {
                creditsEl.textContent = (app.userData.credits || 0).toLocaleString();
            }
            
            const levelEl = document.getElementById('profile-level');
            if (levelEl) {
                levelEl.textContent = `Уровень ${app.userData.level || 1}`;
            }
            
            const xpCurrentEl = document.getElementById('profile-xp-current');
            if (xpCurrentEl) {
                xpCurrentEl.textContent = app.userData.xp || 0;
            }
            
            const xpNeededEl = document.getElementById('profile-xp-needed');
            if (xpNeededEl) {
                xpNeededEl.textContent = app.userData.next_level_xp || 150;
            }
            
            // Обновляем прогресс-бар
            const progressBar = document.getElementById('xp-progress');
            if (progressBar) {
                const currentXp = app.userData.xp || 0;
                const neededXp = app.userData.next_level_xp || 150;
                const progress = (currentXp / neededXp) * 100;
                
                progressBar.style.transition = 'none';
                progressBar.style.width = '0%';
                
                setTimeout(() => {
                    progressBar.style.transition = 'width 1s ease-out';
                    progressBar.style.width = `${Math.min(progress, 100)}%`;
                }, 10);
            }
            
            // Рендер ачивок
            renderAchievements();
            console.log('Профиль успешно отрендерен');
        } catch (error) {
            console.error('Ошибка при рендере профиля:', error);
            showNotification('Ошибка отображения профиля', 'error');
        }
    };

    // Рендер ачивок
    const renderAchievements = () => {
        try {
            console.log('Рендер ачивок...');
            const container = document.getElementById('achievements-container');
            if (!container) {
                console.warn('Контейнер для ачивок не найден');
                return;
            }
            
            container.innerHTML = '';
            
            if (!app.userData || !app.userData.achievements || app.userData.achievements.length === 0) {
                container.innerHTML = '<p class="no-achievements">Нет открытых достижений</p>';
                return;
            }
            
            app.userData.achievements.forEach(achievement => {
                try {
                    // Проверяем необходимые данные
                    if (!achievement.key || achievement.tier === undefined) {
                        console.warn('Пропущена ачивка с недостающими данными:', achievement);
                        return;
                    }
                    
                    const achievementData = app.achievements[achievement.key];
                    if (!achievementData) {
                        console.warn(`Данные об ачивке не найдены: ${achievement.key}`);
                        return;
                    }
                    
                    const tierClass = achievement.tier === 1 ? 'bronze' : 
                                     achievement.tier === 2 ? 'silver' : 'gold';
                    
                    const achievementEl = document.createElement('div');
                    achievementEl.className = `achievement-card ${tierClass}`;
                    achievementEl.innerHTML = `
                        <img src="/static/img/achievements/${achievement.key}_${tierClass}.png" 
                             alt="${achievementData.title}" onerror="this.onerror=null;this.src='/static/img/achievements/placeholder.png'">
                        <div class="achievement-info">
                            <h4>${achievementData.title}</h4>
                            <p>${achievementData.description}</p>
                        </div>
                    `;
                    
                    container.appendChild(achievementEl);
                } catch (achError) {
                    console.error('Ошибка при рендере конкретной ачивки:', achError);
                }
            });
            
            console.log('Ачивки успешно отрендерены');
        } catch (error) {
            console.error('Критическая ошибка при рендере ачивок:', error);
            showNotification('Ошибка отображения достижений', 'error');
        }
    };

    // Рендер матчей
    const renderMatches = () => {
        try {
            console.log('Рендер матчей...');
            const container = document.getElementById('matches-container');
            if (!container) {
                console.warn('Контейнер для матчей не найден');
                return;
            }
            
            container.innerHTML = '';
            
            if (!app.matches || app.matches.length === 0) {
                container.innerHTML = '<p class="no-matches">Нет запланированных матчей</p>';
                return;
            }
            
            app.matches.forEach(match => {
                try {
                    // Проверяем необходимые данные
                    if (!match.match_id || !match.home_team || !match.away_team) {
                        console.warn('Пропущен матч с недостающими данными:', match);
                        return;
                    }
                    
                    const matchEl = document.createElement('div');
                    matchEl.className = 'match-card';
                    matchEl.innerHTML = `
                        <div class="match-header">
                            <span class="match-date">${match.date || 'Дата не указана'} ${match.time || ''}</span>
                            <span class="match-status ${match.status || 'scheduled'}">${getStatusText(match.status)}</span>
                        </div>
                        <div class="match-teams">
                            <div class="team home">
                                <span class="team-name">${match.home_team}</span>
                                ${match.score_home ? `<span class="score">${match.score_home}</span>` : ''}
                            </div>
                            <div class="vs">vs</div>
                            <div class="team away">
                                <span class="team-name">${match.away_team}</span>
                                ${match.score_away ? `<span class="score">${match.score_away}</span>` : ''}
                            </div>
                        </div>
                        <div class="match-venue">${match.venue || 'Место не указано'}</div>
                        <button class="bet-button" data-match-id="${match.match_id}">Сделать ставку</button>
                    `;
                    
                    container.appendChild(matchEl);
                } catch (matchError) {
                    console.error('Ошибка при рендере конкретного матча:', matchError);
                }
            });
            
            // Добавляем обработчики кнопок
            document.querySelectorAll('.bet-button').forEach(button => {
                button.addEventListener('click', (e) => {
                    const matchId = e.target.dataset.matchId;
                    showBetModal(matchId);
                });
            });
            
            console.log('Матчи успешно отрендерены');
        } catch (error) {
            console.error('Критическая ошибка при рендере матчей:', error);
            showNotification('Ошибка отображения матчей', 'error');
        }
    };

    // Текст для статуса матча
    const getStatusText = (status) => {
        const statuses = {
            'scheduled': 'Запланирован',
            'live': 'Идет матч',
            'done': 'Завершен'
        };
        return statuses[status] || (status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Неизвестно');
    };

    // Показ модального окна ставки
    const showBetModal = (matchId) => {
        const modal = document.getElementById('bet-modal');
        if (!modal) {
            console.error('Модальное окно не найдено');
            return;
        }
        
        modal.dataset.matchId = matchId;
        
        // Загружаем данные матча
        const match = app.matches.find(m => m.match_id === matchId);
        if (!match) {
            console.error(`Матч не найден: ${matchId}`);
            showNotification('Матч не найден', 'error');
            return;
        }
        
        const titleEl = document.getElementById('modal-match-title');
        const dateEl = document.getElementById('modal-match-date');
        
        if (titleEl) titleEl.textContent = `${match.home_team} vs ${match.away_team}`;
        if (dateEl) dateEl.textContent = `${match.date} ${match.time}`;
        
        // Скрываем все типы ставок сначала
        document.querySelectorAll('.bet-type').forEach(el => {
            el.style.display = 'none';
        });
        
        // Показываем доступные типы ставок
        if (match.status === 'scheduled') {
            document.getElementById('bet-type-1x2').style.display = 'block';
            document.getElementById('bet-type-total').style.display = 'block';
            document.getElementById('bet-type-exact').style.display = 'block';
        }
        
        modal.style.display = 'block';
    };

    // Закрытие модального окна
    const closeBetModal = () => {
        const modal = document.getElementById('bet-modal');
        if (modal) modal.style.display = 'none';
    };

    // Размещение ставки
    const placeBet = async () => {
        const modal = document.getElementById('bet-modal');
        if (!modal) {
            showNotification('Ошибка: модальное окно не найдено', 'error');
            return;
        }
        
        const matchId = modal.dataset.matchId;
        if (!matchId) {
            showNotification('Ошибка: ID матча не найден', 'error');
            return;
        }
        
        const betType = document.querySelector('input[name="bet-type"]:checked')?.value;
        const selection = document.querySelector('input[name="selection"]:checked')?.value;
        const amount = parseInt(document.getElementById('bet-amount').value);
        
        if (!betType || !selection || !amount || amount <= 0) {
            showNotification('Пожалуйста, заполните все поля корректно', 'error');
            return;
        }
        
        try {
            console.log(`Размещение ставки: ${betType} ${selection} ${amount}`);
            const response = await fetch('/api/bet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: app.userId,
                    match_id: matchId,
                    bet_type: betType,
                    selection: selection,
                    amount: amount
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                showNotification(`Ставка размещена! Коэффициент: ${data.odds}`, 'success');
                closeBetModal();
                
                // Обновляем данные пользователя
                await loadUserData();
                renderProfile();
            } else {
                const errorMsg = data.error || 'Ошибка при размещении ставки';
                throw new Error(errorMsg);
            }
        } catch (error) {
            console.error('Ошибка ставки:', error);
            showNotification(error.message || 'Ошибка при размещении ставки', 'error');
        }
    };

    // Ежедневный чек-ин
    const dailyCheckin = async () => {
        try {
            console.log('Ежедневный чек-ин...');
            const response = await fetch('/api/daily-checkin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_id: app.userId })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                const message = `Чек-ин успешен! +${data.credits_reward} кредитов, +${data.xp_reward} XP (Стрик: ${data.streak})`;
                showNotification(message, 'success');
                
                // Обновляем данные пользователя
                await loadUserData();
                renderProfile();
            } else {
                const errorMsg = data.error || 'Ошибка ежедневного чек-ина';
                throw new Error(errorMsg);
            }
        } catch (error) {
            console.error('Ошибка чек-ина:', error);
            showNotification(error.message || 'Ошибка ежедневного чек-ина', 'error');
        }
    };

    // Показ уведомления
    const showNotification = (message, type = 'info') => {
        const notification = document.getElementById('notification');
        if (!notification) return;
        
        notification.textContent = message;
        notification.className = `notification ${type}`;
        notification.style.display = 'block';
        
        setTimeout(() => {
            notification.style.display = 'none';
        }, 5000);
    };

    // Инициализация обработчиков
    const initEventListeners = () => {
        // Навигация
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const page = e.target.dataset.page;
                if (page) {
                    console.log(`Переход на страницу: ${page}`);
                    showPage(page);
                }
            });
        });
        
        // Кнопка чек-ина
        const checkinButton = document.getElementById('checkin-button');
        if (checkinButton) {
            checkinButton.addEventListener('click', dailyCheckin);
        }
        
        // Кнопка закрытия модального окна
        const closeModal = document.getElementById('close-modal');
        if (closeModal) {
            closeModal.addEventListener('click', closeBetModal);
        }
        
        // Кнопка размещения ставки
        const placeBetButton = document.getElementById('place-bet-button');
        if (placeBetButton) {
            placeBetButton.addEventListener('click', placeBet);
        }
        
        // Выбор суммы ставки
        document.querySelectorAll('.bet-amount-option').forEach(option => {
            option.addEventListener('click', () => {
                const amountInput = document.getElementById('bet-amount');
                if (amountInput) {
                    amountInput.value = option.dataset.amount;
                    updateOdds();
                }
            });
        });
        
        // Обновление коэффициентов при выборе ставки
        document.querySelectorAll('input[name="bet-type"], input[name="selection"]').forEach(input => {
            input.addEventListener('change', updateOdds);
        });
        
        // Обновление коэффициентов при изменении суммы
        const amountInput = document.getElementById('bet-amount');
        if (amountInput) {
            amountInput.addEventListener('change', updateOdds);
        }
    };

    // Обновление коэффициентов
    const updateOdds = () => {
        const betType = document.querySelector('input[name="bet-type"]:checked')?.value;
        const selection = document.querySelector('input[name="selection"]:checked')?.value;
        const amount = parseInt(document.getElementById('bet-amount').value) || 10;
        
        if (!betType || !selection) return;
        
        // В реальном приложении здесь был бы запрос к API для получения коэффициентов
        // Для примера используем базовые значения
        let odds = 1.5;
        
        if (betType === '1x2') {
            if (selection === '1') odds = 2.10;
            if (selection === 'X') odds = 3.20;
            if (selection === '2') odds = 1.85;
        } else if (betType === 'total') {
            if (selection === 'over') odds = 1.90;
            if (selection === 'under') odds = 1.85;
        } else if (betType === 'exact_score') {
            odds = 5.50;
        }
        
        const oddsEl = document.getElementById('current-odds');
        const winningsEl = document.getElementById('potential-winnings');
        
        if (oddsEl) oddsEl.textContent = odds.toFixed(2);
        if (winningsEl) winningsEl.textContent = (amount * odds).toFixed(2);
    };

    // Инициализация админ-панели (ИСПРАВЛЕНО!)
    const initAdminPanel = () => {
        try {
            console.log('Инициализация админ-панели...');
            const urlParams = new URLSearchParams(window.location.search);
            const userId = urlParams.get('user_id');
            
            // Сравниваем с ownerTelegramId из скрытого элемента
            if (userId && ownerTelegramId && userId === ownerTelegramId) {
                console.log('Пользователь является владельцем');
                const adminTab = document.getElementById('admin-tab');
                if (adminTab) {
                    adminTab.style.display = 'block';
                    console.log('Админ-панель активирована');
                }
            } else {
                console.log('Пользователь НЕ является владельцем');
            }
        } catch (error) {
            console.error('Ошибка инициализации админ-панели:', error);
        }
    };

    // Запуск приложения
    initEventListeners();
    initApp();
});