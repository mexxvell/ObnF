// miniapp.js — handles Telegram WebApp init, session registration, polling notifications, burger menu, basic UI

(function(){
  // Telegram WebApp
  const tg = window.Telegram.WebApp;
  tg.expand(); // попытка развернуть

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
    } catch(e){
      console.error('initSession error', e);
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
    } catch(e){
      console.warn('notify poll err', e);
    }
  }

  function showLiveBanner(note){
    const el = document.getElementById('live-banner');
    if(!el) return;
    el.innerHTML = `<div class="banner-inner">
      <div class="logos"><span>${note.team1}</span> — <span>${note.team2}</span></div>
      <div class="score">${note.score1}:${note.score2}</div>
    </div>`;
    el.classList.remove('hidden');
    el.classList.add('pulse');
    el.onclick = function(){ window.parent.location.href = '/miniapp/match/' + note.id; };
  }

  function hideLiveBanner(){
    const el = document.getElementById('live-banner');
    if(el){
      el.classList.add('hidden');
      el.classList.remove('pulse');
    }
  }

  // burger menu toggle
  function setupBurger(){
    const burger = document.getElementById('burger');
    const side = document.getElementById('side-menu');
    const close = document.getElementById('close-burger');
    burger && burger.addEventListener('click', ()=> side.classList.toggle('hidden'));
    close && close.addEventListener('click', (e)=> { e.preventDefault(); side.classList.add('hidden'); });
  }

  // tabs (switch iframe src)
  function setupTabs(){
    document.querySelectorAll('.tab-btn').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        const frame = document.getElementById('page-frame');
        if(tab === 'home') frame.src = '/miniapp/home';
        else if(tab === 'nlo') frame.src = '/miniapp/nlo' ;
        else if(tab === 'pred') frame.src = '/miniapp/predictions';
        else if(tab === 'profile') frame.src = '/miniapp/profile';
        else if(tab === 'support') frame.src = '/miniapp/support';
      });
    });
  }

  // init all
  document.addEventListener('DOMContentLoaded', ()=>{
    initSession();
    setupBurger();
    setupTabs();
    pollNotifications();
    pollInterval = setInterval(pollNotifications, 8000);
  });

  // graceful cleanup
  window.addEventListener('beforeunload', ()=>{
    if(pollInterval) clearInterval(pollInterval);
  });

})();
