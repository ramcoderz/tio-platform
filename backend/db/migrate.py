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

        if "status_json" not in columns:
            logger.info("Adding status_json column to chatbots table...")
            cursor.execute("ALTER TABLE chatbots ADD COLUMN status_json JSON")
        else:
            logger.info("Column chatbots.status_json already exists.")

        # Check if conversations.user_id exists
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]
        if "user_id" not in columns:
            logger.info("Adding user_id column to conversations table...")
            cursor.execute("ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        else:
            logger.info("Column conversations.user_id already exists.")

        # Create ingestion_jobs table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id INTEGER PRIMARY KEY,
                chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
                status VARCHAR(50) DEFAULT 'pending',
                current_stage VARCHAR(50) DEFAULT 'queued',
                progress INTEGER DEFAULT 0,
                error_message TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("Checked/Created ingestion_jobs table.")

        # Update ingestion_jobs columns
        cursor.execute("PRAGMA table_info(ingestion_jobs)")
        job_columns = [col[1] for col in cursor.fetchall()]
        
        new_job_cols = {
            "total_chunks": "INTEGER DEFAULT 0",
            "indexed_chunks": "INTEGER DEFAULT 0",
            "failed_chunks": "INTEGER DEFAULT 0",
            "updated_at": "DATETIME",
        }
        
        for col, col_type in new_job_cols.items():
            if col not in job_columns:
                logger.info(f"Adding {col} column to ingestion_jobs table...")
                cursor.execute(f"ALTER TABLE ingestion_jobs ADD COLUMN {col} {col_type}")

        conn.commit()
        logger.info("Migration completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
