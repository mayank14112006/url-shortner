# Antigravity URL Shortener

A high-performance URL shortener featuring a secure JSON Web Token (JWT) user authentication flow, Base62 numeric ID encoding, Redis caching for microsecond redirects, and a highly polished dark-themed single-page dashboard.

---

## Technical Stack

*   **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
*   **Primary Database**: [PostgreSQL](https://www.postgresql.org/) (mapped via [SQLAlchemy ORM](https://www.sqlalchemy.org/))
*   **In-Memory Cache**: [Redis](https://redis.io/) (via [redis-py](https://github.com/redis/redis-py) for caching redirects and expiring links)
*   **Authentication**: JWT (JSON Web Tokens via `python-jose` and `passlib` with `bcrypt` for secure hashing)
*   **Frontend**: Single HTML page styled with custom modern CSS (glassmorphism, interactive transitions) and vanilla JavaScript.

---

## Architectural Workflow

```
                                  +-------------------+
                                  |     Frontend      |
                                  | (Single HTML + JS)|
                                  +---------+---------+
                                            |
                                 REST HTTP  | (JWT Bearer Token)
                                            v
                                  +---------+---------+
                                  |  FastAPI Backend  |
                                  +----+----+----+----+
                                       |    |    |
                   Check Cache /       |    |    |
                   Save Redirect mapping    |    | Read / Write User & URL details
                                       |    |    +-----------------------------+
                                       v    v                                  v
                               +-------+----+---+                      +-------+--------+
                               |  Redis Cache   |                      |   PostgreSQL   |
                               | (Fast Redirect)|                      |  (Primary DB)  |
                               +----------------+                      +----------------+
```

### Key Logic & Design Patterns

1.  **Unique Base62 Encoding**:
    When a long URL is shortened, the backend inserts it into PostgreSQL. The database auto-generates a unique sequential integer ID. This integer is converted to a Base62 string (`0-9`, `a-z`, `A-Z`) and padded to exactly 6 characters (e.g. `0000aX`). This guarantees collision-free short codes without brute-force checks.
2.  **Redis-first Caching**:
    *   During redirect (`GET /r/{short_code}`), the server queries Redis.
    *   **Cache Hit**: Decodes JSON details, logs click telemetry asynchronously in the background, and instantly issues a HTTP 307 redirect.
    *   **Cache Miss**: Server queries Postgres, write-backs mapping info to Redis, logs click telemetry, and redirects.
3.  **Active Expiry and TTL Integration**:
    Optional URL expiration details are persisted in the database and saved to Redis utilizing native Redis Key Expire (TTL) parameters. When the TTL expires, Redis automatically evicts the entry, prompting database verification and a graceful HTTP 410 Gone fallback.
4.  **Asynchronous Telemetry**:
    Click counts are logged using FastAPI `BackgroundTasks`, executing database updates post-response. This keeps redirect durations extremely short and unblocked by database write latency.

---

## API Documentation

| Endpoint | Method | Auth Required | Description | Request Payload | Response |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/register` | `POST` | No | Registers a new user account | JSON: `{ "email": "str", "password": "str" }` | `UserOut` json |
| `/login` | `POST` | No | Authenticates user & issues JWT | Form URL-Encoded: `username`, `password` | `{ "access_token": "str", "token_type": "bearer" }` |
| `/shorten` | `POST` | Yes (Bearer) | Generates a 6-character short code | JSON: `{ "original_url": "str", "expires_at": "datetime/null" }` | `URLOut` json |
| `/dashboard` | `GET` | Yes (Bearer) | Lists all URLs created by current user | None | Array of `URLOut` json |
| `/r/{short_code}`| `GET` | No | Redirects short URL to original destination | Path Param: `short_code` | HTTP 307 Temporary Redirect |

---

## Local Setup Instructions

### Prerequisites
Make sure you have python 3.8+ installed, along with running PostgreSQL and Redis instances.

1.  **Clone / Copy files into project folder**:
    Navigate to the project root directory.

2.  **Setup Virtual Environment**:
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**:
    Copy the example environment settings and populate with your credentials:
    ```bash
    cp .env.example .env
    ```
    Open `.env` and fill in your DB/Redis configuration:
    ```ini
    BASE_URL=http://localhost:8000
    SECRET_KEY=9a2f3e82d7b1a03f4e6c8b9d0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b
    DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>
    REDIS_URL=redis://<host>:<port>/<db_index>
    ```

5.  **Run the Server**:
    Start the FastAPI application via Uvicorn:
    ```bash
    uvicorn main:app --reload
    ```
    The application will bind to `http://localhost:8000`.

6.  **Access App & Interactive Docs**:
    *   **Frontend UI**: Visit `http://localhost:8000/` in your browser.
    *   **Swagger API Docs**: Visit `http://localhost:8000/docs`.
    *   **Redoc API Docs**: Visit `http://localhost:8000/redoc`.
