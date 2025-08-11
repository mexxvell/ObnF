# app.py
"""
НЛО — Футбольная Лига
Полный backend-код для Telegram Web App
Версия: 1.0
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps

import psycopg2
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, session, g
)
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
from apscheduler.schedulers.background import BackgroundScheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('NFO_Liga')

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)

# Константы (можно переопределить через Google Sheets)
FIRST_LOGIN_CREDITS = 100
DAILY_CHECKIN_CREDITS = 20
DAILY_STREAK_BONUS = 100
WEEKLY_REWARDS = [300, 200, 100]
REFERRAL_REWARD_REFERRED = 50
REFERRAL_REWARD_REFERRER_AFTER_STAKE = 30
DEFAULT_MARGIN = 0.05  # 5%

# XP системы
XP_REGISTRATION = 50
XP_DAILY_CHECKIN = 10
XP_CORRECT_PREDICTION = 30
XP_EXACT_SCORE_BONUS = 70
XP_ACHIEVEMENT_BRONZE = 15
XP_ACHIEVEMENT_SILVER = 40
XP_ACHIEVEMENT_GOLD = 120
XP_LIKE = 2
XP_COMMENT = 2
XP_REFERRAL = 20

# Подключение к БД
def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(os.environ['DATABASE_URL'])
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Проверка владельца
def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.args.get('user_id') or request.json.get('user_id')
        if not user_id or str(user_id) != os.environ['OWNER_TELEGRAM_ID']:
            return jsonify({"error": "Доступ запрещен"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Google Sheets API
def get_sheets_service():
    creds_info = json.loads(os.environ['GS_CREDS_JSON'])
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return build('sheets', 'v4', credentials=creds)

def ensure_sheets_structure():
    """Создает листы в Google Sheets, если их нет"""
    service = get_sheets_service()
    spreadsheet_id = os.environ['GS_SHEET_ID']
    
    # Список необходимых листов
    required_sheets = [
        "Таблица", "Статистика Голы", "Статистика ассистенты", 
        "Статистика Г+П", "Расписание игр", "Составы", 
        "Детали Матча", "Ставки", "leaderboard_history", "referrals"
    ]
    
    # Получаем текущие листы
    sheet_metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()
    existing_sheets = [sheet['properties']['title'] for sheet in sheet_metadata.get('sheets', [])]
    
    # Создаем отсутствующие листы
    for sheet_name in required_sheets:
        if sheet_name not in existing_sheets:
            logger.info(f"Создаем лист: {sheet_name}")
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {'title': sheet_name}
                    }
                }]
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            
            # Добавляем заголовки
            headers = []
            if sheet_name == "Таблица":
                headers = [["key", "value"]]
            elif sheet_name == "Статистика Голы":
                headers = [["player_id", "player_name", "team", "matches_played", "goals", "season"]]
            elif sheet_name == "Статистика ассистенты":
                headers = [["player_id", "player_name", "team", "matches_played", "assists", "season"]]
            elif sheet_name == "Статистика Г+П":
                headers = [["player_id", "player_name", "team", "matches_played", "goals_plus_assists", "season"]]
            elif sheet_name == "Расписание игр":
                headers = [["match_id", "date_iso", "time_iso", "home_team", "away_team", "status", "score_home", "score_away", "venue", "season", "notes"]]
            elif sheet_name == "Составы":
                headers = [["match_id", "team", "player_id", "player_name", "position", "is_starting"]]
            elif sheet_name == "Детали Матча":
                headers = [["match_id", "event_time", "event_type", "player_id", "player_name", "team", "details"]]
            elif sheet_name == "Ставки":
                headers = [["user_id", "total_bets", "wins", "losses", "win_percent"]]
            elif sheet_name == "leaderboard_history":
                headers = [["week_start_iso", "user_id", "username", "wins", "total_bets", "win_percent", "rank", "reward_given"]]
            elif sheet_name == "referrals":
                headers = [["referrer_id", "referred_id", "timestamp", "reward_granted"]]
                
            if headers:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption="RAW",
                    body={'values': headers}
                ).execute()

# Инициализация при старте
@app.before_first_request
def initialize():
    ensure_sheets_structure()
    logger.info("Структура Google Sheets проверена и инициализирована")

# API для фронтенда
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Получаем профиль пользователя
    cursor.execute("""
        SELECT id, username, display_name, credits, xp, level, 
               daily_checkin_streak, last_checkin_date
        FROM users 
        WHERE id = %s
    """, (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # Регистрация нового пользователя
        cursor.execute("""
            INSERT INTO users (id, credits, xp, level, 
                              daily_checkin_streak, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id, username, display_name, credits, xp, level, 
                      daily_checkin_streak, last_checkin_date
        """, (user_id, FIRST_LOGIN_CREDITS, XP_REGISTRATION, 1, 0))
        user = cursor.fetchone()
        db.commit()
    
    # Получаем открытые ачивки
    cursor.execute("""
        SELECT achievement_key, tier, unlocked_at 
        FROM achievements_unlocked 
        WHERE user_id = %s
    """, (user_id,))
    achievements = cursor.fetchall()
    
    # Формируем ответ
    profile = {
        'id': user[0],
        'username': user[1] or f"user_{user[0]}",
        'display_name': user[2] or f"Игрок {user[0]}",
        'credits': user[3],
        'xp': user[4],
        'level': user[5],
        'daily_streak': user[6],
        'next_level_xp': calculate_xp_for_level(user[5] + 1),
        'achievements': [{
            'key': a[0],
            'tier': a[1],
            'unlocked_at': a[2].isoformat() if a[2] else None
        } for a in achievements]
    }
    
    return jsonify(profile)

@app.route('/api/matches', methods=['GET'])
def get_matches():
    """Возвращает матчи из кеша или обновляет из Google Sheets"""
    db = get_db()
    cursor = db.cursor()
    
    # Проверяем актуальность кеша
    cursor.execute("""
        SELECT data_json, updated_at 
        FROM matches_cache 
        WHERE match_id = 'schedule'
    """)
    cache = cursor.fetchone()
    
    # Если кеш старый или отсутствует - обновляем
    if not cache or (datetime.now(timezone.utc) - cache[1]).total_seconds() > 900:  # 15 минут
        update_matches_cache()
        cursor.execute("""
            SELECT data_json, updated_at 
            FROM matches_cache 
            WHERE match_id = 'schedule'
        """)
        cache = cursor.fetchone()
    
    return jsonify({
        'matches': cache[0] if cache else [],
        'last_updated': cache[1].isoformat() if cache else None
    })

def update_matches_cache():
    """Обновляет кеш матчей из Google Sheets"""
    service = get_sheets_service()
    spreadsheet_id = os.environ['GS_SHEET_ID']
    
    # Получаем расписание игр
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="Расписание игр!A2:K"
    ).execute()
    rows = result.get('values', [])
    
    matches = []
    for row in rows:
        if len(row) >= 11:
            matches.append({
                'match_id': row[0],
                'date': row[1],
                'time': row[2],
                'home_team': row[3],
                'away_team': row[4],
                'status': row[5],
                'score_home': row[6] if len(row) > 6 else None,
                'score_away': row[7] if len(row) > 7 else None,
                'venue': row[8] if len(row) > 8 else None,
                'season': row[9] if len(row) > 9 else None,
                'notes': row[10] if len(row) > 10 else None
            })
    
    # Сохраняем в кеш
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO matches_cache (match_id, data_json, updated_at)
        VALUES ('schedule', %s, NOW())
        ON CONFLICT (match_id) 
        DO UPDATE SET data_json = EXCLUDED.data_json, updated_at = EXCLUDED.updated_at
    """, (json.dumps(matches),))
    db.commit()

