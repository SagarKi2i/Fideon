"""
Generate Activity Logs Feature Documentation PDF
with fully rendered PNG diagrams using matplotlib + reportlab
"""

import os
import sys
import math
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as mpatch
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, ArrowStyle
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import Flowable
from PIL import Image as PILImage
import io

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(OUT_DIR, "_diagram_imgs")
os.makedirs(IMG_DIR, exist_ok=True)

# ─── COLOR PALETTE ────────────────────────────────────────────────────────────
C = {
    "ga":     "#c0392b",   # global_admin  red
    "admin":  "#e67e22",   # admin         orange
    "user":   "#27ae60",   # user          green
    "viewer": "#2980b9",   # viewer        blue
    "guest":  "#95a5a6",   # guest         grey
    "bg":     "#f8f9fa",
    "header": "#1a1a2e",
    "accent": "#16213e",
    "tbl":    "#0f3460",
    "row1":   "#e8f4fd",
    "row2":   "#ffffff",
    "border": "#dee2e6",
    "ok":     "#27ae60",
    "no":     "#c0392b",
    "db":     "#8e44ad",
    "api":    "#2c3e50",
    "fe":     "#1abc9c",
    "hash":   "#d35400",
}

def save_fig(fig, name, dpi=150):
    path = os.path.join(IMG_DIR, f"{name}.png")
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path

def rounded_box(ax, x, y, w, h, color, text, fontsize=9, text_color="white",
                radius=0.04, bold=False, border=None, zorder=3):
    fc = FancyBboxPatch((x - w/2, y - h/2), w, h,
                        boxstyle=f"round,pad=0,rounding_size={radius}",
                        facecolor=color, edgecolor=border or color,
                        linewidth=1.2, zorder=zorder)
    ax.add_patch(fc)
    weight = "bold" if bold else "normal"
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            color=text_color, weight=weight, zorder=zorder+1,
            wrap=True, multialignment="center")

def arrow(ax, x1, y1, x2, y2, color="#555555", lw=1.5, style="->", label="", zorder=2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw),
                zorder=zorder)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx+0.01, my+0.015, label, fontsize=7, color=color, zorder=zorder+1)

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 1 — Role Hierarchy
# ══════════════════════════════════════════════════════════════════════════════
def diag_role_hierarchy():
    fig, ax = plt.subplots(figsize=(11, 7))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 10); ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("Role Hierarchy — Fideon OS", fontsize=16, fontweight="bold",
                 color=C["header"], pad=14)

    roles = [
        (5.0, 6.0, C["ga"],    "global_admin\n[GA] Full system access\nCan manage all roles", 1.8, 0.75),
        (5.0, 4.5, C["admin"], "admin\n[AD] Tenant administrator\nManage users & approve pods", 1.8, 0.75),
        (2.5, 3.0, C["user"],  "user\n[US] Standard user\nUse models & view own logs",  1.7, 0.75),
        (5.0, 3.0, C["viewer"],"viewer\n[VW] Read-only user\nView but not act",           1.7, 0.75),
        (7.5, 3.0, C["guest"], "guest\n[GS] Limited access\nNo activity page",             1.7, 0.75),
    ]
    for (x, y, col, txt, w, h) in roles:
        rounded_box(ax, x, y, w, h, col, txt, fontsize=9, bold=True, radius=0.08)

    # arrows
    conns = [
        (5.0, 5.625, 5.0, 4.875, C["ga"],    ""),
        (5.0, 4.125, 2.5, 3.375, C["admin"], "can manage"),
        (5.0, 4.125, 5.0, 3.375, C["admin"], ""),
        (5.0, 4.125, 7.5, 3.375, C["admin"], ""),
        (4.0, 6.0,   2.5, 3.375, C["ga"],    "can promote"),
        (6.0, 6.0,   7.5, 3.375, C["ga"],    "can demote"),
    ]
    for (x1,y1,x2,y2,col,lbl) in conns:
        arrow(ax, x1, y1, x2, y2, col, lw=2, label=lbl)

    # legend
    legend_items = [
        mpatches.Patch(facecolor=C["ga"],    label="global_admin"),
        mpatches.Patch(facecolor=C["admin"], label="admin"),
        mpatches.Patch(facecolor=C["user"],  label="user"),
        mpatches.Patch(facecolor=C["viewer"],label="viewer"),
        mpatches.Patch(facecolor=C["guest"], label="guest"),
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=9, framealpha=0.7)
    return save_fig(fig, "01_role_hierarchy")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 2 — ER Diagram
# ══════════════════════════════════════════════════════════════════════════════
def diag_er():
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 14); ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Entity-Relationship Diagram — Activity Logs System", fontsize=15,
                 fontweight="bold", color=C["header"], pad=12)

    def entity(x, y, title, fields, w=2.4, color="#1a1a2e"):
        row_h = 0.28
        total_h = 0.38 + len(fields) * row_h
        # header
        hdr = FancyBboxPatch((x - w/2, y - 0.19), w, 0.38,
                              boxstyle="round,pad=0,rounding_size=0.04",
                              facecolor=color, edgecolor=color, linewidth=1.5, zorder=3)
        ax.add_patch(hdr)
        ax.text(x, y, title, ha="center", va="center", fontsize=9,
                color="white", fontweight="bold", zorder=4)
        # body
        body_y = y - 0.19
        for i, (fname, ftype, pk) in enumerate(fields):
            fy = body_y - (i+0.5)*row_h
            bg = "#f0f4ff" if pk else ("#fffdf0" if "FK" in ftype else "white")
            rect = plt.Rectangle((x - w/2, fy - row_h/2), w, row_h,
                                  facecolor=bg, edgecolor=C["border"], linewidth=0.6, zorder=3)
            ax.add_patch(rect)
            label = f"{'PK ' if pk else ('-> ' if 'FK' in ftype else '  ')}{fname}"
            ax.text(x - w/2 + 0.08, fy, label, ha="left", va="center",
                    fontsize=7.2, color="#333", zorder=4)
            ax.text(x + w/2 - 0.06, fy, ftype, ha="right", va="center",
                    fontsize=6.8, color="#777", style="italic", zorder=4)
        return (x, y - 0.19 - total_h + 0.19)  # bottom-center

    # auth.users (external)
    entity(2, 9.0, "auth.users\n(Supabase Auth)", [
        ("id",         "UUID PK",   True),
        ("email",      "TEXT",      False),
        ("created_at", "TIMESTAMPTZ", False),
    ], w=2.6, color="#7f8c8d")

    # user_roles
    entity(2, 6.8, "user_roles", [
        ("id",      "UUID PK",     True),
        ("user_id", "UUID FK",     False),
        ("role",    "app_role",    False),
    ], w=2.4, color=C["tbl"])

    # roles
    entity(2, 4.8, "roles", [
        ("role",         "app_role PK", True),
        ("display_name", "TEXT",        False),
        ("description",  "TEXT",        False),
        ("permissions",  "JSONB",       False),
    ], w=2.4, color=C["tbl"])

    # auth_audit
    entity(6.5, 9.2, "auth_audit", [
        ("id",             "UUID PK",    True),
        ("user_id",        "UUID FK NOT NULL", False),
        ("email",          "TEXT",       False),
        ("role",           "TEXT",       False),
        ("event",          "TEXT",       False),
        ("action_code",    "TEXT",       False),
        ("outcome_code",   "INTEGER",    False),
        ("resource_type",  "TEXT",       False),
        ("resource_id",    "TEXT",       False),
        ("integrity_hash", "TEXT",       False),
        ("created_at",     "TIMESTAMPTZ",False),
    ], w=2.8, color="#8e44ad")

    # audit_logs
    entity(6.5, 4.8, "audit_logs", [
        ("id",             "UUID PK",     True),
        ("user_id",        "UUID FK",     False),
        ("action",         "TEXT",        False),
        ("resource_type",  "TEXT",        False),
        ("resource_id",    "TEXT",        False),
        ("details",        "JSONB",       False),
        ("previous_value", "JSONB",       False),
        ("new_value",      "JSONB",       False),
        ("ip_address",     "TEXT",        False),
        ("user_agent",     "TEXT",        False),
        ("integrity_hash", "TEXT",        False),
        ("created_at",     "TIMESTAMPTZ", False),
    ], w=2.8, color="#2980b9")

    # devices
    entity(11, 9.0, "devices", [
        ("id",               "UUID PK", True),
        ("name",             "TEXT",    False),
        ("status",           "TEXT",    False),
        ("assigned_user_id", "UUID FK", False),
    ], w=2.6, color="#16a085")

    # device_sync_logs
    entity(11, 6.3, "device_sync_logs", [
        ("id",         "UUID PK",    True),
        ("device_id",  "UUID FK",    False),
        ("event_type", "TEXT",       False),
        ("details",    "JSONB",      False),
        ("created_at", "TIMESTAMPTZ",False),
    ], w=2.7, color="#1abc9c")

    # device_usage_logs
    entity(11, 3.8, "device_usage_logs", [
        ("id",           "UUID PK",    True),
        ("device_id",    "UUID FK",    False),
        ("model_id",     "TEXT",       False),
        ("prompt_count", "INTEGER",    False),
        ("tokens_used",  "INTEGER",    False),
        ("duration_ms",  "INTEGER",    False),
        ("created_at",   "TIMESTAMPTZ",False),
    ], w=2.7, color="#27ae60")

    # Relationship lines
    rels = [
        (2, 8.43, 2, 7.23,   "||—o{"),  # users -> user_roles
        (2, 7.08, 6.1, 8.86, "||—o{"),  # user_roles -> auth_audit
        (2, 7.08, 6.1, 4.44, "||—o{"),  # user_roles -> audit_logs
        (2, 8.43, 9.74, 8.63,"||—o{"),  # users -> devices
        (11,8.45, 11, 6.73,  "||—o{"),  # devices -> sync_logs
        (11,8.45, 11, 4.23,  "||—o{"),  # devices -> usage_logs
    ]
    for (x1,y1,x2,y2,label) in rels:
        ax.annotate("", xy=(x2,y2), xytext=(x1,y1),
                    arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.4,
                                   connectionstyle="arc3,rad=0.0"), zorder=2)

    # cardinality labels
    ax.text(1.4, 7.85, "1", fontsize=8, color="#555")
    ax.text(1.7, 7.35, "N", fontsize=8, color="#555")

    # app_role enum box
    rounded_box(ax, 2, 2.8, 2.2, 1.1, "#34495e",
                "«enum» app_role\n\nglobal_admin\nadmin\nuser\nviewer\nguest",
                fontsize=8, radius=0.06)
    arrow(ax, 2, 6.36, 2, 3.35, "#34495e", lw=1.5, style="-|>")

    return save_fig(fig, "02_er_diagram")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 3 — Schema Column Detail
