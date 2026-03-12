# Backend API Test Matrix

This document lists backend APIs only (`backend/app/routes/*`) with test-ready details.

Base URL (local):

- `http://127.0.0.1:8001`

---

## 1) Health

### `GET /health`

- **Purpose:** backend availability check
- **Auth:** none

**cURL**

```bash
curl -X GET "http://127.0.0.1:8001/health"
```

**Expected success**

- `200` with:

```json
{"ok": true}
```

---

## 2) LLM Endpoints

## 2.1 Chat

### `POST /api/chat`

- **Purpose:** main chat inference stream
- **Auth:** required (`Authorization: Bearer <SUPABASE_ACCESS_TOKEN>`)
- **Request body:**
  - `messages` (required): array of `{ role, content }`
  - `conversationId` (optional)
  - `modelId` (optional domain routing hint)

**cURL**

```bash
curl -N -X POST "http://127.0.0.1:8001/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{
    "messages": [
      {"role":"user","content":"Hello, test chat"}
    ],
    "modelId": "insurance"
  }'
```

**Expected success**

- `200` SSE stream (`data: ...`, ends with `data: [DONE]`)

**Common failures**

- `401` unauthorized / invalid token
- `429` rate-limited provider
- `402` provider credits/payment issue
- `500` all fallback providers failed

---

## 2.2 Help Assistant

### `POST /api/help-assistant`

- **Purpose:** help sidebar assistant stream
- **Auth:** currently optional (frontend may still send bearer)
- **Request body:**
  - `messages`: array of `{ role, content }`

**cURL**

```bash
curl -N -X POST "http://127.0.0.1:8001/api/help-assistant" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role":"user","content":"What is Fideon Fabric?"}
    ]
  }'
```

**Expected success**

- `200` SSE stream (`data: ...`, `data: [DONE]`)

**Common failures**

- `429`, `402`, `500` from provider/fallback chain

---

## 2.3 Workflow AI

### `POST /api/workflow-ai`

- **Purpose:** workflow parsing and step assistance
- **Auth:** none (current implementation)
- **Request body:**
  - `action`: `"parse"` or `"assist"` (required)
  - `sop_text`: string (required)
  - `current_step`: object (required for `assist`)
  - `step_context`: string (optional for `assist`)

**cURL (parse)**

```bash
curl -N -X POST "http://127.0.0.1:8001/api/workflow-ai" \
  -H "Content-Type: application/json" \
  -d '{
    "action":"parse",
    "sop_text":"Collect claim details, validate policy, request missing documents, then submit."
  }'
```

**cURL (assist)**

```bash
curl -N -X POST "http://127.0.0.1:8001/api/workflow-ai" \
  -H "Content-Type: application/json" \
  -d '{
    "action":"assist",
    "sop_text":"Collect claim details, validate policy, request missing documents, then submit.",
    "current_step":{"step_number":2,"title":"Validate policy","description":"Check active coverage"},
    "step_context":"Customer submitted FNOL."
  }'
```

**Expected success**

- `200` SSE stream

**Common failures**

- `400` invalid action
- `429`, `402`, `500` provider/fallback errors

---

## 3) Admin / RBAC APIs

All admin APIs require `Authorization: Bearer <ACCESS_TOKEN>`.

## 3.1 List Users

### `GET /api/list-users`

- **Purpose:** list auth users with roles
- **Role required:** `admin` or `global_admin`

**cURL**

```bash
curl -X GET "http://127.0.0.1:8001/api/list-users" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

**Expected success**

- `200` with:

```json
{
  "users": [
    {"id":"...","email":"...","role":"user","created_at":"..."}
  ]
}
```

**Common failures**

- `401` unauthorized
- `403` admin access required

---

## 3.2 Admin Create User

### `POST /api/admin-create-user`

- **Purpose:** create new user (or update password using action mode)
- **Role required:** `admin` or `global_admin`
- **Request body (create):**
  - `email` (required)
  - `password` (required)
  - `full_name` (optional)
  - `role` (optional, default: `user`)
  - `action` (optional, default: `create`)
- **Valid roles:** `global_admin`, `admin`, `user`, `viewer`, `guest`

**cURL (create)**

```bash
curl -X POST "http://127.0.0.1:8001/api/admin-create-user" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{
    "email":"new.user@example.com",
    "password":"TempPass#123",
    "full_name":"New User",
    "role":"viewer"
  }'