@app.route('/api/bet', methods=['POST'])
def place_bet():
    """Размещение ставки пользователем"""
    data = request.json
    user_id = data.get('user_id')
    match_id = data.get('match_id')
    bet_type = data.get('bet_type')  # '1x2', 'total', 'exact_score'
    selection = data.get('selection')
    amount = data.get('amount')
    
    if not all([user_id, match_id, bet_type, selection, amount]):
        return jsonify({"error": "Missing required parameters"}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Проверяем баланс
    cursor.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user or user[0] < amount:
        return jsonify({"error": "Insufficient credits"}), 400
    
    # Получаем коэффициенты
    odds = calculate_odds(match_id, bet_type, selection)
    if not odds:
        return jsonify({"error": "Invalid bet selection"}), 400
    
    # Сохраняем ставку (в реальном приложении здесь была бы логика сохранения ставки)
    # В данном примере мы просто имитируем успешную ставку
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, reason, created_at)
        VALUES (%s, %s, 'bet', %s, NOW())
    """, (user_id, -amount, f"Ставка на матч {match_id}"))
    
    # Обновляем статистику ставок в Google Sheets
    update_betting_stats(user_id, amount)
    
    db.commit()
    
    # Начисляем XP за ставку
    add_xp(user_id, XP_CORRECT_PREDICTION, "Ставка размещена")
    
    return jsonify({
        "success": True,
        "odds": odds,
        "amount": amount,
        "potential_winnings": round(amount * odds, 2)
    })

def calculate_odds(match_id, bet_type, selection):
    """Рассчитывает динамические коэффициенты с учетом маржи"""
    # В реальном приложении здесь был бы запрос к Google Sheets для получения вероятностей
    # Для примера используем базовые значения
    
    # Получаем маржу из Google Sheets или используем значение по умолчанию
    margin = DEFAULT_MARGIN
    
    if bet_type == '1x2':
        # Пример: вероятности для домашней победы, ничьи, выездной победы
        if selection == '1':
            prob = 0.4
        elif selection == 'X':
            prob = 0.3
        elif selection == '2':
            prob = 0.3
        else:
            return None
        
        # Нормализуем вероятность и применяем маржу
        # Формула: коэффициент = 1 / (вероятность / (1 - маржа))
        adjusted_prob = prob / (1 - margin)
        odds = 1 / adjusted_prob
        return round(odds, 2)
    
    elif bet_type == 'total':
        # Пример для тотала >2.5
        prob = 0.6
        adjusted_prob = prob / (1 - margin)
        odds = 1 / adjusted_prob
        return round(odds, 2)
    
    elif bet_type == 'exact_score':
        # Высокий коэффициент для точного счета
        return 5.50
    
    return None

def update_betting_stats(user_id, amount):
    """Обновляет статистику ставок в Google Sheets"""
    service = get_sheets_service()
    spreadsheet_id = os.environ['GS_SHEET_ID']
    
    # Проверяем, есть ли пользователь в статистике
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="Ставки!A2:A"
    ).execute()
    user_ids = [row[0] for row in result.get('values', []) if row]
    
    if str(user_id) in user_ids:
        # Обновляем существующую запись
        idx = user_ids.index(str(user_id)) + 2  # +2 because A2 is first row
        # Получаем текущие значения
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"Ставки!B{idx}:E{idx}"
        ).execute()
        values = result.get('values', [])
        
        if values:
            total_bets = int(values[0][0]) + 1 if len(values[0]) > 0 else 1
            wins = int(values[0][1]) if len(values[0]) > 1 else 0
            losses = int(values[0][2]) if len(values[0]) > 2 else 0
            win_percent = round(wins / total_bets * 100, 2) if total_bets > 0 else 0
            
            # Обновляем данные
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"Ставки!B{idx}:E{idx}",
                valueInputOption="RAW",
                body={'values': [[total_bets, wins, losses, win_percent]]}
            ).execute()
    else:
        # Создаем новую запись
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="Ставки!A1",
            valueInputOption="RAW",
            body={'values': [[user_id, 1, 0, 0, 0]]}
        ).execute()

def calculate_xp_for_level(level):
    """Рассчитывает XP, необходимое для перехода на следующий уровень"""
    # Формула: XP_needed(level) = 100 + floor(1.15^(level-1) * 50)
    return int(100 + (1.15 ** (level - 1)) * 50)

def add_xp(user_id, xp_amount, reason):
    """Начисляет XP пользователю и проверяет переход на новый уровень"""
    db = get_db()
    cursor = db.cursor()
    
    # Получаем текущие данные пользователя
    cursor.execute("""
        SELECT xp, level 
        FROM users 
        WHERE id = %s
    """, (user_id,))
    user = cursor.fetchone()
    
    if not user:
        return
    
    current_xp = user[0]
    current_level = user[1]
    new_xp = current_xp + xp_amount
    
    # Проверяем переход на новый уровень
    next_level_xp = calculate_xp_for_level(current_level + 1)
    new_level = current_level
    
    while new_xp >= next_level_xp:
        new_level += 1
        new_xp -= next_level_xp
        next_level_xp = calculate_xp_for_level(new_level + 1)
    
    # Обновляем данные
    cursor.execute("""
        UPDATE users 
        SET xp = %s, level = %s, updated_at = NOW()
        WHERE id = %s
    """, (new_xp, new_level, user_id))
    
    # Логируем изменение
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, reason, created_at)
        VALUES (%s, %s, 'xp', %s, NOW())
    """, (user_id, xp_amount, reason))
    
    db.commit()
    
    # Проверяем ачивки
    if new_level > current_level:
        check_achievement(user_id, 'level_up', new_level)
    
    return new_level > current_level  # True, если уровень повышен