# ══════════════════════════════════════════════════════════════════════════════
def diag_schema():
    fig, ax = plt.subplots(figsize=(14, 9))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 14); ax.set_ylim(0, 9)
    ax.axis("off")
    ax.set_title("Database Schema — Column Detail (auth_audit & audit_logs)", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    def schema_card(ax, x, y, title, col_color, columns):
        """columns = list of (name, type, constraint)"""
        w = 3.8
        row_h = 0.32
        header_h = 0.45
        total_h = header_h + len(columns) * row_h + 0.1

        # shadow
        shadow = FancyBboxPatch((x - w/2 + 0.04, y - total_h + 0.04 - 0.1), w, total_h,
                                 boxstyle="round,pad=0,rounding_size=0.05",
                                 facecolor="#cccccc", edgecolor="none", zorder=1)
        ax.add_patch(shadow)
        # card bg
        card = FancyBboxPatch((x - w/2, y - total_h + 0.1), w, total_h,
                               boxstyle="round,pad=0,rounding_size=0.05",
                               facecolor="white", edgecolor=col_color, linewidth=1.8, zorder=2)
        ax.add_patch(card)
        # header
        hdr = FancyBboxPatch((x - w/2, y - header_h + 0.1), w, header_h,
                              boxstyle="round,pad=0,rounding_size=0.05",
                              facecolor=col_color, edgecolor=col_color, linewidth=0, zorder=3)
        ax.add_patch(hdr)
        ax.text(x, y - header_h/2 + 0.1, title, ha="center", va="center",
                fontsize=10, color="white", fontweight="bold", zorder=4)

        for i, (col_name, col_type, constraint) in enumerate(columns):
            fy = y - header_h - (i + 0.5) * row_h
            # alternating row
            if i % 2 == 0:
                row_bg = FancyBboxPatch((x - w/2 + 0.01, fy - row_h/2 + 0.01),
                                        w - 0.02, row_h - 0.02,
                                        boxstyle="square,pad=0",
                                        facecolor="#f8f9ff", edgecolor="none", zorder=2)
                ax.add_patch(row_bg)
            # PK gold
            if "PK" in constraint:
                ax.text(x - w/2 + 0.12, fy, "PK", fontsize=7, va="center", zorder=4)
                xoff = 0.26
            elif "FK" in constraint:
                ax.text(x - w/2 + 0.12, fy, "->", fontsize=8, va="center",
                        color="#e67e22", fontweight="bold", zorder=4)
                xoff = 0.26
            else:
                xoff = 0.12
            ax.text(x - w/2 + xoff, fy, col_name, ha="left", va="center",
                    fontsize=8, color="#1a1a2e", fontweight="bold" if "PK" in constraint else "normal",
                    zorder=4)
            ax.text(x + w/2 - 0.1, fy, col_type, ha="right", va="center",
                    fontsize=7.5, color="#555", style="italic", zorder=4)
            if constraint and constraint not in ("PK", "FK"):
                cx = x
                ax.text(cx, fy - 0.09, constraint, ha="center", va="center",
                        fontsize=6.5, color=col_color, zorder=4)

    # auth_audit card
    schema_card(ax, 3.5, 8.7, "auth_audit", "#8e44ad", [
        ("id",             "UUID",        "PK · gen_random_uuid()"),
        ("user_id",        "UUID",        "NOT NULL"),
        ("email",          "TEXT",        ""),
        ("role",           "TEXT",        ""),
        ("event",          "TEXT",        "e.g. login, approve_pod"),
        ("action_code",    "TEXT",        "ATNA: C/R/U/D/E"),
        ("outcome_code",   "INTEGER",     "ATNA: 0/4/8/12"),
        ("resource_type",  "TEXT",        "auth_session / pod_activation"),
        ("resource_id",    "TEXT",        ""),
        ("integrity_hash", "TEXT",        "SHA-256 tamper-evidence"),
        ("created_at",     "TIMESTAMPTZ", "DEFAULT now()"),
    ])

    # audit_logs card
    schema_card(ax, 7.8, 8.7, "audit_logs", "#2980b9", [
        ("id",             "UUID",        "PK · gen_random_uuid()"),
        ("user_id",        "UUID",        "FK -> auth.users(id)"),
        ("action",         "TEXT",        "NOT NULL"),
        ("resource_type",  "TEXT",        "NOT NULL"),
        ("resource_id",    "TEXT",        ""),
        ("details",        "JSONB",       ""),
        ("previous_value", "JSONB",       "before-state (PII-scrubbed)"),
        ("new_value",      "JSONB",       "after-state (PII-scrubbed)"),
        ("ip_address",     "TEXT",        ""),
        ("user_agent",     "TEXT",        ""),
        ("integrity_hash", "TEXT",        "SHA-256 tamper-evidence"),
        ("created_at",     "TIMESTAMPTZ", "DEFAULT now()"),
    ])

    # user_roles card
    schema_card(ax, 12.1, 7.3, "user_roles", C["tbl"], [
        ("id",      "UUID",     "PK"),
        ("user_id", "UUID",     "FK -> auth.users · UNIQUE(user_id,role)"),
        ("role",    "app_role", "enum"),
    ])

    # Indexes box
    idx_txt = ("Indexes on audit_logs:\n"
               "• idx_audit_logs_user_id\n"
               "• idx_audit_logs_resource_type\n"
               "• idx_audit_logs_created_at DESC\n\n"
               "RLS: ENABLED on all tables")
    ax.text(7.8, 1.3, idx_txt, ha="center", va="center", fontsize=8.5,
            color="#1a1a2e", linespacing=1.6,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#eaf4fb", edgecolor="#2980b9", lw=1.5))

    return save_fig(fig, "03_schema_detail")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 4 — RLS Policy Flowchart
# ══════════════════════════════════════════════════════════════════════════════
def diag_rls():
    fig, ax = plt.subplots(figsize=(13, 10))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Row-Level Security (RLS) — auth_audit SELECT Policy", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    def diamond(ax, x, y, w, h, color, text, fontsize=8.5):
        diamond_pts = np.array([[x, y+h/2], [x+w/2, y], [x, y-h/2], [x-w/2, y]])
        patch = plt.Polygon(diamond_pts, closed=True, facecolor=color,
                            edgecolor="white", linewidth=1.5, zorder=3)
        ax.add_patch(patch)
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                color="white", fontweight="bold", zorder=4, multialignment="center")

    def result_box(ax, x, y, w, h, color, text, fontsize=8.5, bold=False):
        rounded_box(ax, x, y, w, h, color, text, fontsize=fontsize, radius=0.06, bold=bold)

    # ── SELECT flow ──
    # Entry
    rounded_box(ax, 6.5, 9.4, 3.5, 0.5, C["header"],
                "SELECT * FROM auth_audit", fontsize=10, bold=True)

    # Diamond 1: authenticated?
    diamond(ax, 6.5, 8.2, 3.4, 0.9, "#2c3e50", "Is user\nauthenticated?", fontsize=8.5)
    arrow(ax, 6.5, 9.15, 6.5, 8.65, "#555", lw=2)

    # No -> denied
    result_box(ax, 10.5, 8.2, 1.8, 0.45, C["no"], "NO 0 rows\nreturned", fontsize=8)
    arrow(ax, 8.2, 8.2, 9.6, 8.2, "#e74c3c", lw=1.8, label="No")

    # Yes -> role check
    diamond(ax, 6.5, 6.9, 3.8, 0.9, "#34495e", "What is caller's role?", fontsize=8.5)
    arrow(ax, 6.5, 7.75, 6.5, 7.35, "#555", lw=2, label="Yes")

    # global_admin branch
    result_box(ax, 1.4, 5.5, 2.3, 0.65, C["ga"],
               "YES ALL rows\n(every role)", fontsize=8, bold=True)
    arrow(ax, 4.6, 6.9, 2.55, 5.82, C["ga"], lw=2, label="global_admin")

    # admin branch -> sub-diamond
    diamond(ax, 5.5, 5.5, 2.8, 0.85, C["admin"], "Row's role\nfield = ?", fontsize=8)
    arrow(ax, 6.3, 6.45, 5.7, 5.93, C["admin"], lw=2, label="admin")

    result_box(ax, 3.8, 4.3, 2.5, 0.6, C["ok"], "YES Row returned\n(admin/user/viewer/guest)", fontsize=7.5)
    arrow(ax, 5.5, 5.07, 5.5, 4.6, C["admin"], lw=1.8, label="admin/user\n/viewer/guest")

    result_box(ax, 7.5, 4.3, 2.2, 0.6, C["no"], "NO Row hidden\n(global_admin rows)", fontsize=7.5)
    arrow(ax, 6.85, 5.5, 7.5, 4.6, "#c0392b", lw=1.8, label="global_admin")

    # user/viewer branch
    result_box(ax, 9.5, 5.5, 2.5, 0.65, C["user"],
               "YES Own rows only\nWHERE user_id=uid()", fontsize=8)
    arrow(ax, 8.4, 6.9, 9.5, 5.82, C["user"], lw=2, label="user/viewer")

    # guest — NO policy matches; guest has zero access via RLS
    result_box(ax, 11.5, 6.9, 1.8, 0.6, C["no"],
               "guest\nNO policy match\n0 rows returned", fontsize=7.5)
    arrow(ax, 8.4, 6.9, 11.3, 6.9, C["guest"], lw=2, label="guest")

    # INSERT section
    ax.axhline(y=3.3, xmin=0.03, xmax=0.97, color="#aaa", lw=1, linestyle="--")
    ax.text(6.5, 3.1, "INSERT POLICY", ha="center", fontsize=10,
            fontweight="bold", color=C["header"])

    rounded_box(ax, 6.5, 2.65, 3.5, 0.45, C["header"],
                "INSERT INTO auth_audit", fontsize=9, bold=True)
    diamond(ax, 6.5, 1.7, 3.8, 0.85, "#2c3e50", "auth.uid() = user_id?", fontsize=8.5)
    arrow(ax, 6.5, 2.42, 6.5, 2.12, "#555", lw=2)

    result_box(ax, 3.8, 1.7, 2.0, 0.45, C["ok"], "YES Insert\nallowed", fontsize=8.5)
    arrow(ax, 4.6, 1.7, 4.8, 1.7, C["ok"], lw=2, label="Yes")

    result_box(ax, 9.5, 1.7, 2.0, 0.45, C["no"], "NO Insert\ndenied", fontsize=8.5)
    arrow(ax, 8.4, 1.7, 8.5, 1.7, C["no"], lw=2, label="No")

    return save_fig(fig, "04_rls_policy")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 5 — Data Flow
# ══════════════════════════════════════════════════════════════════════════════
def diag_data_flow():
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 14); ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Data Flow — How Audit Logs Are Created", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    def swim_lane(y_center, label, color, height=1.2):
        rect = plt.Rectangle((0.3, y_center - height/2), 13.4, height,
                              facecolor=color + "18", edgecolor=color, lw=1.2,
                              linestyle="--", zorder=1)
        ax.add_patch(rect)
        ax.text(0.55, y_center, label, va="center", ha="left", fontsize=8.5,
                color=color, fontweight="bold", rotation=90)

    swim_lane(7.0, "USER ACTION",    C["user"],  0.9)
    swim_lane(5.7, "FRONTEND COMPONENTS", C["fe"], 1.0)
    swim_lane(4.4, "AUDIT HASH LIB", C["hash"], 0.9)
    swim_lane(3.1, "SUPABASE RLS",   C["db"],   0.9)
    swim_lane(1.8, "DB STORAGE",     "#1a1a2e", 0.9)

    # User actions
    rounded_box(ax, 3,    7.0, 1.8, 0.5, C["user"],    "User Login",    fontsize=8.5, bold=True)
    rounded_box(ax, 6.5,  7.0, 1.8, 0.5, C["user"],    "User Logout",   fontsize=8.5, bold=True)
    rounded_box(ax, 10.5, 7.0, 2.2, 0.5, C["admin"],   "Admin Approve/\nReject Pod", fontsize=8.5, bold=True)

    # Frontend components
    rounded_box(ax, 3,    5.7, 1.8, 0.55, C["fe"],     "Auth.tsx",      fontsize=8.5, bold=True)
    rounded_box(ax, 6.5,  5.7, 1.8, 0.55, C["fe"],     "Layout.tsx",    fontsize=8.5, bold=True)
    rounded_box(ax, 10.5, 5.7, 2.2, 0.55, C["fe"],     "PodActivation\nRequests.tsx", fontsize=8.5, bold=True)

    # Hash lib
    rounded_box(ax, 7, 4.4, 4.5, 0.55, C["hash"],
                "auditHash.ts  ->  SHA-256( user_id + role + event + action_code\n"
                "+ outcome_code + resource_type + resource_id + previous_value + new_value + created_at )",
                fontsize=8, bold=True)

    # RLS
    rounded_box(ax, 7, 3.1, 5.5, 0.55, C["db"],
                "Supabase RLS:  INSERT policy  ->  auth.uid() = user_id  ->  ALLOWED",
                fontsize=8, bold=True)

    # DB
    rounded_box(ax, 4.5, 1.8, 3.2, 0.55, "#8e44ad",
                "auth_audit table\n(integrity_hash stored)", fontsize=8, bold=True)
    rounded_box(ax, 9.5, 1.8, 3.0, 0.55, "#2980b9",
                "audit_logs table\n(details JSONB)", fontsize=8, bold=True)

    # Arrows: user -> frontend
    for x in [3, 6.5, 10.5]:
        arrow(ax, x, 6.72, x, 5.97, "#555", lw=1.8)

    # frontend -> hash
    for x in [3, 6.5, 10.5]:
        arrow(ax, x, 5.43, 7 + (x-7)*0.2, 4.68, "#555", lw=1.5)

    # hash -> rls
    arrow(ax, 7, 4.12, 7, 3.38, C["hash"], lw=2, label="with integrity_hash")

    # rls -> db
    arrow(ax, 5.5, 2.82, 4.8, 2.08, C["db"], lw=2, label="auth_audit rows")
    arrow(ax, 8.5, 2.82, 9.2, 2.08, C["db"], lw=2, label="audit_logs rows")

    # numbered steps
    for i, (x, y, txt) in enumerate([
        (2.0, 7.4, "① User\ntriggers\naction"),
        (1.8, 5.1, "② Component\ncaptures event"),
        (2.0, 3.9, "③ Hash\ncomputed"),
        (2.0, 2.55,"④ RLS\nvalidation"),
        (2.0, 1.35,"⑤ Row\npersisted"),
    ], 1):
        ax.text(x, y, txt, fontsize=7.5, color="#555", ha="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#ccc"))

    return save_fig(fig, "05_data_flow")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 6 — Login Sequence
