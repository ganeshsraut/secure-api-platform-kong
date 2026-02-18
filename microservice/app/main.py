import os
import sqlite3
import bcrypt
import jwt
import datetime
from fastapi import FastAPI, HTTPException, Header

JWT_SECRET = os.getenv("JWT_SECRET", "changeme")
JWT_ALGORITHM = "HS256"
DB_PATH = "/data/sqlite.db"

app = FastAPI()

# ------------------------
# DB INIT
# ------------------------
def init_db():
    os.makedirs("/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("SELECT * FROM users WHERE username=?", ("admin",))
    if not cur.fetchone():
        hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())
        cur.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            ("admin", hashed)
        )

    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

# ------------------------
# JWT HELPERS
# ------------------------
def create_token(username):
    payload = {
        "sub": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def validate_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ------------------------
# ROUTES
# ------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/login")
def login(body: dict):
    username = body.get("username")
    password = body.get("password")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401)

    if not bcrypt.checkpw(password.encode(), row[0]):
        raise HTTPException(status_code=401)

    return {"token": create_token(username)}

@app.get("/verify")
def verify(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    data = validate_token(token)
    return {"valid": True, "user": data["sub"]}

@app.get("/users")
def users(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401)

    token = authorization.split(" ")[1]
    validate_token(token)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id,username FROM users")
    data = cur.fetchall()
    conn.close()

    return {"users": [{"id": u[0], "username": u[1]} for u in data]}