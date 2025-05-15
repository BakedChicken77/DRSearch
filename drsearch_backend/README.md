# DRSearch
A RAG Chatbot




## To run test, use this command:
### This will:
* **Run all tests in tests/**
* **Measure coverage on the app/ directory**
* **Show lines missed in coverage**
```powershell
poetry run pytest --cov=app --cov-report=term-missing -q

```



### Authentication — Detailed Technical Walk-through
Use this section verbatim (or excerpt as needed) in project documentation.

---

## 1. High-level overview
* **Goal:** Enforce Azure AD JWT Bearer authentication on every HTTP request while keeping local-dev friction near zero.  
* **Implementation:** A single ASGI-compatible `AuthMiddleware` class, injected **after** `CORSMiddleware` in `create_app()`.  
* **Dependencies:** `pyjwt`, `requests`, `python-json-logger`, and FastAPI/Starlette’s middleware stack.

---

## 2. Configuration prerequisites
| **Variable** | **Purpose** | **Example** |
|--------------|-------------|-------------|
| `AUTH_ENABLED` | Toggle auth (`True` = prod, `False` = dev bypass) | `True` |
| `AZURE_AD_TENANT_ID` | Azure AD tenant (Gov cloud uses `login.microsoftonline.us`)
| `AZURE_AD_CLIENT_ID` | Application (client) ID of the **frontend** SPA |
| `CORS_ORIGINS` | Comma-sep list consumed by `pydantic-settings` | `http://localhost:3000` |

No other environment variables are touched by auth.

---

## 3. Startup sequence

1. **`create_app()`** instantiates FastAPI.  
2. **`CORSMiddleware`** is added **first** so it can post-process all responses (including 401s).  
3. **`AuthMiddleware(app, settings)`** is injected. Constructor logic:  
   1. Skip everything if `AUTH_ENABLED=False`.  
   2. Call Azure AD well-known discovery:  
      ```
      https://login.microsoftonline.us/<TENANT_ID>/.well-known/openid-configuration
      ```  
      The JSON payload provides `issuer` and `jwks_uri`.  
   3. Store both fields for the lifetime of the process. A failed fetch is fatal (raises `RuntimeError` → container will crash fast).  

No other work is done at startup; JWKS discovery is deferred to first token decode and then cached.

---

## 4. Per-request lifecycle

> Executed by `AuthMiddleware.__call__(scope, receive, send)`.

| Step | Detail |
|------|--------|
| **1. Scope filtering** | Only `scope["type"] == "http"` is processed; WebSocket & lifespan frames pass unmodified. |
| **2. Dev bypass** | If `auth_enabled=False`, `request.state.user = {"username": "devuser"}` and the request proceeds with no checks. |
| **3. CORS pre-flight pass-through** | `OPTIONS` requests are forwarded immediately (they carry no credentials). |
| **4. Token extraction** | Reads `Authorization` header. Missing or non-`Bearer …` → `HTTPException 401 ("Missing bearer token")`. |
| **5. Validation (`decode_bearer`)** | *Cache layer* ↴<br>• `_jwks_client(jwks_uri)` is `functools.cache`-backed so each unique URI is fetched once.<br>• `jwt.decode()` is called with:<br>&nbsp;&nbsp;• `algorithms=["RS256"]` (matches `"alg":"RS256"` in Azure tokens)<br>&nbsp;&nbsp;• `audience="api://<CLIENT_ID>"`<br>&nbsp;&nbsp;• `issuer` from discovery<br>Standard PyJWT verification is applied. |
| **6. Attach user** | On success, the decoded claims dict is stored in `request.state.user`. |
| **7. Error path** | Any `TokenValidationError` bubbles to `HTTPException 401`, which is handled by FastAPI’s default handler — *after* CORS — ensuring the SPA sees correct CORS headers even on auth failures. |

Latency impact: after warm-up, token verification is dominated by an RSA-SHA256 signature check (~150–250 µs on modern CPUs).

---

## 5. Error semantics

| **Scenario** | **HTTP** | **`detail`** field |
|--------------|----------|--------------------|
| No `Authorization` header | 401 | `Missing bearer token` |
| Wrong scheme (`Basic …`) | 401 | `Missing bearer token` |
| Expired token | 401 | `Token expired` |
| Invalid signature / wrong audience / wrong issuer | 401 | Same text from PyJWT (wrapped by `TokenValidationError`) |
| Any other uncaught exception | Propagates to default 500 handler (rare) |

All 401 responses still include the CORS headers injected earlier by `CORSMiddleware`.

---

## 6. Local development workflow

```env
AUTH_ENABLED=False          # disables OAuth completely
CORS_ORIGINS=http://localhost:3000
```

* No Azure AD calls are made.  
* `request.state.user` is always `{"username": "devuser"}` so downstream code needn’t branch.  
* Useful for Cypress integration tests or offline hacking.

---

## 7. Security considerations & recommendations

1. **Algorithm pinning** – Only `"RS256"` is whitelisted, preventing *alg:none* downgrade attacks.  
2. **JWKS caching** – Prevents per-request network hops but does **not** cache indefinitely; if Azure rotates keys the `kid` mismatch will automatically trigger a fresh fetch by `PyJWKClient`.  
3. **Audience scoping** – Locks tokens to this API (`api://<CLIENT_ID>`). Frontend ID and backend ID **must** match in Azure portal.  
4. **Issuer check** – Tokens issued by other tenants (incl. MSA) are rejected.  
5. **Dev bypass** – Never set `AUTH_ENABLED=False` in staging or prod.

---

## 8. Troubleshooting checklist

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `401 Missing bearer token` from nginx but you sent the header | Proxy stripped it (check `proxy_set_header Authorization $http_authorization;`) | Add header forwarding |
| `401 Token expired` immediately after login | Local clock skew > 5 min | Sync system clock / NTP |
| CORS headers missing on 401 | AuthMiddleware accidentally registered **before** CORS | Ensure ordering in `create_app()` |
| Intermittent `jwks_uri` fetch timeouts on cold start | Outbound firewall blocks `login.microsoftonline.us` | Add rule / mirror JWKS internally |

---

### TL;DR
v2 authentication uses a self-contained ASGI middleware that:

1. Fetches Azure AD OIDC metadata once at startup.  
2. Caches JWKs lazily for signature verification.  
3. Validates every Bearer token (`RS256`, correct `aud`, correct `iss`).  
4. Injects decoded claims into `request.state.user`.  
5. Plays nicely with CORS, streaming responses, and a local-dev bypass flag.