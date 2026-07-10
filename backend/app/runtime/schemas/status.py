"""
运行时状态常量 — 定义所有实体允许的状态值

Conversation: created / active / closed / archived
Session:      created / running / success / failed / cancelled / expired
Prompt:       draft / active / inactive / archived
Trace:        success / failed / running
Feedback:     inaccurate / incomplete / useful / unsafe / other
"""

# ── Conversation ──
CONV_CREATED = "created"
CONV_ACTIVE = "active"
CONV_CLOSED = "closed"
CONV_ARCHIVED = "archived"
CONV_STATUSES = {CONV_CREATED, CONV_ACTIVE, CONV_CLOSED, CONV_ARCHIVED}

# ── Session ──
SESS_CREATED = "created"
SESS_RUNNING = "running"
SESS_SUCCESS = "success"
SESS_FAILED = "failed"
SESS_CANCELLED = "cancelled"
SESS_EXPIRED = "expired"
SESS_STATUSES = {SESS_CREATED, SESS_RUNNING, SESS_SUCCESS, SESS_FAILED, SESS_CANCELLED, SESS_EXPIRED}

# ── Prompt ──
PR_DRAFT = "draft"
PR_ACTIVE = "active"
PR_INACTIVE = "inactive"
PR_ARCHIVED = "archived"
PR_STATUSES = {PR_DRAFT, PR_ACTIVE, PR_INACTIVE, PR_ARCHIVED}

# ── Trace ──
TRACE_SUCCESS = "success"
TRACE_FAILED = "failed"
TRACE_RUNNING = "running"
TRACE_STATUSES = {TRACE_SUCCESS, TRACE_FAILED, TRACE_RUNNING}

# ── Feedback type ──
FB_INACCURATE = "inaccurate"
FB_INCOMPLETE = "incomplete"
FB_USEFUL = "useful"
FB_UNSAFE = "unsafe"
FB_OTHER = "other"
FB_TYPES = {FB_INACCURATE, FB_INCOMPLETE, FB_USEFUL, FB_UNSAFE, FB_OTHER}
