# app.py
import os
import logging
import threading
import time
import json
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import Flask, request, render_template, jsonify, session, redirect, url_for
import telebot
from telebot import types
from sqlalchemy import create_engine, text as sql_text
import random

# Optional: gspread for Google Sheets integration
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GS_ENABLED = True
    logger = logging.getLogger(__name__)
    logger.info("gspread и oauth2client успешно импортированы")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning("gspread не установлен: %s", e)
    GS_ENABLED = False

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Environment / Config ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN required")

OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0")) or None
if not OWNER_ID:
    raise RuntimeError("OWNER_TELEGRAM_ID required")

RENDER_URL = os.getenv("RENDER_URL", "https://football-league-app.onrender.com").rstrip('/')
WEBHOOK_URL = f"{RENDER_URL}/{TOKEN}"
MINIAPP_URL = f"{RENDER_URL}/miniapp"

DATABASE_URL = os.getenv("DATABASE_URL")  # Postgres URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Google Sheets
GS_CREDS_JSON = os.getenv("GS_CREDS_JSON")  # JSON string of service account creds
GS_SHEET_ID = os.getenv("GS_SHEET_ID")      # spreadsheet id

# Promo codes mapping by milestone level
PROMOCODES_BY_LEVEL = {
    10: "PROMO10",
    25: "PROMO25",
    50: "PROMO50",
    100: "PROMO100"
}

# --- DB init ---
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required (Postgres).")

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

