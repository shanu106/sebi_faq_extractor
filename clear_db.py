#!/usr/bin/env python3
import sys
import logging
from database import drop_db, init_db
from vector_db import get_vector_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clear_db")

def clear_and_init():
    logger.info("Dropping and recreating PostgreSQL tables...")
    try:
        drop_db()
        init_db()
        logger.info("PostgreSQL database tables reset successfully.")
    except Exception as e:
        logger.error(f"Error resetting PostgreSQL: {e}")
        sys.exit(1)

    logger.info("Resetting Qdrant vector database collection...")
    try:
        vdb = get_vector_db()
        try:
            vdb.client.delete_collection(vdb.collection_name)
            logger.info(f"Deleted Qdrant collection '{vdb.collection_name}'.")
        except Exception as q_del_err:
            logger.warning(f"Failed to delete Qdrant collection (might not exist): {q_del_err}")
        
        vdb._init_collection()
        logger.info("Qdrant collection initialized successfully.")
    except Exception as e:
        logger.error(f"Error resetting Qdrant: {e}")
        sys.exit(1)

    logger.info("All databases reset successfully!")

if __name__ == "__main__":
    clear_and_init()
