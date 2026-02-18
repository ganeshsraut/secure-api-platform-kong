# secure-api-platform-kong
AI-Native Devops Assignement - Secure API Platform using Kong on Kubernetes

## 🏗 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Client / Postman                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              DDoS Protection Layer                           │
│         (NGINX Ingress + Rate Limiting)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Kong API Gateway                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ✓ JWT Authentication Plugin                         │   │
│  │ ✓ Rate Limiting (10 req/min per IP)                │   │
│  │ ✓ IP Whitelisting (10.0.0.0/8, 127.0.0.1/32)      │   │
│  │ ✓ Custom Lua Plugin (Header Injection)             │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              FastAPI Microservice                           │
│  ┌──────────────┬──────────────┬──────────────────────┐    │
│  │ /health      │ /login       │ /users (protected)   │    │
│  │ (public)     │ (public)     │ (JWT required)       │    │
│  └──────────────┴──────────────┴──────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│           SQLite Database (/data/sqlite.db)                │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities:

| Layer | Purpose | Technology |
|-------|---------|------------|
| **DDoS** | Volumetric attack protection | NGINX Ingress |
| **Kong** | Centralized authentication, rate limiting, IP control | Kong Gateway |
| **Microservice** | Business logic, user management | FastAPI |
| **Database** | User credential storage | SQLite |

## 🔄 API Request Flow

### Flow Diagram:

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ POST /login
       │ (username, password)
       │
┌──────▼──────────────────────┐
│    Kong Gateway              │
│  (No plugins on /login)      │
└──────┬──────────────────────┘
       │
       │ Forward to microservice
       │
┌──────▼──────────────────────────────┐
│  FastAPI Microservice                │
│  1. Check username/password          │
│  2. Hash password check              │
│  3. Generate JWT                     │
└──────┬──────────────────────────────┘
       │
       │ Return: { "token": "eyJ0..." }
       │
┌──────▼──────────────────────┐
│    Kong Gateway              │
│  (Return to client)          │
└──────┬──────────────────────┘
       │
┌──────▼─────────┐
│   Client       │
│ (Has JWT now)  │
└────────────────┘

═══════════════════════════════════════════════════════════

┌─────────────────────────────────────┐
│   Client                             │
│ GET /users                           │
│ Header: Authorization: Bearer <JWT>  │
└──────┬──────────────────────────────┘
       │
┌──────▼────────────────────────────────────┐
│    Kong Gateway                            │
│  1. Check JWT Plugin enabled ✓             │
│  2. Extract token from header              │
│  3. Validate JWT signature                 │
│  4. Check expiration                       │
│  5. If valid → Forward request             │
│  6. If invalid → Return 401 Unauthorized   │
└──────┬────────────────────────────────────┘
       │
       │ (Only valid requests reach here)
       │
┌──────▼──────────────────────────────┐
│  FastAPI Microservice                │
│  1. Query SQLite DB                  │
│  2. Return user list                 │
└──────┬──────────────────────────────┘
       │
       │ Return: { "users": [...] }
       │
┌──────▼────────────────────────────────┐
│    Kong Gateway                        │
│  (Apply custom Lua logic if needed)    │
└──────┬────────────────────────────────┘
       │
┌──────▼──────┐
│   Client     │
│ (Has data)   │
└──────────────┘
```

### Key Points:

| Stage | Handler | Action |
|-------|---------|--------|
| Request arrives | Kong | Apply rate limiting check |
| IP check | Kong IP Restriction Plugin | Verify IP in whitelist |
| Auth check | Kong JWT Plugin | Validate token (if route requires it) |
| Forward | Kong | Route to microservice |
| Business logic | FastAPI | Process request |
| Response | Kong | Return to client |


## 🔐 JWT Authentication Flow

### 1️⃣ Token Generation (/login)

```
POST /login
{
  "username": "admin",
  "password": "admin123"
}
        ↓
Microservice validates credentials against SQLite
        ↓
If valid:
  payload = {
    "sub": "admin",
    "exp": datetime.utcnow() + timedelta(hours=1)
  }
  token = jwt.encode(payload, SECRET_KEY, "HS256")
        ↓
Return: { "token": "eyJ0eXAiOiJKV1QiLCJhbGc..." }
```

### 2️⃣ Token Validation (/users with JWT)

```
GET /users
Header: Authorization: Bearer <token>
        ↓
Kong JWT Plugin intercepts request
        ↓
1. Extract token from Authorization header
2. Verify signature using SECRET_KEY
3. Check expiration time
4. If valid → allow request through
5. If invalid → return 401 Unauthorized
        ↓