# ══════════════════════════════════════════════════════════════════════════════
def diag_seq_login():
    fig, ax = plt.subplots(figsize=(13, 8))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Sequence Diagram — Login Audit Event", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    actors = [
        (1.5,  "User",          C["user"]),
        (4.0,  "Auth.tsx",      C["fe"]),
        (6.8,  "Supabase Auth", C["db"]),
        (9.5,  "auditHash.ts",  C["hash"]),
        (12.0, "auth_audit\ntable", "#8e44ad"),
    ]

    # Lifelines
    for (x, name, col) in actors:
        rounded_box(ax, x, 7.5, 1.6, 0.55, col, name, fontsize=8.5, bold=True)
        ax.plot([x, x], [7.22, 0.4], color=col, lw=1.5, linestyle="--", zorder=1)

    def msg(y, x1, x2, text, col="#555", ret=False, note=""):
        style = "<-" if ret else "->"
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle=style, color=col, lw=1.6), zorder=3)
        mx = (x1 + x2) / 2
        ax.text(mx, y + 0.12, text, ha="center", va="bottom", fontsize=7.8,
                color=col, fontweight="bold" if not ret else "normal",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor=col, lw=0.8, alpha=0.92) if not ret else None)
        if note:
            ax.text(mx, y - 0.15, note, ha="center", fontsize=6.8, color="#888", style="italic")

    def activation(x, y_top, y_bot, col):
        rect = plt.Rectangle((x - 0.08, y_bot), 0.16, y_top - y_bot,
                              facecolor=col, edgecolor="white", lw=1, zorder=2, alpha=0.85)
        ax.add_patch(rect)

    activation(4.0,  6.9, 1.0, C["fe"])
    activation(6.8,  6.5, 5.8, C["db"])
    activation(9.5,  5.1, 4.3, C["hash"])
    activation(12.0, 3.6, 3.0, "#8e44ad")

    msg(6.7,  1.5, 4.0,  "Enter credentials & click Submit", C["user"])
    msg(6.3,  4.0, 6.8,  "signInWithPassword({ email, password })", C["fe"])
    msg(5.9,  6.8, 4.0,  "{ data: { user, session }, error: null }", C["db"], ret=True)
    msg(5.5,  4.0, 4.0,  "Capture createdAt = new Date().toISOString()", C["fe"],
        note="(self-call / internal step)")
    ax.annotate("", xy=(4.4, 5.5), xytext=(4.4, 5.7),
                arrowprops=dict(arrowstyle="->", color=C["fe"], lw=1.2), zorder=3)
    msg(5.0,  4.0, 9.5,  "computeAuditIntegrityHash({ user_id, role, event:'login',\naction_code:'E', outcome_code:0, resource_type:'auth_session', resource_id:null, created_at })", C["fe"])
    msg(4.5,  9.5, 4.0,  "integrity_hash (SHA-256 hex string)", C["hash"], ret=True)
    msg(4.0,  4.0, 12.0, "supabase.from('auth_audit').insert({...row, integrity_hash})", C["fe"])
    msg(3.5,  12.0, 4.0, "{ data, error: null } — Row inserted", "#8e44ad", ret=True)
    msg(3.0,  4.0, 1.5,  "Navigate to dashboard  YES", C["ok"])

    # alt box
    rect_alt = plt.Rectangle((0.4, 2.3), 12.2, 1.0, facecolor="none",
                               edgecolor="#27ae60", lw=1.5, linestyle="--", zorder=2)
    ax.add_patch(rect_alt)
    ax.text(0.5, 3.28, "alt [Login successful]", fontsize=7.5, color="#27ae60",
            fontweight="bold", style="italic")

    return save_fig(fig, "06_seq_login")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 7 — Admin Approves Pod Sequence
# ══════════════════════════════════════════════════════════════════════════════
def diag_seq_pod():
    fig, ax = plt.subplots(figsize=(14, 9))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 14); ax.set_ylim(0, 9)
    ax.axis("off")
    ax.set_title("Sequence Diagram — Admin Approves Pod Activation", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    actors = [
        (1.5,  "Admin",                  C["admin"]),
        (4.0,  "PodActivation\nReqs.tsx",C["fe"]),
        (7.0,  "Supabase DB\n(pod table)",C["db"]),
        (10.0, "auditHash.ts",           C["hash"]),
        (13.0, "auth_audit\ntable",      "#8e44ad"),
    ]

    for (x, name, col) in actors:
        rounded_box(ax, x, 8.5, 1.8, 0.6, col, name, fontsize=8.5, bold=True)
        ax.plot([x, x], [8.2, 0.4], color=col, lw=1.5, linestyle="--", zorder=1)

    def msg(y, x1, x2, text, col="#555", ret=False):
        style = "<-" if ret else "->"
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle=style, color=col, lw=1.6), zorder=3)
        mx = (x1 + x2) / 2
        ax.text(mx, y + 0.13, text, ha="center", va="bottom", fontsize=7.5, color=col,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor=col, lw=0.8, alpha=0.9))

    def activation(x, y_top, y_bot, col):
        rect = plt.Rectangle((x - 0.09, y_bot), 0.18, y_top - y_bot,
                              facecolor=col, edgecolor="white", lw=1, zorder=2, alpha=0.85)
        ax.add_patch(rect)

    activation(4.0,  8.0, 0.8, C["fe"])
    activation(7.0,  7.3, 6.3, C["db"])
    activation(10.0, 5.3, 4.3, C["hash"])
    activation(13.0, 3.6, 2.8, "#8e44ad")

    msg(7.8,  1.5,  4.0,  "Click 'Approve' on pod request", C["admin"])
    msg(7.3,  4.0,  7.0,  "auth.getUser() — verify session", C["fe"])
    msg(6.9,  7.0,  4.0,  "{ user: { id, email, role } }", C["db"], ret=True)
    msg(6.4,  4.0,  7.0,  "UPDATE pod_activation_requests SET status='approved' WHERE id=req.id", C["fe"])
    msg(6.0,  7.0,  4.0,  "{ data, error: null } — Updated", C["db"], ret=True)
    msg(5.5,  4.0,  4.0,  "createdAt = new Date().toISOString()")
    ax.annotate("", xy=(4.4, 5.5), xytext=(4.4, 5.65),
                arrowprops=dict(arrowstyle="->", color="#555", lw=1.2))
    msg(5.0,  4.0,  10.0, "computeAuditIntegrityHash({ user_id, role:'admin',\nevent:'approve_pod:{model_id}', action_code:'U', outcome_code:0, ... })", C["fe"])
    msg(4.5,  10.0, 4.0,  "integrity_hash (SHA-256)", C["hash"], ret=True)
    msg(4.0,  4.0,  13.0, "supabase.from('auth_audit').insert({ role:'admin', event:'approve_pod:{model_id}',\naction_code:'U', outcome_code:0, resource_type:'pod_activation', ... })", C["fe"])
    msg(3.5,  13.0, 4.0,  "Row inserted YES", "#8e44ad", ret=True)
    msg(3.0,  4.0,  1.5,  "Toast: 'Pod approved successfully'  ", C["ok"])

    return save_fig(fig, "07_seq_pod")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 8 — View Activity Logs Sequence
# ══════════════════════════════════════════════════════════════════════════════
def diag_seq_view():
    fig, ax = plt.subplots(figsize=(13, 8))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Sequence Diagram — Viewing Activity Logs (/activity page)", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    actors = [
        (1.5,  "Any User",      "#555"),
        (4.5,  "Activity.tsx",  C["fe"]),
        (8.0,  "Supabase RLS",  C["db"]),
        (11.5, "auth_audit\ntable", "#8e44ad"),
    ]

    for (x, name, col) in actors:
        rounded_box(ax, x, 7.5, 1.8, 0.55, col, name, fontsize=8.5, bold=True)
        ax.plot([x, x], [7.22, 0.5], color=col, lw=1.5, linestyle="--", zorder=1)

    def msg(y, x1, x2, text, col="#555", ret=False):
        style = "<-" if ret else "->"
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle=style, color=col, lw=1.6), zorder=3)
        mx = (x1 + x2) / 2
        ax.text(mx, y + 0.13, text, ha="center", va="bottom", fontsize=7.5, color=col,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor=col, lw=0.8, alpha=0.9))

    def activation(x, y_top, y_bot, col):
        rect = plt.Rectangle((x - 0.09, y_bot), 0.18, y_top - y_bot,
                              facecolor=col, edgecolor="white", lw=1, zorder=2, alpha=0.85)
        ax.add_patch(rect)

    activation(4.5,  7.0, 1.2, C["fe"])
    activation(8.0,  6.0, 1.8, C["db"])
    activation(11.5, 5.6, 2.2, "#8e44ad")

    msg(6.8,  1.5,  4.5,  "Navigate to /activity", "#555")
    msg(6.4,  4.5,  4.5,  "useEffect — fetch on mount")
    ax.annotate("", xy=(4.9, 6.4), xytext=(4.9, 6.55),
                arrowprops=dict(arrowstyle="->", color="#555", lw=1.2))
    msg(6.0,  4.5,  8.0,  "SELECT * FROM auth_audit ORDER BY created_at DESC", C["fe"])
    msg(5.6,  8.0,  11.5, "Evaluate caller's role via RLS policies", C["db"])
    msg(5.2,  11.5, 8.0,  "Return rows matching policy", "#8e44ad", ret=True)

    # Alt block
    y_top, y_bot = 4.7, 1.1
    rect_alt = plt.Rectangle((5.5, y_bot), 6.8, y_top - y_bot, facecolor="none",
                               edgecolor="#aaa", lw=1.3, linestyle="--", zorder=2)
    ax.add_patch(rect_alt)
    ax.text(5.6, y_top - 0.05, "alt  [based on role]", fontsize=7.5, color="#777",
            fontweight="bold", style="italic")

    branches = [
        (4.5, "global_admin -> ALL rows (all roles)",      C["ga"]),
        (3.9, "admin -> rows WHERE role IN (admin,user,\nviewer,guest) — NOT global_admin", C["admin"]),
        (3.2, "user / viewer -> rows WHERE user_id = uid()", C["user"]),
        (2.5, "guest -> 0 rows returned",                  C["guest"]),
    ]
    for (y, txt, col) in branches:
        ax.text(8.9, y, txt, fontsize=7.8, color=col, fontweight="bold",
                va="center",
                bbox=dict(boxstyle="round,pad=0.25", facecolor=col+"22",
                          edgecolor=col, lw=1))
        arrow(ax, 8.0, y, 8.75, y, col, lw=1.5)

    msg(1.5,  8.0, 4.5,  "Filtered rows returned", C["db"], ret=True)
    msg(1.1,  4.5, 1.5,  "Render audit table with role badges  YES", C["ok"])

    return save_fig(fig, "08_seq_view")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 9 — Integrity Hash Flow
