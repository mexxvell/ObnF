// miniapp.js — управление WebApp, навигацией и уведомлениями
(function(){
  const tg = window.Telegram.WebApp;
  tg.expand();
  tg.ready();

  async function initSession() {
    try {
      const user = tg.initDataUnsafe?.user || null;
      if (!user) return;

      const payload = {
        user_id: user.id,
        username: user.username || "",
        display_name: `${user.first_name} ${user.last_name || ""}`,
        ref: window.INIT_REF || null
      };

      const res = await fetch('/miniapp/init', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });

      document.getElementById('user-mini').textContent = user.first_name || '';
      setActiveTabFromURL();
    } catch(e) {
      console.error('Ошибка инициализации:', e);
    }
  }

  function setActiveTabFromURL() {
    const path = window.location.pathname.split('/').pop();
    const tabs = {
      'home': 'home',
      'nlo': 'nlo',
      'predictions': 'pred',
      'profile': 'profile',
      'support': 'support'
    };
    const tab = tabs[path] || 'home';
    setActiveTab(tab);
  }

  function setActiveTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
  }

  // Управление боковым меню
  function setupBurger() {
    const burger = document.getElementById('burger');
    const menu = document.getElementById('side-menu');
    const close = document.getElementById('close-burger');

    burger.addEventListener('click', () => {
      menu.classList.toggle('hidden');
      tg.HapticFeedback.impactOccurred('medium');
    });

    close.addEventListener('click', (e) => {
      e.preventDefault();
      menu.classList.add('hidden');
      tg.HapticFeedback.impactOccurred('light');
    });

    document.addEventListener('click', (e) => {
      if (!menu.contains(e.target) && !burger.contains(e.target) && !menu.classList.contains('hidden')) {
        menu.classList.add('hidden');
      }
    });
  }

  // Переключение вкладок
  function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        tg.HapticFeedback.impactOccurred('light');
        const frame = document.getElementById('page-frame');
        frame.src = `/miniapp/${btn.dataset.tab}`;
        setActiveTab(btn.dataset.tab);
      });
    });
  }

  // Глобальный обработчик ссылок
  function setupLinkHandlers() {
    document.addEventListener('click', (e) => {
      let target = e.target;
      while (target && !target.href) target = target.parentElement;

      if (target && target.href && target.target !== '_blank') {
        e.preventDefault();
        document.getElementById('page-frame').src = target.href;
      }
    });
  }

  // Уведомления
  async function pollNotifications() {
    try {
      const res = await fetch('/miniapp/notifications');
      const data = await res.json();
      if (data.length) showLiveBanner(data[0]);
    } catch(e) { console.error('Ошибка опроса уведомлений:', e); }
  }

  function showLiveBanner(note) {
    const el = document.getElementById('live-banner');
    el.innerHTML = `
      <div class="banner-inner">
        <div class="logos">${note.team1} — ${note.team2}</div>
        <div class="score">${note.score1}:${note.score2}</div>
      </div>
    `;
    el.classList.add('pulse');
    el.onclick = () => {
      document.getElementById('page-frame').src = `/miniapp/match/${note.id}`;
      hideLiveBanner();
    };
    setTimeout(hideLiveBanner, 10000);
  }

  function hideLiveBanner() {
    const el = document.getElementById('live-banner');
    el.classList.remove('pulse');
    setTimeout(() => {
      el.style.opacity = '0';
      setTimeout(() => el.style.display = 'none', 300);
    }, 300);
  }

  // Инициализация
  document.addEventListener('DOMContentLoaded', () => {
    initSession();
    setupBurger();
    setupTabs();
    setupLinkHandlers();
    setInterval(pollNotifications, 8000);
  });
})();