def check_achievement(user_id, achievement_key, value=None):
    """Проверяет выполнение условий для ачивки"""
    # Загружаем данные об ачивках из файла
    with open('achievements.json', 'r', encoding='utf-8') as f:
        achievements = json.load(f)
    
    if achievement_key not in achievements:
        return
    
    achievement = achievements[achievement_key]
    db = get_db()
    cursor = db.cursor()
    
    # Получаем текущий прогресс пользователя по этой ачивке
    cursor.execute("""
        SELECT tier 
        FROM achievements_unlocked 
        WHERE user_id = %s AND achievement_key = %s
    """, (user_id, achievement_key))
    current_tier = cursor.fetchone()
    
    current_tier = current_tier[0] if current_tier else 0
    
    # Определяем, какой уровень достигнут
    new_tier = 0
    if value is None:
        # Для ачивок без значения (например, регистрация)
        new_tier = 1
    else:
        if value >= achievement['gold_threshold']:
            new_tier = 3
        elif value >= achievement['silver_threshold']:
            new_tier = 2
        elif value >= achievement['bronze_threshold']:
            new_tier = 1
    
    # Если новый уровень выше текущего - разблокируем
    if new_tier > current_tier:
        # Сохраняем новую ачивку
        cursor.execute("""
            INSERT INTO achievements_unlocked (user_id, achievement_key, tier, unlocked_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id, achievement_key) 
            DO UPDATE SET tier = EXCLUDED.tier, unlocked_at = EXCLUDED.unlocked_at
        """, (user_id, achievement_key, new_tier))
        
        # Начисляем XP в зависимости от уровня ачивки
        xp_reward = 0
        if new_tier == 1:
            xp_reward = XP_ACHIEVEMENT_BRONZE
        elif new_tier == 2:
            xp_reward = XP_ACHIEVEMENT_SILVER
        elif new_tier == 3:
            xp_reward = XP_ACHIEVEMENT_GOLD
        
        if xp_reward > 0:
            add_xp(user_id, xp_reward, f"Ачивка: {achievement['title']}")
        
        db.commit()
        
        # Проверяем общее количество ачивок для ачивки "Коллекционер"
        if achievement_key != 'achievement_collector':
            cursor.execute("""
                SELECT COUNT(*) 
                FROM achievements_unlocked 
                WHERE user_id = %s
            """, (user_id,))
            total_achievements = cursor.fetchone()[0]
            check_achievement(user_id, 'achievement_collector', total_achievements)