# ══════════════════════════════════════════════════════════════════════════════
def diag_hash():
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("Audit Integrity Hash — Tamper-Evidence Flow", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    # Input fields
    fields = ["user_id", "role", "event", "action_code",
              "outcome_code", "resource_type", "resource_id", "created_at"]
    for i, f in enumerate(fields):
        x = 0.6 + (i % 4) * 1.8
        y = 5.8 if i < 4 else 4.8
        rounded_box(ax, x, y, 1.55, 0.45, C["tbl"], f, fontsize=8.5, radius=0.05)

    # Excluded
    rounded_box(ax, 10.5, 5.3, 1.7, 0.65, C["no"],
                "email\n(excluded — PII)", fontsize=8.5, radius=0.05)
    ax.text(10.5, 4.75, "NO NOT hashed", fontsize=8, color=C["no"],
            ha="center", fontweight="bold")

    # Concat box
    rounded_box(ax, 4.0, 3.7, 5.5, 0.5, "#2c3e50",
                "JSON.stringify({ user_id, role, event, action_code,\noutcome_code, resource_type, resource_id, created_at })",
                fontsize=8, radius=0.05)

    # All inputs -> concat
    for i, f in enumerate(fields):
        x = 0.6 + (i % 4) * 1.8
        y = 5.8 if i < 4 else 4.8
        arrow(ax, x, y - 0.22, 4.0 - 2.0 + (i * 4.0/7), 3.95, "#555", lw=1.2)

    # concat -> SHA-256
    rounded_box(ax, 4.0, 2.85, 3.0, 0.5, C["hash"],
                "crypto.subtle.digest('SHA-256', ...)", fontsize=9, bold=True, radius=0.05)
    arrow(ax, 4.0, 3.45, 4.0, 3.1, C["hash"], lw=2)

    # SHA-256 -> hex
    rounded_box(ax, 4.0, 2.1, 3.0, 0.45, "#8e44ad",
                "ArrayBuffer -> hex string", fontsize=9, radius=0.05)
    arrow(ax, 4.0, 2.6, 4.0, 2.32, "#8e44ad", lw=2)

    # hex -> stored
    rounded_box(ax, 4.0, 1.35, 4.5, 0.5, "#1a1a2e",
                "integrity_hash stored in auth_audit row", fontsize=9, bold=True, radius=0.05)
    arrow(ax, 4.0, 1.87, 4.0, 1.6, "#1a1a2e", lw=2)

    # Verification section
    rounded_box(ax, 10.5, 2.1, 4.0, 1.6, "#2c3e50",
                "Future Verification\n\n1. Read row from DB\n2. Recompute hash from fields\n3. Compare to stored integrity_hash\n\nYES Match = Untampered\nNO Mismatch = TAMPERED!",
                fontsize=8.5, radius=0.06)
    arrow(ax, 6.25, 1.35, 8.5, 1.75, "#555", lw=1.8, label="auditor checks")

    return save_fig(fig, "09_hash_flow")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 10 — Component Architecture
# ══════════════════════════════════════════════════════════════════════════════
def diag_components():
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 14); ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Frontend Component Architecture", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    def group_box(x, y, w, h, color, title):
        rect = FancyBboxPatch((x, y), w, h,
                               boxstyle="round,pad=0,rounding_size=0.1",
                               facecolor=color + "14", edgecolor=color,
                               linewidth=1.8, linestyle="--", zorder=1)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.18, title, ha="center", va="top",
                fontsize=9, color=color, fontweight="bold")

    # Groups
    group_box(0.2, 7.5,  4.5, 2.2, "#e67e22", "Pages (Routes)")
    group_box(0.2, 4.8,  4.5, 2.5, "#1abc9c", "Shared Components")
    group_box(0.2, 2.5,  2.4, 2.0, "#9b59b6", "Hooks")
    group_box(3.0, 2.5,  1.9, 2.0, "#e74c3c", "Libraries")
    group_box(5.2, 7.5,  8.5, 5.5, "#2c3e50", "Supabase (Backend)")

    # Pages
    rounded_box(ax, 1.3, 9.2, 1.7, 0.4, C["fe"],    "Activity.tsx",      fontsize=8)
    rounded_box(ax, 3.2, 9.2, 1.7, 0.4, C["admin"],  "AdminDashboard.tsx",fontsize=7.5)
    rounded_box(ax, 1.3, 8.5, 1.7, 0.4, C["user"],   "Auth.tsx",          fontsize=8)
    rounded_box(ax, 3.2, 8.5, 1.7, 0.4, "#7f8c8d",   "Dashboard.tsx",     fontsize=8)

    # Components
    rounded_box(ax, 1.3, 6.8, 1.7, 0.4, C["fe"],    "AppSidebar.tsx",    fontsize=8)
    rounded_box(ax, 3.2, 6.8, 1.7, 0.4, C["fe"],    "Layout.tsx",        fontsize=8)
    rounded_box(ax, 1.3, 6.1, 1.7, 0.4, C["admin"], "PodActivation\nReqs.tsx", fontsize=7.5)
    rounded_box(ax, 3.2, 6.1, 1.7, 0.4, C["ga"],    "GlobalAdmin\nRoleMgr.tsx", fontsize=7.5)
    rounded_box(ax, 2.2, 5.3, 1.7, 0.4, "#7f8c8d",  "ProtectedRoute.tsx",fontsize=7.5)

    # Hooks + Libs
    rounded_box(ax, 1.4, 3.7, 1.8, 0.45, "#9b59b6", "useUserRole.ts",   fontsize=8, bold=True)
    rounded_box(ax, 1.4, 3.0, 1.8, 0.45, "#9b59b6", "useSupabase.ts",   fontsize=8)
    rounded_box(ax, 3.9, 3.7, 1.5, 0.45, C["hash"],  "auditHash.ts",     fontsize=8, bold=True)
    rounded_box(ax, 3.9, 3.0, 1.5, 0.45, "#2980b9",  "supabaseClient.ts",fontsize=7.5)

    # Supabase group contents
    rounded_box(ax, 7.0, 9.2, 2.2, 0.5, "#8e44ad", "auth_audit table",  fontsize=8.5, bold=True)
    rounded_box(ax, 10.5,9.2, 2.2, 0.5, "#2980b9",  "audit_logs table",  fontsize=8.5, bold=True)
    rounded_box(ax, 7.0, 8.3, 2.2, 0.5, C["tbl"],   "user_roles table",  fontsize=8.5)
    rounded_box(ax, 10.5,8.3, 2.2, 0.5, "#16a085",  "devices table",     fontsize=8.5)
    rounded_box(ax, 7.0, 7.4, 2.2, 0.5, "#2c3e50",  "RLS Policies",      fontsize=8.5, bold=True)
    rounded_box(ax, 10.5,7.4, 2.2, 0.5, "#7f8c8d",  "Supabase Auth\n(sessions)", fontsize=8)

    # App.tsx top
    rounded_box(ax, 7.0, 0.6, 5.5, 0.5, C["header"],
                "App.tsx — Router + ProtectedRoute guards", fontsize=9, bold=True)

    # Arrows: components -> supabase
    for (x1,y1,x2,y2) in [
        (1.3, 9.0, 6.0, 9.2),   # Activity.tsx -> auth_audit
        (2.2, 8.3, 6.0, 8.5),   # Auth.tsx -> auth_audit
        (4.05,3.7, 6.0, 8.9),   # auditHash -> auth_audit
        (3.2, 6.6, 6.0, 8.1),   # Layout.tsx -> audit_logs
        (3.2, 6.0, 6.0, 7.6),   # PodActivationReqs -> RLS
        (1.4, 3.5, 5.8, 8.1),   # useUserRole -> user_roles
    ]:
        arrow(ax, x1, y1, x2, y2, "#aaa", lw=1.2, style="-|>")

    # App.tsx connections
    for x in [1.3, 3.2, 2.2]:
        arrow(ax, x, 0.85, x, 7.7 if x != 2.2 else 5.1, "#555", lw=1.0, style="->")

    return save_fig(fig, "10_components")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 11 — Access Control Matrix
