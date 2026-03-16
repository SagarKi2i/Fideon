"""
API Gateway Walkthrough — Full Documentation PDF
Fideon OS · FastAPI Backend
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from PIL import Image as PILImage

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(OUT_DIR, "_api_gw_imgs")
os.makedirs(IMG_DIR, exist_ok=True)

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":      "#f8f9fa",
    "hdr":     "#1a1a2e",
    "fe":      "#1abc9c",
    "mw":      "#d35400",
    "auth":    "#8e44ad",
    "role":    "#e67e22",
    "route":   "#2980b9",
    "supa":    "#0f3460",
    "llm":     "#16a085",
    "dev":     "#27ae60",
    "ok":      "#27ae60",
    "no":      "#c0392b",
    "warn":    "#f39c12",
    "ga":      "#c0392b",
    "admin":   "#e67e22",
    "user":    "#27ae60",
    "viewer":  "#2980b9",
    "guest":   "#95a5a6",
    "border":  "#dee2e6",
    "grey":    "#7f8c8d",
}

def save_fig(fig, name, dpi=150):
    path = os.path.join(IMG_DIR, f"{name}.png")
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path

def rbox(ax, x, y, w, h, color, text, fs=9, tc="white", bold=False,
         border=None, radius=0.05, zorder=3, alpha=1.0):
    fc = FancyBboxPatch((x - w/2, y - h/2), w, h,
                        boxstyle=f"round,pad=0,rounding_size={radius}",
                        facecolor=color, edgecolor=border or color,
                        linewidth=1.4, zorder=zorder, alpha=alpha)
    ax.add_patch(fc)
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal",
            zorder=zorder+1, multialignment="center")

def arr(ax, x1, y1, x2, y2, col="#555", lw=1.8, style="->",
        label="", lfs=7.2, lpad=(0.04, 0.04), rad=0.0):
    cs = f"arc3,rad={rad}" if rad else "arc3,rad=0.0"
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=col, lw=lw,
                                connectionstyle=cs), zorder=2)
    if label:
        mx, my = (x1+x2)/2 + lpad[0], (y1+y2)/2 + lpad[1]
        ax.text(mx, my, label, fontsize=lfs, color=col,
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="white",
                          ec=col, lw=0.6, alpha=0.9), zorder=4)

def hr_line(ax, y, xmin=0.05, xmax=0.95, col="#ccc", lw=1, ls="--"):
    ax.axhline(y=y, xmin=xmin, xmax=xmax, color=col, lw=lw, linestyle=ls, zorder=1)

def group_box(ax, x, y, w, h, color, title, fs=9):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0,rounding_size=0.1",
                       facecolor=color+"18", edgecolor=color,
                       linewidth=1.8, linestyle="--", zorder=1)
    ax.add_patch(p)
    ax.text(x + w/2, y + h - 0.18, title, ha="center", va="top",
            fontsize=fs, color=color, fontweight="bold")

def diamond(ax, x, y, w, h, color, text, fs=8.5):
    pts = np.array([[x, y+h/2],[x+w/2, y],[x, y-h/2],[x-w/2, y]])
    ax.add_patch(plt.Polygon(pts, closed=True, facecolor=color,
                             edgecolor="white", lw=1.5, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            color="white", fontweight="bold", zorder=4, multialignment="center")

def activation_bar(ax, x, y_top, y_bot, color, w=0.16):
    ax.add_patch(plt.Rectangle((x-w/2, y_bot), w, y_top-y_bot,
                               facecolor=color, edgecolor="white",
                               lw=0.8, zorder=2, alpha=0.9))

# =============================================================================
# DIAGRAM A1 — Full Request Lifecycle Overview
# =============================================================================
def diag_request_lifecycle():
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 14); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("API Gateway — Full Request Lifecycle", fontsize=16,
                 fontweight="bold", color=C["hdr"], pad=14)

    # Column X positions
    cols = {"client": 1.4, "cors": 3.2, "log": 5.0, "auth": 6.8,
            "role": 8.6, "route": 10.4, "supa": 12.2}

    # Top header boxes
    headers = [
        (cols["client"], "Browser /\nFrontend",      C["fe"]),
        (cols["cors"],   "CORS\nMiddleware",          C["mw"]),
        (cols["log"],    "Logging\nMiddleware",       C["mw"]),
        (cols["auth"],   "JWT Auth\nVerification",    C["auth"]),
        (cols["role"],   "Role\nEnforcement",         C["role"]),
        (cols["route"],  "Route\nHandler",            C["route"]),
        (cols["supa"],   "Supabase\nPostgREST",       C["supa"]),
    ]
    for x, lbl, col in headers:
        rbox(ax, x, 9.3, 1.55, 0.65, col, lbl, fs=8.5, bold=True, radius=0.06)
        ax.plot([x, x], [8.97, 0.5], color=col, lw=1.4, ls="--", zorder=1, alpha=0.5)

    # Request flow arrows (top row)
    for i in range(len(headers)-1):
        x1 = headers[i][0] + 0.78
        x2 = headers[i+1][0] - 0.78
        arr(ax, x1, 9.3, x2, 9.3, col="#555", lw=1.8, label="")

    # Step-by-step flow
    steps = [
        # (y,    from_col,   to_col,   box_x,   box_col,  label,           note)
        (8.3, "client", "cors",   cols["cors"],  C["mw"],    "1  HTTP Request arrives",
             "OPTIONS preflight or actual request"),
        (7.4, "cors",   "log",    cols["log"],   C["mw"],    "2  CORS validated",
             "allow_origins=* · allow_methods=* · allow_headers=*"),
        (6.5, "log",    "auth",   cols["log"],   C["mw"],    "3  Request logged",
             "request_id=UUID · method · path · client_ip"),
        (5.6, "log",    "auth",   cols["auth"],  C["auth"],  "4  Bearer token extracted",
             "Header: Authorization: Bearer <JWT>"),
        (4.7, "auth",   "supa",   cols["supa"],  C["supa"],  "5  Token validated vs Supabase",
             "GET /auth/v1/user · returns user object"),
        (3.8, "supa",   "auth",   cols["auth"],  C["auth"],  "6  User object returned",
             "{ id, email, role ... }"),
        (2.9, "auth",   "role",   cols["role"],  C["role"],  "7  Role fetched from user_roles",
             "SELECT role FROM user_roles WHERE user_id=..."),
        (2.0, "role",   "route",  cols["route"], C["route"], "8  Route handler executes",
             "Business logic · DB queries · LLM calls"),
        (1.2, "route",  "client", cols["client"],C["fe"],    "9  Response returned",
             "JSON or SSE stream"),
    ]

    for (y, fc, tc, bx, bc, lbl, note) in steps:
        x1 = cols[fc]
        x2 = cols[tc]
        direction = 1 if x2 >= x1 else -1
        arr(ax, x1 + direction*0.78, y, x2 - direction*0.78, y, bc, lw=2.0)
        # annotation box on right side
        ax.text(cols["supa"] + 0.92, y, lbl, fontsize=8, color=bc,
                fontweight="bold", va="center")
        ax.text(cols["supa"] + 0.92, y - 0.22, note, fontsize=7,
                color="#666", va="center", style="italic")

    # vertical dotted separation
    ax.axvline(x=cols["supa"]+0.5, ymin=0.04, ymax=0.94,
               color="#bbb", lw=1, ls=":")

    # legend
    leg = [mpatches.Patch(fc=C[k], label=v) for k, v in [
        ("fe","Frontend/Client"), ("mw","Middleware Layer"),
        ("auth","Auth Layer"), ("role","Role Layer"),
        ("route","Route Handler"), ("supa","Supabase"),
    ]]
    ax.legend(handles=leg, loc="lower left", fontsize=8,
              framealpha=0.85, ncol=3)
    return save_fig(fig, "A1_request_lifecycle")


# =============================================================================
# DIAGRAM A2 — JWT Auth Validation Flow
# =============================================================================
def diag_jwt_auth():
    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("JWT Authentication Validation Flow", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    # Entry
    rbox(ax, 6, 9.4, 4.5, 0.5, C["hdr"],
         "Incoming Request to Protected Endpoint", fs=10, bold=True)

    # Step 1: Authorization header present?
    diamond(ax, 6, 8.3, 4.2, 0.9, C["auth"],
            "Authorization header\npresent?", fs=8.5)
    arr(ax, 6, 9.15, 6, 8.75)

    # NO branch
    rbox(ax, 10.5, 8.3, 2.0, 0.5, C["no"],
         "401 Unauthorized\n\"Unauthorized\"", fs=8.5, bold=True)
    arr(ax, 8.1, 8.3, 9.5, 8.3, C["no"], label="No")

    # Step 2: Starts with "Bearer "?
    diamond(ax, 6, 7.1, 4.4, 0.9, C["auth"],
            "Starts with\n\"Bearer \" prefix?", fs=8.5)
    arr(ax, 6, 7.85, 6, 7.55)

    rbox(ax, 10.5, 7.1, 2.0, 0.5, C["no"],
         "401 Unauthorized\n\"Unauthorized\"", fs=8.5, bold=True)
    arr(ax, 8.2, 7.1, 9.5, 7.1, C["no"], label="No")

    # Step 3: Extract token
    rbox(ax, 6, 6.1, 4.5, 0.5, C["mw"],
         "Extract:  token = header.split(' ', 1)[1]", fs=8.5, bold=True)
    arr(ax, 6, 6.65, 6, 6.35, C["auth"])

    # Step 4: Call Supabase
    rbox(ax, 6, 5.1, 5.5, 0.75, C["supa"],
         "GET  {SUPABASE_URL}/auth/v1/user\n"
         "Headers: apikey: SUPABASE_ANON_KEY\n"
         "         Authorization: Bearer <token>",
         fs=8, bold=True)
    arr(ax, 6, 5.85, 6, 5.47, C["supa"])

    # Step 5: Response status >= 400?
    diamond(ax, 6, 3.9, 4.4, 0.9, C["auth"],
            "Supabase response\nstatus >= 400?", fs=8.5)
    arr(ax, 6, 4.72, 6, 4.35)

    rbox(ax, 10.5, 3.9, 2.0, 0.5, C["no"],
         "401 Unauthorized\n\"Unauthorized\"", fs=8.5, bold=True)
    arr(ax, 8.2, 3.9, 9.5, 3.9, C["no"], label="Yes")

    # Step 6: Return user object
    rbox(ax, 6, 2.9, 4.5, 0.65, C["ok"],
         "Return user object\n{ id, email, ... }", fs=9, bold=True)
    arr(ax, 6, 3.45, 6, 3.22, C["ok"], label="No (valid)")

    # Step 7: Continue to role check
    rbox(ax, 6, 1.9, 4.5, 0.5, C["route"],
         "Continue to Role Enforcement", fs=9, bold=True)
    arr(ax, 6, 2.57, 6, 2.15, C["route"])

    # Code reference
    ax.text(0.3, 1.0,
            "Source: backend/app/core/supabase.py  ->  async def verify_user(authorization)",
            fontsize=7.5, color="#888", style="italic")

    return save_fig(fig, "A2_jwt_auth")


# =============================================================================
# DIAGRAM A3 — Role Enforcement Flow
# =============================================================================
def diag_role_enforcement():
    fig, ax = plt.subplots(figsize=(13, 10))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("Role Enforcement — Per-Endpoint Authorization", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    # Entry
    rbox(ax, 6.5, 9.4, 5.0, 0.5, C["hdr"],
         "Authenticated user object received", fs=10, bold=True)

    # Fetch role
    rbox(ax, 6.5, 8.55, 6.0, 0.6, C["supa"],
         "SELECT role FROM user_roles\nWHERE user_id = user['id']  LIMIT 1",
         fs=8.5, bold=True)
    arr(ax, 6.5, 9.15, 6.5, 8.85, C["supa"])

    rbox(ax, 6.5, 7.65, 5.0, 0.55, C["role"],
         "requester_role = result[0]['role']  or  None", fs=9, bold=True)
    arr(ax, 6.5, 8.25, 6.5, 7.92, C["role"])

    # Which endpoint?
    diamond(ax, 6.5, 6.55, 5.2, 1.0, "#2c3e50",
            "Endpoint role\nrequirement?", fs=9)
    arr(ax, 6.5, 7.37, 6.5, 7.05)

    # Branches
    branches = [
        (1.5,  5.2, "No Auth\nRequired",    "#7f8c8d",
         "health\nhelp-assistant\nworkflow-ai",  C["ok"], "200 OK"),
        (4.0,  5.2, "Any Auth\n(Bearer)",   C["auth"],
         "chat\npod-activation\n/my-* routes",   C["ok"], "200 OK"),
        (7.0,  5.2, "admin or\nglobal_admin",C["admin"],
         "list-users\ncreate-user\npod/requests",C["ok"], "200 OK"),
        (10.5, 5.2, "global_admin\nonly",   C["ga"],
         "set-user-role\npod/reject",             C["ok"], "200 OK"),
    ]

    for (x, y, req, col, endpoints, rc, rs) in branches:
        rbox(ax, x, y, 2.3, 0.65, col, req, fs=8.5, bold=True, radius=0.06)
        arr(ax, 6.5 + (x-6.5)*0.45, 6.05, x, y+0.32, col, lw=1.8)

        # Endpoint list
        rbox(ax, x, 3.9, 2.3, 0.85, col, endpoints, fs=7.5,
             alpha=0.85, radius=0.06)
        arr(ax, x, 4.87, x, 4.32, col, lw=1.5)

        # role check diamond
        if req != "No Auth\nRequired":
            diamond(ax, x, 2.85, 2.3, 0.8, "#34495e",
                    "Role\nmatches?", fs=8)
            arr(ax, x, 3.47, x, 3.25, col, lw=1.5)
            # YES
            rbox(ax, x, 1.8, 1.8, 0.45, C["ok"], "200 OK", fs=8.5, bold=True)
            arr(ax, x - 0.5, 2.45, x - 0.5, 2.02, C["ok"],
                lw=1.5, label="Yes")
            # NO
            rbox(ax, x + 0.9, 2.85, 1.5, 0.45, C["no"],
                 "403 Forbidden", fs=8, bold=True)
            arr(ax, x + 1.15, 2.85, x + 1.15, 2.85, C["no"])
            arr(ax, x + 1.15, 2.85, x + 0.9 + 0.75, 2.85, C["no"], label="No")
        else:
            rbox(ax, x, 2.85, 2.0, 0.5, C["ok"],
                 "200 OK\n(no auth check)", fs=8, bold=True)
            arr(ax, x, 3.47, x, 3.1, C["ok"], lw=1.5)

    # Device token note
    rbox(ax, 6.5, 0.6, 7.0, 0.45, C["dev"],
         "Device endpoints use x_device_token header (not Bearer JWT)",
         fs=8.5, bold=True)

    return save_fig(fig, "A3_role_enforcement")


# =============================================================================
# DIAGRAM A4 — Middleware Chain
# =============================================================================
def diag_middleware_chain():
    fig, ax = plt.subplots(figsize=(13, 9))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 9); ax.axis("off")
    ax.set_title("FastAPI Middleware Chain & App Setup", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    # Left: middleware stack
    group_box(ax, 0.3, 0.4, 5.8, 8.2, C["mw"], "Middleware Stack (factory.py)")

    stack = [
        (3.2, 7.9, C["mw"],   "1. CORSMiddleware",
         "allow_origins=['*']\nallow_credentials=True\nallow_methods=['*']\nallow_headers=['*']"),
        (3.2, 6.5, C["mw"],   "2. RequestLoggingMiddleware",
         "Assigns request_id (UUID)\nLogs: method, path, client_ip\nLogs response: status_code, duration_ms"),
        (3.2, 5.2, C["auth"],  "3. Auth (per-route dependency)",
         "verify_user(authorization)\nCalls Supabase /auth/v1/user\nRaises 401 if invalid"),
        (3.2, 3.9, C["role"],  "4. Role Check (per-route)",
         "_get_requester_role()\nFetches from user_roles table\n_require_admin() or specific role check"),
        (3.2, 2.7, C["route"], "5. Route Handler",
         "Business logic executes\nDB reads/writes via PostgREST\nLLM calls via litellm"),
        (3.2, 1.5, C["hdr"],   "6. Exception Handler (global)",
         "Catches HTTPException\nReturns: { 'error': exc.detail }\nStatus code preserved"),
    ]

    for (x, y, col, title, desc) in stack:
        rbox(ax, x, y, 5.2, 0.75, col, f"{title}\n{desc}", fs=7.8, radius=0.06)
        if y < 7.9:
            arr(ax, x, y + 0.375 + 0.18, x, y + 0.375 + 0.62, col, lw=2)

    # Right: router table
    group_box(ax, 6.6, 0.4, 6.1, 8.2, C["route"], "Registered Routers (factory.py)")

    routers = [
        (C["ok"],    "health_router",         "GET /health\nGET /api/llm-health\nGET /api/llm-health/providers"),
        (C["fe"],    "chat_router",            "POST /api/chat  (SSE stream)"),
        (C["fe"],    "help_router",            "POST /api/help-assistant"),
        (C["fe"],    "workflow_router",        "POST /api/workflow-ai"),
        (C["dev"],   "device_router",          "GET/POST /api/device-*\nGET/POST /api/devices/pairing/*"),
        (C["dev"],   "federated_router",       "GET/POST /api/federated-learning"),
        (C["admin"], "admin_router",           "GET/POST /api/list-users\n/api/admin-create-user\n/api/admin-set-user-role"),
        (C["role"],  "pod_activation_router",  "GET/POST/DELETE /api/pod-activation/*"),
    ]

    for i, (col, name, routes) in enumerate(routers):
        y = 7.7 - i * 0.93
        rbox(ax, 9.65, y, 5.7, 0.75, col, f"{name}\n{routes}", fs=7.5, radius=0.05)

    # Arrow connecting middleware → routers
    arr(ax, 6.15, 4.6, 6.55, 4.6, C["route"], lw=2.5, label="routes to")

    # Docker/Server info
    rbox(ax, 6.5, 0.05, 12.5, 0.4, C["hdr"],
         "gunicorn main:app  --bind 0.0.0.0:8080  --workers 4  --worker-class uvicorn.workers.UvicornWorker",
         fs=7.8, bold=True)

    return save_fig(fig, "A4_middleware_chain")


# =============================================================================
# DIAGRAM A5 — Complete API Endpoint Map
# =============================================================================
def diag_endpoint_map():
    fig, ax = plt.subplots(figsize=(14, 12))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 14); ax.set_ylim(0, 12); ax.axis("off")
    ax.set_title("Complete API Endpoint Map — Auth Requirements", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    # Column headers
    hdrs = ["Method", "Path", "Auth", "Min Role", "Description"]
    col_x = [0.5, 1.45, 6.5, 8.3, 10.0]
    col_w = [0.85, 4.9, 1.65, 1.6, 3.8]

    endpoints = [
        # method,  path,                              auth,    role,         desc,                         group
        ("GET",  "/health",                          "None",  "-",          "Basic health check",          "HEALTH"),
        ("GET",  "/api/llm-health",                  "None",  "-",          "LLM provider status",         "HEALTH"),
        ("GET",  "/api/llm-health/providers",        "None",  "-",          "Detailed provider probes",    "HEALTH"),
        ("POST", "/api/chat",                        "Bearer","Any auth",   "Stream chat (SSE)",           "CHAT"),
        ("POST", "/api/help-assistant",              "None",  "-",          "Help assistant stream",       "HELP"),
        ("POST", "/api/workflow-ai",                 "None",  "-",          "Workflow parse / assist",     "WORKFLOW"),
        ("GET",  "/api/device-models",               "Device","x_device",   "List device models",          "DEVICE"),
        ("POST", "/api/device-checkin",              "Device","x_device",   "Device check-in",             "DEVICE"),
        ("POST", "/api/device-register",             "None",  "-",          "Register device",             "DEVICE"),
        ("POST", "/api/devices/pairing/start",       "Bearer","Any auth",   "Initiate device pairing",     "DEVICE"),
        ("GET",  "/api/devices/pairing/status/{id}", "Bearer","Any auth",   "Get pairing status",          "DEVICE"),
        ("POST", "/api/devices/pairing/confirm",     "None",  "-",          "Confirm device pairing",      "DEVICE"),
        ("GET/POST","/api/federated-learning",       "Device","x_device",   "Federated learning ops",      "FEDERATED"),
        ("GET",  "/api/pod-activation/my-activations","Bearer","Any auth",  "My activated pods",           "POD"),
        ("GET",  "/api/pod-activation/my-requests",  "Bearer","Any auth",   "My pod requests",             "POD"),
        ("POST", "/api/pod-activation/request",      "Bearer","Any auth",   "Create activation request",   "POD"),
        ("GET",  "/api/pod-activation/requests",     "Bearer","admin+",     "All requests (admin)",        "POD"),
        ("POST", "/api/pod-activation/{id}/approve", "Bearer","admin+",     "Approve request",             "POD"),
        ("POST", "/api/pod-activation/{id}/reject",  "Bearer","global_admin","Reject request",             "POD"),
        ("GET",  "/api/pod-activation/user/{id}/activations","Bearer","admin+","User activations",         "POD"),
        ("POST", "/api/pod-activation/allocate",     "Bearer","admin+",     "Allocate model to user",      "POD"),
        ("DELETE","/api/pod-activation/allocations/{id}","Bearer","admin+", "Deallocate model",            "POD"),
        ("GET",  "/api/list-users",                  "Bearer","admin+",     "List all users with roles",   "ADMIN"),
        ("POST", "/api/admin-create-user",           "Bearer","admin+",     "Create or update user",       "ADMIN"),
        ("POST", "/api/admin-set-user-role",         "Bearer","global_admin","Set user role",              "ADMIN"),
    ]

    group_colors = {
        "HEALTH":   C["ok"],    "CHAT":     C["fe"],
        "HELP":     C["fe"],    "WORKFLOW": C["fe"],
        "DEVICE":   C["dev"],   "FEDERATED":C["dev"],
        "POD":      C["role"],  "ADMIN":    C["ga"],
    }
    auth_colors = {
        "None":   C["grey"],  "Bearer": C["auth"],
        "Device": C["dev"],
    }
    role_colors = {
        "-":           C["grey"],
        "Any auth":    C["user"],
        "x_device":    C["dev"],
        "admin+":      C["admin"],
        "global_admin":C["ga"],
    }
    method_colors = {
        "GET":    "#2980b9",  "POST": "#27ae60",
        "DELETE": "#c0392b",  "GET/POST": "#8e44ad",
    }

    # Header row
    for hdr, x, w in zip(hdrs, col_x, col_w):
        rbox(ax, x + w/2, 11.55, w - 0.06, 0.4, C["hdr"], hdr, fs=9, bold=True, radius=0.03)

    row_h = 0.4
    last_group = None
    offset = 0

    for i, (method, path, auth, role, desc, group) in enumerate(endpoints):
        if group != last_group:
            if last_group is not None:
                ax.axhline(y=11.15 - (i + offset - 0.5) * row_h,
                           xmin=0.02, xmax=0.98, color="#bbb", lw=0.8, ls="-")
            gc = group_colors[group]
            ax.text(0.08, 11.15 - (i + offset) * row_h - row_h/2,
                    group, fontsize=7.5, color=gc, fontweight="bold",
                    va="center", rotation=90)
            last_group = group

        y = 11.15 - (i + offset) * row_h
        bg = "#f0f8ff" if i % 2 == 0 else "white"

        for xi, w in zip(col_x, col_w):
            ax.add_patch(plt.Rectangle((xi, y - row_h), w - 0.04, row_h,
                                       fc=bg, ec=C["border"], lw=0.4, zorder=2))

        mc = method_colors.get(method, "#555")
        ax.text(col_x[0] + col_w[0]/2, y - row_h/2, method,
                ha="center", va="center", fontsize=7.2, color=mc,
                fontweight="bold", zorder=3)

        ax.text(col_x[1] + 0.05, y - row_h/2, path,
                ha="left", va="center", fontsize=7, color="#1a1a2e",
                fontfamily="monospace", zorder=3)

        ac = auth_colors.get(auth, "#555")
        rbox(ax, col_x[2] + col_w[2]/2, y - row_h/2,
             col_w[2] - 0.14, row_h - 0.08, ac,
             auth, fs=7, radius=0.04, zorder=3)

        rc = role_colors.get(role, "#555")
        rbox(ax, col_x[3] + col_w[3]/2, y - row_h/2,
             col_w[3] - 0.14, row_h - 0.08, rc,
             role, fs=7, radius=0.04, zorder=3)

        ax.text(col_x[4] + 0.05, y - row_h/2, desc,
                ha="left", va="center", fontsize=7.2, color="#333", zorder=3)

    # Legend
    leg = [mpatches.Patch(fc=c, label=l) for l, c in [
        ("No Auth", C["grey"]), ("Bearer JWT", C["auth"]),
        ("Device Token", C["dev"]),
        ("Any authenticated", C["user"]),
        ("admin / global_admin", C["admin"]),
        ("global_admin only", C["ga"]),
    ]]
    ax.legend(handles=leg, loc="lower right", fontsize=7.8, ncol=3,
              framealpha=0.9, title="Auth & Role Legend", title_fontsize=8)

    return save_fig(fig, "A5_endpoint_map")


# =============================================================================
# DIAGRAM A6 — LLM Provider Fallback Chain
# =============================================================================
def diag_llm_fallback():
    fig, ax = plt.subplots(figsize=(13, 9))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 9); ax.axis("off")
    ax.set_title("LLM Provider Fallback Chain — /api/chat Route", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    providers = [
        (2.0, 7.5, "#e67e22", "1. Groq (Primary)",
         "Model: llama-3.3-70b-versatile\nURL: api.groq.com/openai/v1/\nFastest · Cloud hosted"),
        (2.0, 5.8, "#8e44ad", "2. RunPod Llama (Secondary)",
         "Model: Meta-Llama-3.1-8B-Instruct\nURL: RUNPOD_GENERATE_URL\nPrivate deployment"),
        (2.0, 4.1, "#2980b9", "3. RunPod Mistral (Tertiary)",
         "Model: Mistral-7B-Instruct-v0.3\nURL: RUNPOD_OPENAI_COMPAT_URL\nOpenAI-compat API"),
        (2.0, 2.4, "#16a085", "4. Fallback Services",
         "Gemini (gemini-1.5-flash)\nOpenAI (gpt-4o-mini)\nClaude (claude-3-5-sonnet)"),
        (2.0, 0.9, "#7f8c8d", "5. Offline Fallback",
         "OFFLINE_LLM_FALLBACK_ENABLED=true\nLocal model or cached response"),
    ]

    for (x, y, col, title, desc) in providers:
        rbox(ax, x, y, 3.2, 0.95, col, f"{title}\n{desc}", fs=8, radius=0.07, bold=False)

    # Arrows with failure labels
    for i in range(len(providers) - 1):
        y1 = providers[i][1] - 0.47
        y2 = providers[i+1][1] + 0.47
        arr(ax, 2.0, y1, 2.0, y2, C["no"], lw=2.0,
            label="  fail / timeout\n  try next  ", lfs=7.5,
            lpad=(0.7, 0.0))

    # Success path
    rbox(ax, 8.5, 7.5, 4.0, 0.65, C["ok"],
         "Streaming SSE Response\nreturned to client", fs=9.5, bold=True)
    arr(ax, 3.6, 7.5, 6.5, 7.5, C["ok"], lw=2.5, label="success")

    for i in range(1, 4):
        arr(ax, 3.6, providers[i][1], 6.5, 7.5, C["ok"],
            lw=1.5, label="", rad=0.2)

    # Config vars box
    group_box(ax, 6.0, 0.2, 6.5, 6.8, C["hdr"], "Environment Config Variables")
    env_vars = [
        ("GROQ_API_KEY",              "Groq API key"),
        ("GROQ_MODEL_CHAT",           "llama-3.3-70b-versatile"),
        ("RUNPOD_API_KEY",            "RunPod API key (or FIDEON_SECRET_KEY)"),
        ("RUNPOD_GENERATE_URL",       "RunPod /generate endpoint URL"),
        ("RUNPOD_OPENAI_COMPAT_URL",  "RunPod OpenAI-compat URL"),
        ("GEMINI_API_KEY",            "Google Gemini API key"),
        ("GEMINI_MODEL",              "gemini-1.5-flash"),
        ("OPENAI_API_KEY",            "OpenAI API key"),
        ("ANTHROPIC_API_KEY",         "Claude API key"),
        ("LLM_CACHE_BACKEND",         "local | redis | momento"),
        ("OFFLINE_LLM_FALLBACK_ENABLED","true | false"),
    ]
    for j, (k, v) in enumerate(env_vars):
        y = 6.6 - j * 0.54
        ax.text(6.2, y, k, fontsize=7.5, color="#1a1a2e",
                fontfamily="monospace", fontweight="bold", va="center")
        ax.text(6.2, y - 0.18, v, fontsize=7, color="#666",
                style="italic", va="center")

    return save_fig(fig, "A6_llm_fallback")


# =============================================================================
# DIAGRAM A7 — Device Authentication Flow
# =============================================================================
def diag_device_auth():
    fig, ax = plt.subplots(figsize=(13, 10))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("Device Authentication — Token & Pairing Flow", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    # Left column: device token auth
    group_box(ax, 0.2, 0.3, 5.8, 9.3, C["dev"], "Device Token Auth  (x_device_token)")

    rbox(ax, 3.1, 8.9, 4.8, 0.5, C["dev"],
         "Device sends: Header  x_device_token: <token>", fs=8.5, bold=True)
    diamond(ax, 3.1, 7.9, 4.4, 0.9, "#2c3e50",
            "device_token present\nin request header?", fs=8.5)
    arr(ax, 3.1, 8.65, 3.1, 8.35)

    rbox(ax, 5.5, 7.9, 1.6, 0.45, C["no"], "401 Unauthorized", fs=8)
    arr(ax, 5.3, 7.9, 5.35, 7.9, C["no"], label="No")

    rbox(ax, 3.1, 6.8, 4.8, 0.6, C["supa"],
         "SELECT * FROM devices\nWHERE device_token = <token>", fs=8.5, bold=True)
    arr(ax, 3.1, 7.45, 3.1, 7.1, C["dev"], label="Yes")

    diamond(ax, 3.1, 5.7, 4.4, 0.9, "#2c3e50",
            "Device found AND\nstatus = active?", fs=8.5)
    arr(ax, 3.1, 6.5, 3.1, 6.15)

    rbox(ax, 5.5, 5.7, 1.6, 0.45, C["no"], "401 Unauthorized", fs=8)
    arr(ax, 5.3, 5.7, 5.35, 5.7, C["no"], label="No")

    rbox(ax, 3.1, 4.7, 4.8, 0.55, C["ok"],
         "Device context passed to route handler", fs=8.5, bold=True)
    arr(ax, 3.1, 5.25, 3.1, 4.98, C["ok"], label="Yes")

    rbox(ax, 3.1, 3.7, 4.8, 0.65, C["dev"],
         "POST /api/device-checkin\nUpdates: last_checkin, online=True\nLogs sync event", fs=8)
    arr(ax, 3.1, 4.42, 3.1, 4.03)

    rbox(ax, 3.1, 2.7, 4.8, 0.65, C["dev"],
         "GET /api/device-models\nReturns assigned model list\nWith metadata", fs=8)

    rbox(ax, 3.1, 1.7, 4.8, 0.65, C["dev"],
         "GET/POST /api/federated-learning\nSubmit gradients, feedback\nGet training jobs", fs=8)

    # Right column: pairing flow
    group_box(ax, 6.5, 0.3, 6.1, 9.3, C["auth"], "Device Pairing Flow  (QR Code / URL)")

    pair_steps = [
        (9.55, 9.0, C["fe"],    "User on frontend initiates pairing"),
        (9.55, 8.2, C["route"], "POST /api/devices/pairing/start\nBody: expires_in_seconds, device_profile\nReturns: pairing_id, pairing_code, pairing_url"),
        (9.55, 7.1, C["dev"],   "Frontend shows QR code or URL\nUser scans with physical device"),
        (9.55, 6.0, C["dev"],   "Device calls\nPOST /api/devices/pairing/confirm\nBody: pairing_id, pairing_code,\ndevice_name, os_type"),
        (9.55, 4.9, C["supa"],  "Backend verifies: HMAC-SHA256\npairing_code_hash matches\nExpiry not exceeded"),
        (9.55, 3.8, C["ok"],    "Device token generated\nSaved to devices table\nReturns: device_token, login_link"),
        (9.55, 2.7, C["auth"],  "GET /api/devices/pairing/status/{id}\nPolled by frontend\nReturns pairing status"),
        (9.55, 1.6, C["ok"],    "Pairing complete\nDevice now uses x_device_token\nfor all subsequent calls"),
    ]
    for i, (x, y, col, txt) in enumerate(pair_steps):
        rbox(ax, x, y, 5.5, 0.65, col, txt, fs=7.8, radius=0.06)
        if i < len(pair_steps) - 1:
            arr(ax, x, y - 0.32, x, pair_steps[i+1][1] + 0.32, col, lw=1.8)

    return save_fig(fig, "A7_device_auth")


# =============================================================================
# DIAGRAM A8 — Error Response Handling
# =============================================================================
def diag_error_handling():
    fig, ax = plt.subplots(figsize=(13, 9))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 9); ax.axis("off")
    ax.set_title("Error Response Handling — HTTP Status Codes", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    # Global exception handler
    rbox(ax, 6.5, 8.5, 7.0, 0.55, C["hdr"],
         "Global Exception Handler:  @app.exception_handler(HTTPException)",
         fs=9.5, bold=True)
    rbox(ax, 6.5, 7.75, 6.5, 0.55, "#34495e",
         "Returns: JSONResponse(status_code=exc.status_code, content={\"error\": exc.detail})",
         fs=8.5, bold=True)
    arr(ax, 6.5, 8.22, 6.5, 8.02)

    codes = [
        (1.3,  6.1, "200 OK",            C["ok"],
         "Request succeeded\nData returned normally"),
        (3.1,  6.1, "400 Bad Request",   C["warn"],
         "Missing params\nInvalid body data\nValidation error"),
        (4.9,  6.1, "401 Unauthorized",  "#e74c3c",
         "No Bearer token\nInvalid / expired JWT\nSupabase auth failed"),
        (6.7,  6.1, "402 Payment Req",   "#f39c12",
         "LLM provider billing\nissue (credits exhausted)"),
        (8.5,  6.1, "403 Forbidden",     C["no"],
         "Role too low\nEndpoint requires\nhigher privilege"),
        (10.3, 6.1, "404 Not Found",     C["grey"],
         "Resource doesn't exist\nDevice not found\nUser not found"),
        (12.1, 6.1, "409 Conflict",      "#9b59b6",
         "Duplicate resource\nAlready exists\n(e.g. duplicate request)"),
    ]
    for (x, y, code, col, desc) in codes:
        rbox(ax, x, y, 1.55, 1.1, col, f"{code}\n\n{desc}", fs=7.5, radius=0.07)
        arr(ax, x, 7.47, x, y + 0.55, col, lw=1.8)

    # Lower row
    codes2 = [
        (3.0,  3.8, "429 Rate Limited",  "#e67e22",
         "Provider rate limit hit\nToo many requests"),
        (6.5,  3.8, "500 Internal Error",C["no"],
         "Database error\nProvider failure\nUnhandled exception"),
    ]
    for (x, y, code, col, desc) in codes2:
        rbox(ax, x, y, 2.8, 0.95, col, f"{code}\n{desc}", fs=8, radius=0.07)

    # Response format
    rbox(ax, 9.5, 3.8, 5.5, 1.5, "#2c3e50",
         "Standard Error Response Format:\n\n"
         "HTTP/1.1 <status_code>\n"
         "Content-Type: application/json\n\n"
         "{\n"
         "    \"error\": \"<human-readable detail>\"\n"
         "}",
         fs=8.5, radius=0.07)

    # PII scrubbing section
    group_box(ax, 0.3, 0.2, 12.1, 2.8, C["mw"], "PII Scrubbing in Logs (logger/__init__.py)")
    redacted = ["password", "token", "api_key", "ssn", "credit_card",
                "dob", "phone", "address", "secret", "authorization",
                "email (masked)", "x_device_token"]
    ax.text(0.6, 2.55, "Fields automatically redacted in all log output:", fontsize=9,
            fontweight="bold", color=C["mw"])
    for i, f in enumerate(redacted):
        x = 0.7 + (i % 6) * 2.0
        y = 2.0 - (i // 6) * 0.6
        rbox(ax, x, y, 1.7, 0.38, C["mw"], f, fs=7.8, radius=0.04)

    return save_fig(fig, "A8_error_handling")


# =============================================================================
# DIAGRAM A9 — Security Configuration Overview
# =============================================================================
def diag_security():
    fig, ax = plt.subplots(figsize=(13, 9))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 9); ax.axis("off")
    ax.set_title("Security Configuration & Environment Variables", fontsize=15,
                 fontweight="bold", color=C["hdr"], pad=12)

    # CORS
    group_box(ax, 0.3, 6.2, 5.8, 2.5, C["warn"], "CORS Configuration (CORSMiddleware)")
    cors = [
        ("allow_origins",     '["*"]',          C["warn"],  "All origins allowed"),
        ("allow_credentials", "True",            C["warn"],  "Cookies & auth cross-origin"),
        ("allow_methods",     '["*"]',           C["warn"],  "All HTTP methods"),
        ("allow_headers",     '["*"]',           C["warn"],  "All request headers"),
    ]
    for i, (k, v, col, note) in enumerate(cors):
        y = 8.2 - i * 0.5
        ax.text(0.6,  y, k,    fontsize=8, color="#1a1a2e", fontweight="bold",
                fontfamily="monospace", va="center")
        ax.text(3.0,  y, v,    fontsize=8, color=col,
                fontfamily="monospace", va="center")
        ax.text(4.3,  y, f"// {note}", fontsize=7.5, color="#888",
                style="italic", va="center")

    # Supabase keys
    group_box(ax, 6.5, 6.2, 6.1, 2.5, C["supa"], "Supabase Auth Keys (config.py)")
    supa_keys = [
        ("SUPABASE_URL",              "Supabase project URL"),
        ("SUPABASE_ANON_KEY",         "Public anon key (used in token validation)"),
        ("SUPABASE_SERVICE_ROLE_KEY", "Admin key (bypasses RLS — server-side only)"),
    ]
    for i, (k, v) in enumerate(supa_keys):
        y = 8.2 - i * 0.65
        rbox(ax, 9.55, y, 5.6, 0.45, C["supa"], f"{k}\n{v}", fs=7.8, radius=0.05)

    # Auth flow summary
    group_box(ax, 0.3, 3.5, 12.1, 2.4, C["auth"], "Authentication Flow Summary")
    flow_items = [
        ("Frontend", "Supabase Auth SDK\nHandles login/logout\nStores JWT in localStorage", C["fe"]),
        ("JWT Token", "Sent in every request\nHeader: Authorization: Bearer <JWT>", C["auth"]),
        ("Backend", "Calls Supabase /auth/v1/user\nValidates token server-side\nGets user.id", C["route"]),
        ("Role Lookup", "Queries user_roles table\nvia PostgREST API\nGets role string", C["role"]),
        ("Decision", "_require_admin() or\nrole in {'admin','global_admin'}\nor role-specific check", C["admin"]),
    ]
    for i, (title, desc, col) in enumerate(flow_items):
        x = 1.6 + i * 2.35
        rbox(ax, x, 4.65, 2.1, 1.3, col, f"{title}\n\n{desc}", fs=7.8, radius=0.07)
        if i < len(flow_items) - 1:
            arr(ax, x + 1.05, 4.65, x + 1.28, 4.65, col, lw=2.0)

    # No rate limiting notice
    group_box(ax, 0.3, 0.3, 5.8, 2.9, C["no"], "Not Implemented (Security Gaps)")
    gaps = [
        ("Rate Limiting",      "No IP-based throttling"),
        ("Security Headers",   "No CSP, X-Frame, HSTS"),
        ("Input Validation",   "Most routes use raw .json()"),
        ("API Key Rotation",   "Static env var keys"),
    ]
    for i, (g, d) in enumerate(gaps):
        y = 2.7 - i * 0.6
        ax.text(0.6, y, f"X  {g}:", fontsize=8.5, color=C["no"],
                fontweight="bold", va="center")
        ax.text(0.6, y - 0.2, f"   {d}", fontsize=8, color="#666",
                style="italic", va="center")

    # Security positives
    group_box(ax, 6.5, 0.3, 6.1, 2.9, C["ok"], "Security Features Implemented")
    goods = [
        ("PII Scrubbing",        "Logs redact sensitive fields"),
        ("Role-Based Access",    "5-tier RBAC via Supabase RLS"),
        ("Tamper-Evident Logs",  "SHA-256 integrity hashes"),
        ("Non-root Container",   "appuser:1001 in Docker"),
        ("Health Check",         "30s /health endpoint probe"),
    ]
    for i, (g, d) in enumerate(goods):
        y = 2.7 - i * 0.6
        ax.text(6.7, y, f"OK  {g}:", fontsize=8.5, color=C["ok"],
                fontweight="bold", va="center")
        ax.text(6.7, y - 0.2, f"      {d}", fontsize=8, color="#666",
                style="italic", va="center")

    return save_fig(fig, "A9_security")


# =============================================================================
# BUILD PDF
# =============================================================================
def build_pdf(imgs):
    pdf_path = os.path.join(OUT_DIR, "API_Gateway_Walkthrough.pdf")
    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=22*mm, bottomMargin=22*mm,
        title="API Gateway Walkthrough — Fideon OS",
        author="Fideon OS",
    )
    W, H = A4
    cw = W - 36*mm
    styles = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    title_s  = S("TT", fontSize=26, leading=32, alignment=TA_CENTER,
                 textColor=colors.HexColor("#1a1a2e"), fontName="Helvetica-Bold")
    sub_s    = S("TS", fontSize=13, leading=17, alignment=TA_CENTER,
                 textColor=colors.HexColor("#555"), fontName="Helvetica")
    h1_s     = S("H1", fontSize=17, leading=21, fontName="Helvetica-Bold",
                 textColor=colors.HexColor("#1a1a2e"),
                 spaceBefore=14, spaceAfter=6)
    h2_s     = S("H2", fontSize=13, leading=16, fontName="Helvetica-Bold",
                 textColor=colors.HexColor("#16213e"),
                 spaceBefore=10, spaceAfter=4)
    body_s   = S("B2", fontSize=9.5, leading=13.5, fontName="Helvetica",
                 textColor=colors.HexColor("#333"), spaceAfter=5,
                 alignment=TA_JUSTIFY)
    cap_s    = S("CP", fontSize=8.5, leading=11, alignment=TA_CENTER,
                 textColor=colors.HexColor("#666"),
                 fontName="Helvetica-Oblique", spaceAfter=12)
    code_s   = S("CD", fontSize=8, leading=11, fontName="Courier",
                 textColor=colors.HexColor("#1a1a2e"),
                 backColor=colors.HexColor("#f4f4f8"),
                 spaceAfter=6, spaceBefore=3,
                 leftIndent=8, rightIndent=8, borderPadding=4)
    bul_s    = S("BL", fontSize=9.5, leading=14, fontName="Helvetica",
                 textColor=colors.HexColor("#333"),
                 leftIndent=18, spaceAfter=2, bulletIndent=6)

    def img_full(path, caption="", scale=0.95):
        pil = PILImage.open(path)
        pw, ph = pil.size
        ratio = ph / pw
        iw = cw * scale
        ih = iw * ratio
        if ih > H * 0.73:
            ih = H * 0.73
            iw = ih / ratio
        r = [Image(path, width=iw, height=ih, hAlign="CENTER")]
        if caption:
            r.append(Paragraph(caption, cap_s))
        return r

    def hr():
        return HRFlowable(width="100%", thickness=0.8,
                          color=colors.HexColor("#dee2e6"),
                          spaceAfter=8, spaceBefore=4)

    def tbl(data, col_widths, header_color="#1a1a2e", alt="#f0f4ff"):
        ts = TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), colors.HexColor(header_color)),
            ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS",(0,1), (-1,-1),
             [colors.HexColor(alt), colors.white]*30),
            ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#dee2e6")),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ])
        t = Table(data, colWidths=col_widths)
        t.setStyle(ts)
        return t

    story = []

    # ── COVER ─────────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 2.0*cm),
        Paragraph("API Gateway Walkthrough", title_s),
        Spacer(1, 0.2*cm),
        Paragraph("Full Technical Documentation", sub_s),
        Spacer(1, 0.3*cm),
        hr(),
        Paragraph("Project: Fideon OS Platform", sub_s),
        Paragraph("Backend: FastAPI + Uvicorn + Gunicorn", sub_s),
        Paragraph("Auth: Supabase JWT Tokens", sub_s),
        Paragraph("Date: 2026-03-16", sub_s),
        Spacer(1, 0.6*cm),
    ]
    story += img_full(imgs["A1"],
                      "Figure 1 — Full Request Lifecycle Overview", scale=0.88)
    story.append(PageBreak())

    # ── SECTION 1: OVERVIEW ───────────────────────────────────────────────────
    story += [
        Paragraph("1. Architecture Overview", h1_s), hr(),
        Paragraph(
            "The Fideon OS backend is a <b>FastAPI</b> application served by "
            "<b>Gunicorn with 4 Uvicorn workers</b> on port 8080. It acts as the "
            "central API gateway for all platform operations — chat, device management, "
            "pod activation, federated learning, and admin control.",
            body_s),
        Spacer(1, 0.2*cm),
        Paragraph("Technology Stack", h2_s),
    ]
    stack_data = [
        ["Component", "Technology", "Details"],
        ["HTTP Server",     "Gunicorn + Uvicorn",    "4 workers, port 8080, UvicornWorker class"],
        ["Framework",       "FastAPI",               "Python 3.11, async/await throughout"],
        ["Auth Provider",   "Supabase Auth",         "JWT tokens validated server-side"],
        ["Database",        "Supabase PostgreSQL",   "Accessed via PostgREST API + supabase-py"],
        ["LLM Routing",     "litellm",               "Unified interface for all LLM providers"],
        ["Logging",         "structlog",             "JSON-formatted, PII-scrubbed"],
        ["Container",       "Docker",                "Non-root user (appuser:1001)"],
        ["CORS",            "CORSMiddleware",        "allow_origins=[*] (permissive)"],
    ]
    story.append(tbl(stack_data, [3.5*cm, 4.0*cm, 10.5*cm]))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 2: MIDDLEWARE ─────────────────────────────────────────────────
    story += [
        Paragraph("2. Middleware Chain", h1_s), hr(),
        Paragraph(
            "Every HTTP request passes through a <b>two-layer middleware chain</b> before "
            "reaching any route handler. CORS runs first (FastAPI's built-in), followed by "
            "the custom <code>RequestLoggingMiddleware</code>. Auth and role checks happen "
            "inside individual route handlers as dependency-injected functions.",
            body_s),
    ]
    story += img_full(imgs["A4"],
                      "Figure 2 — Middleware Chain & Router Registration", scale=0.97)
    story += [Spacer(1, 0.3*cm)]

    story += [Paragraph("Middleware Execution Order", h2_s)]
    mw_data = [
        ["Order", "Middleware", "Layer", "Responsibility"],
        ["1", "CORSMiddleware",             "Framework built-in",   "Validates Origin, sets CORS headers, handles OPTIONS preflight"],
        ["2", "RequestLoggingMiddleware",   "Custom (logger/)",     "Assigns request_id UUID, logs method+path+IP, logs status+duration"],
        ["3", "verify_user() (per-route)",  "Route dependency",     "Extracts Bearer token, validates against Supabase /auth/v1/user"],
        ["4", "_get_requester_role()",      "Route helper",         "Queries user_roles table for caller's role string"],
        ["5", "_require_admin() / role check","Route logic",        "Raises 403 if role insufficient for the endpoint"],
        ["6", "Route Handler",              "Business logic",       "Executes actual logic: DB reads, LLM calls, response"],
        ["7", "http_exception_handler",     "Global exception",     "Catches HTTPException, returns {\"error\": detail}"],
    ]
    story.append(tbl(mw_data,
                     [1.0*cm, 4.5*cm, 3.5*cm, 9.0*cm]))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 3: JWT AUTH ───────────────────────────────────────────────────
    story += [
        Paragraph("3. JWT Authentication Flow", h1_s), hr(),
        Paragraph(
            "Authentication uses <b>Supabase JWT tokens</b>. The frontend obtains a JWT "
            "after login via the Supabase Auth SDK, and passes it in the "
            "<code>Authorization: Bearer &lt;token&gt;</code> header. The backend "
            "validates the token by calling Supabase's <code>/auth/v1/user</code> endpoint "
            "— it does <b>not</b> verify the JWT signature locally.",
            body_s),
    ]
    story += img_full(imgs["A2"],
                      "Figure 3 — JWT Token Validation Flow", scale=0.92)
    story += [Spacer(1, 0.3*cm)]
    story += [
        Paragraph("verify_user() — Source Code (core/supabase.py)", h2_s),
        Paragraph(
            "async def verify_user(authorization: Optional[str]) -&gt; Dict[str, Any]:<br/>"
            "&nbsp;&nbsp;if not authorization or not authorization.lower().startswith('bearer '):<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;raise HTTPException(status_code=401, detail='Unauthorized')<br/>"
            "&nbsp;&nbsp;token = authorization.split(' ', 1)[1]<br/>"
            "&nbsp;&nbsp;async with httpx.AsyncClient(timeout=30) as client:<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;resp = await client.get(<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;f'{SUPABASE_URL}/auth/v1/user',<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;headers={'apikey': SUPABASE_ANON_KEY,<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'Authorization': f'Bearer {token}'},<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;)<br/>"
            "&nbsp;&nbsp;if resp.status_code &gt;= 400:<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;raise HTTPException(status_code=401, detail='Unauthorized')<br/>"
            "&nbsp;&nbsp;return resp.json()",
            code_s),
        PageBreak(),
    ]

    # ── SECTION 4: ROLE ENFORCEMENT ───────────────────────────────────────────
    story += [
        Paragraph("4. Role Enforcement", h1_s), hr(),
        Paragraph(
            "After JWT validation, the backend fetches the caller's role from the "
            "<code>user_roles</code> Supabase table. Role enforcement is applied "
            "<b>per-endpoint</b> — different routes require different minimum roles.",
            body_s),
    ]
    story += img_full(imgs["A3"],
                      "Figure 4 — Per-Endpoint Role Enforcement Flow", scale=0.95)
    story += [Spacer(1, 0.3*cm)]
    story += [
        Paragraph("Role Check Source Code (routes/admin.py, routes/pod_activation.py)", h2_s),
        Paragraph(
            "async def _get_requester_role(authorization):<br/>"
            "&nbsp;&nbsp;requester = await verify_user(authorization)<br/>"
            "&nbsp;&nbsp;requester_roles = await postgrest_get('user_roles',<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;f'select=role&amp;user_id=eq.{requester[\"id\"]}&amp;limit=1')<br/>"
            "&nbsp;&nbsp;requester_role = requester_roles[0].get('role') if requester_roles else None<br/>"
            "&nbsp;&nbsp;return requester, requester_role<br/><br/>"
            "def _require_admin(role: Optional[str]) -&gt; None:<br/>"
            "&nbsp;&nbsp;if role not in {'admin', 'global_admin'}:<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;raise HTTPException(status_code=403, detail='Admin access required')",
            code_s),
        PageBreak(),
    ]

    # ── SECTION 5: ENDPOINT MAP ───────────────────────────────────────────────
    story += [
        Paragraph("5. Complete API Endpoint Map", h1_s), hr(),
        Paragraph(
            "The platform exposes <b>25 API endpoints</b> across 8 route modules. "
            "Each endpoint has a specific auth requirement: no auth, Bearer JWT, "
            "or device token — plus a minimum role for protected routes.",
            body_s),
    ]
    story += img_full(imgs["A5"],
                      "Figure 5 — All 25 Endpoints with Auth Requirements", scale=0.98)
    story += [Spacer(1, 0.3*cm)]

    story += [Paragraph("Endpoint Summary by Module", h2_s)]
    ep_sum = [
        ["Module", "Router", "Endpoints", "Auth"],
        ["Health",     "health_router",        "3",  "None (public)"],
        ["Chat",       "chat_router",           "1",  "Bearer JWT (any auth)"],
        ["Help",       "help_router",           "1",  "None (public)"],
        ["Workflow",   "workflow_router",       "1",  "None (public)"],
        ["Device",     "device_router",         "6",  "Bearer JWT or x_device_token"],
        ["Federated",  "federated_router",      "1",  "x_device_token"],
        ["Pod Activation","pod_activation_router","9","Bearer JWT (role varies)"],
        ["Admin",      "admin_router",          "3",  "Bearer JWT (admin+)"],
    ]
    story.append(tbl(ep_sum,
                     [3.0*cm, 4.5*cm, 2.5*cm, 8.0*cm]))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 6: LLM FALLBACK ───────────────────────────────────────────────
    story += [
        Paragraph("6. LLM Provider Fallback Chain", h1_s), hr(),
        Paragraph(
            "The <code>/api/chat</code> endpoint uses <b>litellm</b> to route requests "
            "through a waterfall of LLM providers. If the primary provider fails "
            "(timeout, rate limit, error), the next provider is tried automatically. "
            "All responses are streamed back to the client as <b>Server-Sent Events (SSE)</b>.",
            body_s),
    ]
    story += img_full(imgs["A6"],
                      "Figure 6 — LLM Provider Fallback Chain", scale=0.95)
    story += [Spacer(1, 0.3*cm)]
    story += [Paragraph("Provider Priority Order", h2_s)]
    llm_data = [
        ["Priority", "Provider",       "Model",                         "URL / Service"],
        ["1 (Primary)",  "Groq",       "llama-3.3-70b-versatile",       "api.groq.com/openai/v1/"],
        ["2",            "RunPod Llama","Meta-Llama-3.1-8B-Instruct",   "RUNPOD_GENERATE_URL"],
        ["3",            "RunPod Mistral","Mistral-7B-Instruct-v0.3",   "RUNPOD_OPENAI_COMPAT_URL"],
        ["4a",           "Gemini",      "gemini-1.5-flash",              "generativelanguage.googleapis.com"],
        ["4b",           "OpenAI",      "gpt-4o-mini",                   "api.openai.com/v1/"],
        ["4c",           "Claude",      "claude-3-5-sonnet-20241022",    "api.anthropic.com/v1/messages"],
        ["5 (Offline)",  "Fallback Svc","(local/cached)",               "OFFLINE_LLM_FALLBACK_ENABLED=true"],
    ]
    story.append(tbl(llm_data,
                     [2.5*cm, 3.0*cm, 5.5*cm, 7.0*cm]))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 7: DEVICE AUTH ────────────────────────────────────────────────
    story += [
        Paragraph("7. Device Authentication & Pairing", h1_s), hr(),
        Paragraph(
            "Physical devices (AI edge boxes) use a separate authentication mechanism: "
            "<b>device tokens</b> passed via the <code>x_device_token</code> header. "
            "Devices are paired to user accounts via a QR-code / URL-based pairing flow.",
            body_s),
    ]
    story += img_full(imgs["A7"],
                      "Figure 7 — Device Token & Pairing Flow", scale=0.95)
    story += [Spacer(1, 0.3*cm)]
    story += [
        Paragraph("Device Token vs JWT Token", h2_s),
    ]
    token_data = [
        ["Property",      "Bearer JWT Token",                  "x_device_token"],
        ["Used by",       "Browser / Frontend (users)",        "Physical edge devices"],
        ["Header",        "Authorization: Bearer <token>",     "x_device_token: <token>"],
        ["Issued by",     "Supabase Auth (login)",             "Backend (pairing confirm)"],
        ["Validated via", "GET /auth/v1/user (Supabase)",      "DB lookup in devices table"],
        ["Endpoints",     "chat, pod-activation, admin, pairing","device-models, checkin, federated"],
        ["Expiry",        "Supabase session TTL",              "Stored in DB, revocable"],
    ]
    story.append(tbl(token_data,
                     [3.5*cm, 6.5*cm, 8.0*cm]))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 8: ERROR HANDLING ─────────────────────────────────────────────
    story += [
        Paragraph("8. Error Response Handling", h1_s), hr(),
        Paragraph(
            "All errors are handled by a <b>global exception handler</b> registered in "
            "<code>factory.py</code>. Every error returns a consistent JSON body. "
            "Sensitive fields are never included in error messages — they are scrubbed "
            "from all log output by the PII scrubber.",
            body_s),
    ]
    story += img_full(imgs["A8"],
                      "Figure 8 — Error Handling & Status Code Reference", scale=0.95)
    story += [Spacer(1, 0.3*cm)]
    story += [Paragraph("HTTP Status Code Reference", h2_s)]
    err_data = [
        ["Status", "Meaning",          "When It Occurs"],
        ["200",    "OK",               "Request succeeded normally"],
        ["400",    "Bad Request",      "Missing/invalid parameters, validation error"],
        ["401",    "Unauthorized",     "No Bearer token, invalid JWT, Supabase auth failed"],
        ["402",    "Payment Required", "LLM provider billing issue (credits exhausted)"],
        ["403",    "Forbidden",        "User role is too low for this endpoint"],
        ["404",    "Not Found",        "Resource not found (device, user, request)"],
        ["409",    "Conflict",         "Duplicate resource (e.g. duplicate pod request)"],
        ["429",    "Rate Limited",     "LLM provider rate limit hit"],
        ["500",    "Internal Error",   "Database failure, provider error, unhandled exception"],
    ]
    story.append(tbl(err_data,
                     [1.8*cm, 3.5*cm, 13.2*cm]))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 9: SECURITY ───────────────────────────────────────────────────
    story += [
        Paragraph("9. Security Configuration", h1_s), hr(),
        Paragraph(
            "This section summarises the security posture of the API gateway — "
            "what protections are in place and which gaps exist.",
            body_s),
    ]
    story += img_full(imgs["A9"],
                      "Figure 9 — Security Configuration Overview", scale=0.95)
    story += [Spacer(1, 0.3*cm)]

    story += [Paragraph("Environment Variables Reference", h2_s)]
    env_data = [
        ["Variable",                     "Purpose",                        "Required"],
        ["SUPABASE_URL",                  "Supabase project endpoint",      "Yes"],
        ["SUPABASE_ANON_KEY",             "Token validation key",           "Yes"],
        ["SUPABASE_SERVICE_ROLE_KEY",     "Admin DB operations",            "Yes"],
        ["GROQ_API_KEY",                  "Primary LLM provider",           "Yes"],
        ["RUNPOD_API_KEY / FIDEON_SECRET_KEY","RunPod access",             "Optional"],
        ["RUNPOD_GENERATE_URL",           "RunPod /generate endpoint",      "Optional"],
        ["GEMINI_API_KEY",                "Gemini fallback",                "Optional"],
        ["OPENAI_API_KEY",                "OpenAI fallback",                "Optional"],
        ["ANTHROPIC_API_KEY",             "Claude fallback",                "Optional"],
        ["LLM_CACHE_BACKEND",             "local | redis | momento",        "Optional"],
        ["OFFLINE_LLM_FALLBACK_ENABLED",  "Enable offline fallback",        "Optional"],
    ]
    story.append(tbl(env_data,
                     [5.5*cm, 7.0*cm, 5.5*cm]))
    story += [Spacer(1, 0.5*cm)]

    story += [
        hr(),
        Paragraph(
            "<i>API Gateway Walkthrough — Fideon OS. "
            "Generated 2026-03-16 from live codebase analysis.</i>",
            cap_s),
    ]

    doc.build(story)
    return pdf_path


# =============================================================================
if __name__ == "__main__":
    print("Generating API Gateway diagrams...")
    imgs = {
        "A1": diag_request_lifecycle(),
        "A2": diag_jwt_auth(),
        "A3": diag_role_enforcement(),
        "A4": diag_middleware_chain(),
        "A5": diag_endpoint_map(),
        "A6": diag_llm_fallback(),
        "A7": diag_device_auth(),
        "A8": diag_error_handling(),
        "A9": diag_security(),
    }
    print(f"  Generated {len(imgs)} diagrams in {IMG_DIR}")
    print("Building PDF...")
    pdf = build_pdf(imgs)
    print(f"\nDone: {pdf}")
