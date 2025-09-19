import os
import psycopg

def init_db():
    conn_str = os.environ['DATABASE_URL']
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as c:
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    url TEXT,
                    title TEXT,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    print("PostgreSQL database initialized successfully")

if __name__ == '__main__':
    init_db()