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
    """Создает и проверяет соединение с Google Sheets API"""
    try:
        logger.info("🔍 Инициализация Google Sheets API...")
        
        # Проверяем наличие необходимых переменных окружения
        if not os.environ.get('GS_CREDS_JSON'):
            logger.error("❌ Переменная окружения GS_CREDS_JSON не установлена")
            return None
        
        if not os.environ.get('GS_SHEET_ID'):
            logger.error("❌ Переменная окружения GS_SHEET_ID не установлена")
            return None
        
        # Парсим JSON-ключи
        try:
            creds_info = json.loads(os.environ['GS_CREDS_JSON'])
            logger.info("✅ JSON-ключи для Google API успешно распаршены")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга GS_CREDS_JSON: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка при парсинге GS_CREDS_JSON: {str(e)}")
            return None
        
        # Создаем учетные данные
        try:
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            logger.info("✅ Учетные данные для Google API успешно созданы")
        except Exception as e:
            logger.error(f"❌ Ошибка создания учетных данных: {str(e)}")
            return None
        
        # Создаем сервис
        try:
            service = build('sheets', 'v4', credentials=creds)
            logger.info("✅ Сервис Google Sheets API успешно создан")
            
            # Проверяем доступ к таблице
            spreadsheet_id = os.environ['GS_SHEET_ID']
            try:
                sheet_metadata = service.spreadsheets().get(
                    spreadsheetId=spreadsheet_id
                ).execute()
                
                logger.info(f"✅ Доступ к Google Таблице подтвержден (ID: {spreadsheet_id})")
                logger.info(f"   Название таблицы: {sheet_metadata.get('properties', {}).get('title', 'Неизвестно')}")
                
                # Логируем существующие листы
                sheets = [sheet['properties']['title'] for sheet in sheet_metadata.get('sheets', [])]
                logger.info(f"   Существующие листы: {', '.join(sheets) if sheets else 'отсутствуют'}")
                
                return service
            except Exception as e:
                logger.error(f"❌ Ошибка доступа к Google Таблице: {str(e)}")
                logger.error("   Возможные причины:")
                logger.error("   1. Неправильный GS_SHEET_ID")
                logger.error("   2. Сервисный аккаунт не имеет прав доступа")
                logger.error("   3. Таблица не существует или удалена")
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка создания сервиса Google Sheets: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации Google Sheets API: {str(e)}")
        return None

def ensure_sheets_structure():
    """Создает листы в Google Sheets, если их нет"""
    logger.info("🔍 Проверка структуры Google Sheets...")
    
    service = get_sheets_service()
    if not service:
        logger.error("❌ Не удалось подключиться к Google Sheets API")
        return False
    
    spreadsheet_id = os.environ['GS_SHEET_ID']
    
    # Список необходимых листов
    required_sheets = [
        "Таблица", "Статистика Голы", "Статистика ассистенты", 
        "Статистика Г+П", "Расписание игр", "Составы", 
        "Детали Матча", "Ставки", "leaderboard_history", "referrals"
    ]
    
    try:
        # Получаем текущие листы
        sheet_metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()
        existing_sheets = [sheet['properties']['title'] for sheet in sheet_metadata.get('sheets', [])]
        
        logger.info(f"   Найдено существующих листов: {len(existing_sheets)}")
        
        # Создаем отсутствующие листы
        created_sheets = []
        for sheet_name in required_sheets:
            if sheet_name not in existing_sheets:
                logger.info(f"   🆕 Создаем лист: {sheet_name}")
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
                created_sheets.append(sheet_name)
                
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
        
        if created_sheets:
            logger.info(f"✅ Успешно создано {len(created_sheets)} новых листов: {', '.join(created_sheets)}")
        else:
            logger.info("✅ Все необходимые листы уже существуют")
            
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при работе с Google Sheets: {str(e)}")
        logger.error("   Подробности ошибки:")
        logger.error(f"   - Spreadsheet ID: {spreadsheet_id}")
        logger.error(f"   - Тип ошибки: {type(e).__name__}")
        logger.error(f"   - Сообщение: {str(e)}")
        return False

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

