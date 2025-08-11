-- sql/schema.sql
-- Схема базы данных для НЛО — Футбольная Лига

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,  -- Telegram ID
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
    referrer_id BIGINT REFERENCES users(id)
);

-- Таблица достижений
CREATE TABLE IF NOT EXISTS achievements_unlocked (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    achievement_key TEXT NOT NULL,
    tier SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 3),  -- 1=bronze, 2=silver, 3=gold
    unlocked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, achievement_key)
);

-- Кэш матчей
CREATE TABLE IF NOT EXISTS matches_cache (
    match_id TEXT PRIMARY KEY,
    data_json JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Кэш лидерборда
CREATE TABLE IF NOT EXISTS leaderboard_cache (
    id SERIAL PRIMARY KEY,
    week_start_iso TEXT NOT NULL,
    data_json JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (week_start_iso)
);

-- Транзакции (изменения кредитов и XP)
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('credit', 'xp', 'bet', 'reward')),
    reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- История лидерборда
CREATE TABLE IF NOT EXISTS leaderboard_history (
    id SERIAL PRIMARY KEY,
    week_start_iso TEXT NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    wins INTEGER NOT NULL,
    total_bets INTEGER NOT NULL,
    win_percent NUMERIC(5,2) NOT NULL,
    rank INTEGER NOT NULL,
    reward_given BOOLEAN NOT NULL DEFAULT false
);

-- Лог админ-действий
CREATE TABLE IF NOT EXISTS admin_actions_log (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    details JSONB,
    ts TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_users_credits ON users(credits);
CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp);
CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements_unlocked(user_id);
CREATE INDEX IF NOT EXISTS idx_leaderboard_week ON leaderboard_cache(week_start_iso);
CREATE INDEX IF NOT EXISTS idx_leaderboard_history_week ON leaderboard_history(week_start_iso);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_time ON transactions(created_at);

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_users_modtime ON users;
CREATE TRIGGER update_users_modtime
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_matches_cache_modtime ON matches_cache;
CREATE TRIGGER update_matches_cache_modtime
    BEFORE UPDATE ON matches_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_leaderboard_cache_modtime ON leaderboard_cache;
CREATE TRIGGER update_leaderboard_cache_modtime
    BEFORE UPDATE ON leaderboard_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();