```

**cURL (password update mode)**

```bash
curl -X POST "http://127.0.0.1:8001/api/admin-create-user" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{
    "action":"update_password",
    "email":"new.user@example.com",
    "password":"NewTempPass#456",
    "role":"viewer"
  }'
```

**Expected success**

- create: `200` with `{"success": true, "user": {"id":"...","email":"..."}}`
- update password: `200` with success message

**Common failures**

- `400` invalid role / missing fields / Supabase admin API error
- `401` unauthorized
- `403` admin access required
- `404` user not found (password update mode)

---

## 3.3 Set User Role

### `POST /api/admin-set-user-role`

- **Purpose:** update a user's role
- **Role required:** `global_admin` only
- **Request body:**
  - `user_id` (required)
  - `role` (required)

**cURL**

```bash
curl -X POST "http://127.0.0.1:8001/api/admin-set-user-role" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{
    "user_id":"<TARGET_USER_UUID>",
    "role":"admin"
  }'
```

**Expected success**

- `200` with `{"success":true,"user_id":"...","role":"admin"}`

**Common failures**

- `400` invalid payload/role
- `401` unauthorized
- `403` global admin access required

---

## 4) Device APIs

## 4.1 Device Models

### `GET /api/device-models`

- **Purpose:** get assigned models for a device
- **Auth:** `x-device-token` header required

**cURL**

```bash
curl -X GET "http://127.0.0.1:8001/api/device-models" \
  -H "x-device-token: <DEVICE_TOKEN>"
```

**Expected success**

- `200` with `device_id`, `models[]`, `total_models`

**Common failures**

- `400` missing token
- `401` invalid token
- `403` device deactivated

---

## 4.2 Device Check-in

### `POST /api/device-checkin`

- **Purpose:** heartbeat/update device status and sync flags
- **Auth:** `x-device-token` header required
- **Request body (optional fields):**
  - `os_type`
  - `app_version`
  - `local_models` (array; each item can be `model_id` or object containing `model_id`)

**cURL**

```bash
curl -X POST "http://127.0.0.1:8001/api/device-checkin" \
  -H "Content-Type: application/json" \
  -H "x-device-token: <DEVICE_TOKEN>" \
  -d '{
    "os_type":"windows",
    "app_version":"1.0.0",
    "local_models":[{"model_id":"policy-comparison"}]
  }'
```

**Expected success**

- `200` with `{"success":true,"device_id":"...","status":"online","message":"Check-in successful"}`

**Common failures**

- `400` missing token
- `401` invalid token
- `403` device deactivated

---

## 4.3 Device Register

### `POST /api/device-register`

- **Purpose:** finalize device registration by token
- **Auth:** body token required (no bearer required)
- **Request body:**
  - `device_token` (required)
  - `device_name` (optional)
  - `os_type` (optional)
  - `app_version` (optional)

**cURL**

```bash
curl -X POST "http://127.0.0.1:8001/api/device-register" \
  -H "Content-Type: application/json" \
  -d '{
    "device_token":"<DEVICE_TOKEN>",
    "device_name":"Claims Desktop - Chicago",
    "os_type":"windows",
    "app_version":"1.0.0"
  }'
```

**Expected success**

- `200` with `{"success":true,"device_id":"...","device_name":"...","message":"Device registered successfully"}`

**Common failures**

- `400` missing `device_token`
- `401` invalid token
- `403` device deactivated

---

## Notes for Test Execution

- LLM endpoints stream SSE; use `curl -N`.
- For auth-protected admin/chat APIs, use a valid Supabase access token.
- For device APIs, use a valid `device_token` generated in `public.devices`.
- Fallback provider order in backend:
  - Groq -> RunPod Llama -> RunPod Mistral -> Gemini -> OpenAI -> Claude