# Флаг для отслеживания состояния инициализации
_initialized = False

def init_database():
    """Полная инициализация базы данных с проверкой всех таблиц и колонок"""
    logger.info("🔍 Начинаем проверку структуры базы данных...")
    
    try:
        # Сначала очищаем возможные ошибки транзакции
        db = get_db()
        cursor = db.cursor()
        cursor.execute("ROLLBACK")  # Сбрасываем текущую транзакцию, если она в состоянии ошибки
        db.commit()
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при сбросе транзакции: {str(e)}")
        
        # Проверяем существование всех необходимых таблиц
        required_tables = [
            'users', 'achievements_unlocked', 'matches_cache', 
            'leaderboard_cache', 'transactions', 'leaderboard_history',
            'admin_actions_log'
        ]
        
        existing_tables = []
        for table in required_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = %s
                )
            """, (table,))
            if cursor.fetchone()[0]:
                existing_tables.append(table)
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            logger.info(f"⚠️ Отсутствуют таблицы: {', '.join(missing_tables)}")
            
            # Попробуем создать недостающие таблицы через schema.sql
            try:
                with open('sql/schema.sql', 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                
                # Выполняем скрипт построчно, чтобы обработать возможные ошибки
                for statement in sql_script.split(';'):
                    statement = statement.strip()
                    if statement:
                        try:
                            cursor.execute(statement)
                        except Exception as e:
                            logger.warning(f"Предупреждение при выполнении SQL: {str(e)}")
                
                db.commit()
                logger.info("✅ Все таблицы успешно созданы из schema.sql")
                
                # Перепроверяем
                existing_tables = []
                for table in required_tables:
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = %s
                        )
                    """, (table,))
                    if cursor.fetchone()[0]:
                        existing_tables.append(table)
                
                still_missing = [table for table in required_tables if table not in existing_tables]
                if still_missing:
                    logger.warning(f"⚠️ Всё ещё отсутствуют таблицы: {', '.join(still_missing)}")
            except Exception as e:
                logger.error(f"❌ Ошибка при выполнении schema.sql: {str(e)}")
                # Создаем минимально необходимые таблицы вручную
                create_minimal_tables(cursor, db)
        else:
            logger.info("✅ Все таблицы существуют")
            
            # Проверяем структуру таблицы users
            check_users_table_structure(cursor, db)
            
            # Проверяем структуру таблицы matches_cache
            check_matches_cache_table(cursor, db)
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации базы данных: {str(e)}")
        # Создаем минимально необходимые таблицы
        try:
            db = get_db()
            cursor = db.cursor()
            create_minimal_tables(cursor, db)
        except Exception as e2:
            logger.error(f"❌ Не удалось создать минимальные таблицы: {str(e2)}")