# ══════════════════════════════════════════════════════════════════════════════
def diag_access_matrix():
    fig, ax = plt.subplots(figsize=(14, 9))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.axis("off")
    ax.set_title("Access Control Matrix — Activity Logs Feature", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    rows = [
        "Access /activity page",
        "View own audit rows",
        "View all 'user' role rows",
        "View all 'admin' role rows",
        "View all 'viewer' role rows",
        "View all 'guest' role rows",
        "View 'global_admin' rows",
        "View ALL audit_logs",
        "View own audit_logs",
        "Approve / Reject Pods",
        "List all users (API)",
        "Create users (API)",
        "Set user roles (API)",
        "View device_sync_logs",
        "View device_usage_logs",
        "Access Admin Dashboard",
    ]
    cols = ["global_admin", "admin", "user", "viewer", "guest"]
    col_colors_hdr = [C["ga"], C["admin"], C["user"], C["viewer"], C["guest"]]

    data = [
        ["YES", "YES", "YES", "YES", "NO"],
        ["YES", "YES", "YES", "YES", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "NO", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "YES", "YES", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "NO", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
        ["YES", "YES", "NO", "NO", "NO"],
    ]

    cell_w = 1.8
    cell_h = 0.42
    label_w = 5.2
    x0 = 0.5
    y0 = 8.2

    # Header row
    ax.text(x0 + label_w/2, y0 + 0.05, "Permission / Capability",
            ha="center", va="center", fontsize=9.5, fontweight="bold", color="white",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=C["header"], edgecolor="none"))
    for j, (col, col_c) in enumerate(zip(cols, col_colors_hdr)):
        x = x0 + label_w + j * cell_w + cell_w/2
        rounded_box(ax, x, y0 + 0.05, cell_w - 0.06, 0.38, col_c, col,
                    fontsize=8.5, bold=True, radius=0.04)

    for i, row_label in enumerate(rows):
        y = y0 - (i + 1) * cell_h
        bg_color = "#f0f4ff" if i % 2 == 0 else "white"
        rect = plt.Rectangle((x0, y - cell_h/2), label_w, cell_h,
                              facecolor=bg_color, edgecolor=C["border"], lw=0.5, zorder=2)
        ax.add_patch(rect)
        ax.text(x0 + 0.15, y, row_label, ha="left", va="center",
                fontsize=8.2, color="#1a1a2e", zorder=3)

        for j, (val, col_c) in enumerate(zip(data[i], col_colors_hdr)):
            x = x0 + label_w + j * cell_w + cell_w/2
            rect2 = plt.Rectangle((x0 + label_w + j*cell_w, y - cell_h/2),
                                   cell_w, cell_h,
                                   facecolor=bg_color, edgecolor=C["border"], lw=0.5, zorder=2)
            ax.add_patch(rect2)
            color = C["ok"] if val == "YES" else C["no"]
            ax.text(x, y, val, ha="center", va="center", fontsize=11,
                    color=color, fontweight="bold", zorder=3)

    ax.set_xlim(0, 14); ax.set_ylim(0, 9)
    return save_fig(fig, "11_access_matrix")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 12 — Event Types Reference
# ══════════════════════════════════════════════════════════════════════════════
def diag_events():
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.axis("off")
    ax.set_title("Audit Event Types & ATNA Codes Reference", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)
    ax.set_xlim(0, 13); ax.set_ylim(0, 7)

    events = [
        ("login",                "Successful sign-in",        "Any",           "E", "0",  "auth_session",    C["user"]),
        ("login_failed",         "Failed sign-in attempt",    "Any",           "E", "8",  "auth_session",    C["no"]),
        ("logout",               "User logs out",             "Any",           "E", "0",  "auth_session",    C["user"]),
        ("approve_pod:{model_id}","Admin approves pod",       "admin/global",  "U", "0",  "pod_activation",  C["admin"]),
        ("reject_pod:{model_id}", "Admin rejects pod",        "admin/global",  "U", "0",  "pod_activation",  C["admin"]),
    ]

    headers = ["Event Name", "Description", "Actor", "Action\nCode", "Outcome\nCode", "Resource Type"]
    widths = [2.6, 2.2, 1.6, 0.85, 0.85, 1.8]
    x_starts = [0.3]
    for w in widths[:-1]:
        x_starts.append(x_starts[-1] + w)

    # Header
    for hdr, x, w in zip(headers, x_starts, widths):
        rounded_box(ax, x + w/2, 5.4, w - 0.08, 0.42, C["header"], hdr,
                    fontsize=8.5, bold=True, radius=0.04)

    # Rows
    for i, (ev, desc, actor, ac, oc, rt, col) in enumerate(events):
        y = 4.6 - i * 0.75
        bg = "#f8f4ff" if i % 2 == 0 else "white"
        for x, w in zip(x_starts, widths):
            rect = plt.Rectangle((x, y - 0.3), w - 0.04, 0.6,
                                  facecolor=bg, edgecolor=C["border"], lw=0.7, zorder=2)
            ax.add_patch(rect)
        vals = [ev, desc, actor, ac, oc, rt]
        for v, x, w in zip(vals, x_starts, widths):
            ax.text(x + w/2, y, v, ha="center", va="center", fontsize=8,
                    color="#1a1a2e", zorder=3,
                    fontweight="bold" if v in (ev,) else "normal")
        # row color indicator
        rnd = FancyBboxPatch((x_starts[0] - 0.02, y - 0.28), 0.08, 0.56,
                              boxstyle="round,pad=0,rounding_size=0.02",
                              facecolor=col, edgecolor="none", zorder=4)
        ax.add_patch(rnd)

    # ATNA legend
    ax.text(0.3, 1.4, "ATNA Action Codes:", fontsize=9, fontweight="bold", color=C["header"])
    atna_a = [("C","Create"), ("R","Read"), ("U","Update"), ("D","Delete"), ("E","Execute")]
    for i, (code, meaning) in enumerate(atna_a):
        rounded_box(ax, 0.9 + i*1.5, 0.85, 1.3, 0.42, C["tbl"],
                    f"{code} = {meaning}", fontsize=8.5, radius=0.04)

    ax.text(8.5, 1.4, "ATNA Outcome Codes:", fontsize=9, fontweight="bold", color=C["header"])
    atna_o = [("0","Success"), ("4","Minor fail"), ("8","Serious"), ("12","Major")]
    out_cols = [C["ok"], "#f39c12", "#e67e22", C["no"]]
    for i, ((code, meaning), col) in enumerate(zip(atna_o, out_cols)):
        rounded_box(ax, 9.0 + i*1.0, 0.85, 0.9, 0.42, col,
                    f"{code}\n{meaning}", fontsize=7.5, radius=0.04)

    return save_fig(fig, "12_events")

# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 13 — Backend Logging Architecture
# ══════════════════════════════════════════════════════════════════════════════
def diag_backend():
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13); ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("Backend Logging Architecture — FastAPI + Structlog", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    def group(x, y, w, h, color, title):
        rect = FancyBboxPatch((x, y), w, h,
                               boxstyle="round,pad=0,rounding_size=0.1",
                               facecolor=color + "18", edgecolor=color,
                               linewidth=1.8, linestyle="--", zorder=1)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.15, title, ha="center", va="top",
                fontsize=9, color=color, fontweight="bold")

    group(0.3, 3.5, 4.0, 3.2, C["api"], "FastAPI Application")
    group(4.8, 3.5, 3.4, 3.2, C["hash"], "Logger Module")
    group(8.7, 3.5, 3.8, 3.2, "#1abc9c", "Log Output")

    # FastAPI boxes
    rounded_box(ax, 2.3, 6.1, 3.0, 0.45, C["api"], "factory.py\napp = create_app()", fontsize=8)
    rounded_box(ax, 2.3, 5.3, 3.0, 0.5,  C["api"], "RequestLogging\nMiddleware", fontsize=8.5, bold=True)
    rounded_box(ax, 2.3, 4.4, 3.0, 0.45, C["api"], "API Routes\nadmin.py, models.py …", fontsize=8)

    # Logger boxes
    rounded_box(ax, 6.5, 6.1, 2.8, 0.45, C["hash"], "structlog\nJSON formatter", fontsize=8)
    rounded_box(ax, 6.5, 5.3, 2.8, 0.6,  C["hash"],
                "PII Scrubber\nPass 1 (sync processor): Field-name → [REDACTED]\n"
                "Pass 2 (async): scrub_text() via ThreadPoolExecutor(2)\n"
                "Event loop never blocked by Presidio NLP",
                fontsize=7, bold=True)

    # Output boxes
    rounded_box(ax, 10.6, 6.1, 2.8, 0.45, "#1abc9c", "Console\nJSON output", fontsize=8)
    rounded_box(ax, 10.6, 5.3, 2.8, 0.55, "#1abc9c",
                "logs/app.log\nRotatingFileHandler\n10 MB × 5 backups (50 MB max)",
                fontsize=7.5, bold=True)

    # Per-request fields
    rounded_box(ax, 6.5, 4.05, 5.8, 1.0, "#2c3e50",
                "Per-Request Log Fields:\nrequest_id (UUID)  •  method  •  path  •  client_ip\n"
                "status_code  •  duration_ms  •  exc_info (on 5xx errors)\n"
                "LOG_LEVEL env var (default: INFO)  •  Startup warning if Presidio unavailable",
                fontsize=7.5, radius=0.06)

    # Arrows
    arrow(ax, 2.3, 5.85, 2.3, 5.55, C["api"], lw=1.8)
    arrow(ax, 2.3, 5.05, 2.3, 4.62, C["api"], lw=1.8)
    arrow(ax, 3.8, 5.3,  5.1, 5.7,  C["api"], lw=2)
    arrow(ax, 7.8, 6.1,  9.2, 6.1,  C["hash"], lw=2)
    arrow(ax, 7.8, 5.3,  9.2, 5.3,  C["hash"], lw=2)
    arrow(ax, 6.5, 5.05, 6.5, 4.57, C["hash"], lw=1.5)

    # Frontend vs Backend comparison
    group(0.3, 0.2, 12.1, 2.9, "#7f8c8d", "Frontend vs Backend Logging Comparison")
    comp = [
        ("Aspect",       "Frontend (auth_audit table)", "Backend (logs/app.log)"),
        ("Storage",      "Supabase PostgreSQL",          "Local file system"),
        ("Format",       "Structured table rows",        "JSON lines (structlog)"),
        ("PII Pass 1",   "Email stored, excluded from hash","Field-name keywords → [REDACTED]"),
        ("PII Pass 2",   "Regex: SSN, card, phone, IBAN → <TYPE>","Presidio NLP async via scrub_text() / ThreadPoolExecutor"),
        ("Tamper-Proof", "SHA-256 integrity_hash",       "No hash (file-based)"),
        ("Queryable",    "Yes — via Supabase SQL / RLS", "No — file read only"),
        ("Visibility",   "Role-filtered via RLS",        "Server-side only"),
    ]
    col_w = [2.2, 4.8, 4.8]
    xs = [0.5, 2.75, 7.6]
    for i, (aspect, fe_val, be_val) in enumerate(comp):
        y = 2.8 - i * 0.31
        bg = "#f0f0f0" if i == 0 else ("#f8fff8" if i % 2 == 0 else "white")
        for xi, w, val in zip(xs, col_w, (aspect, fe_val, be_val)):
            rect = plt.Rectangle((xi, y - 0.15), w, 0.31,
                                  facecolor=bg if i > 0 else C["header"],
                                  edgecolor=C["border"], lw=0.5, zorder=2)
            ax.add_patch(rect)
            tc = "white" if i == 0 else "#1a1a2e"
            ax.text(xi + w/2, y, val, ha="center", va="center",
                    fontsize=7.5 if i > 0 else 8, color=tc,
                    fontweight="bold" if i == 0 else "normal", zorder=3)

    return save_fig(fig, "13_backend")


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 14 — PII Scrubbing Pipeline (Two-Pass Architecture)
# ══════════════════════════════════════════════════════════════════════════════
def diag_presidio():
    fig, ax = plt.subplots(figsize=(13, 9))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9)
    ax.axis("off")
    ax.set_title("PII Scrubbing Pipeline — Two-Pass Architecture", fontsize=14,
                 fontweight="bold", color=C["header"], pad=12)

    # ── INPUT ───────────────────────────────────────────────────────────────
    rounded_box(ax, 6.5, 8.5, 6.0, 0.55, C["api"],
                "Input: Log Event / Payload (any field → any string value)", fontsize=9)
    # Arrow down from input to split junction
    arrow(ax, 6.5, 8.225, 6.5, 7.85, C["api"], lw=2)
    # Split to Pass 1 (left) and Pass 2 (right)
    ax.annotate("", xy=(2.7, 7.45), xytext=(6.5, 7.85),
                arrowprops=dict(arrowstyle="->", color="#555", lw=1.5))
    ax.annotate("", xy=(9.3, 7.45), xytext=(6.5, 7.85),
                arrowprops=dict(arrowstyle="->", color="#555", lw=1.5))
    ax.text(4.5, 7.75, "Pass 1", fontsize=8, color=C["hash"], fontweight="bold", ha="center")
    ax.text(8.5, 7.75, "Pass 2", fontsize=8, color=C["viewer"], fontweight="bold", ha="center")

    # ── PASS 1: Field-name Match ─────────────────────────────────────────────
    p1_grp = FancyBboxPatch((0.2, 1.4), 5.0, 5.9,
                             boxstyle="round,pad=0,rounding_size=0.1",
                             facecolor=C["hash"] + "18", edgecolor=C["hash"],
                             linewidth=1.8, linestyle="--", zorder=1)
    ax.add_patch(p1_grp)
    ax.text(2.7, 7.2, "Pass 1 — Field-name Keyword Match", ha="center", va="top",
            fontsize=9, color=C["hash"], fontweight="bold")

    rounded_box(ax, 2.7, 6.3, 4.4, 1.3, C["hash"],
                "REDACTED_FIELDS (backend) / REDACTED_KEYS (frontend)\n"
                "password · passwd · secret · token · api_key · authorization\n"
                "ssn · social_security · credit_card · card_number · cvv · dob\n"
                "date_of_birth · birth_date · full_name · first_name · last_name\n"
                "mobile · phone · phone_number · address  (20 fields total)",
                fontsize=7.5)
    arrow(ax, 2.7, 5.65, 2.7, 5.35, C["hash"], lw=1.5)
    rounded_box(ax, 2.7, 5.05, 4.4, 0.5, "#c0392b",
                "Value replaced with:  [REDACTED]", fontsize=9, bold=True)
    arrow(ax, 2.7, 4.8, 2.7, 4.55, C["hash"], lw=1.5)
    rounded_box(ax, 2.7, 4.25, 4.4, 0.5, C["api"],
                'Example: { "password": "abc123" }  →  { "password": "[REDACTED]" }',
                fontsize=7.5)

    # Dependencies box at bottom
    rounded_box(ax, 2.7, 2.55, 4.4, 1.7, "#2c3e50",
                "Backend Dependencies (requirements.txt):\n"
                "structlog >= 23.1.0, < 25.0.0\n"
                "presidio-analyzer >= 2.2.0\n"
                "presidio-anonymizer >= 2.2.0\n"
                "spacy >= 3.4.0, < 4.0.0\n"
                "en-core-web-sm @ 3.7.1  (spaCy English NLP model)\n"
                "Frontend: no extra deps — pure regex",
                fontsize=7.5)

    # ── PASS 2: Content-based Scan ───────────────────────────────────────────
    p2_grp = FancyBboxPatch((5.5, 0.2), 7.2, 7.1,
                             boxstyle="round,pad=0,rounding_size=0.1",
                             facecolor=C["viewer"] + "15", edgecolor=C["viewer"],
                             linewidth=1.8, linestyle="--", zorder=1)
    ax.add_patch(p2_grp)
    ax.text(9.1, 7.2, "Pass 2 — Async Content Scan  (scrub_text() / ThreadPoolExecutor)", ha="center", va="top",
            fontsize=8.5, color=C["viewer"], fontweight="bold")

    # Shared email pre-masking step
    rounded_box(ax, 9.1, 6.65, 6.6, 0.65, "#7f8c8d",
                "Shared pre-step (both backend & frontend): Email masking\n"
                "user@example.com  →  u***@example.com  (cheaper than NLP scan)",
                fontsize=8)
    arrow(ax, 9.1, 6.325, 9.1, 6.05, "#7f8c8d", lw=1.5)
    # Split to backend (left) and frontend (right)
    ax.annotate("", xy=(7.2, 5.75), xytext=(9.1, 6.05),
                arrowprops=dict(arrowstyle="->", color="#555", lw=1.3))
    ax.annotate("", xy=(10.9, 5.75), xytext=(9.1, 6.05),
                arrowprops=dict(arrowstyle="->", color="#555", lw=1.3))

    # ── BACKEND sub ──────────────────────────────────────────────────────────
    be_grp = FancyBboxPatch((5.7, 0.4), 3.1, 5.25,
                             boxstyle="round,pad=0,rounding_size=0.1",
                             facecolor=C["hash"] + "12", edgecolor=C["hash"],
                             linewidth=1.2, zorder=1)
    ax.add_patch(be_grp)
    ax.text(7.25, 5.55, "Backend (Python — Presidio, async)", ha="center", va="top",
            fontsize=8.5, color=C["hash"], fontweight="bold")

    rounded_box(ax, 7.25, 4.95, 2.8, 0.6, C["hash"],
                "AnalyzerEngine.analyze()\nlanguage='en'  entities list", fontsize=7.5)
    rounded_box(ax, 7.25, 3.95, 2.8, 1.1, C["hash"],
                "Entity types detected:\nPERSON · EMAIL_ADDRESS\nPHONE_NUMBER · CREDIT_CARD\nUS_SSN · IBAN_CODE · LOCATION\n(IP_ADDRESS excluded — kept for forensics)",
                fontsize=7)
    rounded_box(ax, 7.25, 2.9, 2.8, 0.65, C["hash"],
                "AnonymizerEngine.anonymize()\nOperatorConfig('replace')", fontsize=7.5)
    rounded_box(ax, 7.25, 2.0, 2.8, 0.55, C["api"],
                "→  <ENTITY_TYPE>  placeholder\n<PERSON>  <US_SSN>  <CREDIT_CARD>",
                fontsize=7.5, bold=True)
    rounded_box(ax, 7.25, 1.0, 2.8, 0.9, "#95a5a6",
                "Graceful degradation:\n_PRESIDIO_AVAILABLE = False\n→ Pass 1 field-name only\n(no exception raised)",
                fontsize=7, text_color="#444444")

    arrow(ax, 7.25, 4.65, 7.25, 4.5, C["hash"], lw=1.3)
    arrow(ax, 7.25, 3.95, 7.25, 3.58, C["hash"], lw=1.3)  # top of entities to bottom
    arrow(ax, 7.25, 2.9, 7.25, 2.575, C["hash"], lw=1.3)
    arrow(ax, 7.25, 2.0, 7.25, 1.775, C["hash"], lw=1.3)  # output to degradation note

    # ── FRONTEND sub ─────────────────────────────────────────────────────────
    fe_grp = FancyBboxPatch((9.1, 0.4), 3.4, 5.25,
                             boxstyle="round,pad=0,rounding_size=0.1",
                             facecolor=C["fe"] + "20", edgecolor=C["fe"],
                             linewidth=1.2, zorder=1)
    ax.add_patch(fe_grp)
    ax.text(10.8, 5.55, "Frontend (TypeScript — Regex)", ha="center", va="top",
            fontsize=8.5, color=C["fe"], fontweight="bold")

    rounded_box(ax, 10.8, 4.95, 3.0, 0.6, C["fe"],
                "contentScrubString(value)\nPII_PATTERNS: PiiPattern[]", fontsize=7.5)
    rounded_box(ax, 10.8, 3.75, 3.0, 1.5, C["fe"],
                "Regex patterns:\nUS_SSN:   \\b\\d{3}-\\d{2}-\\d{4}\\b\n"
                "CREDIT_CARD: (13-16 digits, spaces/dashes)\n"
                "PHONE_NUMBER: intl / US formats\n"
                "IBAN_CODE: [A-Z]{2}\\d{2}[A-Z0-9]+\n"
                "EMAIL_ADDRESS: safety net regex",
                fontsize=7)
    rounded_box(ax, 10.8, 2.55, 3.0, 0.6, C["api"],
                "→  <ENTITY_TYPE>  placeholder\n<US_SSN>  <CREDIT_CARD>  <PHONE_NUMBER>",
                fontsize=7.5, bold=True)
    rounded_box(ax, 10.8, 1.0, 3.0, 1.0, "#7f8c8d",
                "No ML model required\nRuns in browser / Node.js\nEntity labels mirror Presidio\nZero external dependencies",
                fontsize=7, text_color="#444444")

    arrow(ax, 10.8, 4.65, 10.8, 4.5, C["fe"], lw=1.3)
    arrow(ax, 10.8, 3.75, 10.8, 3.3, C["fe"], lw=1.3)
    arrow(ax, 10.8, 2.55, 10.8, 2.25, C["fe"], lw=1.3)

    return save_fig(fig, "14_presidio")


