"""
Lightweight migration script to alter the database tables
"""
import logging
from sqlalchemy import create_engine, text
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    logger.info("Starting database migration...")
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Add columns to faq_versions
        columns_to_add = [
            ("source_url", "VARCHAR(500)"),
            ("category", "VARCHAR(255)"),
            ("topic", "VARCHAR(255)"),
            ("subtopic", "VARCHAR(255)"),
            ("document_publish_date", "TIMESTAMP")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                # PostgreSQL ALTER TABLE ADD COLUMN IF NOT EXISTS
                query = text(f"ALTER TABLE faq_versions ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
                conn.execute(query)
                logger.info(f"Column '{col_name}' checked/added to 'faq_versions'.")
            except Exception as e:
                logger.error(f"Error adding column '{col_name}': {e}")
                raise
                
        conn.commit()
    logger.info("Database migration completed successfully!")

if __name__ == "__main__":
    run_migrations()
