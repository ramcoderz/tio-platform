import asyncio
import sqlite3
from backend.config.settings import get_settings

settings = get_settings()
db_path = settings.sqlite_url.replace("sqlite+aiosqlite:///", "")

def migrate():
    print(f"Applying migrations to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Add missing columns to uploaded_documents
    columns_to_add = [
        ("summary", "TEXT"),
        ("intel_report", "TEXT"),
        ("created_at", "DATETIME")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE uploaded_documents ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to uploaded_documents")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists")
                print(f"Error adding {col_name}: {e}")

    # 2. Add missing columns to messages
    messages_cols = [
        ("parent_id", "INTEGER"),
        ("created_at", "DATETIME")
    ]
    for col_name, col_type in messages_cols:
        try:
            cursor.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to messages")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists in messages")
            else:
                print(f"Error adding {col_name} to messages: {e}")

    # 3. Add missing columns to users
    users_cols = [
        ("username", "VARCHAR(64)")
    ]
    for col_name, col_type in users_cols:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to users")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists in users")
            else:
                print(f"Error adding {col_name} to users: {e}")
                
    # 4. Ensure relationships table exists
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY,
                source_id INTEGER REFERENCES uploaded_documents(id),
                target_id INTEGER REFERENCES uploaded_documents(id),
                type VARCHAR(64),
                description TEXT,
                weight FLOAT
            )
        """)
        print("Ensured relationships table exists")
    except Exception as e:
        print(f"Error creating relationships table: {e}")

    # 5. Create system_configs table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_configs (
                id INTEGER PRIMARY KEY,
                key VARCHAR(64) UNIQUE,
                value TEXT
            )
        """)
        # Insert default auto_delete_hours if not exists
        cursor.execute("INSERT OR IGNORE INTO system_configs (key, value) VALUES ('auto_delete_hours', '4')")
        print("Ensured system_configs table exists with defaults")
    except Exception as e:
        print(f"Error creating system_configs table: {e}")
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