Authenticated request reaches microservice
```

### 3️⃣ Token Structure

```
Header: {
  "alg": "HS256",
  "typ": "JWT"
}

Payload: {
  "sub": "admin",           # username
  "exp": 1700000000,        # expiration timestamp
  "iat": 1699996400         # issued at timestamp
}

Signature: HMACSHA256(base64(header) + "." + base64(payload), SECRET_KEY)
```

### 4️⃣ Error Cases

| Scenario | HTTP Status | Error |
|----------|-------------|-------|
| No Authorization header | 401 | Missing token |
| Invalid signature | 401 | Invalid token |
| Expired token | 401 | Token expired |
| Malformed token | 401 | Invalid format |

## 🔓 Authentication Bypass Strategy

### Routes Without Authentication:

| Route | Method | Purpose | Plugin Applied |
|-------|--------|---------|-----------------|
| `/health` | GET | System health check | ❌ None |
| `/verify` | GET | Public token validation | ❌ None |
| `/login` | POST | User authentication | ❌ None |

### Routes With Authentication:

| Route | Method | Purpose | Plugin Applied |
|-------|--------|---------|-----------------|
| `/users` | GET | List users | ✅ JWT Plugin |

### Implementation in Kong Configuration:

From [kong/kong.yaml](kong/kong.yaml):

```yaml
routes:
  - name: login-route
    paths: [/login]
    # ❌ NO plugins = public access
    
  - name: health-route
    paths: [/health]
    # ❌ NO plugins = public access
    
  - name: users-route
    paths: [/users]
    plugins:
      - name: jwt  # ✅ JWT plugin ONLY on /users
```

### Why This Design?

| Route | Why Bypass | Real-World Use Case |
|-------|-----------|-------------------|
| `/health` | K8s liveness probes need public access | K8s readiness checks |
| `/verify` | Gateway bypass for internal validation | Service-to-service checks |
| `/login` | Users need to get token first | Public user onboarding |

### Security Implication:

✅ **Principle**: Least Privilege
- Only `/users` requires JWT
- `/login` is intentionally public (users need to authenticate first)
- `/health` is intentionally public (K8s probes cannot carry JWT)

❌ **NOT BYPASSED**: Unauthorized users cannot access `/users` without valid JWT

## 🧪 Testing Guide

### Prerequisites:

```bash
# 1. Minikube local kubernetes
minikube start

# 2. Create namespace 
kubectl create namespace api-platform

# 3. Kong deployed
kubectl get pods -n api-platform

# 4. Port forward to Kong proxy
kubectl port-forward svc/kong-kong-proxy 8000:80 -n api-platform
```

---

### A️⃣ Test 1: Public API Access (/health)

**What it tests:** Authentication bypass works

```bash
curl -X GET http://localhost:8000/health
```

**Expected Response:**
```json
{ "status": "ok" }
```

**Status Code:** `200 OK` ✅

---

### B️⃣ Test 2: User Login (/login)

**What it tests:** JWT generation works

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**Expected Response:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTcwMDAwMDAwMH0..."
}
```

**Status Code:** `200 OK` ✅

**Store token:**
```bash
export JWT_TOKEN="<token_from_response>"
```

---

### C️⃣ Test 3: Protected API Without Token (/users)

**What it tests:** JWT validation required

```bash
curl -X GET http://localhost:8000/users
```

**Expected Response:**
```json
{
  "message": "Unauthorized"
}
```

**Status Code:** `401 Unauthorized` ✅

---

### D️⃣ Test 4: Protected API With Valid Token (/users)

**What it tests:** JWT validation passes

```bash
curl -X GET http://localhost:8000/users \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**Expected Response:**
```json
{
  "users": [
    {"id": 1, "username": "admin"}
  ]
}
```

**Status Code:** `200 OK` ✅

---

### E️⃣ Test 5: Rate Limiting (10 requests per minute per IP)

**What it tests:** Rate limiting plugin enforces limits

```bash
#!/bin/bash
# Script to test rate limiting

echo "Testing rate limiting (10 req/min)..."

for i in {1..15}; do
  echo "Request $i:"
  curl -s -X GET http://localhost:8000/health \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -w "\nHTTP Status: %{http_code}\n\n"
  
  sleep 0.5
