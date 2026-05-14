import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

def migrate_db():
    db_path = "tio.db"
    if not os.path.exists(db_path):
        logger.info("No tio.db found, skipping migration.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if chatbots.user_id exists
        cursor.execute("PRAGMA table_info(chatbots)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "user_id" not in columns:
            logger.info("Adding user_id column to chatbots table...")
            cursor.execute("ALTER TABLE chatbots ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        else:
            logger.info("Column chatbots.user_id already exists.")

        # Check if conversations.user_id exists
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]
        if "user_id" not in columns:
            logger.info("Adding user_id column to conversations table...")
            cursor.execute("ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        else:
            logger.info("Column conversations.user_id already exists.")

        conn.commit()
        logger.info("Migration completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
