"""
UCAT Prep — a Streamlit study app.

Pages: Dashboard (analytics), Practice Questions, Flashcards (spaced repetition),
Study Scheduler, Strategy & Skills, and an AI Tutor powered by Claude.

Covers the four current UCAT subtests: Verbal Reasoning, Decision Making,
Quantitative Reasoning, and Situational Judgement.

Runs on Neon / any PostgreSQL when DATABASE_URL is set, otherwise on a local
SQLite file. Set ANTHROPIC_API_KEY to enable the AI Tutor and APP_PASSWORD to
gate access.
"""

import os
import random
from datetime import date, datetime, timedelta

# Pull secrets into the environment before the data layer reads DATABASE_URL.
try:
    import streamlit as _st_pre
    for _key in ("DATABASE_URL", "ANTHROPIC_API_KEY", "APP_PASSWORD"):
        if _key in _st_pre.secrets:
            os.environ.setdefault(_key, str(_st_pre.secrets[_key]))
except Exception:
    pass

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

import database as db

# ── Cached data access ───────────────────────────────────────────────────────
# Every repeated database read goes through one of these st.cache_data wrappers,
# so identical reads within a rerun (e.g. two widgets needing the same data) and
# across reruns (e.g. navigating pages without editing anything) are served from
# memory instead of re-querying. Every write path calls the matching cache
# .clear() immediately after writing, so nothing is ever stale after a user
# action — the TTLs below are just a safety net, not the source of correctness.

@st.cache_data(ttl=3600, show_spinner=False)
def cached_subjects():
    return db.get_subjects()


@st.cache_data(ttl=300, show_spinner=False)
def cached_questions(subject_id=None, difficulty=None):
    return db.get_questions(subject_id=subject_id, difficulty=difficulty)


@st.cache_data(ttl=300, show_spinner=False)
def cached_question_counts():
    return db.get_question_counts_by_subject()


@st.cache_data(ttl=300, show_spinner=False)
def cached_topics(subject_id=None, high_yield_only=False):
    return db.get_topics(subject_id=subject_id, high_yield_only=high_yield_only)


@st.cache_data(ttl=300, show_spinner=False)
def cached_flashcard_bank():
    return db.get_flashcard_bank()


@st.cache_data(ttl=60, show_spinner=False)
def cached_overall_stats(uid):
    return db.get_overall_stats(uid)


@st.cache_data(ttl=60, show_spinner=False)
def cached_accuracy_by_subject(uid):
    return db.get_accuracy_by_subject(uid)


@st.cache_data(ttl=60, show_spinner=False)
def cached_attempts_over_time(uid, days):
    return db.get_attempts_over_time(uid, days)


@st.cache_data(ttl=60, show_spinner=False)
def cached_study_tasks(uid, status=None):
    return db.get_study_tasks(uid, status=status)


@st.cache_data(ttl=60, show_spinner=False)
def cached_flashcards(uid, subject_id=None, due_only=False):
    return db.get_flashcards(uid, subject_id=subject_id, due_only=due_only)


def _invalidate_content_cache():
    """Call after any write to the shared questions/topics/flashcards content bank."""
    cached_questions.clear()
    cached_question_counts.clear()
    cached_topics.clear()
    cached_flashcard_bank.clear()


def _invalidate_stats_cache():
    """Call after any write that can change a user's stats/analytics."""
    cached_overall_stats.clear()
    cached_accuracy_by_subject.clear()
    cached_attempts_over_time.clear()


def _invalidate_tasks_cache():
    cached_study_tasks.clear()
    cached_overall_stats.clear()


def _invalidate_flashcard_progress_cache():
    cached_flashcards.clear()
    cached_overall_stats.clear()


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UCAT Prep",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

# ── Theme (paper / ink / teal, serif headings + mono numerics) ─────────────────
# Mirrors the palette and type system used by the UCAT Guide page, so the whole
# app reads as one design system rather than a native-Streamlit default plus one
# custom-styled page.
st.markdown("""
<style>
:root{
    --paper:#EFF1EC; --paper-2:#FAFBF8; --card:#FFFFFF;
    --ink:#16211F; --ink-soft:#4C5651; --ink-faint:#78827C;
    --line:#DBDFD6; --line-strong:#C7CCC1;
    --teal:#0C6B58; --teal-bright:#0F8A70; --teal-wash:#E4EFEA;
    --coral:#C24A38; --coral-wash:#F6E6E1;
    --gold:#B5762A; --gold-wash:#F3E7D6;
    --serif:"Charter","Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
    --mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;
}
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: var(--paper) !important; color: var(--ink); font-family: var(--sans);
}
[data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    font-family: var(--serif) !important; font-weight: 600 !important;
    letter-spacing: -.01em; color: var(--ink);
}

/* Sidebar */
[data-testid="stSidebar"] { background: var(--ink) !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] div { color: var(--paper) !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 { color: #FFFFFF !important; }
[data-testid="stSidebar"] [data-testid="stMetric"] { background: transparent !important; border: none !important; padding: 4px 0 !important; }
[data-testid="stSidebar"] [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 20px !important; }
[data-testid="stSidebar"] [data-testid="stMetricLabel"] { color: #9FB3AB !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.14) !important; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: var(--teal-bright) !important; font-weight: 600 !important; }
[data-testid="stSidebar"] [role="radiogroup"] input { accent-color: var(--teal-bright); }
[data-testid="stSidebar"] button[kind^="secondary"] { background: rgba(255,255,255,0.07) !important; border: 1px solid rgba(255,255,255,0.3) !important; }
[data-testid="stSidebar"] button[kind^="secondary"]:hover { background: rgba(255,255,255,0.14) !important; border-color: var(--teal-bright) !important; }
[data-testid="stSidebar"] button[kind^="secondary"] p { color: var(--paper) !important; }

/* Buttons */
button[kind^="primary"] { background: var(--teal) !important; border: 1px solid var(--teal) !important; color: #fff !important; border-radius: 8px !important; font-weight: 600 !important; }
button[kind^="primary"]:hover { background: var(--teal-bright) !important; border-color: var(--teal-bright) !important; }
button[kind^="secondary"] { border: 1px solid var(--line-strong) !important; border-radius: 8px !important; color: var(--ink) !important; font-weight: 600 !important; }
button[kind^="secondary"]:hover { border-color: var(--teal) !important; color: var(--teal) !important; }

/* Tabs */
[data-baseweb="tab-list"] { border-bottom: 1px solid var(--line) !important; gap: 1.6rem !important; }
[data-testid="stTab"] { color: var(--ink-soft) !important; font-family: var(--sans) !important; }
[data-testid="stTab"][aria-selected="true"] { color: var(--teal) !important; font-weight: 600 !important; }
[data-baseweb="tab-highlight"] { background-color: var(--teal) !important; }

/* Metrics */
[data-testid="stMetric"] { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 18px; }
[data-testid="stMetricValue"] { font-family: var(--serif) !important; font-weight: 700 !important; color: var(--teal); font-variant-numeric: tabular-nums; }
[data-testid="stMetricLabel"] p { font-family: var(--mono) !important; text-transform: uppercase; letter-spacing: .07em; font-size: .7rem !important; color: var(--ink-faint) !important; }

/* Expanders */
[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 10px; background: var(--card); }
[data-testid="stExpander"] summary { font-weight: 600; color: var(--ink); }

/* Alerts */
[data-testid="stAlertContentInfo"] { background: var(--teal-wash) !important; color: var(--ink) !important; border-left: 3px solid var(--teal) !important; }
[data-testid="stAlertContentSuccess"] { background: var(--teal-wash) !important; color: var(--ink) !important; border-left: 3px solid var(--teal-bright) !important; }
[data-testid="stAlertContentWarning"] { background: var(--gold-wash) !important; color: var(--ink) !important; border-left: 3px solid var(--gold) !important; }
[data-testid="stAlertContentError"] { background: var(--coral-wash) !important; color: var(--ink) !important; border-left: 3px solid var(--coral) !important; }
[data-testid="stAlertContainer"] { border-radius: 8px; }

/* Progress bar */
[data-testid="stProgress"] > div > div > div { background: var(--teal) !important; }

/* Misc */
hr { border-color: var(--line) !important; }
[data-testid="metric-container"] {
    background: white; border-radius: 10px; padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--line);
}
.flashcard {
    background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 38px 28px; text-align: center; font-size: 19px; color: var(--ink);
    font-family: var(--serif); box-shadow: 0 4px 14px rgba(0,0,0,0.05); min-height: 150px;
    display: flex; align-items: center; justify-content: center;
}
.pill { display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; color:white; font-family: var(--sans); }
.auth-hero { max-width:380px; margin:60px auto 0; text-align:center; }
.auth-hero .mark { font-size:2.6rem; margin-bottom:8px; }
.auth-hero h2 { font-family: var(--serif); margin-bottom:4px; color: var(--ink); }
.auth-hero .eyebrow { font-family: var(--mono); font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color: var(--teal); margin-bottom:6px; }
.auth-hero p { color: var(--ink-soft); margin-bottom:28px; font-size:14px; }
</style>
""", unsafe_allow_html=True)


