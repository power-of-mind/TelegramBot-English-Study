from connection_db import get_db_connection

def initialize_db():
    """Создаёт таблицы в базе данных."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Создание таблицы пользователей
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Создание общего словаря
            cur.execute("""
            CREATE TABLE IF NOT EXISTS words (
            id SERIAL PRIMARY KEY,
            target_word VARCHAR(255) UNIQUE NOT NULL,
            translate_word VARCHAR(255) NOT NULL
            )
            """)

            # Создание персонального словаря
            cur.execute("""
            CREATE TABLE IF NOT EXISTS user_words (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users (user_id),
            target_word VARCHAR(255) NOT NULL,
            translate_word VARCHAR(255) NOT NULL,
            UNIQUE (user_id, target_word)
            )
            """)
            
            conn.commit()

def ensure_user_exists(user_id, username):
    """Проверяет, существует-ли пользователь в базе данных и создает его, если это необходимо."""
    query = (
        "INSERT INTO users (user_id, username) "
        "VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE "
        "SET username = EXCLUDED.username"
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, username))
            conn.commit()

def fill_common_words_table(common_words):
    """Заполняет общий словарь."""
    query = (
        "INSERT INTO words (target_word, translate_word) "
        "VALUES (%s, %s) "
        "ON CONFLICT (target_word) DO NOTHING"
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, common_words)
            conn.commit()
            
def check_word_existence(word):
    """Проверяет, существует-ли слово в общем словаре."""
    query = "SELECT 1 FROM words WHERE target_word = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (word,))
            return cur.fetchone() is not None

def get_random_words(cid, limit=4):
    """Получает случайные слова из общего и персонального словарей."""
    query = (
        "SELECT target_word, translate_word "
        "FROM ("
        "SELECT target_word, translate_word FROM words "
        "UNION "
        "SELECT target_word, translate_word FROM user_words WHERE user_id = %s"
        ") AS combined_words "
        "ORDER BY RANDOM() "
        "LIMIT %s;"
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cid, limit))
            return cur.fetchall()

def add_word_to_user(user_id, target_word, translate_word):
    """Добавляет слово в персональный словарь."""
    query = (
        "INSERT INTO user_words (user_id, target_word, translate_word) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (user_id, target_word) DO NOTHING"
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                user_id,
                target_word.strip().capitalize(),
                translate_word.strip().capitalize()
            ))
            conn.commit()

def delete_user_word(user_id, word_to_delete):
    """Удаляет слово из персонального словаря."""
    query = (
        "DELETE FROM user_words "
        "WHERE user_id = %s AND target_word = %s "
        "RETURNING target_word"
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, word_to_delete))
            result = cur.fetchone()
            conn.commit()
            return result

def update_word_to_user_dict(user_id, target_word, translate_word):
    """Обновляет персональный словарь."""
    query = (
        "INSERT INTO user_words (user_id, target_word, translate_word) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (user_id, target_word) DO UPDATE "
        "SET translate_word = EXCLUDED.translate_word"
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, target_word, translate_word))
            conn.commit()
