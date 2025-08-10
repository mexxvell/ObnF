// miniapp.js — handles Telegram WebApp init, session registration, polling notifications, burger menu, basic UI

(function(){
  // Telegram WebApp
  const tg = window.Telegram.WebApp;
  tg.expand(); // попытка развернуть
  tg.ready(); // Готовим WebApp к работе

  // init: get initDataUnsafe (quick demo) and POST to server to register session
  async function initSession(){
    try {
      const user = (tg.initDataUnsafe && tg.initDataUnsafe.user) || null;
      if(!user){
        console.warn("Telegram user info not available");
        return;
      }
      const payload = {
        user_id: user.id,
        username: user.username || "",
        display_name: (user.first_name || "") + " " + (user.last_name || ""),
        ref: window.INIT_REF || null
      };
      const res = await fetch('/miniapp/init', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const j = await res.json();
      if(j && j.success) console.log('Session registered');
      
      // show user in header
      document.getElementById('user-mini').textContent = user.first_name || '';
      
      // Initialize active tab
      const currentPath = window.location.pathname;
      if(currentPath.includes('/miniapp/home')) {
        setActiveTab('home');
      } else if(currentPath.includes('/miniapp/nlo')) {
        setActiveTab('nlo');
      } else if(currentPath.includes('/miniapp/predictions')) {
        setActiveTab('pred');
      } else if(currentPath.includes('/miniapp/profile')) {
        setActiveTab('profile');
      } else if(currentPath.includes('/miniapp/support')) {
        setActiveTab('support');
      }
    } catch(e){
      console.error('initSession error', e);
    }
  }

  function setActiveTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('active');
  }

// Загрузка данных из Google Sheets
async function loadTournaments() {
  try {
    const res = await fetch('/api/tournaments');
    const data = await res.json();
    const container = document.getElementById('tournaments-container');
    container.innerHTML = data.map(t => `
      <div class="tournament-card">
        <h3>${t.Команда}</h3>
        <div class="details">
          <span>Игр: ${t.Игр}</span>
          <span>Очки: ${t.Очки}</span>
        </div>
      </div>
    `).join('');
  } catch(e) {
    console.error('Error loading tournaments:', e);
  }
}

  // polling unseen notifications every 8 seconds
  let pollInterval = null;
  async function pollNotifications(){
    try {
      const r = await fetch('/miniapp/notifications');
      const arr = await r.json();
      if(arr && arr.length){
        // show topmost as banner
        const top = arr[0];
        showLiveBanner(top);
      } else {
        hideLiveBanner();
      }
    } catch(e) {
      console.warn('notify poll err', e);
    }
  }

  function showLiveBanner(note) {
    const el = document.getElementById('live-banner');
    if(!el) return;
    
    el.innerHTML = `
      <div class="banner-inner">
        <div class="logos"><span>${note.team1}</span> — <span>${note.team2}</span></div>
        <div class="score">${note.score1}:${note.score2}</div>
      </div>
    `;
    
    el.classList.add('pulse');
    el.onclick = function() { 
      document.getElementById('page-frame').src = '/miniapp/match/' + note.id; 
      hideLiveBanner();
    };
    
    // Auto hide after 10 seconds
    setTimeout(hideLiveBanner, 10000);
  }

  function hideLiveBanner() {
    const el = document.getElementById('live-banner');
    if(el) {
      el.classList.remove('pulse');
      setTimeout(() => {
        el.style.opacity = '0';
        setTimeout(() => el.style.display = 'none', 300);
      }, 300);
    }
  }

  // burger menu toggle
  function setupBurger() {
    const burger = document.getElementById('burger');
    const side = document.getElementById('side-menu');
    const close = document.getElementById('close-burger');
    
    burger && burger.addEventListener('click', () => {
      side.classList.toggle('hidden');
      tg.HapticFeedback.impactOccurred('medium');
    });
    
    close && close.addEventListener('click', (e) => { 
      e.preventDefault(); 
      side.classList.add('hidden');
      tg.HapticFeedback.impactOccurred('light');
    });
    
    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
      if (!side.contains(e.target) && !burger.contains(e.target) && !side.classList.contains('hidden')) {
        side.classList.add('hidden');
      }
    });
  }

  // tabs (switch iframe src)
  function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        tg.HapticFeedback.impactOccurred('light');
        const tab = btn.dataset.tab;
        const frame = document.getElementById('page-frame');
        
        if(tab === 'home') frame.src = '/miniapp/home';
        else if(tab === 'nlo') frame.src = '/miniapp/nlo';
        else if(tab === 'pred') frame.src = '/miniapp/predictions';
        else if(tab === 'profile') frame.src = '/miniapp/profile';
        else if(tab === 'support') frame.src = '/miniapp/support';
        
        setActiveTab(tab);
      });
    });
  }

  // Global link handler
  function setupLinkHandlers() {
    document.addEventListener('click', function(e) {
      let target = e.target;
      while (target && !target.href) {
        target = target.parentElement;
      }
      
      if (target && target.href) {
        const href = target.href;
        const isInternal = href.includes(window.location.host) && href.includes('/miniapp');
        
        if (isInternal && target.target !== '_blank') {
          e.preventDefault();
          
          // Special handling for match links
          if (href.includes('/miniapp/match/')) {
            const matchId = href.split('/').pop();
            document.getElementById('page-frame').src = `/miniapp/match/${matchId}`;
            return;
          }
          
          // For all other internal links
          document.getElementById('page-frame').src = href;
        }
      }
    });
  }

  // init all
  document.addEventListener('DOMContentLoaded', () => {
    initSession();
    setupBurger();
    setupTabs();
    setupLinkHandlers();
    pollNotifications();
    pollInterval = setInterval(pollNotifications, 8000);
    
    // Setup iframe load handler
    const frame = document.getElementById('page-frame');
    if (frame) {
      frame.onload = function() {
        try {
          // Update active tab based on iframe content
          const src = frame.src;
          if (src.includes('/miniapp/home')) setActiveTab('home');
          else if (src.includes('/miniapp/nlo')) setActiveTab('nlo');
          else if (src.includes('/miniapp/predictions')) setActiveTab('pred');
          else if (src.includes('/miniapp/profile')) setActiveTab('profile');
          else if (src.includes('/miniapp/support')) setActiveTab('support');
        } catch (e) {
          console.error('Error updating tab state:', e);
        }
      };
    }
  });

  // graceful cleanup
  window.addEventListener('beforeunload', () => {
    if (pollInterval) clearInterval(pollInterval);
  });
})();