# ── Site gate (optional) + per-account login ───────────────────────────────────
def _check_site_password() -> bool:
    """Optional shared password that gates the whole app before individual sign-in."""
    pwd = os.environ.get("APP_PASSWORD", "")
    if not pwd or st.session_state.get("_site_authenticated"):
        return True
    st.markdown(
        "<div class='auth-hero'>"
        "<div class='mark'>🩺</div>"
        "<div class='eyebrow'>UCAT Prep</div>"
        "<h2>Welcome back</h2>"
        "<p>Enter the site password to continue</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        pw = st.text_input("Password", type="password", placeholder="Enter password", label_visibility="collapsed")
        if st.button("Continue", type="primary", width="stretch"):
            if pw == pwd:
                st.session_state["_site_authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password — please try again.")
    st.stop()
    return False


def _check_account() -> bool:
    """Per-account sign-in/sign-up so each student's progress is tracked separately."""
    if st.session_state.get("user_id"):
        return True
    st.markdown(
        "<div class='auth-hero'>"
        "<div class='mark'>🩺</div>"
        "<div class='eyebrow'>UCAT Prep</div>"
        "<h2>Score in the top decile.</h2>"
        "<p>Sign in to your account to start studying</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        tab_login, tab_signup = st.tabs(["Sign in", "Create account"])
        with tab_login:
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Sign in", type="primary", width="stretch"):
                    user = db.verify_user(u, p) if u and p else None
                    if user:
                        st.session_state["user_id"] = user["id"]
                        st.session_state["username"] = user["username"]
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")
        with tab_signup:
            with st.form("signup_form"):
                u2 = st.text_input("Choose a username")
                p2 = st.text_input("Choose a password", type="password")
                p2b = st.text_input("Confirm password", type="password")
                if st.form_submit_button("Create account", type="primary", width="stretch"):
                    if not u2 or not p2:
                        st.error("Enter a username and password.")
                    elif p2 != p2b:
                        st.error("Passwords don't match.")
                    elif len(p2) < 4:
                        st.error("Password must be at least 4 characters.")
                    else:
                        uid = db.create_user(u2, p2)
                        if uid:
                            st.session_state["user_id"] = uid
                            st.session_state["username"] = u2.strip()
                            st.rerun()
                        else:
                            st.error("That username is already taken.")
    st.stop()
    return False


_check_site_password()
_check_account()


# ── Helpers ───────────────────────────────────────────────────────────────────
SUBJECTS = cached_subjects()
SUB_BY_ID = {s["id"]: s for s in SUBJECTS}
SUB_BY_NAME = {s["name"]: s for s in SUBJECTS}


def pill(text, color):
    return f"<span class='pill' style='background:{color}'>{text}</span>"


def subject_selectbox(label, key=None, include_all=False, default_name=None):
    names = (["All subtests"] if include_all else []) + [s["name"] for s in SUBJECTS]
    idx = 0
    if default_name and default_name in names:
        idx = names.index(default_name)
    choice = st.selectbox(label, names, index=idx, key=key)
    if choice == "All subtests":
        return None
    return SUB_BY_NAME[choice]["id"]


def _paginate(items, page_key, page_size=20):
    """Slice `items` to a bounded page, with a page picker only shown when needed.
    Keeps list-heavy admin views fast and DOM-light no matter how large the
    underlying bank grows."""
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    if page_key in st.session_state and st.session_state[page_key] > total_pages:
        st.session_state[page_key] = total_pages
    if total_pages > 1:
        page_num = st.number_input(f"Page (of {total_pages})", 1, total_pages, 1, key=page_key)
    else:
        page_num = 1
    start = (page_num - 1) * page_size
    return items[start:start + page_size]


# Cognitive subtests are reported on a 300–900 scale; SJT is reported in bands.
COGNITIVE_CODES = {"VR", "DM", "QR"}

# Official UCAT pacing (current 2025+ format): (questions, minutes) per subtest.
# Used to derive a realistic per-question time budget for mock exams.
SUBTEST_TIMING = {
    "VR":  (44, 22),
    "DM":  (35, 37),
    "QR":  (36, 26),
    "SJT": (69, 26),
}


def seconds_per_question(code):
    q, m = SUBTEST_TIMING.get(code, (1, 1))
    return (m * 60) / q


def fmt_mmss(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def est_scaled_score(accuracy_pct):
    """Rough, indicative 300–900 scaled score from raw accuracy (motivational only)."""
    return int(round((300 + accuracy_pct / 100 * 600) / 10) * 10)


def est_sjt_band(accuracy_pct):
    if accuracy_pct >= 80:
        return "Band 1"
    if accuracy_pct >= 60:
        return "Band 2"
    if accuracy_pct >= 40:
        return "Band 3"
    return "Band 4"


def days_to_exam():
    iso = db.get_context(st.session_state["user_id"], "exam_date")
    if not iso:
        return None, None
    try:
        d = date.fromisoformat(iso)
        return (d - date.today()).days, d
    except ValueError:
        return None, None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🩺 UCAT Prep")
    st.caption(f"👤 Signed in as **{st.session_state.get('username', '')}**")
    if st.button("Log out", width="stretch"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    stats = cached_overall_stats(st.session_state["user_id"])
    acc = (stats["correct"] / stats["attempts"] * 100) if stats["attempts"] else 0
    st.metric("Overall accuracy", f"{acc:.0f}%", help="Across all answered practice questions")
    st.metric("Cards due today", stats["cards_due"])
    dte, exam_d = days_to_exam()
    if dte is not None:
        st.metric("Days to exam", dte)
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "🧭 UCAT Guide", "📝 Practice Questions", "⏱️ Mock Exam", "🃏 Flashcards",
         "🗓️ Study Scheduler", "📚 Strategy & Skills", "🤖 AI Tutor", "⚙️ Manage"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("Set an exam date in ⚙️ Manage to enable the countdown.")


# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    st.title("📊 Dashboard")
    uid = st.session_state["user_id"]
    stats = cached_overall_stats(uid)
    acc = (stats["correct"] / stats["attempts"] * 100) if stats["attempts"] else 0

    dte, exam_d = days_to_exam()
    if dte is not None:
        if dte >= 0:
            st.info(f"🗓️ **{dte} days** until your UCAT on **{exam_d.strftime('%B %d, %Y')}**.")
        else:
            st.success("🎉 Your scheduled exam date has passed — good luck / well done!")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Questions answered", stats["attempts"])
    c2.metric("Accuracy", f"{acc:.0f}%")
    c3.metric("Cards mastered", f"{stats['cards_mastered']}/{stats['cards']}")
    task_pct = (stats["tasks_done"] / stats["tasks_total"] * 100) if stats["tasks_total"] else 0
    c4.metric("Study plan", f"{task_pct:.0f}%", help=f"{stats['tasks_done']} of {stats['tasks_total']} tasks done")

    st.markdown("### Estimated scores")
    rows = cached_accuracy_by_subject(uid)
    df = pd.DataFrame(rows)
    df["code"] = df["subject_id"].map(lambda sid: SUB_BY_ID.get(sid, {}).get("code", ""))
    df["accuracy"] = df.apply(lambda r: (r["correct"] / r["attempts"] * 100) if r["attempts"] else 0, axis=1)

    score_cols = st.columns(len(SUBJECTS))
    cog_total = 0
    for col, (_, r) in zip(score_cols, df.iterrows()):
        if r["code"] in COGNITIVE_CODES:
            sc = est_scaled_score(r["accuracy"]) if r["attempts"] else None
            cog_total += sc if sc else 0
            col.metric(r["subject_name"], f"{sc}" if sc else "—",
                       help="Indicative 300–900 scaled score from your accuracy")
        else:
            band = est_sjt_band(r["accuracy"]) if r["attempts"] else "—"
            col.metric(r["subject_name"], band, help="Indicative SJT band (1 = strongest)")
    cog_attempted = df[df["code"].isin(COGNITIVE_CODES)]["attempts"].sum()
    if cog_attempted:
        st.caption(f"🎯 Indicative cognitive total: **{cog_total} / 2700** "
                   f"(VR + DM + QR, each 300–900). Estimates from accuracy only — not official UCAT scores.")

    st.markdown("### Accuracy by subtest")
    if not df.empty and df["attempts"].sum() > 0:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["subject_name"], y=df["accuracy"],
            marker_color=df["color"].tolist(),
            text=[f"{v:.0f}%" for v in df["accuracy"]], textposition="outside",
            customdata=df["attempts"],
            hovertemplate="%{x}<br>Accuracy: %{y:.0f}%<br>Attempts: %{customdata}<extra></extra>",
        ))
        fig.update_layout(yaxis_title="Accuracy (%)", yaxis_range=[0, 110],
                          height=340, margin=dict(t=10, b=10), plot_bgcolor="white")
        st.plotly_chart(fig, width="stretch")

        # Readiness — weakest subtests
        ready = df[df["attempts"] > 0].sort_values("accuracy")
        weakest = ready.head(2)["subject_name"].tolist()
        if weakest:
            st.caption(f"💡 Focus area: your lowest accuracy is in **{', '.join(weakest)}**.")
    else:
        st.info("No practice questions answered yet. Head to **📝 Practice Questions** to begin — your analytics will populate here.")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("### Activity (last 30 days)")
        ts = pd.DataFrame(cached_attempts_over_time(uid, 30))
        if not ts.empty:
            ts["accuracy"] = ts["correct"] / ts["attempts"] * 100
            fig2 = px.line(ts, x="day", y="attempts", markers=True)
            fig2.update_traces(line_color="#2E86C1")
            fig2.update_layout(height=280, margin=dict(t=10, b=10), plot_bgcolor="white",
                               yaxis_title="Questions", xaxis_title="")
            st.plotly_chart(fig2, width="stretch")
        else:
            st.caption("No activity recorded in the last 30 days.")
    with colB:
        st.markdown("### Question bank coverage")
        qc = pd.DataFrame(cached_question_counts())
        if not qc.empty and qc["questions"].sum() > 0:
            fig3 = go.Figure(go.Pie(labels=qc["subject_name"], values=qc["questions"],
                                    marker_colors=qc["color"].tolist(), hole=0.45))
            fig3.update_layout(height=280, margin=dict(t=10, b=10), showlegend=True)
            st.plotly_chart(fig3, width="stretch")

    # Upcoming tasks
    st.markdown("### 🗓️ Upcoming study tasks")
    tasks = [t for t in cached_study_tasks(uid) if t["status"] != "Done"][:5]
    if tasks:
        for t in tasks:
            cols = st.columns([4, 2, 2, 1])
            sub = SUB_BY_ID.get(t["subject_id"])
            cols[0].markdown(f"**{t['title']}**" + (f" · {sub['name']}" if sub else ""))
            cols[1].caption(f"⏱️ {t['duration_min']} min")
            cols[2].caption(f"📅 {t['due_date'] or '—'}")
            if cols[3].button("✓", key=f"dash_done_{t['id']}", help="Mark done"):
                db.set_task_status(uid, t["id"], "Done")
                _invalidate_tasks_cache()
                st.rerun()
    else:
        st.caption("No open tasks. Add some in **🗓️ Study Scheduler**.")


# ════════════════════════════════════════════════════════════════════════════
# PRACTICE QUESTIONS
# ════════════════════════════════════════════════════════════════════════════
def page_practice():
    st.title("📝 Practice Questions")
    ss = st.session_state

    with st.expander("⚙️ Quiz settings", expanded="quiz" not in ss):
        c1, c2, c3 = st.columns(3)
        with c1:
            sid = subject_selectbox("Subtest", key="quiz_subject", include_all=True)
        with c2:
            difficulty = st.selectbox("Difficulty", ["All", "Easy", "Medium", "Hard"], key="quiz_diff")
        with c3:
            n = st.number_input("Questions", 1, 50, 5, key="quiz_n")
        if st.button("▶️ Start quiz", type="primary"):
            pool = cached_questions(subject_id=sid, difficulty=difficulty)
            random.shuffle(pool)
            pool = pool[:int(n)]
            if not pool:
                st.warning("No questions match those filters yet. Add some in ⚙️ Manage.")
            else:
                ss["quiz"] = pool
                ss["quiz_idx"] = 0
                ss["quiz_answered"] = {}
                ss["quiz_correct"] = 0
                ss["quiz_start"] = datetime.now().timestamp()
                st.rerun()

    if "quiz" not in ss:
        st.info("Configure your quiz above and press **Start quiz**. Every answer is logged so your Dashboard analytics stay current.")
        return

    quiz = ss["quiz"]
    idx = ss["quiz_idx"]

    # Finished
    if idx >= len(quiz):
        score = ss["quiz_correct"]
        total = len(quiz)
        st.success(f"## ✅ Quiz complete — {score}/{total} correct ({score/total*100:.0f}%)")
        st.progress(score / total)
        if st.button("🔄 New quiz"):
            for k in ("quiz", "quiz_idx", "quiz_answered", "quiz_correct"):
                ss.pop(k, None)
            st.rerun()
        return

    q = quiz[idx]
    sub = SUB_BY_ID.get(q["subject_id"])
    st.progress((idx) / len(quiz), text=f"Question {idx + 1} of {len(quiz)}")
    if sub:
        st.markdown(pill(sub["name"], sub["color"]) + f"  &nbsp; <span style='color:#888'>{q['difficulty']}</span>", unsafe_allow_html=True)
    st.markdown(f"### {q['stem']}")

    options = {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]}
    answered = ss["quiz_answered"].get(idx)

    if not answered:
        choice = st.radio("Choose one:", list(options.keys()),
                          format_func=lambda k: f"{k}. {options[k]}", key=f"q_{idx}")
        if st.button("Submit answer", type="primary"):
            is_correct = (choice == q["correct"])
            elapsed = datetime.now().timestamp() - ss.get("quiz_start", datetime.now().timestamp())
            db.record_attempt(ss["user_id"], q["id"], q["subject_id"], choice, is_correct, round(elapsed, 1))
            _invalidate_stats_cache()
            ss["quiz_answered"][idx] = choice
            if is_correct:
                ss["quiz_correct"] += 1
            ss["quiz_start"] = datetime.now().timestamp()
            st.rerun()
    else:
        for k, v in options.items():
            if k == q["correct"]:
                st.markdown(f"✅ **{k}. {v}**")
            elif k == answered:
                st.markdown(f"❌ ~~{k}. {v}~~")
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;{k}. {v}", unsafe_allow_html=True)
        if answered == q["correct"]:
            st.success("Correct!")
        else:
            st.error(f"Not quite — the answer is **{q['correct']}**.")
        if q.get("explanation"):
            st.info(f"**Explanation.** {q['explanation']}")
        if st.button("Next ▶️", type="primary"):
            ss["quiz_idx"] += 1
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# FLASHCARDS
# ════════════════════════════════════════════════════════════════════════════
def page_flashcards():
    st.title("🃏 Flashcards")
    st.caption("Spaced repetition (SM-2). Rate each card honestly — harder cards come back sooner.")
    ss = st.session_state
    uid = ss["user_id"]

    c1, c2 = st.columns([3, 1])
    with c1:
        sid = subject_selectbox("Subtest", key="fc_subject", include_all=True)
    with c2:
        due_only = st.toggle("Due only", value=True, key="fc_due")

    cards = cached_flashcards(uid, subject_id=sid, due_only=due_only)
    if not cards:
        if due_only:
            st.success("🎉 No cards due right now. Toggle off **Due only** to review ahead, or add cards in ⚙️ Manage.")
        else:
            st.info("No flashcards yet. Add some in ⚙️ Manage.")
        return

    if "fc_pos" not in ss or ss.get("fc_count") != len(cards):
        ss["fc_pos"] = 0
        ss["fc_count"] = len(cards)
        ss["fc_show_back"] = False

    pos = ss["fc_pos"] % len(cards)
    card = cards[pos]
    sub = SUB_BY_ID.get(card["subject_id"])

    st.progress((pos) / len(cards), text=f"Card {pos + 1} of {len(cards)} due")
    if sub:
        st.markdown(pill(sub["name"], sub["color"]), unsafe_allow_html=True)

    face = card["back"] if ss.get("fc_show_back") else card["front"]
    label = "ANSWER" if ss.get("fc_show_back") else "PROMPT"
    st.markdown(f"<div class='flashcard'><div><div style='font-size:11px;letter-spacing:1px;color:#9aa;margin-bottom:12px'>{label}</div>{face}</div></div>", unsafe_allow_html=True)
    st.write("")

    if not ss.get("fc_show_back"):
        if st.button("🔄 Show answer", type="primary", width="stretch"):
            ss["fc_show_back"] = True
            st.rerun()
    else:
        st.caption("How well did you recall it?")
        cols = st.columns(4)
        ratings = [("😖 Again", 0), ("😬 Hard", 3), ("🙂 Good", 4), ("😎 Easy", 5)]
        for col, (lbl, quality) in zip(cols, ratings):
            if col.button(lbl, key=f"fc_rate_{quality}", width="stretch"):
                db.review_flashcard(uid, card["id"], quality)
                _invalidate_flashcard_progress_cache()
                ss["fc_show_back"] = False
                ss["fc_pos"] = pos + 1
                ss["fc_count"] = None  # force refresh of the due list
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# STUDY SCHEDULER
# ════════════════════════════════════════════════════════════════════════════
def page_scheduler():
    st.title("🗓️ Study Scheduler")
    ss = st.session_state
    uid = ss["user_id"]

    with st.expander("➕ Add a study task"):
        with st.form("add_task", clear_on_submit=True):
            c1, c2 = st.columns(2)
            title = c1.text_input("Task", placeholder="e.g. Review enzyme kinetics + 10 Qs")
            sid = c2.selectbox("Subtest", ["—"] + [s["name"] for s in SUBJECTS])
            c3, c4, c5 = st.columns(3)
            ttype = c3.selectbox("Type", ["Review", "Practice", "Flashcards", "Full-length", "CARS"])
            due = c4.date_input("Due date", value=date.today())
            dur = c5.number_input("Minutes", 15, 480, 60, step=15)
            notes = st.text_area("Notes", placeholder="Optional")
            if st.form_submit_button("Add task", type="primary"):
                if title.strip():
                    db.upsert_study_task(uid, {
                        "title": title.strip(),
                        "subject_id": SUB_BY_NAME[sid]["id"] if sid != "—" else None,
                        "task_type": ttype, "due_date": due.isoformat(),
                        "duration_min": int(dur), "notes": notes,
                    })
                    _invalidate_tasks_cache()
                    st.success("Task added.")
                    st.rerun()
                else:
                    st.warning("Give the task a title.")

    # Auto-generate a plan
    with st.expander("✨ Generate a study plan"):
        st.caption("Creates one strategy + one practice task per subtest, spread across the days you choose.")
        gc1, gc2 = st.columns(2)
        weeks = gc1.number_input("Spread over (days)", 3, 60, 14)
        per_day = gc2.number_input("Tasks per day", 1, 6, 2)
        if st.button("Generate plan"):
            plan_tasks = []
            for s in SUBJECTS:
                plan_tasks.append((f"Review: {s['name']} high-yield topics", s["id"], "Review"))
                plan_tasks.append((f"Practice: {s['name']} question set", s["id"], "Practice"))
                plan_tasks.append((f"Flashcards: {s['name']}", s["id"], "Flashcards"))
            day = 0
            for i, (title, sid, ttype) in enumerate(plan_tasks):
                due = date.today() + timedelta(days=int(i // per_day) % int(weeks))
                db.upsert_study_task(uid, {"title": title, "subject_id": sid, "task_type": ttype,
                                           "due_date": due.isoformat(), "duration_min": 60})
            _invalidate_tasks_cache()
            st.success(f"Generated {len(plan_tasks)} tasks.")
            st.rerun()

    filt = st.radio("Show", ["All", "Todo", "In Progress", "Done"], horizontal=True)
    tasks = cached_study_tasks(uid, status=filt)
    if not tasks:
        st.info("No tasks. Add one above or generate a plan.")
        return

    today = date.today()
    for t in tasks:
        sub = SUB_BY_ID.get(t["subject_id"])
        overdue = t["due_date"] and t["due_date"] < today.isoformat() and t["status"] != "Done"
        cols = st.columns([0.5, 4, 2, 2, 1.5, 0.6])
        done = t["status"] == "Done"
        if cols[0].checkbox("", value=done, key=f"task_chk_{t['id']}", label_visibility="collapsed"):
            if not done:
                db.set_task_status(uid, t["id"], "Done")
                _invalidate_tasks_cache()
                st.rerun()
        else:
            if done:
                db.set_task_status(uid, t["id"], "Todo")
                _invalidate_tasks_cache()
                st.rerun()
        title_md = f"~~{t['title']}~~" if done else f"**{t['title']}**"
        badge = pill(sub["name"], sub["color"]) if sub else ""
        cols[1].markdown(f"{title_md}  {badge}", unsafe_allow_html=True)
        cols[2].caption(f"🏷️ {t['task_type']} · ⏱️ {t['duration_min']}m")
        date_txt = t["due_date"] or "—"
        cols[3].markdown(f"<span style='color:{'#c0392b' if overdue else '#888'}'>📅 {date_txt}{' (overdue)' if overdue else ''}</span>", unsafe_allow_html=True)
        status = cols[4].selectbox("", ["Todo", "In Progress", "Done"],
                                   index=["Todo", "In Progress", "Done"].index(t["status"]),
                                   key=f"task_status_{t['id']}", label_visibility="collapsed")
        if status != t["status"]:
            db.set_task_status(uid, t["id"], status)
            _invalidate_tasks_cache()
            st.rerun()
        if cols[5].button("🗑️", key=f"task_del_{t['id']}"):
            db.delete_study_task(uid, t["id"])
            _invalidate_tasks_cache()
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# UCAT GUIDE (native page — a full strategy playbook)
# ════════════════════════════════════════════════════════════════════════════
_SCORE_ANCHORS = [(1580, 10), (1680, 20), (1760, 30), (1820, 40), (1880, 50),
                   (1950, 60), (2020, 70), (2100, 80), (2200, 90), (2340, 97)]


def _score_percentile(total):
    lo = _SCORE_ANCHORS[0]
    if total <= lo[0]:
        return max(1, round(lo[1] * total / lo[0]))
    for a, b in zip(_SCORE_ANCHORS, _SCORE_ANCHORS[1:]):
        if total <= b[0]:
            return round(a[1] + (b[1] - a[1]) * (total - a[0]) / (b[0] - a[0]))
    return 99


def _score_tier(total):
    if total >= 2300:
        return "Outstanding", "Top few percent — competitive for the most selective courses."
    if total >= 2100:
        return "Excellent", "Top 20% of the cohort — a strong, widely competitive score."
    if total >= 1950:
        return "Above average", "Above the median. Solid, and competitive at many schools."
    if total >= 1760:
        return "Around average", "Middle of the pack — room to push into the upper deciles."
    return "Building", "Below this year's average — a clear focus area to train up."


def _g_card(name, tagline, color, count, minutes, per_q, fmt):
    with st.container(border=True):
        st.markdown(pill(name, color), unsafe_allow_html=True)
        st.markdown(f"**{tagline}**")
        st.caption(f"QUESTIONS  **{count}**  ·  TIME  **{minutes} min**  ·  PER Q  **{per_q}**  ·  {fmt}")


def _g_block(title, color, bullets):
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem'>"
        f"<span style='width:.6rem;height:.6rem;border-radius:2px;background:{color};display:inline-block'></span>"
        f"<b>{title}</b></div>",
        unsafe_allow_html=True,
    )
    st.markdown("\n".join(f"- {b}" for b in bullets))


def _g_example(color, q, a, trap=None):
    st.markdown(
        f"<div style='background:var(--paper-2,#FAFBF8);border:1px solid var(--line,#DBDFD6);"
        f"border-left:4px solid {color};border-radius:0 10px 10px 0;padding:.9rem 1.05rem;margin:.4rem 0'>"
        f"<div style='font-weight:600;margin-bottom:.4rem'>{q}</div>"
        f"<div style='color:var(--ink-soft,#4C5651)'>{a}</div></div>",
        unsafe_allow_html=True,
    )
    if trap:
        st.markdown(
            f"<div style='background:var(--coral-wash,#F6E6E1);border-radius:8px;padding:.5rem .9rem;"
            f"font-size:.9rem;color:#8a3324;margin:.4rem 0 1.2rem'><b>⚠ Trap —</b> {trap}</div>",
            unsafe_allow_html=True,
        )


def _g_subtest_tab(code, color, intro, what_tests, strategy_title, strategy, traps_title, traps, example):
    st.caption(intro)
    c1, c2 = st.columns(2)
    with c1:
        _g_block("What it tests", color, what_tests)
        _g_block(strategy_title, color, strategy)
    with c2:
        _g_block(traps_title, color, traps)
        _g_block("Worked micro-example", color, [])
        _g_example(color, *example[:2], trap=example[2] if len(example) > 2 else None)


def page_guide():
    vr_c = SUB_BY_NAME.get("Verbal Reasoning", {}).get("color", "#3B6488")
    dm_c = SUB_BY_NAME.get("Decision Making", {}).get("color", "#6E5299")
    qr_c = SUB_BY_NAME.get("Quantitative Reasoning", {}).get("color", "#12795C")
    sjt_c = SUB_BY_NAME.get("Situational Judgement", {}).get("color", "#B06A2C")

    st.markdown("<div style='font-family:var(--mono);font-size:.75rem;letter-spacing:.14em;"
                "text-transform:uppercase;color:var(--teal)'>University Clinical Aptitude Test · 2025 / 2026 cycle</div>",
                unsafe_allow_html=True)
    st.title("Score in the top decile.")
    st.markdown(
        "The UCAT is not a knowledge test — it is a **speed and decision test**. Everyone sitting it can do the "
        "maths and read the passage. The score gap is pace, technique, and nerve. This is the complete playbook "
        "for closing it."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Questions", "184")
    c2.metric("Testing time", "111 min")
    c3.metric("Subtests", "4")
    c4.metric("Max score", "2700")

    st.divider()

    # ── 01 · Format ──────────────────────────────────────────────────────────
    st.markdown("`01`")
    st.header("The exam at a glance")
    st.markdown(
        "Four subtests, back to back, computer-based, at a Pearson VUE test centre. Abstract Reasoning was "
        "removed for the 2025 cycle — the three cognitive subtests below are what build your out-of-2700 score. "
        "Situational Judgement is scored separately as a band."
    )
    cols = st.columns(4)
    with cols[0]:
        _g_card("Verbal Reasoning", "Read fast, infer faster", vr_c, 44, 22, "~30 s", "11 passages")
    with cols[1]:
        _g_card("Decision Making", "Logic under a clock", dm_c, 35, 37, "~63 s", "Standalone")
    with cols[2]:
        _g_card("Quantitative Reasoning", "Applied numeracy", qr_c, 36, 26, "~43 s", "Data sets")
    with cols[3]:
        _g_card("Situational Judgement", "Think like a doctor", sjt_c, 69, 26, "~23 s", "Scenarios")

    cols = st.columns(3)
    cols[0].metric("Scaled per cognitive subtest", "300–900")
    cols[1].metric("SJT outcome (1 = best)", "Band 1–4")
    cols[2].metric("Wrong answers never cost you", "No −marking")
    st.caption(
        "On-screen basic calculator (QR only), a laminated noteboard and pen at your desk. A short instruction "
        "screen precedes each subtest. There is no long scheduled break inside the 111 minutes — pace as one "
        "continuous sitting."
    )

    st.divider()

    # ── 02 · Scoring ─────────────────────────────────────────────────────────
    st.markdown("`02`")
    st.header("Scoring & what actually counts as good")
    st.markdown(
        "Raw marks in VR, DM and QR are converted to a scaled 300–900 each and summed to a total out of 2700. "
        "Universities weight this differently — some use hard cut-offs, some rank, some combine it with grades — "
        "so “good” is always relative to your target schools and this year's cohort."
    )
    st.dataframe(
        pd.DataFrame([
            {"2025 cohort": "Average", "Total score": "≈ 1891", "What it means": "Roughly 630 per subtest"},
            {"2025 cohort": "5th decile (median)", "Total score": "1880", "What it means": "Middle of the pack"},
            {"2025 cohort": "6th decile", "Total score": "1950", "What it means": "Above average"},
            {"2025 cohort": "8th decile", "Total score": "2100", "What it means": "Top 20% — a strong, competitive score"},
            {"2025 cohort": "Top few percent", "Total score": "2300+", "What it means": "Outstanding; opens the most selective courses"},
        ]),
        hide_index=True, width="stretch",
    )
    st.caption(
        "2025 decile ladder: 1st 1580 · 2nd 1680 · 3rd 1760 · 4th 1820 · 5th 1880 · 6th 1950 · 8th 2100. "
        "Boundaries drift a little each year, so treat these as guides, not guarantees."
    )

    st.markdown("#### The SJT band — don't neglect it")
    st.dataframe(
        pd.DataFrame([
            {"Band": "1", "Standing": "Excellent", "Where it lands you": "Closest to the expert panel. Advantageous everywhere SJT is used."},
            {"Band": "2", "Standing": "Good", "Where it lands you": "Most common outcome (~39% of candidates). Competitive at all schools."},
            {"Band": "3", "Standing": "Modest", "Where it lands you": "Accepted by many, but a weakness where SJT is scored or ranked."},
            {"Band": "4", "Standing": "Concerning", "Where it lands you": "~10% of candidates. Some schools will not consider Band 4 at all."},
        ]),
        hide_index=True, width="stretch",
    )

    with st.container(border=True):
        st.markdown("#### Score checker")
        st.caption("Drag your target scaled scores. The estimate shows roughly where that total sits in the 2025 cohort.")
        c1, c2, c3 = st.columns(3)
        vr_s = c1.slider("VR", 300, 900, 650, 10)
        dm_s = c2.slider("DM", 300, 900, 650, 10)
        qr_s = c3.slider("QR", 300, 900, 650, 10)
        total = vr_s + dm_s + qr_s
        pct = _score_percentile(total)
        tier, desc = _score_tier(total)
        frac = max(0.0, min(1.0, (total - 1500) / (2400 - 1500)))
        st.progress(frac)
        sc = st.columns(4)
        for col, label in zip(sc, ["1580", "1880", "2100", "2340+"]):
            col.caption(label)
        m1, m2 = st.columns([1, 2])
        m1.metric("Total / 2700", total)
        with m2:
            st.markdown(f"**{tier}**")
            st.caption(f"{desc} ~{pct}th percentile.")
        st.caption("Estimates from 2025 percentile data — a planning tool, not an official prediction.")

    st.divider()

    # ── 03-06 · Subtest deep dives ───────────────────────────────────────────
    st.markdown("`03–06`")
    st.header("Subtest deep dives")
    tab_vr, tab_dm, tab_qr, tab_sjt = st.tabs(["📖 Verbal Reasoning", "🧩 Decision Making",
                                                "🔢 Quantitative Reasoning", "🩺 Situational Judgement"])
    with tab_vr:
        _g_subtest_tab(
            "VR", vr_c,
            "Eleven passages, four questions each, and only half a minute per question. You cannot read every "
            "word — VR is a test of controlled skimming and disciplined logic, judged only on what the passage says.",
            what_tests=[
                "Comprehension and inference from dense, often dull text (science, history, policy).",
                "Separating what is **stated** from what is merely plausible or true in the real world.",
                "**Two question types:** True/False/Can't Tell statements, and free-text inference (\"the author would most agree…\").",
            ],
            strategy_title="Strategy that moves the needle",
            strategy=[
                "**Question first, then hunt.** Read the statement, lift its keywords, scan the passage for them, decide. Don't pre-read the whole passage.",
                "**Budget ~2 minutes per passage.** A stopwatch in your head beats a per-question one here.",
                "**Decode Can't Tell:** if answering needs outside knowledge or an assumption the text never makes, it's Can't Tell, not True.",
            ],
            traps_title="Common traps",
            traps=[
                "**Absolute words** — \"all\", \"never\", \"only\", \"always\". One counter-example in the text makes them False.",
                "**Your own knowledge.** If it's true in life but unstated in the passage, it isn't True here.",
                "**Sinking** three minutes into one brutal passage. Flag it, guess, move.",
            ],
            example=(
                "Passage: “The clinic opened a second site in 2019 to reduce waiting times.” Statement: <i>Waiting times fell after 2019.</i>",
                "Answer: <b>Can't Tell.</b> The passage gives the intent (“to reduce”), never the outcome. Tempting as True — but nothing states times actually fell.",
                "“Reduce” describes a goal, not a result. Reading purpose as fact is the #1 VR error.",
            ),
        )
    with tab_dm:
        _g_subtest_tab(
            "DM", dm_c,
            "The most time-generous subtest — over a minute per question — and the one that rewards careful, "
            "structured reasoning over speed. Each question stands alone. Use the noteboard.",
            what_tests=[
                "Logical puzzles and deductions from a set of conditions.",
                "Syllogisms — which conclusions **must** follow from given statements.",
                "Venn diagrams and set interpretation.",
                "Recognising assumptions and picking the **strongest argument**.",
                "Probability and basic statistical reasoning.",
                "**Scoring quirk:** some questions have five Yes/No statements — get all right for full marks, most right for partial, so grind these out.",
            ],
            strategy_title="Strategy that moves the needle",
            strategy=[
                "**Draw it.** Venn diagrams and logic grids on the noteboard beat holding it in your head.",
                "**“Strongest argument”** = directly relevant + no logical flaw + addresses the actual question.",
                "**Syllogisms:** accept only conclusions that are *necessarily* true, never just probable.",
                "**Spend the time you're given.** This is where accuracy pays — don't rush what's deliberately paced.",
            ],
            traps_title="Common traps",
            traps=[
                "Treating a conclusion that **could** be true as one that **must** be true.",
                "Picking the argument that “sounds” sensible instead of the one that's actually logically airtight.",
                "Skipping the noteboard and trying to hold a 4-variable puzzle in your head.",
            ],
            example=(
                "“All members of the team are qualified. Some qualified people are first-aiders.” Conclusion: <i>Some team members are first-aiders.</i>",
                "Answer: <b>No.</b> The team are all qualified, but the qualified first-aiders needn't include any team member. It could be true — but it doesn't have to be.",
                "“Could be true” ≠ “must be true”. DM only rewards necessity.",
            ),
        )
    with tab_qr:
        _g_subtest_tab(
            "QR", qr_c,
            "The maths is only GCSE-level — the difficulty is doing it accurately in 43 seconds while reading a "
            "chart. Fluency with percentages and a fast hand on the on-screen calculator is worth more than any clever trick.",
            what_tests=[
                "Percentages, percentage change and **reverse** percentages.",
                "Ratios, proportion and best-value comparisons.",
                "Rates — speed/distance/time, unit conversion.",
                "Reading data from tables, graphs and charts.",
                "Area, volume and simple geometry.",
                "**Calculator reality:** it's a basic four-function calculator you click — slow. Learn the number-key shortcuts.",
            ],
            strategy_title="Strategy that moves the needle",
            strategy=[
                "**Read the question before the data.** Only compute the one number asked — data sets bury a lot of decoys.",
                "**Guard your units.** £/pence, km/m, per-week vs per-year — the trap is almost always a unit switch.",
                "**Estimate to eliminate.** Ballpark first; if only one option is near, you may not need exact arithmetic.",
                "**Flag the calculation-heavy ones** and clear the quick wins first.",
            ],
            traps_title="Common traps",
            traps=[
                "**Reverse percentages** — adding the % back on instead of dividing by the decimal multiplier.",
                "Answering a different unit than the one asked for.",
                "Doing simple arithmetic on the slow on-screen calculator instead of in your head.",
            ],
            example=(
                "A jacket costs £48 after a 20% discount. What was the original price?",
                "Answer: <b>£60.</b> £48 is 80% of the original, so original = 48 ÷ 0.8 = £60. Not £48 × 1.2 = £57.60 — that's the reverse-percentage trap.",
                "Adding the % back on undershoots. Divide by the decimal multiplier instead.",
            ),
        )
    with tab_sjt:
        _g_subtest_tab(
            "SJT", sjt_c,
            "Scenarios from clinical and student life, judged against a panel of medical experts. It looks like "
            "“common sense” — which is exactly why people under-prepare and land in Band 3. Learn the "
            "examiner's value system and Band 1 is very reachable.",
            what_tests=[
                "Integrity, empathy, teamwork and coping under pressure — not medical knowledge.",
                "How closely your judgement matches the professional consensus.",
                "**Question types:** Appropriateness (very appropriate → very inappropriate), Importance (very important → not important at all), and Most/Least appropriate.",
            ],
            strategy_title="The examiner's value system",
            strategy=[
                "**Patient safety overrides everything.** If a patient is at risk, doing nothing is never appropriate.",
                "**Never cover up** or ignore a mistake — honesty and probity always score.",
                "**Escalate proportionately:** usually raise it with the person first, then go to a senior if needed.",
                "**Stay within your competence** and seek help when out of your depth — that's a strength, not a failing.",
                "**Be non-judgemental** and protect confidentiality.",
            ],
            traps_title="Common traps",
            traps=[
                "Choosing “do nothing” whenever patient safety is even slightly in question.",
                "Jumping straight to reporting someone without first addressing it directly.",
                "Prioritising a colleague's comfort or your own convenience over safety or honesty.",
            ],
            example=(
                "A fellow student turns up to a hospital placement smelling of alcohol. Response: <i>“Say nothing to avoid embarrassing them.”</i>",
                "Rating: <b>Very inappropriate.</b> Patient safety and professional standards outrank a colleague's comfort. The appropriate path is to raise it — with them, and if needed a supervisor.",
                "Avoid the two extremes: never “ignore it”, but also rarely jump straight to reporting someone without first addressing it directly.",
            ),
        )

    st.divider()

    # ── 07 · Timing doctrine ─────────────────────────────────────────────────
    st.markdown("`07`")
    st.header("The interface & the timing doctrine")
    st.markdown(
        "More points are lost to the clock than to difficulty. The single biggest score lever for most "
        "candidates is not knowing more — it's never leaving a question blank and never letting one question "
        "eat the time of three."
    )
    cols = st.columns(3)
    with cols[0]:
        with st.container(border=True):
            st.caption("RULE ONE")
            st.markdown("**Answer everything**")
            st.caption("No negative marking. A blank and a wrong answer score the same — so a guess can only "
                        "help. In the last seconds of every subtest, fill all remaining answers with one "
                        "“banker” letter.")
    with cols[1]:
        with st.container(border=True):
            st.caption("RULE TWO")
            st.markdown("**Flag & move**")
            st.caption("Every subtest has a Flag button and a navigator. The moment a question runs long, flag "
                        "it and go. Anchoring on one hard item is the classic way to run out of time with easy "
                        "marks unanswered.")
    with cols[2]:
        with st.container(border=True):
            st.caption("RULE THREE")
            st.markdown("**Know your tools**")
            st.caption("Calculator (QR only, number-key shortcuts), on-screen timer, flag/navigator, and a "
                        "laminated noteboard + pen at your desk. Practise with these exact tools so exam day "
                        "holds no surprises.")
    st.info(
        "**Your per-question pace, memorised.** VR ≈ 30 s · DM ≈ 60 s · QR ≈ 43 s · SJT ≈ 23 s. You won't watch "
        "the clock every question — but you should *feel* when you've overstayed. Internalise these four "
        "numbers and “flag & move” becomes automatic."
    )

    st.divider()

    # ── 08 · Preparation plan ────────────────────────────────────────────────
    st.markdown("`08`")
    st.header("The preparation plan")
    st.markdown(
        "Six to eight focused weeks beats months of drift. The pattern that works: learn the technique first, "
        "drill weaknesses second, then live almost entirely inside full timed mocks. Review is where the score "
        "is made — analysing *why* each answer was wrong is worth more than doing another hundred questions."
    )
    phases = [
        ("Weeks 1–2 · Foundations", "Learn the game before playing it",
         "Sit one diagnostic to find your weak subtest. Learn the format and the strategy for each section "
         "(this guide). Practise **untimed** — you're building correct method, not speed yet. Start daily "
         "mental-maths and speed-reading warm-ups."),
        ("Weeks 3–5 · Targeted drilling", "Attack your weaknesses, then add the clock",
         "Drill by subtest and question type, hardest area first. Introduce timing gradually until you hit the "
         "real per-question pace. Keep an error log — every mistake gets a one-line “why” so the same "
         "trap never catches you twice."),
        ("Weeks 6–8 · Full mocks", "Live under exam conditions",
         "Two to three **full, timed mocks** a week, in one sitting, no phone, using the on-screen calculator "
         "and noteboard. Review every mock in full. Save the **official UCAT practice tests** for last — "
         "they're the truest calibration of where you'll land."),
    ]
    for i, (wk, title, body) in enumerate(phases, start=1):
        c1, c2 = st.columns([1, 11])
        c1.markdown(
            f"<div style='width:2.2rem;height:2.2rem;border-radius:50%;background:var(--teal,#0C6B58);"
            f"color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700'>{i}</div>",
            unsafe_allow_html=True,
        )
        with c2:
            st.caption(wk.upper())
            st.markdown(f"**{title}**")
            st.markdown(body)
    st.warning(
        "**The one habit that separates top scorers.** They review more than they grind. Doing 40 questions "
        "and understanding all 40 mistakes beats doing 200 and glancing at the score. Volume without review "
        "just rehearses your errors."
    )

    st.divider()

    # ── 09 · Resources ───────────────────────────────────────────────────────
    st.markdown("`09`")
    st.header("Resources, ranked by usefulness")
    st.markdown(
        "Start with the free official material for accuracy, add a question bank for volume, and use timed "
        "mocks to build stamina. Quality and realism matter far more than sheer quantity."
    )
    resources = [
        ("FREE · OFFICIAL", "UCAT Consortium practice materials (ucat.ac.uk)",
         "The most representative questions and the two official mock exams. The single best calibration tool "
         "— do the full mocks near the end of your prep.", True),
        ("FREE · THIS APP", "Your UCAT Prep question bank",
         "A difficulty-calibrated, duplicate-free bank with per-user progress tracking and flashcards — use it "
         "for daily drilling and to see accuracy by subtest.", True),
        ("PAID · VOLUME", "Commercial question banks & mock platforms",
         "Providers such as Medify, MedEntry, Pastest and others offer thousands of questions and timed mocks. "
         "Useful for stamina — just don't mistake volume for progress.", False),
        ("FREE · SKILLS", "Mental-maths & speed-reading drills",
         "Times-tables, percentage and fraction fluency for QR; timed skim-reading for VR. Ten focused minutes "
         "a day compounds fast.", False),
    ]
    for badge, title, body, free in resources:
        badge_color = "var(--teal,#0C6B58)" if free else "var(--ink-faint,#78827C)"
        with st.container(border=True):
            c1, c2 = st.columns([1, 6])
            c1.markdown(
                f"<span style='font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;font-weight:700;"
                f"color:#fff;background:{badge_color};padding:.2rem .45rem;border-radius:5px;white-space:nowrap'>"
                f"{badge}</span>", unsafe_allow_html=True,
            )
            with c2:
                st.markdown(f"**{title}**")
                st.caption(body)
    st.caption(
        "There are no “real past papers” — the UCAT is a non-disclosed exam, so no genuine past "
        "questions exist anywhere. Anything advertised as leaked past papers is neither official nor reliable; "
        "the official practice tests are as close as it gets."
    )

    st.divider()

    # ── 10 · Exam day ────────────────────────────────────────────────────────
    st.markdown("`10`")
    st.header("Exam day")
    st.markdown(
        "By now the technique is built — the job is to protect it from nerves and logistics. Nothing on the "
        "day should be a first-time experience."
    )
    c1, c2 = st.columns(2)
    with c1:
        _g_block("Before you go", "#0C6B58", [
            "Sleep properly the night before — cramming past midnight costs more than it adds.",
            "Bring the **correct photo ID**; check the test-centre rules the day before.",
            "Eat something steady and hydrate; arrive early to settle your nerves.",
        ])
        _g_block("Keeping nerves in check", "#0C6B58", [
            "Slow breathing between subtests resets a racing mind faster than re-reading a question.",
            "You've rehearsed this exact format — the day is just another mock with higher stakes.",
        ])
    with c2:
        _g_block("During the test", "#0C6B58", [
            "Work one subtest at a time. A rough section is not the exam — reset and move on.",
            "Trust your pace and your “flag & move” reflex; don't renegotiate strategy mid-exam.",
            "Always spend the final seconds of each subtest filling every blank.",
        ])
        _g_block("Perspective", "#0C6B58", [
            "The UCAT is one part of your application, alongside grades, personal statement and interview.",
            "Different schools weight it differently — a strong score opens doors, but it isn't the whole decision.",
        ])

    st.divider()

    # ── 11 · Mindset ─────────────────────────────────────────────────────────
    st.markdown("`11`")
    st.header("The eleven commandments")
    st.markdown("Everything above, distilled. If you internalise nothing else, internalise these.")
    commandments = [
        "**Never leave a blank.** No negative marking means a guess is free upside.",
        "**Flag and move** the instant a question runs long. Protect the easy marks.",
        "**Answer only what's asked** — in VR and QR the data is full of decoys.",
        "**“Can't Tell” is a real answer.** If the passage doesn't say it, don't infer it.",
        "**Must, not might.** DM rewards necessity, never mere possibility.",
        "**Divide, don't add back** for reverse percentages.",
        "**Patient safety first** in every SJT scenario; never do nothing.",
        "**Review beats volume.** Understand every mistake before doing more.",
        "**Live in full timed mocks** for the final stretch.",
        "**Save the official tests** for your truest calibration near the end.",
        "**It's one part of the application.** Prepare hard, then keep it in perspective.",
    ]
    c1, c2 = st.columns(2)
    half = (len(commandments) + 1) // 2
    for col, chunk, start in ((c1, commandments[:half], 1), (c2, commandments[half:], half + 1)):
        with col:
            for i, item in enumerate(chunk, start=start):
                st.markdown(f"**{i:02d}.** {item}")

    st.caption(
        "Figures reflect the 2025 / 2026 test cycle (Abstract Reasoning removed; scored out of 2700). Data: "
        "UCAT Consortium test-format & statistics, 2025. Always confirm the current year's format and your "
        "universities' requirements at [ucat.ac.uk](https://www.ucat.ac.uk)."
    )


# ════════════════════════════════════════════════════════════════════════════
# CONTENT REVIEW
# ════════════════════════════════════════════════════════════════════════════
def page_content():
    st.title("📚 Strategy & Skills")
    c1, c2 = st.columns([3, 1])
    with c1:
        sid = subject_selectbox("Subtest", key="content_subject", include_all=True)
    with c2:
        hy = st.toggle("High-yield only", value=False, key="content_hy")

    topics = cached_topics(subject_id=sid, high_yield_only=hy)
    if not topics:
        st.info("No topics found. Add review notes in ⚙️ Manage.")
        return

    # group by subject
    by_subject = {}
    for t in topics:
        by_subject.setdefault(t["subject_name"], []).append(t)

    for sname, items in by_subject.items():
        color = items[0]["color"]
        st.markdown(f"### {pill(sname, color)}", unsafe_allow_html=True)
        for t in items:
            label = ("⭐ " if t["high_yield"] else "") + t["name"]
            with st.expander(label):
                if t.get("summary"):
                    st.caption(t["summary"])
                st.markdown(t.get("content") or "_No notes yet._")
                st.caption("💬 Ask the AI Tutor about this topic from the 🤖 AI Tutor page.")


# ════════════════════════════════════════════════════════════════════════════
# AI TUTOR
# ════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = (
    "You are an expert UCAT tutor. Help the student prepare for the four current UCAT "
    "subtests: Verbal Reasoning, Decision Making, Quantitative Reasoning, and Situational "
    "Judgement. The UCAT is a timed aptitude test — emphasise technique, speed, and "
    "time-management as much as accuracy. For Situational Judgement, ground answers in the "
    "GMC 'Good Medical Practice' principles (patient safety, confidentiality, integrity, "
    "working within competence). "
    "Explain clearly and concisely, use analogies where helpful, show the reasoning for "
    "quantitative problems step by step, and when relevant point out common UCAT traps and "
    "time-saving shortcuts. Keep answers focused and exam-oriented."
)


def page_tutor():
    st.title("🤖 AI Tutor")
    uid = st.session_state["user_id"]
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not _HAS_ANTHROPIC or not api_key:
        st.warning(
            "The AI Tutor needs the `anthropic` package and an `ANTHROPIC_API_KEY`. "
            "Add the key to your Streamlit secrets or environment to enable chat. "
            "Everything else in the app works without it."
        )
        return

    cols = st.columns([4, 1])
    cols[0].caption("Ask anything — concepts, practice problems, study strategy.")
    if cols[1].button("🗑️ Clear chat"):
        db.clear_chat_history(uid)
        st.rerun()

    history = db.get_chat_history(uid, 40)
    for m in history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prompt = st.chat_input("e.g. Explain the difference between competitive and noncompetitive inhibition")
    if prompt:
        db.save_message(uid, "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                msgs = [{"role": m["role"], "content": m["content"]} for m in db.get_chat_history(uid, 20)]
                with st.spinner("Thinking…"):
                    resp = client.messages.create(
                        model="claude-opus-4-8",
                        max_tokens=1200,
                        system=SYSTEM_PROMPT,
                        messages=msgs,
                    )
                answer = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            except Exception as e:
                answer = f"⚠️ Sorry, the tutor hit an error: `{e}`"
            st.markdown(answer)
            db.save_message(uid, "assistant", answer)
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# MANAGE
# ════════════════════════════════════════════════════════════════════════════
def page_manage():
    st.title("⚙️ Manage")
    uid = st.session_state["user_id"]
    tabs = st.tabs(["Account", "Exam date", "Questions", "Flashcards", "Topics"])

    # Account
    with tabs[0]:
        st.markdown(f"**Username:** {st.session_state.get('username', '')}")
        st.caption("Passwords are stored as a salted hash — nobody, including us, can look up or "
                   "display your current password. Set a new one below instead.")
        st.divider()
        st.markdown("**Change password**")
        with st.form("change_pw", clear_on_submit=True):
            cur_pw = st.text_input("Current password", type="password")
            new_pw = st.text_input("New password", type="password")
            new_pw2 = st.text_input("Confirm new password", type="password")
            if st.form_submit_button("Update password", type="primary"):
                user = db.verify_user(st.session_state["username"], cur_pw) if cur_pw else None
                if not user:
                    st.error("Current password is incorrect.")
                elif not new_pw or len(new_pw) < 4:
                    st.error("New password must be at least 4 characters.")
                elif new_pw != new_pw2:
                    st.error("New passwords don't match.")
                else:
                    db.set_password(uid, new_pw)
                    st.success("Password updated.")

    # Exam date
    with tabs[1]:
        cur = db.get_context(uid, "exam_date")
        cur_d = date.fromisoformat(cur) if cur else date.today() + timedelta(days=90)
        new_d = st.date_input("UCAT exam date", value=cur_d)
        if st.button("Save exam date", type="primary"):
            db.set_context(uid, "exam_date", new_d.isoformat())
            st.success("Saved.")
            st.rerun()

    # Questions
    with tabs[2]:
        with st.form("add_q", clear_on_submit=True):
            st.markdown("**Add a practice question**")
            sname = st.selectbox("Subtest", [s["name"] for s in SUBJECTS], key="mq_sub")
            stem = st.text_area("Question stem")
            c = st.columns(2)
            a = c[0].text_input("Option A")
            b = c[1].text_input("Option B")
            cc = c[0].text_input("Option C")
            d = c[1].text_input("Option D")
            c2 = st.columns(2)
            correct = c2[0].selectbox("Correct answer", ["A", "B", "C", "D"])
            diff = c2[1].selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
            expl = st.text_area("Explanation")
            if st.form_submit_button("Add question", type="primary"):
                if stem and a and b and cc and d:
                    db.upsert_question({
                        "subject_id": SUB_BY_NAME[sname]["id"], "stem": stem,
                        "option_a": a, "option_b": b, "option_c": cc, "option_d": d,
                        "correct": correct, "explanation": expl, "difficulty": diff,
                    })
                    _invalidate_content_cache()
                    st.success("Question added.")
                    st.rerun()
                else:
                    st.warning("Fill in the stem and all four options.")
        st.divider()
        qs = cached_questions()
        search = st.text_input("🔍 Search questions", key="mq_search",
                                placeholder="Filter by keyword or subtest…")
        filtered = qs
        if search:
            needle = search.lower()
            filtered = [q for q in qs if needle in q["stem"].lower()
                       or needle in SUB_BY_ID.get(q["subject_id"], {}).get("name", "").lower()]
        st.caption(f"{len(filtered)} of {len(qs)} questions" if search else f"{len(qs)} questions in the bank")
        for q in _paginate(filtered, "mq_page"):
            with st.expander(f"[{SUB_BY_ID.get(q['subject_id'],{}).get('name','?')}] {q['stem'][:70]}"):
                st.markdown(f"**Correct:** {q['correct']} · **Difficulty:** {q['difficulty']}")
                st.caption(q.get("explanation") or "")
                if st.button("Delete", key=f"delq_{q['id']}"):
                    db.delete_question(q["id"])
                    _invalidate_content_cache()
                    st.rerun()

    # Flashcards
    with tabs[3]:
        with st.form("add_fc", clear_on_submit=True):
            st.markdown("**Add a flashcard**")
            sname = st.selectbox("Subtest", [s["name"] for s in SUBJECTS], key="mfc_sub")
            front = st.text_area("Front (prompt)")
            back = st.text_area("Back (answer)")
            if st.form_submit_button("Add flashcard", type="primary"):
                if front and back:
                    db.upsert_flashcard({"subject_id": SUB_BY_NAME[sname]["id"], "front": front, "back": back})
                    _invalidate_content_cache()
                    st.success("Flashcard added.")
                    st.rerun()
                else:
                    st.warning("Fill in both sides.")
        st.divider()
        cards = cached_flashcard_bank()
        fc_search = st.text_input("🔍 Search flashcards", key="mfc_search",
                                   placeholder="Filter by keyword or subtest…")
        fc_filtered = cards
        if fc_search:
            needle = fc_search.lower()
            fc_filtered = [fc for fc in cards if needle in fc["front"].lower() or needle in fc["back"].lower()
                          or needle in SUB_BY_ID.get(fc["subject_id"], {}).get("name", "").lower()]
        st.caption(f"{len(fc_filtered)} of {len(cards)} flashcards" if fc_search else f"{len(cards)} flashcards")
        for fc in _paginate(fc_filtered, "mfc_page"):
            with st.expander(f"[{SUB_BY_ID.get(fc['subject_id'],{}).get('name','?')}] {fc['front'][:70]}"):
                st.markdown(f"**Back:** {fc['back']}")
                if st.button("Delete", key=f"delfc_{fc['id']}"):
                    db.delete_flashcard(fc["id"])
                    _invalidate_content_cache()
                    st.rerun()

    # Topics
    with tabs[4]:
        with st.form("add_topic", clear_on_submit=True):
            st.markdown("**Add a review topic**")
            sname = st.selectbox("Subtest", [s["name"] for s in SUBJECTS], key="mt_sub")
            name = st.text_input("Topic name")
            hy = st.checkbox("High-yield ⭐")
            summary = st.text_input("One-line summary")
            content = st.text_area("Notes (Markdown supported)", height=160)
            if st.form_submit_button("Add topic", type="primary"):
                if name:
                    db.upsert_topic({"subject_id": SUB_BY_NAME[sname]["id"], "name": name,
                                     "high_yield": 1 if hy else 0, "summary": summary, "content": content})
                    _invalidate_content_cache()
                    st.success("Topic added.")
                    st.rerun()
                else:
                    st.warning("Give the topic a name.")
        st.divider()
        topics_all = cached_topics()
        st.caption(f"{len(topics_all)} topics")
        for t in topics_all:
            with st.expander(f"{'⭐ ' if t['high_yield'] else ''}[{t['subject_name']}] {t['name']}"):
                st.markdown(t.get("content") or "_No notes._")
                if st.button("Delete", key=f"delt_{t['id']}"):
                    db.delete_topic(t["id"])
                    _invalidate_content_cache()
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# MOCK EXAM (timed)
# ════════════════════════════════════════════════════════════════════════════
def _build_mock(subtest_ids):
    """Assemble an ordered question list grouped by subtest, with a time budget."""
    questions = []
    for s in SUBJECTS:
        if subtest_ids and s["id"] not in subtest_ids:
            continue
        qs = cached_questions(subject_id=s["id"])
        random.shuffle(qs)
        questions.extend(qs)
    budget = sum(seconds_per_question(SUB_BY_ID[q["subject_id"]]["code"]) for q in questions)
    return questions, int(budget)


def _finish_mock(ss, elapsed):
    """Record every answered question to analytics once, then flip to the results screen."""
    if not ss.get("mock_graded"):
        for i, q in enumerate(ss["mock"]):
            chosen = ss["mock_answers"].get(i)
            if chosen:
                db.record_attempt(ss["user_id"], q["id"], q["subject_id"], chosen, chosen == q["correct"], 0)
        _invalidate_stats_cache()
        ss["mock_graded"] = True
    ss["mock_elapsed"] = int(elapsed)
    ss["mock_done"] = True


def _mock_results(ss):
    quiz = ss["mock"]
    answers = ss["mock_answers"]
    rows = {}
    for i, q in enumerate(quiz):
        code = SUB_BY_ID[q["subject_id"]]["code"]
        r = rows.setdefault(code, {"name": SUB_BY_ID[q["subject_id"]]["name"],
                                   "color": SUB_BY_ID[q["subject_id"]]["color"],
                                   "correct": 0, "total": 0})
        r["total"] += 1
        if answers.get(i) == q["correct"]:
            r["correct"] += 1
    return rows


def page_mock():
    st.title("⏱️ Mock Exam")
    ss = st.session_state

    # ── Results screen ────────────────────────────────────────────────────────
    if ss.get("mock_done"):
        rows = _mock_results(ss)
        total_q = sum(r["total"] for r in rows.values())
        total_correct = sum(r["correct"] for r in rows.values())
        used = ss.get("mock_elapsed", 0)
        st.success(f"## ✅ Mock complete — {total_correct}/{total_q} correct "
                   f"({(total_correct/total_q*100) if total_q else 0:.0f}%)")
        st.caption(f"⏱️ Time used: {fmt_mmss(used)} of {fmt_mmss(ss.get('mock_budget', 0))}")

        cols = st.columns(len(rows) or 1)
        cog_total, cog_any = 0, False
        for col, (code, r) in zip(cols, rows.items()):
            acc = (r["correct"] / r["total"] * 100) if r["total"] else 0
            if code in COGNITIVE_CODES:
                sc = est_scaled_score(acc)
                cog_total += sc
                cog_any = True
                col.metric(r["name"], sc, help=f"{r['correct']}/{r['total']} correct · indicative 300–900")
            else:
                col.metric(r["name"], est_sjt_band(acc), help=f"{r['correct']}/{r['total']} correct · indicative band")
        if cog_any:
            st.caption(f"🎯 Indicative cognitive total: **{cog_total} / 2700**. "
                       "Estimates from accuracy only — not official UCAT scores. "
                       "All answers were saved to your analytics.")

        with st.expander("Review answers"):
            for i, q in enumerate(ss["mock"]):
                chosen = ss["mock_answers"].get(i)
                ok = chosen == q["correct"]
                mark = "✅" if ok else ("❌" if chosen else "⏭️")
                st.markdown(f"{mark} **{q['stem'][:90]}**")
                opts = {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]}
                st.caption(f"Your answer: {chosen or '— (skipped)'} · Correct: {q['correct']} ({opts[q['correct']]})")
                if q.get("explanation"):
                    st.caption(f"💡 {q['explanation']}")

        if st.button("🔄 New mock", type="primary"):
            for k in list(ss.keys()):
                if k.startswith("mock"):
                    ss.pop(k, None)
            st.rerun()
        return

    # ── Setup screen ──────────────────────────────────────────────────────────
    if "mock" not in ss:
        st.markdown("Sit a timed, UCAT-paced mock using your question bank. Each subtest is "
                    "timed at the real per-question rate, so the clock pressure mirrors the exam.")
        st.caption("Official pacing — VR 44Q/21m · DM 35Q/37m · QR 36Q/26m · SJT 69Q/26m. "
                   "Add more questions in ⚙️ Manage to lengthen your mocks.")
        mode = st.radio("Mode", ["Full mock (all subtests)", "Single subtest"], horizontal=True)
        subtest_ids = None
        if mode == "Single subtest":
            sid = subject_selectbox("Subtest", key="mock_subtest")
            subtest_ids = [sid] if sid else None

        # preview count + budget
        preview_q, preview_budget = _build_mock(subtest_ids)
        if not preview_q:
            st.warning("No questions available for that selection. Add some in ⚙️ Manage.")
            return
        st.info(f"📋 {len(preview_q)} questions · ⏱️ {fmt_mmss(preview_budget)} total")

        if st.button("▶️ Start mock", type="primary"):
            quiz, budget = _build_mock(subtest_ids)
            ss["mock"] = quiz
            ss["mock_idx"] = 0
            ss["mock_answers"] = {}
            ss["mock_budget"] = budget
            ss["mock_start"] = datetime.now().timestamp()
            st.rerun()
        return

    # ── In-progress exam ──────────────────────────────────────────────────────
    quiz = ss["mock"]
    budget = ss["mock_budget"]
    elapsed = datetime.now().timestamp() - ss["mock_start"]
    remaining = budget - elapsed

    # Time's up → grade automatically
    if remaining <= 0:
        _finish_mock(ss, budget)
        st.rerun()

    idx = ss["mock_idx"]
    if idx >= len(quiz):
        _finish_mock(ss, elapsed)
        st.rerun()

    # Header: live countdown (cosmetic client-side ticker) + progress
    top = st.columns([2, 3])
    with top[0]:
        components.html(f"""
            <div id='ucat-timer' style="font:600 26px/1.2 -apple-system,Segoe UI,Roboto,sans-serif;
                 color:{'#c0392b' if remaining < 60 else '#11324D'}"></div>
            <script>
              let r = {int(remaining)};
              const el = document.getElementById('ucat-timer');
              function tick() {{
                const m = Math.floor(Math.max(0,r)/60), s = Math.max(0,r)%60;
                el.textContent = '⏱️ ' + m + ':' + String(s).padStart(2,'0') + ' remaining';
                if (r > 0) {{ r--; setTimeout(tick, 1000); }}
              }}
              tick();
            </script>
        """, height=44)
    with top[1]:
        st.progress(idx / len(quiz), text=f"Question {idx + 1} of {len(quiz)}")

    q = quiz[idx]
    sub = SUB_BY_ID.get(q["subject_id"])
    if sub:
        st.markdown(pill(sub["name"], sub["color"]) + f"  &nbsp; <span style='color:#888'>{q['difficulty']}</span>",
                    unsafe_allow_html=True)
    st.markdown(f"### {q['stem']}")

    options = {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]}
    prev = ss["mock_answers"].get(idx)
    choice = st.radio("Choose one:", list(options.keys()),
                      format_func=lambda k: f"{k}. {options[k]}",
                      index=list(options).index(prev) if prev in options else 0,
                      key=f"mock_q_{idx}")

    nav = st.columns([1, 1, 1, 3])
    if nav[0].button("◀ Back", disabled=idx == 0):
        ss["mock_idx"] -= 1
        st.rerun()
    if nav[1].button("Skip ▶"):
        ss["mock_idx"] += 1
        st.rerun()
    if nav[2].button("Save & next ▶", type="primary"):
        ss["mock_answers"][idx] = choice
        ss["mock_idx"] += 1
        st.rerun()
    if nav[3].button("🏁 Finish & grade"):
        if choice:
            ss["mock_answers"][idx] = choice
        _finish_mock(ss, elapsed)
        st.rerun()


# ── Router ────────────────────────────────────────────────────────────────────
PAGES = {
    "📊 Dashboard": page_dashboard,
    "🧭 UCAT Guide": page_guide,
    "📝 Practice Questions": page_practice,
    "⏱️ Mock Exam": page_mock,
    "🃏 Flashcards": page_flashcards,
    "🗓️ Study Scheduler": page_scheduler,
    "📚 Strategy & Skills": page_content,
    "🤖 AI Tutor": page_tutor,
    "⚙️ Manage": page_manage,
}
PAGES[page]()
