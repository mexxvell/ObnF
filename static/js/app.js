// static/js/app.js
/**
 * НЛО — Футбольная Лига
 * Основной JavaScript для Telegram Web App
 * Версия: 1.0
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
        achievements: {}
    };

    // Загрузка данных пользователя
    const loadUserData = async () => {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            app.userId = urlParams.get('user_id') || '123456';
            
            const response = await fetch(`/api/profile?user_id=${app.userId}`);
            if (!response.ok) throw new Error('Не удалось загрузить профиль');
            
            app.userData = await response.json();
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
            const response = await fetch('/api/matches');
            if (!response.ok) throw new Error('Не удалось загрузить матчи');
            
            const data = await response.json();
            app.matches = data.matches;
            return true;
        } catch (error) {
            console.error('Ошибка загрузки матчей:', error);
            showNotification('Ошибка загрузки матчей. Проверьте подключение.', 'error');
            return false;
        }
    };

    // Инициализация приложения
    const initApp = async () => {
        showPage('splash');
        
        // Загружаем данные
        const userDataLoaded = await loadUserData();
        const matchesLoaded = await loadMatches();
        
        // Если все загружено - переходим к основному экрану
        if (userDataLoaded && matchesLoaded) {
            renderProfile();
            renderMatches();
            setTimeout(() => showPage('main'), 2000); // Показ splash 2 секунды
        } else {
            setTimeout(() => showPage('main'), 2000); // Даже при ошибках показываем интерфейс
        }
    };

    // Отображение страницы
    const showPage = (pageId) => {
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });
        
        document.getElementById(pageId).classList.add('active');
        app.currentPage = pageId;
        
        // Анимация для профиля
        if (pageId === 'profile') {
            animateProgressBar();
        }
    };

    // Рендер профиля
    const renderProfile = () => {
        if (!app.userData) return;
        
        // Обновляем данные профиля
        document.getElementById('profile-username').textContent = 
            app.userData.display_name || app.userData.username;
        
        document.getElementById('profile-credits').textContent = 
            app.userData.credits.toLocaleString();
        
        document.getElementById('profile-level').textContent = 
            `Уровень ${app.userData.level}`;
        
        document.getElementById('profile-xp-current').textContent = 
            app.userData.xp;
        
        document.getElementById('profile-xp-needed').textContent = 
            app.userData.next_level_xp;
        
        // Обновляем прогресс-бар
        const progress = (app.userData.xp / app.userData.next_level_xp) * 100;
        document.getElementById('xp-progress').style.width = `${Math.min(progress, 100)}%`;
        
        // Рендер ачивок
        renderAchievements();
    };

    // Анимация прогресс-бара
    const animateProgressBar = () => {
        const progressBar = document.getElementById('xp-progress');
        const width = progressBar.style.width;
        progressBar.style.width = '0%';
        
        setTimeout(() => {
            progressBar.style.transition = 'width 1s ease-out';
            progressBar.style.width = width;
        }, 10);
    };

    // Рендер ачивок
    const renderAchievements = () => {
        const container = document.getElementById('achievements-container');
        container.innerHTML = '';
        
        app.userData.achievements.forEach(achievement => {
            const achievementData = app.achievements[achievement.key];
            if (!achievementData) return;
            
            const tierClass = achievement.tier === 1 ? 'bronze' : 
                             achievement.tier === 2 ? 'silver' : 'gold';
            
            const achievementEl = document.createElement('div');
            achievementEl.className = `achievement-card ${tierClass}`;
            achievementEl.innerHTML = `
                <img src="/static/img/achievements/${achievement.key}_${tierClass}.png" 
                     alt="${achievementData.title}">
                <div class="achievement-info">
                    <h4>${achievementData.title}</h4>
                    <p>${achievementData.description}</p>
                </div>
            `;
            
            container.appendChild(achievementEl);
        });
    };

    // Рендер матчей
    const renderMatches = () => {
        const container = document.getElementById('matches-container');
        container.innerHTML = '';
        
        if (app.matches.length === 0) {
            container.innerHTML = '<p class="no-matches">Нет запланированных матчей</p>';
            return;
        }
        
        app.matches.forEach(match => {
            const matchEl = document.createElement('div');
            matchEl.className = 'match-card';
            matchEl.innerHTML = `
                <div class="match-header">
                    <span class="match-date">${match.date} ${match.time}</span>
                    <span class="match-status ${match.status}">${getStatusText(match.status)}</span>
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
                <div class="match-venue">${match.venue || ''}</div>
                <button class="bet-button" data-match-id="${match.match_id}">Сделать ставку</button>
            `;
            
            container.appendChild(matchEl);
        });
        
        // Добавляем обработчики кнопок
        document.querySelectorAll('.bet-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const matchId = e.target.dataset.matchId;
                showBetModal(matchId);
            });
        });
    };

    // Текст для статуса матча
    const getStatusText = (status) => {
        const statuses = {
            'scheduled': 'Запланирован',
            'live': 'Идет матч',
            'done': 'Завершен'
        };
        return statuses[status] || status;
    };

    // Показ модального окна ставки
    const showBetModal = (matchId) => {
        const modal = document.getElementById('bet-modal');
        modal.dataset.matchId = matchId;
        
        // Загружаем данные матча
        const match = app.matches.find(m => m.match_id === matchId);
        if (!match) return;
        
        document.getElementById('modal-match-title').textContent = 
            `${match.home_team} vs ${match.away_team}`;
        
        document.getElementById('modal-match-date').textContent = 
            `${match.date} ${match.time}`;
        
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
        document.getElementById('bet-modal').style.display = 'none';
    };

    // Размещение ставки
    const placeBet = async () => {
        const modal = document.getElementById('bet-modal');
        const matchId = modal.dataset.matchId;
        
        const betType = document.querySelector('input[name="bet-type"]:checked')?.value;
        const selection = document.querySelector('input[name="selection"]:checked')?.value;
        const amount = parseInt(document.getElementById('bet-amount').value);
        
        if (!betType || !selection || !amount || amount <= 0) {
            showNotification('Пожалуйста, заполните все поля корректно', 'error');
            return;
        }
        
        try {
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
            
            if (data.success) {
                showNotification(`Ставка размещена! Коэффициент: ${data.odds}`, 'success');
                closeBetModal();
                
                // Обновляем данные пользователя
                await loadUserData();
                renderProfile();
            } else {
                throw new Error(data.error || 'Ошибка при размещении ставки');
            }
        } catch (error) {
            console.error('Ошибка ставки:', error);
            showNotification(error.message || 'Ошибка при размещении ставки', 'error');
        }
    };

    // Ежедневный чек-ин
    const dailyCheckin = async () => {
        try {
            const response = await fetch('/api/daily-checkin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_id: app.userId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification(
                    `Чек-ин успешен! +${data.credits_reward} кредитов, +${data.xp_reward} XP (Стрик: ${data.streak})`,
                    'success'
                );
                
                // Обновляем данные пользователя
                await loadUserData();
                renderProfile();
            } else {
                throw new Error(data.error || 'Ошибка чек-ина');
            }
        } catch (error) {
            console.error('Ошибка чек-ина:', error);
            showNotification(error.message || 'Ошибка ежедневного чек-ина', 'error');
        }
    };

    // Показ уведомления
    const showNotification = (message, type = 'info') => {
        const notification = document.getElementById('notification');
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
                if (page) showPage(page);
            });
        });
        
        // Кнопка чек-ина
        document.getElementById('checkin-button')?.addEventListener('click', dailyCheckin);
        
        // Кнопка закрытия модального окна
        document.getElementById('close-modal')?.addEventListener('click', closeBetModal);
        
        // Кнопка размещения ставки
        document.getElementById('place-bet-button')?.addEventListener('click', placeBet);
        
        // Выбор суммы ставки
        document.querySelectorAll('.bet-amount-option').forEach(option => {
            option.addEventListener('click', () => {
                document.getElementById('bet-amount').value = option.dataset.amount;
            });
        });
        
        // Обновление коэффициентов при выборе ставки
        document.querySelectorAll('input[name="bet-type"]').forEach(input => {
            input.addEventListener('change', updateOdds);
        });
        
        document.querySelectorAll('input[name="selection"]').forEach(input => {
            input.addEventListener('change', updateOdds);
        });
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
        
        document.getElementById('current-odds').textContent = odds.toFixed(2);
        document.getElementById('potential-winnings').textContent = 
            (amount * odds).toFixed(2);
    };

    // Инициализация админ-панели (если владелец)
    const initAdminPanel = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id');
        
        if (userId === process.env.OWNER_TELEGRAM_ID) {
            document.getElementById('admin-tab').style.display = 'block';
        }
    };

    // Запуск приложения
    initEventListeners();
    initApp();
    initAdminPanel();
});