import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import redis
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

# Connect with PostgreSQL, fallback to SQLite if it fails
engine = None
try:
    if DATABASE_URL:
        # Try testing connection
        from sqlalchemy import create_engine
        test_engine = create_engine(
            DATABASE_URL, 
            connect_args={"connect_timeout": 3} if "postgresql" in DATABASE_URL else {}
        )
        # Test connection
        conn = test_engine.connect()
        conn.close()
        engine = test_engine
except Exception as e:
    import sys
    print(f"WARNING: Database connection failed. Falling back to local SQLite database. Error: {e}", file=sys.stderr)
    DATABASE_URL = "sqlite:///url_shortener.db"

if engine is None:
    # Use SQLite fallback
    if not DATABASE_URL:
        DATABASE_URL = "sqlite:///url_shortener.db"
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Setup Redis client (decode_responses=True to work with string data directly)
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Ping Redis to verify connectivity
    redis_client.ping()
except Exception as e:
    import sys
    print(f"WARNING: Redis cache connection failed. App will redirect using Postgres directly. Error: {e}", file=sys.stderr)
    # Mock redis client that raises exceptions or returns None so catch blocks trigger
    class MockRedis:
        def get(self, *args, **kwargs): return None
        def set(self, *args, **kwargs): return None
        def delete(self, *args, **kwargs): return None
        def ping(self): raise ConnectionError("Mock Redis Connection Error")
    redis_client = MockRedis()


def get_db():
    """Dependency generator for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis():
    """Dependency provider for the Redis client."""
    try:
        yield redis_client
    except Exception as e:
        # Log or handle Redis connection failures gracefully
        raise e
