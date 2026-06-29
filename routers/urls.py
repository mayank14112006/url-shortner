import os
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import database, models, schemas, auth
from utils.encoder import generate_short_code

# Logger setup
logger = logging.getLogger(__name__)

router = APIRouter()
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


# --- Background Tasks ---

def increment_clicks_in_db(short_code: str):
    """Asynchronously increments the click count for a short code in PostgreSQL."""
    db = database.SessionLocal()
    try:
        db.query(models.URL).filter(models.URL.short_code == short_code).update(
            {models.URL.clicks: models.URL.clicks + 1}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error incrementing click count for {short_code}: {e}")
        db.rollback()
    finally:
        db.close()


def remove_expired_cache(short_code: str):
    """Asynchronously removes an expired URL cache entry from Redis."""
    try:
        redis_client = database.redis_client
        redis_client.delete(f"url:{short_code}")
    except Exception as e:
        logger.error(f"Error deleting expired URL from Redis cache: {e}")


# --- API Routes ---

@router.post("/shorten", response_model=schemas.URLOut, status_code=status.HTTP_201_CREATED)
def shorten_url(
    url_in: schemas.URLCreate,
    db: Session = Depends(database.get_db),
    redis_client = Depends(database.get_redis),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Shortens a given URL using Base62 encoding.
    Caches the redirect mapping in Redis and stores it in PostgreSQL.
    """
    original_url = url_in.original_url.strip()
    
    # Ensure URL has protocol prefix
    if not (original_url.startswith("http://") or original_url.startswith("https://")):
        original_url = "http://" + original_url

    # Expiry time check
    if url_in.expires_at and url_in.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiry time cannot be in the past."
        )

    # 1. Insert row in URL table to generate auto-increment ID
    db_url = models.URL(
        original_url=original_url,
        expires_at=url_in.expires_at,
        user_id=current_user.id
    )
    db.add(db_url)
    db.flush()  # Populates db_url.id without committing transaction

    # 2. Encode ID into a Base62 string and pad it
    short_code = generate_short_code(db_url.id)
    db_url.short_code = short_code
    db.commit()
    db.refresh(db_url)

    # 3. Cache the mapping in Redis
    try:
        cache_val = {
            "original_url": db_url.original_url,
            "expires_at": db_url.expires_at.isoformat() if db_url.expires_at else None
        }
        if db_url.expires_at:
            ttl = int((db_url.expires_at - datetime.utcnow()).total_seconds())
            if ttl > 0:
                redis_client.set(f"url:{short_code}", json.dumps(cache_val), ex=ttl)
        else:
            redis_client.set(f"url:{short_code}", json.dumps(cache_val))
    except Exception as e:
        logger.error(f"Redis cache write error: {e}")

    # 4. Construct response schema
    return schemas.URLOut(
        id=db_url.id,
        original_url=db_url.original_url,
        short_code=db_url.short_code,
        short_url=f"{BASE_URL}/r/{db_url.short_code}",
        clicks=db_url.clicks,
        created_at=db_url.created_at,
        expires_at=db_url.expires_at,
        user_id=db_url.user_id
    )


@router.get("/r/{short_code}")
def redirect_to_original(
    short_code: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db),
    redis_client = Depends(database.get_redis)
):
    """
    Redirects a short code to the original URL.
    Checks Redis cache first. On miss, falls back to PostgreSQL.
    Tracks clicks asynchronously.
    """
    original_url = None
    expires_at_str = None
    cache_hit = False

    # 1. Attempt Redis read
    try:
        cached_data = redis_client.get(f"url:{short_code}")
        if cached_data:
            data = json.loads(cached_data)
            original_url = data.get("original_url")
            expires_at_str = data.get("expires_at")
            cache_hit = True
    except Exception as e:
        logger.error(f"Redis cache read failure: {e}")

    # 2. Redis hit path
    if cache_hit and original_url:
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at < datetime.utcnow():
                background_tasks.add_task(remove_expired_cache, short_code)
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="This shortened URL has expired."
                )

        # Queue async click counter increment
        background_tasks.add_task(increment_clicks_in_db, short_code)
        return RedirectResponse(url=original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # 3. Cache miss: DB fallback
    db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shortened URL not found."
        )

    # Check expiration in DB
    if db_url.expires_at and db_url.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This shortened URL has expired."
        )

    # 4. Write back to Redis cache
    try:
        cache_val = {
            "original_url": db_url.original_url,
            "expires_at": db_url.expires_at.isoformat() if db_url.expires_at else None
        }
        if db_url.expires_at:
            ttl = int((db_url.expires_at - datetime.utcnow()).total_seconds())
            if ttl > 0:
                redis_client.set(f"url:{short_code}", json.dumps(cache_val), ex=ttl)
        else:
            redis_client.set(f"url:{short_code}", json.dumps(cache_val))
    except Exception as e:
        logger.error(f"Redis cache write failure: {e}")

    # Queue async click counter increment
    background_tasks.add_task(increment_clicks_in_db, short_code)
    return RedirectResponse(url=db_url.original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/dashboard", response_model=list[schemas.URLOut])
def get_dashboard(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Returns all URLs created by the authenticated user."""
    urls = db.query(models.URL).filter(models.URL.user_id == current_user.id).order_by(models.URL.created_at.desc()).all()
    
    # Construct response format
    result = []
    for db_url in urls:
        result.append(schemas.URLOut(
            id=db_url.id,
            original_url=db_url.original_url,
            short_code=db_url.short_code,
            short_url=f"{BASE_URL}/r/{db_url.short_code}",
            clicks=db_url.clicks,
            created_at=db_url.created_at,
            expires_at=db_url.expires_at,
            user_id=db_url.user_id
        ))
    return result
