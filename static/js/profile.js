// profile.js — логика страницы профиля

document.addEventListener('DOMContentLoaded', () => {
    // Инициализация вкладок
    setupTabs();
    
    // Инициализация ежедневного чекина
    setupDailyCheckin();
    
    // Инициализация реферальной системы
    setupReferrals();
    
    // Загрузка данных
    loadProfileData();
});

function setupTabs() {
    const tabs = document.querySelectorAll('.profile-tab');
    const tabContents = document.querySelectorAll('.profile-tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Удаляем активный класс со всех вкладок
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Добавляем активный класс текущей вкладке
            tab.classList.add('active');
            const tabName = tab.dataset.tab;
            document.querySelector(`.profile-tab-content[data-tab-content="${tabName}"]`).classList.add('active');
        });
    });
}

function setupDailyCheckin() {
    const checkinBtn = document.getElementById('daily-checkin-btn');
    if (!checkinBtn) return;
    
    checkinBtn.addEventListener('click', () => {
        fetch('/miniapp/daily_check', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                
                // Обновляем отображение стрика
                updateStreakDisplay(data.streak);
                
                // Обновляем баланс
                const balanceElement = document.querySelector('.user-balance');
                if (balanceElement) {
                    balanceElement.textContent = `${data.coins} кредитов`;
                }
            } else {
                showNotification(data.error || 'Ошибка при получении бонуса', 'error');
            }
        })
        .catch(error => {
            console.error('Error daily checkin:', error);
            showNotification('Произошла ошибка. Попробуйте позже.', 'error');
        });
    });
}

function updateStreakDisplay(streak) {
    const days = document.querySelectorAll('.streak-day');
    
    days.forEach((day, index) => {
        if (index < streak) {
            day.classList.add('active');
        } else {
            day.classList.remove('active');
        }
    });
}

function setupReferrals() {
    const copyBtn = document.getElementById('copy-referral-link');
    if (!copyBtn) return;
    
    copyBtn.addEventListener('click', () => {
        const linkInput = document.getElementById('referral-link');
        linkInput.select();
        document.execCommand('copy');
        
        // Анимация копирования
        copyBtn.classList.add('copy-animation');
        setTimeout(() => {
            copyBtn.classList.remove('copy-animation');
        }, 500);
        
        showNotification('Ссылка скопирована!', 'success');
    });
}

function loadProfileData() {
    // Загрузка количества рефералов
    loadReferralStats();
}

function loadReferralStats() {
    const referralCount = document.getElementById('referral-count');
    const referralBonus = document.getElementById('referral-bonus');
    
    if (referralCount && referralBonus) {
        fetch('/miniapp/referral_stats')
            .then(response => response.json())
            .then(data => {
                referralCount.textContent = data.count;
                referralBonus.textContent = data.bonus;
            })
            .catch(error => {
                console.error('Error loading referral stats:', error);
            });
    }
}

function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type} show`;
    toast.innerHTML = `
        <div class="toast-content">
            <span class="toast-message">${message}</span>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}