def init_db():
    with engine.connect() as conn:
        # users table
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                coins INTEGER DEFAULT 0,
                badges TEXT DEFAULT '',
                referrer BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                banned_until TIMESTAMP
            )
        '''))
        # matches
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS matches (
                id SERIAL PRIMARY KEY,
                round INTEGER,
                team1 TEXT,
                team2 TEXT,
                score1 INTEGER DEFAULT 0,
                score2 INTEGER DEFAULT 0,
                datetime TIMESTAMP,
                status TEXT DEFAULT 'scheduled', -- scheduled/live/finished
                stream_url TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                odds_team1 INTEGER DEFAULT 35,
                odds_team2 INTEGER DEFAULT 65,
                odds_draw INTEGER DEFAULT 0
            )
        '''))
        # subscriptions
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS match_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                match_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # comments (просто пример)
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                match_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # notifications (server-side for in-app banners)
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                match_id INTEGER,
                event TEXT,
                seen BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # shop orders
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                item TEXT,
                price INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # active sessions for in-app presence
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS active_sessions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE,
                page TEXT,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # bets table for predictions
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS bets (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                match_id INTEGER,
                type TEXT,  -- team1, team2, draw
                amount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # products table for shop
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT,
                price INTEGER,
                image TEXT,
                description TEXT
            )
        '''))
        # tournaments table
        conn.execute(sql_text('''
            CREATE TABLE IF NOT EXISTS tournaments (
                id SERIAL PRIMARY KEY,
                name TEXT,
                date_range TEXT,
                participants INTEGER,
                price INTEGER
            )
        '''))
    logger.info("DB initialized")

init_db()

# --- gspread (Google Sheets) setup ---
gs_client = None
sheet = None
if GS_ENABLED and GS_CREDS_JSON and GS_SHEET_ID:
    try:
        creds_dict = json.loads(GS_CREDS_JSON)
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gs_client = gspread.authorize(creds)
        sheet = gs_client.open_by_key(GS_SHEET_ID)
        logger.info("Google Sheets connected")
    except Exception as e:
        logger.error("Google Sheets connection failed: %s", e)
        gs_client = None
else:
    status = {
        "GS_ENABLED": GS_ENABLED,
        "GS_CREDS_JSON": bool(GS_CREDS_JSON),
        "GS_SHEET_ID": bool(GS_SHEET_ID)
    }
    logger.info("Google Sheets is not enabled. Status: %s", status)
    gs_client = None

# --- Flask and TeleBot ---
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET", "supersecret")

bot = telebot.TeleBot(TOKEN)
# remove webhook then set
try:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    logger.info("Webhook set to %s", WEBHOOK_URL)
except Exception as e:
    logger.warning("Failed to set webhook: %s", e)

# --- Miniapp routes ---
@app.route('/')
def index():
    return redirect(url_for('miniapp'))

@app.route('/miniapp')
def miniapp():
    # base page with WebApp JS that will set session via initData
    return render_template('miniapp_index.html', miniapp_url=MINIAPP_URL, owner_id=OWNER_ID)

@app.route('/miniapp/init', methods=['POST'])
def miniapp_init():
    """
    Called from JS inside Telegram WebApp to register the user session.
    Expect JSON: { "user_id": 12345, "username": "name", "display_name": "Full Name" }
    """
    data = request.json or {}
    user_id = int(data.get('user_id', 0))
    username = data.get('username') or ""
    display_name = data.get('display_name') or ""
    if not user_id:
        return jsonify({"success": False}), 400
    session['user_id'] = user_id
    ensure_user_exists(user_id, username, display_name)
    # update active session
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM active_sessions WHERE user_id = :id"), {"id": user_id})
        conn.execute(sql_text("INSERT INTO active_sessions (user_id, page) VALUES (:id, :page) ON CONFLICT (user_id) DO UPDATE SET last_active=NOW(), page=:page"),
                     {"id": user_id, "page": "home"})
    return jsonify({"success": True})

@app.route('/miniapp/profile')
def miniapp_profile():
    user_id = session.get('user_id', 0)
    if not user_id:
        return "Не авторизован", 403
    return render_template('profile.html')

@app.route('/miniapp/profile_api')
def miniapp_profile_api():
    user_id = session.get('user_id', 0)
    if not user_id:
        return jsonify({"error": "unauth"}), 403
    with engine.connect() as conn:
        row = conn.execute(sql_text("SELECT id, username, display_name, level, xp, badges, coins FROM users WHERE id = :id"),
                           {"id": user_id}).fetchone()
    if not row:
        return jsonify({"error": "notfound"}), 404
    return jsonify({
        "id": row.id,
        "username": row.username,
        "display_name": row.display_name,
        "level": row.level,
        "xp": row.xp,
        "badges": (row.badges or "").split(",") if row.badges else [],
        "coins": row.coins
    })
 
@app.route('/miniapp/standings')
def miniapp_standings():
    if not gs_client or not sheet:
        return "Google Sheets не настроен", 500
    try:
        ws = sheet.worksheet("ТАБЛИЦА")
        data = ws.get_all_values()
        return render_template('standings.html', table=data)
    except Exception as e:
        logger.error(f"Ошибка чтения Google Sheets: {e}")
        return "Ошибка чтения данных", 500

@app.route('/miniapp/create_order', methods=['POST'])
def miniapp_create_order():
    user_id = session.get('user_id', 0)
    if not user_id:
        return jsonify({"success": False, "error": "unauth"}), 403
    data = request.json or {}
    item = data.get('item')
    price = int(data.get('price', 0))
    if not item or price <= 0:
        return jsonify({"success": False, "error": "invalid"}), 400
    with engine.begin() as conn:
        conn.execute(sql_text(
            "INSERT INTO orders (user_id, item, price) VALUES (:uid, :item, :price)"
        ), {"uid": user_id, "item": item, "price": price})
    return jsonify({"success": True})

@app.route('/miniapp/support')
def miniapp_support():
    return render_template('support.html')

@app.route('/miniapp/nlo')
def miniapp_nlo():
    return render_template('nlo.html')

@app.route('/miniapp/predictions')
def miniapp_predictions():
    return render_template('predictions.html')

@app.route('/miniapp/shop')
def miniapp_shop():
    products = get_products()
    return render_template('shop.html', products=products)

@app.route('/miniapp/home')
def miniapp_home():
    user_id = session.get('user_id', 0)
    # show top-level home (cards, latest matches)
    rounds = []
    for r in range(1,4):
        matches = get_matches(r)
        rounds.append({"number": r, "matches": matches})
    return render_template('home.html', rounds=rounds, user_id=user_id, owner_id=OWNER_ID)

@app.route('/miniapp/matches')
def miniapp_matches():
    user_id = session.get('user_id', 0)
    rounds = []
    for r in range(1,4):
        matches = get_matches(r)
        rounds.append({"number": r, "matches": matches})
    # unseen notifications
    notifications = get_unseen_notifications(user_id)
    return render_template('matches.html', rounds=rounds, notifications=notifications, user_id=user_id)

@app.route('/miniapp/match/<int:match_id>')
def miniapp_match_detail(match_id):
    user_id = session.get('user_id', 0)
    match = get_match(match_id)
    if not match:
        return "Матч не найден", 404
    form1 = get_team_form(match.team1)
    form2 = get_team_form(match.team2)
    players1 = get_team_players(match.team1)
    players2 = get_team_players(match.team2)
    subscribed = is_subscribed_to_match(user_id, match_id)
    return render_template('match_detail.html', match=match, form1=form1, form2=form2,
                           players1=players1, players2=players2, subscribed=subscribed,
                           user_id=user_id, OWNER_ID=OWNER_ID)

@app.route('/miniapp/subscribe/<int:match_id>', methods=['POST'])
def miniapp_subscribe(match_id):
    user_id = session.get('user_id', 0)
    if not user_id:
        return jsonify({"success": False}), 403
    subscribe_to_match(user_id, match_id)
    return jsonify({"success": True})

@app.route('/miniapp/unsubscribe/<int:match_id>', methods=['POST'])
def miniapp_unsubscribe(match_id):
    user_id = session.get('user_id', 0)
    if not user_id:
        return jsonify({"success": False}), 403
    unsubscribe_from_match(user_id, match_id)
    return jsonify({"success": True})

@app.route('/miniapp/update_score', methods=['POST'])
def miniapp_update_score():
    data = request.json or {}
    user_id = session.get('user_id', 0)
    if user_id != OWNER_ID:
        return jsonify({"success": False, "error": "access denied"}), 403
    match_id = int(data.get('match_id'))
    score1 = int(data.get('score1'))
    score2 = int(data.get('score2'))
    ok = update_match_score(match_id, score1, score2)
    if ok:
        send_score_update_notifications(match_id, score1, score2)
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route('/miniapp/notifications')
def miniapp_notifications_api():
    user_id = session.get('user_id', 0)
    notes = get_unseen_notifications(user_id)
    out = []
    for n in notes:
        out.append({
            "id": n.id,
            "team1": n.team1,
            "team2": n.team2,
            "score1": n.score1,
            "score2": n.score2,
            "event": n.event,
            "created_at": str(n.created_at)
        })
    return jsonify(out)

@app.route('/miniapp/mark_seen/<int:notif_id>', methods=['POST'])
def miniapp_mark_seen(notif_id):
    if mark_notification_seen(notif_id):
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route('/miniapp/place_bet', methods=['POST'])
def place_bet():
    user_id = session.get('user_id', 0)
    if not user_id:
        return jsonify({"error": "unauth"}), 403
    
    data = request.json
    match_id = data.get('match_id')
    bet_type = data.get('bet_type')  # team1, team2, draw
    amount = data.get('amount')
    
    if not match_id or not bet_type or not amount:
        return jsonify({"error": "invalid data"}), 400
    
    # Проверка, что матч еще не начался
    match = get_match(match_id)
    if not match or match.status != 'scheduled':
        return jsonify({"error": "match not available"}), 400
    
    # Проверка, что пользователь имеет достаточно средств
    user = get_user(user_id)
    if user.coins < amount:
        return jsonify({"error": "insufficient funds"}), 400
    
    # Запись ставки
    with engine.begin() as conn:
        conn.execute(sql_text("""
            INSERT INTO bets (user_id, match_id, type, amount)
            VALUES (:user_id, :match_id, :bet_type, :amount)
        """), {
            "user_id": user_id,
            "match_id": match_id,
            "bet_type": bet_type,
            "amount": amount
        })
        # Списание средств
        conn.execute(sql_text("""
            UPDATE users SET coins = coins - :amount WHERE id = :user_id
        """), {
            "amount": amount,
            "user_id": user_id
        })
    
    return jsonify({"success": True})

@app.route('/miniapp/bets')
def user_bets():
    user_id = session.get('user_id', 0)
    if not user_id:
        return jsonify({"error": "unauth"}), 403
    
    bets = get_user_bets(user_id)
    return jsonify(bets)

@app.route('/miniapp/admin/bets')
def admin_bets():
    user_id = session.get('user_id', 0)
    if user_id != OWNER_ID:
        return "Доступ запрещён", 403
    
    bets = get_all_bets()
    return render_template('admin_bets.html', bets=bets)

@app.route('/miniapp/admin/update_odds', methods=['POST'])
def update_odds():
    user_id = session.get('user_id', 0)
    if user_id != OWNER_ID:
        return jsonify({"success": False, "error": "access denied"}), 403
    
    data = request.json
    match_id = data.get('match_id')
    odds_team1 = data.get('odds_team1')
    odds_team2 = data.get('odds_team2')
    odds_draw = data.get('odds_draw')
    
    if not match_id or odds_team1 is None or odds_team2 is None or odds_draw is None:
        return jsonify({"error": "invalid data"}), 400
    
    with engine.begin() as conn:
        conn.execute(sql_text("""
            UPDATE matches 
            SET odds_team1 = :odds_team1, 
                odds_team2 = :odds_team2, 
                odds_draw = :odds_draw 
            WHERE id = :match_id
        """), {
            "odds_team1": odds_team1,
            "odds_team2": odds_team2,
            "odds_draw": odds_draw,
            "match_id": match_id
        })
    
    return jsonify({"success": True})

@app.route('/miniapp/admin/set_match_result', methods=['POST'])
def set_match_result():
    user_id = session.get('user_id', 0)
    if user_id != OWNER_ID:
        return jsonify({"success": False, "error": "access denied"}), 403
    
    data = request.json
    match_id = data.get('match_id')
    score1 = data.get('score1')
    score2 = data.get('score2')
    
    if not match_id or score1 is None or score2 is None:
        return jsonify({"error": "invalid data"}), 400
    
    # Обновление счета матча
    update_match_score(match_id, score1, score2)
    
    # Закрытие ставок и расчет выигрышей
    process_bets_for_match(match_id, score1, score2)
    
    return jsonify({"success": True})

# --- Admin panel (miniapp visible only if session user == owner) ---
@app.route('/miniapp/admin')
def miniapp_admin():
    user_id = session.get('user_id', 0)
    if user_id != OWNER_ID:
        return "Доступ запрещён", 403
    stats = current_online_counts()
    # latest comments
    with engine.connect() as conn:
        comments = conn.execute(sql_text("SELECT c.id, c.user_id, c.text, c.created_at, u.display_name FROM comments c LEFT JOIN users u ON c.user_id = u.id ORDER BY c.created_at DESC LIMIT 50")).fetchall()
    return render_template('admin.html', stats=stats, comments=comments)

@app.route('/miniapp/admin/delete_comment/<int:comment_id>', methods=['POST'])
def admin_delete_comment(comment_id):
    user_id = session.get('user_id', 0)
    if user_id != OWNER_ID:
        return jsonify({"success": False}), 403
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM comments WHERE id = :id"), {"id": comment_id})
    return jsonify({"success": True})

@app.route('/miniapp/admin/ban_user', methods=['POST'])
def admin_ban_user():
    user_id = session.get('user_id', 0)
    if user_id != OWNER_ID:
        return jsonify({"success": False}), 403
    data = request.json or {}
    target = int(data.get('target'))
    period = data.get('period')  # '10m', '1h', '1d', 'perm'
    if period == 'perm':
        until = datetime(3000,1,1)
    else:
        delta = {'10m':10, '1h':60, '1d':1440}.get(period, 10)
        until = datetime.now(timezone.utc) + timedelta(minutes=delta)
    with engine.begin() as conn:
        conn.execute(sql_text("UPDATE users SET banned_until = :until WHERE id = :id"), {"until": until, "id": target})
    return jsonify({"success": True})

# --- Telegram bot handlers ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    user_id = message.chat.id
    ensure_user_exists(user_id, user.username, f"{user.first_name} {user.last_name or ''}")
    # Просто отправляем приветственное сообщение БЕЗ клавиатуры
    bot.send_message(user_id, "Добро пожаловать в Лигу! Нажмите кнопку 'Open' рядом со скрепкой, чтобы открыть приложение.")

@bot.message_handler(func=lambda m: m.text == "🔗 Пригласить друга")
def referral(message):
    user = message.from_user
    user_id = message.chat.id
    # referral link: miniapp with ref param (we will parse in frontend)
    ref_link = f"{MINIAPP_URL}?ref={user_id}"
    bot.send_message(user_id, f"Поделитесь ссылкой с другом: {ref_link}\nЕсли друг зарегистрируется через неё — вы получите бонусы!")

# Webhook processing
@app.route(f"/{TOKEN}", methods=['POST'])
def telegram_webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "", 200

# --- Helpers ---
def ensure_user_exists(user_id, username=None, display_name=None, referrer=None):
    with engine.begin() as conn:
        r = conn.execute(sql_text("SELECT id FROM users WHERE id = :id"), {"id": user_id}).fetchone()
        if not r:
            conn.execute(sql_text(
                "INSERT INTO users (id, username, display_name, referrer) VALUES (:id, :username, :display_name, :referrer)"
            ), {"id": user_id, "username": username or "", "display_name": display_name or "", "referrer": referrer})

def user_level_for_xp(xp):
    """Example XP -> level mapping (progressive). Returns level and xp needed for next."""
    # simple: level increases every 100 xp up to 100 level
    level = min(100, xp // 100 + 1)
    next_xp = (level) * 100
    return level, next_xp

def add_xp(user_id, xp_amount, reason=""):
    with engine.begin() as conn:
        row = conn.execute(sql_text("SELECT xp, level FROM users WHERE id = :id"), {"id": user_id}).fetchone()
        if not row:
            return
        new_xp = (row.xp or 0) + xp_amount
        level, next_xp = user_level_for_xp(new_xp)
        badges_added = []
        # if new milestones reached, give badge or promo
        if level >= 10 and "lvl10" not in (row.badges or ""):
            badges_added.append("lvl10")
        if level >= 25 and "lvl25" not in (row.badges or ""):
            badges_added.append("lvl25")
        if level >= 50 and "lvl50" not in (row.badges or ""):
            badges_added.append("lvl50")
        if level >= 100 and "lvl100" not in (row.badges or ""):
            badges_added.append("lvl100")
        # update DB
        new_badges = (row.badges or "")
        for b in badges_added:
            if new_badges:
                new_badges += "," + b
            else:
                new_badges = b
        conn.execute(sql_text("UPDATE users SET xp = :xp, level = :level, badges = :badges, last_active = NOW() WHERE id = :id"),
                     {"xp": new_xp, "level": level, "badges": new_badges, "id": user_id})
        # If promo code milestone hit, create a coupon order or save promo to user (this is simplified)
        for lvl in PROMOCODES_BY_LEVEL:
            if level >= lvl and str(lvl) not in (row.badges or ""):
                # attach promo as badge to avoid double awarding (reuse badge store)
                logger.info("User %s reached level %s, awarding promo %s", user_id, lvl, PROMOCODES_BY_LEVEL[lvl])
        return level

def current_online_counts():
    with engine.connect() as conn:
        total = conn.execute(sql_text("SELECT COUNT(*) FROM users")).scalar()
        online = conn.execute(sql_text("SELECT COUNT(*) FROM active_sessions WHERE last_active > NOW() - INTERVAL '5 minutes'")).scalar()
        # daily etc (simple)
        today = conn.execute(sql_text("SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '1 day'")).scalar()
        week = conn.execute(sql_text("SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '7 days'")).scalar()
    return {"total": total, "online": online, "today": today, "week": week}

def get_user(user_id):
    with engine.connect() as conn:
        row = conn.execute(sql_text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).fetchone()
    return row

def get_user_bets(user_id):
    with engine.connect() as conn:
        rows = conn.execute(sql_text("""
            SELECT b.*, m.team1, m.team2, m.datetime, m.status 
            FROM bets b 
            JOIN matches m ON b.match_id = m.id 
            WHERE b.user_id = :user_id 
            ORDER BY b.created_at DESC
        """), {"user_id": user_id}).fetchall()
    return [{
        "id": r.id,
        "match_id": r.match_id,
        "team1": r.team1,
        "team2": r.team2,
        "datetime": str(r.datetime),
        "status": r.status,
        "type": r.type,
        "amount": r.amount,
        "created_at": str(r.created_at)
    } for r in rows]

def get_all_bets():
    with engine.connect() as conn:
        rows = conn.execute(sql_text("""
            SELECT b.*, m.team1, m.team2, m.datetime, m.status, u.username, u.display_name 
            FROM bets b 
            JOIN matches m ON b.match_id = m.id 
            JOIN users u ON b.user_id = u.id 
            ORDER BY b.created_at DESC
        """)).fetchall()
    return [{
        "id": r.id,
        "user_id": r.user_id,
        "username": r.username,
        "display_name": r.display_name,
        "match_id": r.match_id,
        "team1": r.team1,
        "team2": r.team2,
        "datetime": str(r.datetime),
        "status": r.status,
        "type": r.type,
        "amount": r.amount,
        "created_at": str(r.created_at)
    } for r in rows]

def get_products():
    with engine.connect() as conn:
        # Если в базе нет товаров, добавляем тестовые
        products = conn.execute(sql_text("SELECT * FROM products")).fetchall()
        if not products:
            test_products = [
                {"name": "Футболка", "price": 500, "image": "product1.jpg", "description": "Официальная футболка лиги"},
                {"name": "Кепка", "price": 300, "image": "product2.jpg", "description": "Стильная кепка с логотипом"},
                {"name": "Сувенир", "price": 150, "image": "product3.jpg", "description": "Сувенирный набор"},
                {"name": "Эксклюзивный набор", "price": 1000, "image": "product4.jpg", "description": "Полный набор фаната"}
            ]
            for product in test_products:
                conn.execute(sql_text("""
                    INSERT INTO products (name, price, image, description)
                    VALUES (:name, :price, :image, :description)
                """), product)
            products = conn.execute(sql_text("SELECT * FROM products")).fetchall()
    return [{
        "id": p.id,
        "name": p.name,
        "price": p.price,
        "image": p.image,
        "description": p.description
    } for p in products]

def calculate_odds(match):
    """Рассчитывает коэффициенты с учетом маржи 5%"""
    total = match.odds_team1 + match.odds_team2 + match.odds_draw
    if total == 0:
        return {
            'team1': 2.0,
            'team2': 2.0,
            'draw': 2.0
        }
    
    k_factor = 1.05  # Маржа 5%
    return {
        'team1': round((100 / match.odds_team1) * k_factor, 2) if match.odds_team1 > 0 else 0,
        'team2': round((100 / match.odds_team2) * k_factor, 2) if match.odds_team2 > 0 else 0,
        'draw': round((100 / match.odds_draw) * k_factor, 2) if match.odds_draw > 0 else 0
    }

def process_bets_for_match(match_id, score1, score2):
    """Обработка ставок после завершения матча"""
    with engine.begin() as conn:
        # Получаем информацию о матче
        match = conn.execute(sql_text("SELECT * FROM matches WHERE id = :match_id"), {"match_id": match_id}).fetchone()
        if not match:
            return
        
        # Определяем результат матча
        result = "draw"
        if score1 > score2:
            result = "team1"
        elif score2 > score1:
            result = "team2"
        
        # Получаем все ставки на матч
        bets = conn.execute(sql_text("""
            SELECT * FROM bets WHERE match_id = :match_id
        """), {"match_id": match_id}).fetchall()
        
        # Рассчитываем коэффициенты
        odds = calculate_odds(match)
        
        # Обрабатываем каждую ставку
        for bet in bets:
            # Если ставка выиграла
            if bet.type == result:
                # Рассчитываем выигрыш
                win_amount = bet.amount * odds[result]
                # Добавляем выигрыш пользователю
                conn.execute(sql_text("""
                    UPDATE users SET coins = coins + :win_amount WHERE id = :user_id
                """), {"win_amount": win_amount, "user_id": bet.user_id})
            # Если ставка проиграла, средства уже списаны при размещении ставки

# --- Match helpers (simple wrappers) ---
def get_matches(round_number=None):
    with engine.connect() as conn:
        if round_number:
            rows = conn.execute(sql_text("SELECT * FROM matches WHERE round = :r ORDER BY datetime"), {"r": round_number}).fetchall()
        else:
            rows = conn.execute(sql_text("SELECT * FROM matches ORDER BY datetime")).fetchall()
    return rows

def get_match(match_id):
    with engine.connect() as conn:
        r = conn.execute(sql_text("SELECT * FROM matches WHERE id = :id"), {"id": match_id}).fetchone()
    return r

def get_team_form(team):
    # simple: derive form randomly or from external table; here placeholder
    return "-/-/-/-/-"

def get_team_players(team):
    # placeholder
    return []

def update_match_score(match_id, s1, s2):
    with engine.begin() as conn:
        conn.execute(sql_text("UPDATE matches SET score1 = :s1, score2 = :s2, last_updated = NOW(), status = 'finished' WHERE id = :id"),
                     {"s1": s1, "s2": s2, "id": match_id})
    return True

# --- Notifications & subscriptions ---
def subscribe_to_match(user_id, match_id):
    with engine.begin() as conn:
        exists = conn.execute(sql_text("SELECT 1 FROM match_subscriptions WHERE user_id = :uid AND match_id = :mid"),
                             {"uid": user_id, "mid": match_id}).fetchone()
        if not exists:
            conn.execute(sql_text("INSERT INTO match_subscriptions (user_id, match_id) VALUES (:uid, :mid)"),
                         {"uid": user_id, "mid": match_id})
    return True

def unsubscribe_from_match(user_id, match_id):
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM match_subscriptions WHERE user_id = :uid AND match_id = :mid"),
                     {"uid": user_id, "mid": match_id})
    return True

def is_subscribed_to_match(user_id, match_id):
    with engine.connect() as conn:
        r = conn.execute(sql_text("SELECT 1 FROM match_subscriptions WHERE user_id = :uid AND match_id = :mid"),
                         {"uid": user_id, "mid": match_id}).fetchone()
    return bool(r)

def get_match_subscribers(match_id):
    with engine.connect() as conn:
        rows = conn.execute(sql_text("SELECT user_id FROM match_subscriptions WHERE match_id = :mid"), {"mid": match_id}).fetchall()
    return [r.user_id for r in rows]

def create_notification(user_id, match_id, event):
    with engine.begin() as conn:
        conn.execute(sql_text("INSERT INTO notifications (user_id, match_id, event) VALUES (:uid, :mid, :ev)"),
                     {"uid": user_id, "mid": match_id, "ev": event})
    return True

def get_unseen_notifications(user_id):
    with engine.connect() as conn:
        rows = conn.execute(sql_text(
            "SELECT n.id, m.team1, m.team2, m.score1, m.score2, n.event, n.created_at "
            "FROM notifications n JOIN matches m ON n.match_id = m.id WHERE n.user_id = :uid AND n.seen = FALSE ORDER BY n.created_at DESC"
        ), {"uid": user_id}).fetchall()
    return rows

def mark_notification_seen(nid):
    with engine.begin() as conn:
        conn.execute(sql_text("UPDATE notifications SET seen = TRUE WHERE id = :id"), {"id": nid})
    return True

def send_score_update_notifications(match_id, score1, score2):
    match = get_match(match_id)
    if not match:
        return
    subscribers = get_match_subscribers(match_id)
    message = f"⚽ Обновление: {match.team1} - {match.team2}\nСчет {score1}:{score2}"
    for uid in subscribers:
        try:
            # if user has active session, create in-app notification, else send telegram message
            with engine.connect() as conn:
                sess = conn.execute(sql_text("SELECT page, last_active FROM active_sessions WHERE user_id = :id AND last_active > NOW() - INTERVAL '5 minutes'"), {"id": uid}).fetchone()
            if sess:
                # user online in-app but maybe not viewing this match
                # create in-app notification
                create_notification(uid, match_id, "Изменение счета")
            else:
                # send telegram notification
                bot.send_message(uid, message)
        except Exception as e:
            logger.error("send notification err: %s", e)

# --- Google Sheets sync (periodic) ---
def sync_to_sheets():
    if not gs_client or not sheet:
        logger.warning("Google Sheets not configured; skipping sync")
        return
    while True:
        try:
            # example: push users to sheet "Users" and matches to "Matches"
            try:
                users_ws = sheet.worksheet("Users")
            except Exception:
                users_ws = sheet.add_worksheet("Users", rows=1000, cols=10)
            with engine.connect() as conn:
                rows = conn.execute(sql_text("SELECT id, username, display_name, level, xp, coins, badges, created_at FROM users ORDER BY created_at DESC")).fetchall()
            data = [["id","username","display_name","level","xp","coins","badges","created_at"]]
            for r in rows:
                data.append([r.id, r.username, r.display_name, r.level, r.xp, r.coins, r.badges, str(r.created_at)])
            users_ws.clear()
            users_ws.update('A1', data)
            # matches
            try:
                matches_ws = sheet.worksheet("Matches")
            except Exception:
                matches_ws = sheet.add_worksheet("Matches", rows=500, cols=10)
            with engine.connect() as conn:
                mrows = conn.execute(sql_text("SELECT id, round, team1, team2, score1, score2, datetime, status FROM matches ORDER BY datetime")).fetchall()
            mdata = [["id","round","team1","team2","score1","score2","datetime","status"]]
            for m in mrows:
                mdata.append([m.id, m.round, m.team1, m.team2, m.score1, m.score2, str(m.datetime), m.status])
            matches_ws.clear()
            matches_ws.update('A1', mdata)
            logger.info("Synced DB -> Google Sheets")
        except Exception as e:
            logger.error("Sheets sync err: %s", e)
        # run every 6-12 hours (configurable). Here: 6 hours
        time.sleep(6 * 3600)

# start sheets sync thread only if configured
if gs_client and sheet:
    t = threading.Thread(target=sync_to_sheets, daemon=True)
    t.start()

# --- Test data generator (if no matches) ---
def generate_test_matches():
    with engine.begin() as conn:
        cnt = conn.execute(sql_text("SELECT COUNT(*) FROM matches")).scalar()
        if cnt == 0:
            teams = [("Динамо","Спартак"),("Торпедо","Зенит"),("Локомотив","Челси"),("Динамо","Зенит")]
            now = datetime.now(timezone.utc)
            for i, pair in enumerate(teams, start=1):
                conn.execute(sql_text("INSERT INTO matches (round, team1, team2, datetime, stream_url, odds_team1, odds_team2) VALUES (:r,:a,:b,:dt,:url, 35, 65)"),
                             {"r": i, "a": pair[0], "b": pair[1], "dt": now + timedelta(days=i), "url": "https://www.youtube.com/embed/dQw4w9WgXcQ"})
            logger.info("Inserted test matches")

generate_test_matches()

# --- Static helpers for rendering templates ---
@app.context_processor
def inject_now():
    return {'now': datetime.now(timezone.utc), 'OWNER_ID': OWNER_ID}

# --- Run ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)