@app.route('/api/daily-checkin', methods=['POST'])
def daily_checkin():
    """Ежедневный чек-ин пользователя"""
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Получаем данные пользователя
    cursor.execute("""
        SELECT daily_checkin_streak, last_checkin_date 
        FROM users 
        WHERE id = %s
    """, (user_id,))
    user = cursor.fetchone()
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    current_streak, last_checkin = user
    
    # Проверяем, прошел ли день с последнего чек-ина
    today = datetime.now(timezone.utc).date()
    if last_checkin and last_checkin >= today:
        return jsonify({"error": "Already checked in today"}), 400
    
    # Обновляем стрик
    new_streak = 1
    if last_checkin and (today - last_checkin).days == 1:
        new_streak = current_streak + 1
    
    # Начисляем кредиты
    credits_reward = DAILY_CHECKIN_CREDITS
    if new_streak == 7:
        credits_reward += DAILY_STREAK_BONUS
    
    # Обновляем пользователя
    cursor.execute("""
        UPDATE users 
        SET daily_checkin_streak = %s, 
            last_checkin_date = %s,
            credits = credits + %s,
            updated_at = NOW()
        WHERE id = %s
    """, (new_streak, today, credits_reward, user_id))
    
    # Начисляем XP
    add_xp(user_id, XP_DAILY_CHECKIN, "Ежедневный чек-ин")
    
    # Проверяем ачивку для чек-инов
    check_achievement(user_id, 'daily_streaks', new_streak)
    
    db.commit()
    
    return jsonify({
        "success": True,
        "streak": new_streak,
        "credits_reward": credits_reward,
        "xp_reward": XP_DAILY_CHECKIN
    })

