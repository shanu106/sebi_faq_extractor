"""
Database connection and session management
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from config import settings
import logging

logger = logging.getLogger(__name__)

import socket
import subprocess
import re
from urllib.parse import urlparse, urlunparse

def resolve_hostname(hostname: str) -> str:
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        # Fallback to system host command (macOS helper)
        try:
            result = subprocess.run(
                ["host", hostname],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                match = re.search(r"has address\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", result.stdout)
                if match:
                    resolved_ip = match.group(1)
                    logger.warning(f"Standard DNS lookup failed for {hostname}. Resolved via 'host' command to {resolved_ip}")
                    return resolved_ip
        except Exception as e:
            logger.error(f"Fallback DNS resolution via 'host' failed: {e}")
            
        # Fallback to system nslookup command
        try:
            result = subprocess.run(
                ["nslookup", hostname],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                ips = re.findall(r"Address:\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", result.stdout)
                if len(ips) > 1:
                    resolved_ip = ips[-1]
                    logger.warning(f"Standard DNS lookup failed for {hostname}. Resolved via 'nslookup' command to {resolved_ip}")
                    return resolved_ip
        except Exception as e:
            logger.error(f"Fallback DNS resolution via 'nslookup' failed: {e}")
            
        raise

def get_resolved_db_url(db_url: str) -> str:
    if not db_url:
        return db_url
    try:
        parsed = urlparse(db_url)
        if parsed.hostname:
            resolved_ip = resolve_hostname(parsed.hostname)
            netloc = resolved_ip
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            if parsed.username:
                if parsed.password:
                    netloc = f"{parsed.username}:{parsed.password}@{netloc}"
                else:
                    netloc = f"{parsed.username}@{netloc}"
            
            new_parts = list(parsed)
            new_parts[1] = netloc
            return urlunparse(new_parts)
    except Exception as e:
        logger.error(f"DNS resolution process failed for URL: {e}")
    return db_url

resolved_db_url = get_resolved_db_url(settings.database_url)

# Create engine with connection pooling
engine = create_engine(
    resolved_db_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Test connections before using
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    from models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")


def drop_db():
    """Drop all tables (for testing)"""
    from models import Base
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")