def create_minimal_tables(cursor, db):
    """Создает минимально необходимые таблицы для запуска приложения"""
    logger.info("🔧 Создаем минимально необходимые таблицы...")
    
    # Таблица users
    cursor.execute("""
        DROP TABLE IF EXISTS users CASCADE;
        CREATE TABLE users (
            id BIGINT PRIMARY KEY,
            username TEXT,
            display_name TEXT,
            credits INTEGER NOT NULL DEFAULT 0,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            daily_checkin_streak INTEGER NOT NULL DEFAULT 0,
            last_checkin_date DATE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            banned_until TIMESTAMP,
            referrer_id BIGINT
        )
    """)
    
    # Таблица matches_cache
    cursor.execute("""
        DROP TABLE IF EXISTS matches_cache CASCADE;
        CREATE TABLE matches_cache (
            match_id TEXT PRIMARY KEY,
            data_json JSONB NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    
    # Таблица achievements_unlocked
    cursor.execute("""
        DROP TABLE IF EXISTS achievements_unlocked CASCADE;
        CREATE TABLE achievements_unlocked (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            achievement_key TEXT NOT NULL,
            tier SMALLINT NOT NULL,
            unlocked_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    
    db.commit()
    logger.info("✅ Минимальные таблицы успешно созданы")

def check_users_table_structure(cursor, db):
    """Проверяет и исправляет структуру таблицы users с правильной обработкой типов данных"""
    logger.info("🔍 Проверяем структуру таблицы users...")
    
    # Получаем текущие колонки
    cursor.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'users'
    """)
    columns_info = {row[0]: {'type': row[1], 'nullable': row[2]} for row in cursor.fetchall()}
    
    # Определяем необходимые колонки
    required_columns = {
        'id': {'type': 'bigint', 'nullable': 'NO', 'default': None},
        'username': {'type': 'text', 'nullable': 'YES', 'default': None},
        'display_name': {'type': 'text', 'nullable': 'YES', 'default': None},
        'credits': {'type': 'integer', 'nullable': 'NO', 'default': '0'},
        'xp': {'type': 'integer', 'nullable': 'NO', 'default': '0'},
        'level': {'type': 'integer', 'nullable': 'NO', 'default': '1'},
        'daily_checkin_streak': {'type': 'integer', 'nullable': 'NO', 'default': '0'},
        'last_checkin_date': {'type': 'date', 'nullable': 'YES', 'default': None},
        'created_at': {'type': 'timestamp without time zone', 'nullable': 'NO', 'default': 'NOW()'},
        'updated_at': {'type': 'timestamp without time zone', 'nullable': 'NO', 'default': 'NOW()'},
        'banned_until': {'type': 'timestamp without time zone', 'nullable': 'YES', 'default': None},
        'referrer_id': {'type': 'bigint', 'nullable': 'YES', 'default': None}
    }
    
    # Проверяем и добавляем недостающие колонки
    for col_name, col_spec in required_columns.items():
        if col_name not in columns_info:
            logger.warning(f"⚠️ Отсутствует колонка {col_name} в таблице users")
            
            # Создаем колонку
            null_constraint = "NOT NULL" if col_spec['nullable'] == 'NO' else ""
            default_clause = f"DEFAULT {col_spec['default']}" if col_spec['default'] else ""
            
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_spec['type']} {null_constraint} {default_clause}")
            
            # Если колонка NOT NULL и не имеет DEFAULT, устанавливаем значение по умолчанию
            if col_spec['nullable'] == 'NO' and not col_spec['default']:
                default_val = '0' if 'int' in col_spec['type'] else 'NOW()' if 'timestamp' in col_spec['type'] else "''"
                cursor.execute(f"UPDATE users SET {col_name} = {default_val} WHERE {col_name} IS NULL")
            
            db.commit()
            logger.info(f"✅ Добавлена колонка {col_name} в таблицу users")
            columns_info[col_name] = {'type': col_spec['type'], 'nullable': col_spec['nullable']}
    
    # Проверяем типы существующих колонок
    for col_name, col_spec in required_columns.items():
        if col_name in columns_info:
            current_info = columns_info[col_name]
            
            # Проверяем тип данных
            current_type = current_info['type']
            required_type = col_spec['type']
            
            # Специальная обработка для timestamp
            if 'timestamp' in required_type and 'timestamp' in current_type:
                continue  # Типы совместимы
            
            # Проверяем NOT NULL
            if col_spec['nullable'] == 'NO' and current_info['nullable'] == 'YES':
                logger.warning(f"⚠️ Колонка {col_name} должна быть NOT NULL")
                try:
                    # Устанавливаем значения по умолчанию для существующих NULL
                    if col_spec['default']:
                        cursor.execute(f"UPDATE users SET {col_name} = {col_spec['default']} WHERE {col_name} IS NULL")
                    else:
                        default_val = '0' if 'int' in required_type else 'NOW()' if 'timestamp' in required_type else "''"
                        cursor.execute(f"UPDATE users SET {col_name} = {default_val} WHERE {col_name} IS NULL")
                    
                    # Делаем колонку NOT NULL
                    cursor.execute(f"ALTER TABLE users ALTER COLUMN {col_name} SET NOT NULL")
                    db.commit()
                    logger.info(f"✅ Колонка {col_name} теперь NOT NULL")
                except Exception as e:
                    logger.error(f"❌ Не удалось сделать колонку {col_name} NOT NULL: {str(e)}")
            
            # Проверяем тип данных
            type_mapping = {
                'integer': 'int',
                'bigint': 'int',
                'text': 'str',
                'date': 'date',
                'timestamp': 'datetime'
            }
            
            current_simple = next((k for k in type_mapping if k in current_type), current_type)
            required_simple = next((k for k in type_mapping if k in required_type), required_type)
            
            if current_simple != required_simple:
                logger.warning(f"⚠️ Некорректный тип колонки {col_name}: ожидается {required_type}, текущий {current_type}")
                
                try:
                    # Специальная обработка для timestamp
                    if 'timestamp' in required_type and 'timestamp' not in current_type:
                        cursor.execute(f"ALTER TABLE users ALTER COLUMN {col_name} TYPE TIMESTAMP USING {col_name}::timestamp")
                        db.commit()
                        logger.info(f"✅ Тип колонки {col_name} исправлен на TIMESTAMP")
                        continue
                    
                    # Специальная обработка для integer
                    if 'int' in required_type and 'int' not in current_type:
                        cursor.execute(f"ALTER TABLE users ALTER COLUMN {col_name} TYPE INTEGER USING {col_name}::integer")
                        db.commit()
                        logger.info(f"✅ Тип колонки {col_name} исправлен на INTEGER")
                        continue
                    
                    # Для других типов
                    cursor.execute(f"ALTER TABLE users ALTER COLUMN {col_name} TYPE {required_type}")
                    db.commit()
                    logger.info(f"✅ Тип колонки {col_name} исправлен на {required_type}")
                except Exception as e:
                    logger.error(f"❌ Не удалось исправить тип колонки {col_name}: {str(e)}")

def check_matches_cache_table(cursor, db):
    """Проверяет и исправляет структуру таблицы matches_cache"""
    logger.info("🔍 Проверяем структуру таблицы matches_cache...")
    
    # Проверяем существование таблицы
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'matches_cache'
        )
    """)
    table_exists = cursor.fetchone()[0]
    
    if not table_exists:
        logger.warning("⚠️ Таблица matches_cache не существует")
        cursor.execute("""
            CREATE TABLE matches_cache (
                match_id TEXT PRIMARY KEY,
                data_json JSONB NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        db.commit()
        logger.info("✅ Таблица matches_cache создана")
        return
    
    # Проверяем колонки
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'matches_cache'
    """)
    columns = [row[0] for row in cursor.fetchall()]
    
    required_columns = {
        'match_id': 'TEXT PRIMARY KEY',
        'data_json': 'JSONB NOT NULL',
        'updated_at': 'TIMESTAMP NOT NULL DEFAULT NOW()'
    }
    
    for col_name, col_def in required_columns.items():
        if col_name not in columns:
            logger.warning(f"⚠️ Отсутствует колонка {col_name} в таблице matches_cache")
            
            if 'NOT NULL' in col_def:
                default_val = 'NOW()' if 'TIMESTAMP' in col_def else "'{}'"
                cursor.execute(f"ALTER TABLE matches_cache ADD COLUMN {col_name} {col_def.split('NOT NULL')[0]}")
                cursor.execute(f"UPDATE matches_cache SET {col_name} = {default_val} WHERE {col_name} IS NULL")
                cursor.execute(f"ALTER TABLE matches_cache ALTER COLUMN {col_name} SET NOT NULL")
            else:
                cursor.execute(f"ALTER TABLE matches_cache ADD COLUMN {col_name} {col_def}")
            
            db.commit()
            logger.info(f"✅ Добавлена колонка {col_name} в таблицу matches_cache")

@app.before_request
def check_initialization():
    """Проверяет и запускает инициализацию при первом запросе"""
    global _initialized
    if not _initialized:
        logger.info("🚀 Запуск инициализации приложения...")
        try:
            init_database()  # Сначала инициализируем базу данных
            initialize()     # Затем инициализируем Google Sheets
            _initialized = True
            logger.info("✅ Инициализация приложения завершена успешно")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при инициализации: {str(e)}")
            # Важно: не устанавливаем _initialized = True при ошибке,
            # чтобы попытаться инициализироваться при следующем запросе

def initialize():
    """Функция инициализации структуры Google Sheets"""
    logger.info("🚀 Начало инициализации Google Sheets...")
    
    # Проверяем доступ к Google Sheets API
    service = get_sheets_service()
    if not service:
        logger.error("❌ Критическая ошибка: не удалось подключиться к Google Sheets API")
        logger.warning("   Приложение будет работать без интеграции с Google Sheets")
        return False
    
    # Проверяем структуру
    try:
        logger.info("🔍 Проверка структуры Google Sheets...")
        if ensure_sheets_structure():
            logger.info("✅ Структура Google Sheets проверена и инициализирована")
            return True
        else:
            logger.warning("⚠️ Не удалось полностью инициализировать структуру Google Sheets")
            return False
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации Google Sheets: {str(e)}")
        
        # Показываем более подробную информацию об ошибке
        logger.error("   Детали ошибки:")
        logger.error(f"   - Тип ошибки: {type(e).__name__}")
        logger.error(f"   - Сообщение: {str(e)}")
        
        # Проверяем, есть ли у сервисного аккаунта доступ
        spreadsheet_id = os.environ.get('GS_SHEET_ID', 'не указан')
        logger.error(f"   - Spreadsheet ID: {spreadsheet_id}")
        logger.error("   - Возможные причины:")
        logger.error("     1. Неправильный Spreadsheet ID")
        logger.error("     2. Сервисный аккаунт не добавлен как редактор таблицы")
        logger.error("     3. Таблица не существует или удалена")
        logger.error("     4. Недостаточно прав у сервисного аккаунта")
        
        return False

# API для фронтенда
@app.route('/')
def index():
    owner_telegram_id = os.environ.get('OWNER_TELEGRAM_ID', '')
    return render_template('index.html', owner_telegram_id=owner_telegram_id)

@app.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    logger.info(f"🔍 Запрос профиля для пользователя {user_id}")
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Принудительно проверяем структуру таблицы users
        check_users_table_structure(cursor, db)
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке структуры таблицы users: {str(e)}")
    
    # Получаем профиль пользователя
    try:
        cursor.execute("""
            SELECT id, username, display_name, credits, xp, level, 
                   daily_checkin_streak, last_checkin_date, created_at, updated_at
            FROM users 
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе к таблице users: {str(e)}")
        # Пытаемся восстановить таблицу
        try:
            create_minimal_tables(cursor, db)
            user = None
        except Exception as e2:
            logger.error(f"❌ Не удалось восстановить таблицу users: {str(e2)}")
            return jsonify({"error": "Database error"}), 500
    
    if not user:
        logger.info(f"🆕 Регистрация нового пользователя {user_id}")
        # Регистрация нового пользователя
        try:
            # Убедимся, что все колонки существуют
            cursor.execute("""
                INSERT INTO users (id, credits, xp, level, 
                                  daily_checkin_streak, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id, username, display_name, credits, xp, level, 
                          daily_checkin_streak, last_checkin_date, created_at, updated_at
            """, (user_id, FIRST_LOGIN_CREDITS, XP_REGISTRATION, 1, 0))
            user = cursor.fetchone()
            db.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка при создании пользователя: {str(e)}")
            
            # Попробуем упрощенный запрос без некоторых колонок
            try:
                cursor.execute("""
                    INSERT INTO users (id, credits, xp, level, daily_checkin_streak)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, username, display_name, credits, xp, level, 
                              daily_checkin_streak, last_checkin_date, created_at, updated_at
                """, (user_id, FIRST_LOGIN_CREDITS, XP_REGISTRATION, 1, 0))
                user = cursor.fetchone()
                db.commit()
            except Exception as e2:
                logger.error(f"❌ Критическая ошибка при создании пользователя: {str(e2)}")
                return jsonify({"error": "Database error"}), 500
    
    # Получаем открытые ачивки
    achievements = []
    try:
        # Проверяем существование таблицы achievements_unlocked
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'achievements_unlocked'
            )
        """)
        if cursor.fetchone()[0]:
            cursor.execute("""
                SELECT achievement_key, tier, unlocked_at 
                FROM achievements_unlocked 
                WHERE user_id = %s
            """, (user_id,))
            achievements = cursor.fetchall()
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе ачивок: {str(e)}")
    
    # Формируем ответ
    profile = {
        'id': user[0],
        'username': user[1] or f"user_{user[0]}",
        'display_name': user[2] or f"Игрок {user[0]}",
        'credits': user[3] if user[3] is not None else FIRST_LOGIN_CREDITS,
        'xp': user[4] if user[4] is not None else XP_REGISTRATION,
        'level': user[5] if user[5] is not None else 1,
        'daily_streak': user[6] if user[6] is not None else 0,
        'next_level_xp': calculate_xp_for_level(user[5] + 1) if user[5] is not None else calculate_xp_for_level(2),
        'achievements': [{
            'key': a[0],
            'tier': a[1],
            'unlocked_at': a[2].isoformat() if a[2] else None
        } for a in achievements]
    }
    
    logger.info(f"✅ Профиль пользователя {user_id} успешно загружен")
    return jsonify(profile)

@app.route('/api/matches', methods=['GET'])
def get_matches():
    """Возвращает матчи из кеша или обновляет из Google Sheets"""
    logger.info("🔍 Запрос матчей")
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Принудительно проверяем структуру таблицы matches_cache
        check_matches_cache_table(cursor, db)
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке структуры таблицы matches_cache: {str(e)}")
    
    # Проверяем актуальность кеша
    try:
        cursor.execute("""
            SELECT data_json, updated_at 
            FROM matches_cache 
            WHERE match_id = 'schedule'
        """)
        cache = cursor.fetchone()
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе кеша матчей: {str(e)}")
        cache = None
    
    # ИСПРАВЛЕНИЕ: Работаем с timezone-aware датами
    now = datetime.now(timezone.utc)
    
    # Если кеш старый или отсутствует - обновляем
    if not cache or (now - cache[1].replace(tzinfo=timezone.utc)).total_seconds() > 900:  # 15 минут
        logger.info("🔄 Кеш матчей устарел или отсутствует, обновляем...")
        update_matches_cache()
        
        try:
            cursor.execute("""
                SELECT data_json, updated_at 
                FROM matches_cache 
                WHERE match_id = 'schedule'
            """)
            cache = cursor.fetchone()
        except Exception as e:
            logger.error(f"❌ Ошибка при повторном запросе кеша: {str(e)}")
            cache = None
    
    if cache:
        logger.info(f"✅ Кеш матчей успешно загружен (обновлено: {cache[1].isoformat()})")
        return jsonify({
            'matches': cache[0],
            'last_updated': cache[1].isoformat()
        })
    else:
        logger.warning("⚠️ Кеш матчей пуст, возвращаем пустой список")
        return jsonify({
            'matches': [],
            'last_updated': None
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