@app.route('/api/admin/update-sheets', methods=['POST'])
@owner_required
def admin_update_sheets():
    """Обновляет кеш из Google Sheets (админ-действие)"""
    update_matches_cache()
    return jsonify({"success": True, "message": "Данные обновлены из Google Sheets"})

@app.route('/api/admin/pay-rewards', methods=['POST'])
@owner_required
def admin_pay_rewards():
    """Выплачивает награды за лидерборд (админ-действие)"""
    pay_weekly_rewards()
    return jsonify({"success": True, "message": "Награды выплачены"})

def pay_weekly_rewards():
    """Выплачивает награды за лидерборд и сохраняет историю"""
    service = get_sheets_service()
    spreadsheet_id = os.environ['GS_SHEET_ID']
    db = get_db()
    cursor = db.cursor()
    
    # Получаем топ-10 из Google Sheets
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="Ставки!A2:E"
    ).execute()
    
    rows = result.get('values', [])
    leaderboard = []
    
    for row in rows:
        if len(row) >= 5:
            try:
                user_id = row[0]
                total_bets = int(row[1])
                wins = int(row[2])
                win_percent = float(row[4]) if row[4] else 0
                
                if total_bets >= 5:  # Минимум 5 ставок для участия
                    leaderboard.append({
                        'user_id': user_id,
                        'wins': wins,
                        'total_bets': total_bets,
                        'win_percent': win_percent
                    })
            except (ValueError, IndexError):
                continue
    
    # Сортируем: win_percent (desc), total_bets (desc)
    leaderboard.sort(key=lambda x: (-x['win_percent'], -x['total_bets']))
    
    # Берем топ-3
    top_users = leaderboard[:3]
    
    # Выплачиваем награды
    for i, user in enumerate(top_users):
        reward = WEEKLY_REWARDS[i]
        
        # Начисляем кредиты
        cursor.execute("""
            UPDATE users 
            SET credits = credits + %s 
            WHERE id = %s
        """, (reward, user['user_id']))
        
        # Логируем в историю
        cursor.execute("""
            INSERT INTO leaderboard_history 
            (week_start_iso, user_id, username, wins, total_bets, win_percent, rank, reward_given)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            user['user_id'],
            f"user_{user['user_id']}",
            user['wins'],
            user['total_bets'],
            user['win_percent'],
            i + 1,
            True
        ))
        
        # Начисляем XP
        add_xp(user['user_id'], 50, f"Лидерборд недели: место {i+1}")
    
    db.commit()
    
    # Сбрасываем статистику ставок в Google Sheets
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range="Ставки!B2:E"
    ).execute()

# Еженедельный сброс (запускается по расписанию)
def scheduled_weekly_reset():
    """Задача для еженедельного сброса лидерборда"""
    logger.info("Запуск еженедельного сброса лидерборда")
    pay_weekly_rewards()

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=scheduled_weekly_reset,
    trigger='cron',
    day_of_week='mon',
    hour=4,
    timezone='Europe/Zagreb'
)
scheduler.start()

# Обработка ошибок
@app.errorhandler(500)
def server_error(e):
    logger.exception("Внутренняя ошибка сервера")
    return jsonify({"error": "Внутренняя ошибка сервера"}), 500

if __name__ == '__main__':
    # Для локальной разработки
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)