done
```

**Expected Behavior:**

| Requests | Response | Status |
|----------|----------|--------|
| 1-10 | `{"status":"ok"}` | `200 OK` |
| 11-15 | Rate limit exceeded | `429 Too Many Requests` |

**Verify in Kong logs:**
```bash
kubectl logs -n default deploy/kong -f | grep "rate_limiting"
```

---

### F️⃣ Test 6: IP Whitelisting

**What it tests:** Only allowed IPs access APIs

**Current Whitelist** (from [kong/kong.yaml](kong/kong.yaml)):
```yaml
allow:
  - 127.0.0.1/32
  - 10.0.0.0/8
```

#### Test 6a: From Whitelisted IP (localhost)

```bash
curl -X GET http://localhost:8000/health
```

**Expected:** `200 OK` ✅

#### Test 6b: Simulate Non-Whitelisted IP ⚠️

Note: Testing from external IPs requires different setup. Instead, verify in Kong:

```bash
# Check IP restriction plugin configuration
kubectl exec -n default pod/kong-<pod-id> -- \
  kong config db:export | grep -A 5 "ip_restriction"
```

**Expected:** Plugin shows whitelist `10.0.0.0/8` and `127.0.0.1/32`

---

### G️⃣ Test 7: DDoS Protection (NGINX Rate Limiting)

**What it tests:** NGINX Ingress protects against volumetric attacks

**Configuration** (from [k8s/api-ingress.yaml](k8s/api-ingress.yaml)):
```yaml
annotations:
  nginx.ingress.kubernetes.io/limit-rps: "5"
  nginx.ingress.kubernetes.io/limit-connections: "10"
```

#### Simulated Load Test:

```bash
#!/bin/bash
# Simulate volumetric attack

echo "Generating 20 requests per second (exceeds 5 RPS limit)..."

for i in {1..100}; do
  curl -s -X GET http://localhost:8000/health \
    -w "%{http_code}\n" &
done

wait
```

**Expected Response Distribution:**

| Requests | Response | Reason |
|----------|----------|--------|
| ~5/sec | `200 OK` | Within NGINX limit |
| ~15/sec | `503 Service Unavailable` | NGINX rate limit exceeded |

**Verify NGINX behavior:**
```bash
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx -f | grep "limiting"
```

---

### H️⃣ Test 8: Custom Lua Plugin (Header Injection)

**What it tests:** Custom Kong Lua plugin adds headers

**Plugin** (from [kong/plugins/custom.lua](kong/plugins/custom.lua)):
```lua
function plugin:access(conf)
  kong.service.request.set_header("X-Request-ID", 
    kong.request.get_header("X-Request-ID") or "generated-id")
end
```

```bash
curl -X GET http://localhost:8000/users \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -v
```

**Expected Response Headers:**
```
> X-Request-ID: generated-id
```

**Verify in response:**
```bash
curl -X GET http://localhost:8000/users \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -i | grep "X-Request-ID"
```

---

### 📊 Test Summary Checklist:

```
✅ Test 1: /health returns 200
✅ Test 2: /login returns JWT token
✅ Test 3: /users without token returns 401
✅ Test 4: /users with token returns 200
✅ Test 5: Rate limiting enforces 10 req/min
✅ Test 6: IP whitelist blocks unauthorized IPs
✅ Test 7: NGINX rate limiting (5 req/sec) enforced
✅ Test 8: Custom Lua plugin adds X-Request-ID header
```

### Automated Test Script:

Create `tests/integration-test.sh`:

```bash
#!/bin/bash
set -e

API_URL="http://localhost:8000"
PASS=0
FAIL=0

test_endpoint() {
  local name=$1
  local method=$2
  local endpoint=$3
  local expected_status=$4
  local headers=$5
  
  response=$(curl -s -w "\n%{http_code}" -X $method "$API_URL$endpoint" $headers)
  status=$(echo "$response" | tail -n1)
  
  if [ "$status" == "$expected_status" ]; then
    echo "✅ $name - $status"
    ((PASS++))
  else
    echo "❌ $name - Expected $expected_status, got $status"
    ((FAIL++))
  fi
}

echo "Running Integration Tests..."
echo "=============================="

test_endpoint "Health Check" "GET" "/health" "200"

jwt_response=$(curl -s -X POST "$API_URL/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')

JWT_TOKEN=$(echo $jwt_response | grep -o '"token":"[^"]*' | cut -d'"' -f4)

test_endpoint "Get Users (No Auth)" "GET" "/users" "401"
test_endpoint "Get Users (With Auth)" "GET" "/users" "200" "-H 'Authorization: Bearer $JWT_TOKEN'"

echo "=============================="
echo "Passed: $PASS"
echo "Failed: $FAIL"

[ $FAIL -eq 0 ] && exit 0 || exit 1
```

Run tests:
```bash
bash tests/integration-test.sh
```