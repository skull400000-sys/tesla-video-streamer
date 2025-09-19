import os
import psycopg2

def init_db():
    conn_str = os.environ['DATABASE_URL']
    conn = psycopg2.connect(conn_str)
    c = conn.cursor()
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
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("PostgreSQL database initialized successfully")

if __name__ == '__main__':
    init_db()