# ══════════════════════════════════════════════════════════════════════════════
# BUILD PDF
# ══════════════════════════════════════════════════════════════════════════════
def build_pdf(img_paths):
    pdf_path = os.path.join(OUT_DIR, "Activity_Logs_Full_Documentation.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=22*mm, bottomMargin=22*mm,
        title="Activity Logs Feature — Full Documentation",
        author="Fideon OS",
    )

    W, H = A4
    content_w = W - 36*mm

    styles = getSampleStyleSheet()
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    title_s   = S("Title2",   fontSize=26, leading=32, alignment=TA_CENTER,
                  textColor=colors.HexColor("#1a1a2e"), fontName="Helvetica-Bold", spaceAfter=6)
    sub_s     = S("Sub",      fontSize=13, leading=17, alignment=TA_CENTER,
                  textColor=colors.HexColor("#555555"), fontName="Helvetica", spaceAfter=4)
    h1_s      = S("H1",       fontSize=17, leading=21, textColor=colors.HexColor("#1a1a2e"),
                  fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=6,
                  borderPadding=(0,0,4,0))
    h2_s      = S("H2",       fontSize=13, leading=17, textColor=colors.HexColor("#16213e"),
                  fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    h3_s      = S("H3",       fontSize=11, leading=14, textColor=colors.HexColor("#2c3e50"),
                  fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3)
    body_s    = S("Body2",    fontSize=9.5, leading=13.5, textColor=colors.HexColor("#333333"),
                  fontName="Helvetica", spaceAfter=5, alignment=TA_JUSTIFY)
    cap_s     = S("Caption",  fontSize=8.5, leading=11, alignment=TA_CENTER,
                  textColor=colors.HexColor("#666"), fontName="Helvetica-Oblique", spaceAfter=12)
    code_s    = S("Code2",    fontSize=8, leading=11, fontName="Courier",
                  textColor=colors.HexColor("#1a1a2e"), backColor=colors.HexColor("#f4f4f8"),
                  spaceAfter=6, spaceBefore=3, leftIndent=8, rightIndent=8, borderPadding=4)
    bullet_s  = S("Bullet2",  fontSize=9.5, leading=14, fontName="Helvetica",
                  textColor=colors.HexColor("#333333"), leftIndent=18, spaceAfter=2,
                  bulletIndent=6)

    def img_full(path, caption="", scale=0.95):
        pil = PILImage.open(path)
        pw, ph = pil.size
        ratio = ph / pw
        iw = content_w * scale
        ih = iw * ratio
        if ih > H * 0.72:
            ih = H * 0.72
            iw = ih / ratio
        elems = [Image(path, width=iw, height=ih, hAlign="CENTER")]
        if caption:
            elems.append(Paragraph(caption, cap_s))
        return elems

    def hr():
        return HRFlowable(width="100%", thickness=0.8,
                          color=colors.HexColor("#dee2e6"), spaceAfter=8, spaceBefore=4)

    def role_badge_table():
        data = [
            ["Role", "Color Code", "Permissions Level", "Activity Page"],
            ["global_admin", "Red (#c0392b)",   "Full access — sees ALL logs from ALL roles", "YES All rows"],
            ["admin",        "Orange (#e67e22)", "Sees admin/user/viewer/guest — NOT global_admin", "YES Filtered rows"],
            ["user",         "Green (#27ae60)",  "Standard user — own logs only",             "YES Own rows only"],
            ["viewer",       "Blue (#2980b9)",   "Read-only — own logs only",                  "YES Own rows only"],
            ["guest",        "Grey (#95a5a6)",   "Most restricted — no activity page access",  "NO Blocked"],
        ]
        role_colors = ["#c0392b", "#e67e22", "#27ae60", "#2980b9", "#95a5a6"]
        ts = TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
             [colors.HexColor("#f8f9fa"), colors.white]*10),
            ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",  (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 7),
        ])
        for i, rc in enumerate(role_colors, 1):
            ts.add("TEXTCOLOR", (0,i), (0,i), colors.HexColor(rc))
            ts.add("FONTNAME",  (0,i), (0,i), "Helvetica-Bold")
        t = Table(data, colWidths=[2.8*cm, 3.2*cm, 8.5*cm, 3.5*cm])
        t.setStyle(ts)
        return t

    def atna_table():
        data = [
            ["Code", "Meaning", "Used For", "Type"],
            ["C", "Create",  "Creating new resources",              "Action"],
            ["R", "Read",    "Reading/viewing records",             "Action"],
            ["U", "Update",  "Modifying existing records",          "Action"],
            ["D", "Delete",  "Deleting records",                    "Action"],
            ["E", "Execute", "Executing operations (login/logout)", "Action"],
            ["0",  "Success",        "Operation completed normally", "Outcome"],
            ["4",  "Minor failure",  "Low severity issue",          "Outcome"],
            ["8",  "Serious failure","High severity problem",        "Outcome"],
            ["12", "Major failure",  "Critical error",              "Outcome"],
        ]
        out_colors = {5: "#27ae60", 6: "#f39c12", 7: "#e67e22", 8: "#c0392b"}
        ts = TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
             [colors.HexColor("#f8f9fa"), colors.white]*10),
            ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",  (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 7),
        ])
        for row_i, col in out_colors.items():
            ts.add("TEXTCOLOR", (0, row_i), (0, row_i), colors.HexColor(col))
            ts.add("FONTNAME",  (0, row_i), (0, row_i), "Helvetica-Bold")
        t = Table(data, colWidths=[1.5*cm, 3.5*cm, 9.0*cm, 3.5*cm])
        t.setStyle(ts)
        return t

    def event_table():
        data = [
            ["Event", "Description", "Actor", "action_code", "outcome_code", "resource_type"],
            ["login",                  "Successful sign-in",    "Any",         "E", "0", "auth_session"],
            ["login_failed",           "Failed sign-in attempt","Any",         "E", "8", "auth_session"],
            ["logout",                 "Sign-out click",        "Any",         "E", "0", "auth_session"],
            ["approve_pod:{model_id}", "Admin approves pod",    "admin/global","U", "0", "pod_activation"],
            ["reject_pod:{model_id}",  "Admin rejects pod",     "admin/global","U", "0", "pod_activation"],
        ]
        ts = TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#8e44ad")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
             [colors.HexColor("#f8f4ff"), colors.white]*5),
            ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",  (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("FONTNAME",    (0,1), (0,-1), "Courier"),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
        ])
        t = Table(data, colWidths=[4.2*cm, 3.5*cm, 2.5*cm, 2.0*cm, 2.2*cm, 3.5*cm])
        t.setStyle(ts)
        return t

    def rls_table():
        data = [
            ["Table", "Policy Name", "Operation", "Who", "Condition"],
            ["auth_audit", "Users insert own",        "INSERT", "Any auth user",  "auth.uid() = user_id"],
            ["auth_audit", "Users see own",           "SELECT", "user/viewer",      "user_id = auth.uid()"],
            ["auth_audit", "Admins see user+admin",   "SELECT", "admin",          "role IN (admin,user,viewer,guest)"],
            ["auth_audit", "Global admins see all",   "SELECT", "global_admin",   "No restriction"],
            ["audit_logs", "System can insert",       "INSERT", "Any",            "true"],
            ["audit_logs", "Users see own",           "SELECT", "Any",            "auth.uid() = user_id"],
            ["audit_logs", "Admins view all",         "SELECT", "admin/global",   "has_role(uid,'admin') [hierarchical: includes global_admin]"],
            ["device_sync_logs",  "Admins only view", "SELECT", "admin/global",   "has_role(uid,'admin') [hierarchical]"],
            ["device_usage_logs", "Admins only view", "SELECT", "admin/global",   "has_role(uid,'admin') [hierarchical]"],
        ]
        ts = TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
             [colors.HexColor("#f0f4f8"), colors.white]*10),
            ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#dee2e6")),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",  (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("FONTNAME",    (4,1), (4,-1), "Courier"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
        ])
        t = Table(data, colWidths=[3.2*cm, 4.5*cm, 2.2*cm, 2.8*cm, 5.2*cm])
        t.setStyle(ts)
        return t

    # ── Assemble story ────────────────────────────────────────────────────────
    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 2.5*cm),
        Paragraph("Activity Logs Feature", title_s),
        Paragraph("Full Technical Documentation", sub_s),
        Spacer(1, 0.3*cm),
        hr(),
        Spacer(1, 0.3*cm),
        Paragraph("Project: Fideon OS Platform", sub_s),
        Paragraph("Feature: Audit Trail &amp; Activity Log System", sub_s),
        Paragraph("Roles Covered: global_admin · admin · user · viewer · guest", sub_s),
        Paragraph("Date: 2026-03-16", sub_s),
        Spacer(1, 0.6*cm),
    ]
    story += img_full(img_paths["01"], "Figure 1 — Role Hierarchy Overview", scale=0.85)
    story.append(PageBreak())

    # ── SECTION 1: OVERVIEW ────────────────────────────────────────────────────
    story += [
        Paragraph("1. Feature Overview", h1_s), hr(),
        Paragraph(
            "The <b>Activity Logs</b> system provides a tamper-evident, role-scoped audit trail "
            "of all significant actions taken across the Fideon OS platform. It is built on "
            "<b>two Supabase PostgreSQL tables</b> (<i>auth_audit</i> and <i>audit_logs</i>), enforced "
            "by PostgreSQL <b>Row-Level Security (RLS)</b> policies, and surfaced to users via the "
            "<b>/activity</b> frontend page.",
            body_s),
        Spacer(1, 0.3*cm),
        Paragraph("Core Design Principles", h2_s),
    ]
    principles = [
        ("<b>Tamper-Evidence:</b>", "Each auth_audit row stores a SHA-256 integrity_hash computed from non-PII fields. Any post-write modification invalidates the hash."),
        ("<b>Privacy (PII Protection):</b>", "The email field is stored in the row but deliberately excluded from the integrity hash. Backend server logs use PII scrubbing for fields like password, token, email, phone, ssn."),
        ("<b>Least Privilege:</b>", "Each role sees only what they are authorized to see via RLS policies. Users see only their own rows; admins see their org; global_admin sees all."),
        ("<b>ATNA Compliance:</b>", "Action codes (C/R/U/D/E) and outcome codes (0/4/8/12) follow the ATNA (Audit Trail and Node Authentication) healthcare audit standard."),
        ("<b>Immutability:</b>", "Audit rows are protected by PostgreSQL BEFORE UPDATE / BEFORE DELETE triggers (prevent_audit_modification()) that raise an exception for any modification attempt — including service_role and direct DB connections. This enforces EU AI Act Art.12, SOC2 CC7.2, and NAIC compliance."),
    ]
    for title, desc in principles:
        story.append(Paragraph(f"• {title} {desc}", bullet_s))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 2: ROLES ────────────────────────────────────────────────────
    story += [
        Paragraph("2. Role Definitions &amp; Hierarchy", h1_s), hr(),
        Paragraph(
            "The platform uses a <b>five-tier role model</b> stored as a PostgreSQL enum "
            "(<code>app_role</code>) and managed through the <code>user_roles</code> table. "
            "Only <b>global_admin</b> can assign or change roles.",
            body_s),
        Spacer(1, 0.3*cm),
        role_badge_table(),
        Spacer(1, 0.6*cm),
    ]
    story += img_full(img_paths["01"], "Figure 2 — Role Hierarchy with Promotion Paths", scale=0.80)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 3: ER DIAGRAM ──────────────────────────────────────────────
    story += [
        Paragraph("3. Entity-Relationship (ER) Diagram", h1_s), hr(),
        Paragraph(
            "The diagram below shows all seven database tables and their relationships. "
            "The <b>auth_audit</b> and <b>audit_logs</b> tables both reference <b>auth.users</b> "
            "via user_id. Device-related logs are linked to the <b>devices</b> table.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["02"], "Figure 3 — Full Entity-Relationship Diagram", scale=0.98)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 4: SCHEMA ─────────────────────────────────────────────────
    story += [
        Paragraph("4. Database Schema — Column-Level Detail", h1_s), hr(),
        Paragraph(
            "Detailed column specifications for the two primary audit tables and the role "
            "assignment table, including data types, constraints, and descriptions.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["03"], "Figure 4 — Schema Column Detail Diagram", scale=0.98)
    story += [Spacer(1, 0.4*cm)]

    story += [
        Paragraph("4.1 auth_audit — SQL Definition", h2_s),
        Paragraph(
            "CREATE TABLE public.auth_audit (<br/>"
            "&nbsp;&nbsp;id &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;UUID &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;PRIMARY KEY DEFAULT gen_random_uuid(),<br/>"
            "&nbsp;&nbsp;user_id &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;UUID &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;NOT NULL REFERENCES auth.users(id),<br/>"
            "&nbsp;&nbsp;email &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;role &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;event &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;action_code &nbsp;&nbsp;&nbsp;TEXT, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-- ATNA: C/R/U/D/E<br/>"
            "&nbsp;&nbsp;outcome_code &nbsp;&nbsp;INTEGER, &nbsp;&nbsp;-- ATNA: 0/4/8/12<br/>"
            "&nbsp;&nbsp;resource_type &nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;resource_id &nbsp;&nbsp;&nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;integrity_hash &nbsp;TEXT, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-- SHA-256 tamper-evidence<br/>"
            "&nbsp;&nbsp;created_at &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;TIMESTAMPTZ DEFAULT now()<br/>"
            ");",
            code_s),
        Spacer(1, 0.3*cm),
        Paragraph("4.2 audit_logs — SQL Definition", h2_s),
        Paragraph(
            "CREATE TABLE public.audit_logs (<br/>"
            "&nbsp;&nbsp;id &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;UUID &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;PRIMARY KEY DEFAULT gen_random_uuid(),<br/>"
            "&nbsp;&nbsp;user_id &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;UUID &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;REFERENCES auth.users(id),<br/>"
            "&nbsp;&nbsp;action &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;TEXT &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;NOT NULL,<br/>"
            "&nbsp;&nbsp;resource_type &nbsp;TEXT &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;NOT NULL,<br/>"
            "&nbsp;&nbsp;resource_id &nbsp;&nbsp;&nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;details &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;JSONB,<br/>"
            "&nbsp;&nbsp;previous_value &nbsp;JSONB, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-- before-state, PII-scrubbed (added migration 20260316000002)<br/>"
            "&nbsp;&nbsp;new_value &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;JSONB, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-- after-state, PII-scrubbed (added migration 20260316000002)<br/>"
            "&nbsp;&nbsp;ip_address &nbsp;&nbsp;&nbsp;&nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;user_agent &nbsp;&nbsp;&nbsp;&nbsp;TEXT,<br/>"
            "&nbsp;&nbsp;integrity_hash &nbsp;TEXT, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-- SHA-256 tamper-evidence (added migration 20260316000001)<br/>"
            "&nbsp;&nbsp;created_at &nbsp;&nbsp;&nbsp;&nbsp;TIMESTAMPTZ DEFAULT now()<br/>"
            ");<br/>"
            "CREATE INDEX idx_audit_logs_user_id ON public.audit_logs (user_id);<br/>"
            "CREATE INDEX idx_audit_logs_resource_type ON public.audit_logs (resource_type);<br/>"
            "CREATE INDEX idx_audit_logs_resource_id ON public.audit_logs (resource_id) WHERE resource_id IS NOT NULL;<br/>"
            "CREATE INDEX idx_audit_logs_created_at ON public.audit_logs (created_at DESC);",
            code_s),
        PageBreak(),
    ]

    # ── SECTION 5: RLS ────────────────────────────────────────────────────
    story += [
        Paragraph("5. Row-Level Security (RLS) Policies", h1_s), hr(),
        Paragraph(
            "All audit tables have RLS <b>enabled</b>. The policies enforce that each role "
            "can only access the rows it is authorized to see. There are <b>no UPDATE or DELETE "
            "policies</b> and additionally, <b>database-level BEFORE UPDATE / BEFORE DELETE triggers</b> "
            "(<code>prevent_audit_modification()</code>) make audit records truly immutable — "
            "even <code>service_role</code> and direct Postgres connections cannot modify rows. "
            "The <code>has_role(uid, 'admin')</code> helper function is <b>hierarchical</b> "
            "and returns true for both <code>admin</code> and <code>global_admin</code>, "
            "so global_admin retains full access to device logs and audit_logs via those policies.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["04"], "Figure 5 — RLS Policy Decision Flow", scale=0.95)
    story += [Spacer(1, 0.4*cm), rls_table(), Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 6: DATA FLOW ──────────────────────────────────────────────
    story += [
        Paragraph("6. Data Flow — How Logs Are Created", h1_s), hr(),
        Paragraph(
            "Every audit row follows a <b>five-step pipeline</b>: the user triggers an action in "
            "the frontend, the relevant component captures the event, <code>auditHash.ts</code> "
            "computes a SHA-256 integrity hash, the Supabase RLS INSERT policy validates the caller, "
            "and finally the row is persisted in the <code>auth_audit</code> table.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["05"], "Figure 6 — Audit Data Flow with Swim Lanes", scale=0.97)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 7: SEQUENCES ──────────────────────────────────────────────
    story += [
        Paragraph("7. Sequence Diagrams", h1_s), hr(),
        Paragraph("7.1 Login Audit Event", h2_s),
        Paragraph(
            "When a user successfully signs in, <code>Auth.tsx</code> immediately captures the "
            "timestamp, calls <code>auditHash.ts</code> to compute the integrity hash, then "
            "inserts a <code>login</code> event row into <code>auth_audit</code>.",
            body_s),
    ]
    story += img_full(img_paths["06"], "Figure 7 — Login Audit Sequence", scale=0.95)
    story += [Spacer(1, 0.4*cm)]

    story += [
        Paragraph("7.2 Admin Approves Pod Activation", h2_s),
        Paragraph(
            "When an admin clicks Approve on a pod request, the component first updates the "
            "pod_activation_requests table, then computes the audit hash and writes an "
            "<code>approve_pod:{model_id}</code> event to <code>auth_audit</code>.",
            body_s),
    ]
    story += img_full(img_paths["07"], "Figure 8 — Admin Approve Pod Sequence", scale=0.95)
    story += [PageBreak()]

    story += [
        Paragraph("7.3 Viewing Activity Logs", h2_s),
        Paragraph(
            "When any authenticated user navigates to <b>/activity</b>, <code>Activity.tsx</code> "
            "issues a SELECT query. The Supabase RLS layer automatically filters rows based on "
            "the caller's role — global_admin sees all, admin sees most, user/viewer sees only "
            "their own rows, and guest receives nothing.",
            body_s),
    ]
    story += img_full(img_paths["08"], "Figure 9 — View Activity Logs Sequence", scale=0.95)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 8: HASH ───────────────────────────────────────────────────
    story += [
        Paragraph("8. Audit Integrity Hash — Tamper Evidence", h1_s), hr(),
        Paragraph(
            "Every row in <code>auth_audit</code> includes an <code>integrity_hash</code> field "
            "computed using <b>SHA-256</b> via the Web Crypto API (<code>crypto.subtle.digest</code>). "
            "The hash is computed from <b>eight non-PII fields</b>. The email field is deliberately "
            "<b>excluded</b> from the hash to protect personally identifiable information.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["09"], "Figure 10 — Integrity Hash Computation & Verification", scale=0.95)
    story += [Spacer(1, 0.4*cm)]

    story += [
        Paragraph("Hash Input Fields", h2_s),
        Paragraph("• <b>user_id</b> — the UUID of the acting user", bullet_s),
        Paragraph("• <b>role</b> — the user's role at time of action", bullet_s),
        Paragraph("• <b>event</b> — the event name (login, logout, approve_pod, etc.)", bullet_s),
        Paragraph("• <b>action_code</b> — ATNA action code (C/R/U/D/E)", bullet_s),
        Paragraph("• <b>outcome_code</b> — ATNA outcome code (0/4/8/12)", bullet_s),
        Paragraph("• <b>resource_type</b> — resource category (auth_session, pod_activation)", bullet_s),
        Paragraph("• <b>resource_id</b> — specific resource identifier (<b>nullable</b>: passed as null for auth_session events such as login / login_failed / logout)", bullet_s),
        Paragraph("• <b>created_at</b> — ISO 8601 timestamp", bullet_s),
        Spacer(1, 0.3*cm),
        Paragraph("<b>Excluded from hash:</b> email (PII — stored in row but not hashed)", body_s),
        PageBreak(),
    ]

    # ── SECTION 9: COMPONENTS ─────────────────────────────────────────────
    story += [
        Paragraph("9. Frontend Component Architecture", h1_s), hr(),
        Paragraph(
            "The frontend is a React/TypeScript single-page application. Role detection is "
            "centralized in the <code>useUserRole</code> hook. All audit writes flow through "
            "<code>auditHash.ts</code>. Route protection is enforced by <code>ProtectedRoute.tsx</code>.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["10"], "Figure 11 — Frontend Component Architecture Diagram", scale=0.97)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 10: ACCESS MATRIX ─────────────────────────────────────────
    story += [
        Paragraph("10. Access Control Matrix", h1_s), hr(),
        Paragraph(
            "The matrix below provides a complete overview of which roles can perform "
            "which operations across the activity logs system and related features.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["11"], "Figure 12 — Full Access Control Matrix", scale=0.97)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 11: EVENTS ────────────────────────────────────────────────
    story += [
        Paragraph("11. Event Types &amp; ATNA Codes", h1_s), hr(),
        Paragraph(
            "The table below lists all audit event types currently implemented, along with "
            "the ATNA-standard action and outcome codes, and the resource types they apply to.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["12"], "Figure 13 — Event Types & ATNA Codes Reference", scale=0.95)
    story += [Spacer(1, 0.4*cm)]

    story += [Paragraph("Event Types Table", h2_s), event_table(), Spacer(1, 0.4*cm)]
    story += [Paragraph("ATNA Code Reference", h2_s), atna_table(), PageBreak()]

    # ── SECTION 12: BACKEND ───────────────────────────────────────────────
    story += [
        Paragraph("12. Backend Logging Architecture", h1_s), hr(),
        Paragraph(
            "In addition to the Supabase-based audit tables, the FastAPI backend implements "
            "structured JSON logging via <b>structlog</b>. A <code>RequestLoggingMiddleware</code> "
            "intercepts every HTTP request, assigns a unique <code>request_id</code>, and logs "
            "method, path, client IP, status code, and duration. "
            "Unhandled exceptions are captured at <b>ERROR</b> level with full traceback "
            "(<code>exc_info=True</code>) before being re-raised, so 500s are never invisible. "
            "The log level is configurable via the <code>LOG_LEVEL</code> environment variable "
            "(default: <code>INFO</code>). Log files use a <b>RotatingFileHandler</b> "
            "(10 MB per file, 5 backups — 50 MB max on disk), preventing unbounded disk growth. "
            "A <b>two-pass PII scrubbing pipeline</b> protects all log output — "
            "Pass 1 (field-name keywords, sync) runs in the structlog processor chain; "
            "Pass 2 (Microsoft Presidio NLP) runs <b>asynchronously</b> via "
            "<code>scrub_text()</code> and a <code>ThreadPoolExecutor(max_workers=2)</code> "
            "so the asyncio event loop is never blocked — see Section 13 for full detail. "
            "A startup warning is emitted if Presidio is unavailable. "
            "An <code>insert_audit_log()</code> helper in <code>backend/app/core/supabase.py</code> "
            "is called by all admin and pod activation routes to write rows into <code>audit_logs</code> "
            "with <b>ip_address</b>, <b>user_agent</b>, and a server-side <b>SHA-256 integrity_hash</b>. "
            "Audit writes are fire-and-forget — failures are silently swallowed so auditing "
            "never blocks the main request path.",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["13"], "Figure 14 — Backend Logging Architecture", scale=0.96)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 13: PII DETECTION ─────────────────────────────────────────
    story += [
        Paragraph("13. PII Detection — Presidio &amp; Regex", h1_s), hr(),
        Paragraph(
            "All log data passes through a <b>two-pass PII scrubbing pipeline</b> before being "
            "written to any output. The pipeline runs in "
            "<code>backend/app/logger/__init__.py</code> (Python/Presidio) and is mirrored in "
            "<code>frontend/src/logger/index.ts</code> (TypeScript/regex).",
            body_s),
        Spacer(1, 0.15*cm),
        Paragraph("Pass 1 — Field-name Keyword Match", h2_s),
        Paragraph(
            "Every key in the log payload is compared against a hard-coded set of 20 sensitive "
            "field names (case-insensitive). A match unconditionally replaces the value with "
            "<code>[REDACTED]</code> — regardless of the actual content. "
            "Fields covered: <code>password</code>, <code>passwd</code>, <code>secret</code>, "
            "<code>token</code>, <code>api_key</code>, <code>authorization</code>, "
            "<code>ssn</code>, <code>social_security</code>, <code>credit_card</code>, "
            "<code>card_number</code>, <code>cvv</code>, <code>dob</code>, "
            "<code>date_of_birth</code>, <code>birth_date</code>, <code>full_name</code>, "
            "<code>first_name</code>, <code>last_name</code>, <code>mobile</code>, "
            "<code>phone</code>, <code>phone_number</code>, <code>address</code>.",
            body_s),
        Spacer(1, 0.15*cm),
        Paragraph("Pass 2 — Async Content-based PII Detection", h2_s),
        Paragraph(
            "After field-name scrubbing, string values can be scanned for PII content — "
            "catching sensitive data inside generic fields like <code>message</code> or "
            "<code>details</code> regardless of the key name. "
            "<b>Pass 2 does NOT run inside the sync structlog processor</b> — doing so would "
            "block the asyncio event loop under load. Instead, Pass 2 is exposed as "
            "<code>await scrub_text(value)</code>, an async helper that offloads Presidio "
            "NLP work to a dedicated <code>ThreadPoolExecutor(max_workers=2)</code> via "
            "<code>loop.run_in_executor()</code>. Call it from route handlers or middleware "
            "whenever you need to log potentially sensitive free-text content.",
            body_s),
        Paragraph(
            "On the <b>backend</b>, Microsoft <b>Presidio</b> (presidio-analyzer + "
            "presidio-anonymizer) uses a <b>spaCy</b> English NLP model to detect named "
            "entities. Detected entities are replaced with labelled placeholders such as "
            "<code>&lt;PERSON&gt;</code>, <code>&lt;US_SSN&gt;</code>, "
            "<code>&lt;CREDIT_CARD&gt;</code>. Email addresses are pre-masked to "
            "<code>u***@domain</code> format before the Presidio scan. "
            "If Presidio or the spaCy model is unavailable, <code>_PRESIDIO_AVAILABLE</code> "
            "is set to <code>False</code>, a startup warning is logged, and the system "
            "degrades gracefully to Pass 1 only — no exception is raised.",
            body_s),
        Paragraph(
            "On the <b>frontend</b>, <code>contentScrubString()</code> applies regex-based "
            "<code>PII_PATTERNS</code> that mirror Presidio entity labels, producing identical "
            "<code>&lt;ENTITY_TYPE&gt;</code> replacements. No ML model is required — "
            "the patterns run in-browser or in Node.js with zero additional dependencies.",
            body_s),
        Spacer(1, 0.2*cm),
    ]

    # Entity type table
    presidio_data = [
        ["Entity Type",    "Example Input",              "Replacement",     "Backend",              "Frontend"],
        ["PERSON",         "John Smith",                 "<PERSON>",        "Presidio NLP",         "—"],
        ["EMAIL_ADDRESS",  "user@example.com",           "u***@example.com","Email mask + Presidio","Email mask + regex"],
        ["PHONE_NUMBER",   "+1 (555) 123-4567",          "<PHONE_NUMBER>",  "Presidio NLP",         "Regex"],
        ["CREDIT_CARD",    "4111 1111 1111 1111",        "<CREDIT_CARD>",   "Presidio NLP",         "Regex"],
        ["US_SSN",         "123-45-6789",                "<US_SSN>",        "Presidio NLP",         "Regex"],
        ["IBAN_CODE",      "GB29NWBK60161331926819",     "<IBAN_CODE>",     "Presidio NLP",         "Regex"],
        ["LOCATION",       "New York, NY",               "<LOCATION>",      "Presidio NLP",         "—"],
        ["IP_ADDRESS",     "192.168.1.1",                "(kept — forensic)","Intentionally excluded","—"],
    ]
    ts_pii = TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1),
         [colors.HexColor("#f8f9fa"), colors.white]*10),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#dee2e6")),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("FONTNAME",      (2,1), (2,-1), "Courier"),
        ("TEXTCOLOR",     (-2,1),(-2,-1), colors.HexColor("#d35400")),
        ("TEXTCOLOR",     (-1,1),(-1,-1), colors.HexColor("#1abc9c")),
    ])
    t_pii = Table(presidio_data, colWidths=[3.5*cm, 4.2*cm, 4.0*cm, 3.8*cm, 2.0*cm])
    t_pii.setStyle(ts_pii)
    story += [t_pii, Spacer(1, 0.3*cm)]

    story += [
        Paragraph("Backend Installation", h3_s),
        Paragraph(
            "pip install presidio-analyzer presidio-anonymizer "
            "spacy  &amp;&amp;  python -m spacy download en_core_web_sm",
            code_s),
        Paragraph(
            "Or via <code>requirements.txt</code>: <code>presidio-analyzer&gt;=2.2.0</code>, "
            "<code>presidio-anonymizer&gt;=2.2.0</code>, <code>spacy&gt;=3.4.0,&lt;4.0.0</code>, "
            "<code>en-core-web-sm @ https://github.com/explosion/spacy-models/...</code>",
            body_s),
        Spacer(1, 0.2*cm),
    ]
    story += img_full(img_paths["14"], "Figure 15 — PII Scrubbing Pipeline (Two-Pass Architecture)", scale=0.96)
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 14: FILE REFERENCE ────────────────────────────────────────
    story += [
        Paragraph("14. File Reference", h1_s), hr(),
        Paragraph("Key source files implementing the Activity Logs feature:", body_s),
        Spacer(1, 0.2*cm),
    ]
    file_data = [
        ["Category", "File Path", "Purpose"],
        ["DB Migration", "supabase/migrations/20260313091500_auth_audit_logs.sql",               "auth_audit table + RLS policies"],
        ["DB Migration", "supabase/migrations/20251116145514_03b8c065-31f2-46c1-a062-a1f2e4363a04.sql", "audit_logs table + RLS policies"],
        ["DB Migration", "supabase/migrations/20260312193000_fnf9_schema_closure.sql",          "Role enum + user_roles + roles tables"],
        ["DB Migration", "supabase/migrations/20260312194000_fnf10_rls_hardening.sql",          "RLS hardening pass"],
        ["DB Migration", "supabase/migrations/20260316000000_auth_audit_user_id_fk.sql",        "FK constraint auth_audit.user_id -> auth.users(id)"],
        ["DB Migration", "supabase/migrations/20260316000001_audit_immutability.sql",           "Immutability triggers + integrity_hash on audit_logs + archive tables"],
        ["DB Migration", "supabase/migrations/20260316000002_audit_logs_change_tracking.sql",   "previous_value + new_value JSONB columns + resource_id index on audit_logs"],
        ["Frontend Page", "frontend/src/app-pages/Activity.tsx",                               "Activity log UI page"],
        ["Frontend Lib",  "frontend/src/lib/auditHash.ts",                                     "SHA-256 integrity hash utility"],
        ["Frontend Page", "frontend/src/app-pages/Auth.tsx",                                   "Login/login_failed audit writer (resource_id: null)"],
        ["Frontend Comp", "frontend/src/components/Layout.tsx",                                "Logout audit event writer (resource_id: null)"],
        ["Frontend Comp", "frontend/src/components/admin/PodActivationRequests.tsx",           "Pod approve/reject audit"],
        ["Frontend Comp", "frontend/src/components/AppSidebar.tsx",                           "Role-filtered navigation"],
        ["Frontend Hook", "frontend/src/hooks/useUserRole.ts",                                "Role detection hook"],
        ["Backend",       "backend/app/core/supabase.py",                                     "insert_audit_log() helper (ip_address, user_agent, integrity_hash)"],
        ["Backend",       "backend/app/routes/admin.py",                                      "Admin API endpoints + create_user/set_role audit calls"],
        ["Backend",       "backend/app/routes/pod_activation.py",                             "Pod activation endpoints + approve/reject/allocate audit calls"],
        ["Backend",       "backend/app/logger/__init__.py",                                   "Structured request logging + two-pass Presidio PII scrubber"],
        ["Backend",       "backend/requirements.txt",                                         "presidio-analyzer, presidio-anonymizer, spacy, en-core-web-sm"],
        ["Frontend",      "frontend/src/logger/index.ts",                                     "Pino logger + two-pass PII scrubber (field-name + regex content scan)"],
    ]
    ts_f = TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),
         [colors.HexColor("#f8f9fa"), colors.white]*15),
        ("GRID",         (0,0), (-1,-1), 0.4, colors.HexColor("#dee2e6")),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("FONTNAME",     (1,1), (1,-1), "Courier"),
        ("LEFTPADDING",  (0,0), (-1,-1), 5),
    ])
    t_f = Table(file_data, colWidths=[3.2*cm, 8.5*cm, 5.8*cm])
    t_f.setStyle(ts_f)
    story.append(t_f)
    story += [Spacer(1, 0.6*cm)]

    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── SECTION 15: COMPLIANCE & IMMUTABILITY ─────────────────────────────
    story += [
        Paragraph("15. Compliance &amp; Immutability", h1_s), hr(),
        Paragraph(
            "The Activity Logs system is designed to meet the audit trail requirements of "
            "<b>EU AI Act (Art. 12/13)</b>, <b>SOC2 (CC7.2/CC9.1)</b>, and <b>NAIC AI Bulletin</b>. "
            "The following mechanisms are in place:",
            body_s),
        Spacer(1, 0.3*cm),
        Paragraph("15.1 Database-Level Immutability", h2_s),
        Paragraph(
            "Migration <code>20260316000001_audit_immutability.sql</code> installs four "
            "<b>BEFORE UPDATE / BEFORE DELETE</b> triggers on both <code>auth_audit</code> and "
            "<code>audit_logs</code>. The trigger function <code>prevent_audit_modification()</code> "
            "raises a <code>P0001</code> exception for any modification attempt. "
            "This fires regardless of RLS bypass — service_role, backend calls, and direct "
            "Postgres connections are all blocked. Only a superuser running "
            "<code>ALTER TABLE ... DISABLE TRIGGER</code> can circumvent this, and that action "
            "is itself logged by Postgres.",
            body_s),
        Spacer(1, 0.2*cm),
        Paragraph(
            "Verified behavior in Supabase SQL Editor (role: postgres):",
            body_s),
        Paragraph(
            "UPDATE public.auth_audit SET event = 'tampered' WHERE id = (...);",
            code_s),
        Paragraph(
            "Result: <b>ERROR P0001: Audit log records are immutable "
            "(EU AI Act Art.12 / SOC2 CC7.2 / NAIC). "
            "Operation &quot;UPDATE&quot; on table &quot;auth_audit&quot; is not permitted.</b>",
            body_s),
        Spacer(1, 0.3*cm),
        Paragraph("15.2 Integrity Hash Coverage", h2_s),
        Paragraph(
            "Both audit tables now carry <code>integrity_hash</code> (SHA-256). "
            "For <b>auth_audit</b>: computed in <code>auditHash.ts</code> (frontend, Web Crypto API) "
            "over 8 non-PII fields before insert. "
            "For <b>audit_logs</b>: computed in <code>insert_audit_log()</code> (backend, Python hashlib) "
            "over user_id, action, resource_type, resource_id, created_at before insert. "
            "Email and other PII are excluded from both hashes.",
            body_s),
        Spacer(1, 0.3*cm),
        Paragraph("15.3 IP Address &amp; User Agent Capture", h2_s),
        Paragraph(
            "All backend-initiated audit writes (admin actions, pod approvals/rejections, "
            "model allocations) populate <code>ip_address</code> from <code>request.client.host</code> "
            "and <code>user_agent</code> from the HTTP request header. "
            "This provides a complete forensic trail for regulatory review.",
            body_s),
        Spacer(1, 0.3*cm),
        Paragraph("15.4 Retention Policy", h2_s),
        Paragraph(
            "EU AI Act requires logs retained for a minimum of <b>6 months</b>; SOC2 and NAIC "
            "require <b>12 months</b>. The following architecture is implemented via "
            "<b>pg_cron</b> (enabled in Supabase):",
            body_s),
        Spacer(1, 0.1*cm),
        Paragraph(
            "• <b>audit_logs_archive</b> and <b>auth_audit_archive</b> tables mirror the live "
            "tables with identical immutability triggers.",
            bullet_s),
        Paragraph(
            "• A <code>SECURITY DEFINER</code> function (<code>archive_old_audit_logs()</code> / "
            "<code>archive_old_auth_audit()</code>) copies rows older than 12 months to the "
            "archive tables, then deletes from the live table. This is the only controlled "
            "exception to the immutability rule.",
            bullet_s),
        Paragraph(
            "• A pg_cron job runs every Sunday at 02:00 UTC: "
            "<code>SELECT cron.schedule('archive-old-audit-logs', '0 2 * * 0', ...)</code>",
            bullet_s),
        Spacer(1, 0.3*cm),
        Paragraph("15.5 Compliance Framework Coverage", h2_s),
    ]
    compliance_data = [
        ["Framework", "Requirement", "Implementation"],
        ["EU AI Act Art.12/13", "Immutable, traceable AI decision logs", "Immutability triggers + integrity_hash"],
        ["EU AI Act Art.12",    "Retain logs >= 6 months",               "pg_cron archival — rows never deleted"],
        ["SOC2 CC7.2",          "No unauthorized modification",          "DB triggers block all UPDATE/DELETE"],
        ["SOC2 CC9.1",          "Complete and accurate audit trail",     "ip_address + user_agent + integrity_hash"],
        ["NAIC AI Bulletin",    "Full AI decision audit trail",          "approve_pod/reject_pod logged with details"],
        ["NAIC AI Bulletin",    "Available for regulatory review",       "audit_logs_archive retained indefinitely"],
    ]
    ts_c = TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1),
         [colors.HexColor("#e8f8f5"), colors.white]*10),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#dee2e6")),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
    ])
    t_c = Table(compliance_data, colWidths=[4.5*cm, 6.5*cm, 6.5*cm])
    t_c.setStyle(ts_c)
    story += [t_c, Spacer(1, 0.6*cm)]

    story += [
        hr(),
        Paragraph(
            "<i>This document was auto-generated from the Fideon OS codebase. "
            "All diagrams are drawn from live source code analysis. "
            "Generated on 2026-03-16.</i>",
            cap_s),
    ]

    doc.build(story)
    return pdf_path


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating diagrams...")
    img_paths = {
        "01": diag_role_hierarchy(),
        "02": diag_er(),
        "03": diag_schema(),
        "04": diag_rls(),
        "05": diag_data_flow(),
        "06": diag_seq_login(),
        "07": diag_seq_pod(),
        "08": diag_seq_view(),
        "09": diag_hash(),
        "10": diag_components(),
        "11": diag_access_matrix(),
        "12": diag_events(),
        "13": diag_backend(),
        "14": diag_presidio(),
    }
    print(f"  Generated {len(img_paths)} diagrams in {IMG_DIR}")

    print("Building PDF...")
    pdf = build_pdf(img_paths)
    print(f"\nYES PDF created: {pdf}")
