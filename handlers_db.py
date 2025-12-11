from connection_db import get_db_connection

def initialize_db():
    """Создаёт таблицы в базе данных."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Создаем таблицу пользователей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                user_name VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Создаем словарь
            cur.execute("""
                CREATE TABLE IF NOT EXISTS words (
                id SERIAL PRIMARY KEY,
                target_word VARCHAR(255) NOT NULL,
                translate_word VARCHAR(255) NOT NULL,
                CONSTRAINT unique_target_word UNIQUE (target_word)
                );
            """)

            # Создаем таблицу связей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_words (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users (id),
                word_id BIGINT NOT NULL REFERENCES words (id),
                CONSTRAINT unique_user_word UNIQUE (user_id, word_id)
                );
            """)

            conn.commit()

def fill_common_words_table():
    """Заполняет словарь."""
    common_words = [
        ("Peace", "Мир"), ("Green", "Зелёный"), ("White", "Белый"),
        ("Hello", "Привет"), ("Car", "Машина"), ("Sky", "Небо"),
        ("Tree", "Дерево"), ("Book", "Книга"), ("Love", "Любовь"),
        ("Friend", "Друг")
    ]

    query = """
        INSERT INTO words (target_word, translate_word)
        VALUES (%s, %s)
        ON CONFLICT (target_word)
        DO UPDATE SET translate_word = EXCLUDED.translate_word;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, common_words)
            conn.commit()

def ensure_user_exists(cid, username):
    """Проверяет, существует ли пользователь, если нет - создает его и
    связывает со всеми словами."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Проверяем, есть ли пользователь
            cur.execute("SELECT id FROM users WHERE user_id = %s", (cid,))
            result = cur.fetchone()
            if result:
                user_id = result[0]
            else:
                # Создаем нового пользователя
                cur.execute(
                    "INSERT INTO users (user_id, user_name) VALUES (%s, %s) RETURNING id",
                    (cid, username)
                )
                user_id = cur.fetchone()[0]

            # Получаем все id слов из таблицы words
            cur.execute("SELECT id FROM words")
            all_word_ids = cur.fetchall()

            # Связываем пользователя со всеми словами
            for (word_id,) in all_word_ids:
                cur.execute("""
                    INSERT INTO user_words (user_id, word_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (user_id, word_id))

            conn.commit()

def get_random_words(cid, limit=4):
    """Получает случайные слова из словаря."""
    query = """
        SELECT target_word, translate_word
        FROM words
        JOIN user_words ON words.id = user_words.word_id
        JOIN users ON users.id = user_words.user_id
        WHERE users.user_id = %s
        ORDER BY RANDOM()
        LIMIT %s;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cid, limit))
            return cur.fetchall()

def get_word_id(target_word):
    """Проверяет, есть - ли слово в словаре"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM words
                WHERE LOWER(target_word) = LOWER(%s)
            """, (target_word.strip(),))
            result = cur.fetchone()
            if result:
                return result[0]
            else:
                return None

def check_user_word_relation(cid, target_word):
    """Проверяет, есть - ли связь между словом и пользователем"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Получаем id пользователя по cid
            cur.execute("SELECT id FROM users WHERE user_id = %s", (cid,))
            user_result = cur.fetchone()
            if not user_result:
                return None
            user_id = user_result[0]

            # Получаем id слова по target_word (учитывая регистр и пробелы)
            cur.execute("""
                SELECT id FROM words
                WHERE LOWER(target_word) = LOWER(%s)
            """, (target_word.strip(),))
            word_result = cur.fetchone()
            if not word_result:
                return None
            word_id = word_result[0]

            # Проверяем наличие связи в user_words
            cur.execute("""
                SELECT id FROM user_words
                WHERE user_id = %s AND word_id = %s
            """, (user_id, word_id)
            )
            relation = cur.fetchone()
            if relation:
                return relation[0]
            else:
                return None

def add_user_word_relation(cid, target_word):
    """Создает связь пользователя и слова"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Получаем id пользователя по cid
            cur.execute("""
                SELECT id FROM users
                WHERE user_id = %s""", (cid,))
            user_result = cur.fetchone()
            if not user_result:
                raise ValueError("Пользователь не найден")
            user_id = user_result[0]

            # Получаем id слова по target_word
            cur.execute("""
                SELECT id FROM words
                WHERE LOWER(target_word) = LOWER(%s)
            """, (target_word.strip(),))
            word_result = cur.fetchone()
            if not word_result:
                raise ValueError("Слово не найдено")
            word_id = word_result[0]

            # Создаем связь в user_words
            cur.execute("""
                INSERT INTO user_words (user_id, word_id)
                VALUES (%s, %s) RETURNING id
            """, (user_id, word_id)
            )
            relation_id = cur.fetchone()[0]
            conn.commit()
            return relation_id

def add_word(target_word, translate_word):
    """Добавляет слово в словарь"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Обрабатываем входные данные
            target_word_clean = target_word.strip().capitalize()
            translate_word_clean = translate_word.strip().capitalize()

            # Вставляем слова в таблицу words
            cur.execute("""
                INSERT INTO words (target_word, translate_word)
                VALUES (%s, %s)
                ON CONFLICT (target_word) DO NOTHING
                RETURNING id
            """, (target_word_clean, translate_word_clean)
            )
            result = cur.fetchone()
            if result:
                word_id = result[0]
            else:
                # Если слово уже есть, получаем его id
                cur.execute("""
                    SELECT id FROM words
                    WHERE target_word = %s
                """, (target_word_clean,)
                )
                word_id = cur.fetchone()[0]
            conn.commit()
            return word_id

def delete_user_word_relation(cid, word_to_delete):
    """Удаляет связь пользователя со словом"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Получаем id пользователя по cid
            cur.execute("SELECT id FROM users WHERE user_id = %s", (cid,))
            user_result = cur.fetchone()
            if not user_result:
                return None
            user_id = user_result[0]

            # Получаем id слова по target_word (учитывая регистр и пробелы)
            cur.execute("""
                SELECT id FROM words
                WHERE LOWER(target_word) = LOWER(%s)
            """, (word_to_delete.strip(),)
            )
            word_result = cur.fetchone()
            if not word_result:
                return None
            word_id = word_result[0]

            # Удаляем связь и возвращаем id удаленной записи
            cur.execute("""
                DELETE FROM user_words
                WHERE user_id = %s AND word_id = %s
                RETURNING id
            """, (user_id, word_id)
            )

            deleted = cur.fetchone()
            conn.commit()

            if deleted:
                return deleted[0]
            else:
                return None