"""
UCATify — a Streamlit study app.

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
import hmac
import html
import time
import base64
from pathlib import Path
from datetime import date, datetime, timedelta

_LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"
_LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode() if _LOGO_PATH.exists() else ""


def _logo_img(height_px: int, extra_style: str = "") -> str:
    """An <img> tag for the app logo, sized to fit inline HTML (sidebar
    header, sign-in hero) — st.markdown can't reference a local file path
    directly, so it's embedded as a base64 data URI instead."""
    if not _LOGO_B64:
        return ""
    return (f"<img src='data:image/png;base64,{_LOGO_B64}' "
            f"style='height:{height_px}px;width:{height_px}px;{extra_style}' />")

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
def cached_daily_pace(uid, days):
    return db.get_daily_pace(uid, days)


@st.cache_data(ttl=60, show_spinner=False)
def cached_leaderboard_questions():
    return db.get_leaderboard_questions_answered()


@st.cache_data(ttl=60, show_spinner=False)
def cached_leaderboard_pace(min_attempts):
    return db.get_leaderboard_pace(min_attempts=min_attempts)


@st.cache_data(ttl=60, show_spinner=False)
def cached_leaderboard_mock_scores():
    return db.get_leaderboard_mock_scores()


@st.cache_data(ttl=60, show_spinner=False)
def cached_study_tasks(uid, status=None):
    return db.get_study_tasks(uid, status=status)


@st.cache_data(ttl=60, show_spinner=False)
def cached_flashcards(uid, subject_id=None, due_only=False):
    return db.get_flashcards(uid, subject_id=subject_id, due_only=due_only)


@st.cache_data(ttl=60, show_spinner=False)
def cached_last_seen(uid):
    return db.get_last_seen_at(uid)


@st.cache_data(ttl=60, show_spinner=False)
def cached_mistakes(uid, include_resolved=False):
    return db.get_mistakes(uid, include_resolved=include_resolved)


@st.cache_data(ttl=60, show_spinner=False)
def cached_mistake_ids(uid):
    return db.get_mistake_question_ids(uid)


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
    cached_daily_pace.clear()
    cached_leaderboard_questions.clear()
    cached_leaderboard_pace.clear()
    cached_leaderboard_mock_scores.clear()
    cached_last_seen.clear()
    cached_mistakes.clear()
    cached_mistake_ids.clear()


def _invalidate_tasks_cache():
    cached_study_tasks.clear()
    cached_overall_stats.clear()


def _invalidate_flashcard_progress_cache():
    cached_flashcards.clear()
    cached_overall_stats.clear()


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UCATify",
    page_icon=str(_LOGO_PATH) if _LOGO_PATH.exists() else "🩺",
    layout="wide",
    # "auto" (not "expanded"): Streamlit opens the sidebar by default on wide
    # screens but starts it closed on narrow/mobile ones. Forcing "expanded"
    # meant a mobile visitor's first view was the dark sidebar filling the
    # whole viewport, hiding the top nav and all page content behind it.
    initial_sidebar_state="auto",
)

db.init_db()

# ── Theme (paper / ink / teal, serif headings + mono numerics) ─────────────────
# Mirrors the palette and type system used by the UCAT Guide page, so the whole
# app reads as one design system rather than a native-Streamlit default plus one
# custom-styled page.
st.markdown("""
<style>
:root{
    --paper:#F8F6EE; --paper-2:#FCFAF3; --card:#FFFFFF;
    --ink:#14213F; --ink-soft:#3F4C63; --ink-faint:#78859C;
    --line:#E1DCCB; --line-strong:#CEC6AE;
    --teal:#1D3E72; --teal-bright:#2C5590; --teal-wash:#E7ECF4;
    --coral:#C24A38; --coral-wash:#F6E6E1;
    --gold:#BA8F4E; --gold-wash:#F3E7D2;
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

/* Buttons — subtle press feedback (scale down slightly on click) gives
   tactile confirmation that a tap registered, which matters more on the
   touch devices this app is mostly used on than it does on desktop. */
button[kind^="primary"] { background: var(--teal) !important; border: 1px solid var(--teal) !important; color: #fff !important; border-radius: 8px !important; font-weight: 600 !important; transition: background .15s ease, border-color .15s ease, transform .08s ease !important; }
button[kind^="primary"]:hover { background: var(--teal-bright) !important; border-color: var(--teal-bright) !important; }
button[kind^="primary"]:active { transform: scale(0.97); }
button[kind^="secondary"] { border: 1px solid var(--line-strong) !important; border-radius: 8px !important; color: var(--ink) !important; font-weight: 600 !important; transition: border-color .15s ease, color .15s ease, transform .08s ease !important; }
button[kind^="secondary"]:hover { border-color: var(--teal) !important; color: var(--teal) !important; }
button[kind^="secondary"]:active { transform: scale(0.97); }

/* Entrance animation — cards and metrics fade/lift in on each rerun instead
   of just snapping into place, so completing an action (submitting a form,
   finishing a mock, revealing a flashcard) feels like a small reward rather
   than the page silently swapping content out. Ease-out-quint (no bounce)
   reads as precise rather than playful. Staggered by list position so a row
   of stat cards reveals left-to-right instead of blinking in as one block. */
@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
[data-testid="metric-container"], .flashcard, [data-testid="stAlertContainer"], .hero-card,
[data-testid="stPlotlyChart"] {
    animation: fadeSlideIn .32s cubic-bezier(0.22, 1, 0.36, 1) both;
}
[data-testid="column"]:nth-child(1) [data-testid="metric-container"] { animation-delay: 0ms; }
[data-testid="column"]:nth-child(2) [data-testid="metric-container"] { animation-delay: 40ms; }
[data-testid="column"]:nth-child(3) [data-testid="metric-container"] { animation-delay: 80ms; }
[data-testid="column"]:nth-child(4) [data-testid="metric-container"] { animation-delay: 120ms; }
[data-testid="column"]:nth-child(5) [data-testid="metric-container"] { animation-delay: 160ms; }

@media (prefers-reduced-motion: reduce) {
    [data-testid="metric-container"], .flashcard, [data-testid="stAlertContainer"], .hero-card,
    [data-testid="stPlotlyChart"] {
        animation: none !important;
    }
    button[kind^="primary"], button[kind^="secondary"] {
        transition: none !important;
    }
    button[kind^="primary"]:active, button[kind^="secondary"]:active {
        transform: none !important;
    }
}

/* Tabs */
[data-baseweb="tab-list"] { border-bottom: 1px solid var(--line) !important; gap: 1.6rem !important; }
[data-testid="stTab"] { color: var(--ink-soft) !important; font-family: var(--sans) !important; }
[data-testid="stTab"][aria-selected="true"] { color: var(--teal) !important; font-weight: 600 !important; }
[data-baseweb="tab-highlight"] { background-color: var(--teal) !important; }
/* On mobile, tabs with several longer labels (e.g. Leaderboard's "Best Mock
   Score", Manage's five sub-tabs) overflowed Streamlit's tab strip, hiding
   all but a sliver of the last tab behind a small scroll arrow. Wrapping
   instead keeps every tab fully visible and readable without needing to
   discover a horizontal-scroll gesture. */
@media (max-width: 640px) {
    [data-baseweb="tab-list"] { flex-wrap: wrap !important; row-gap: 10px !important; gap: 10px 1.1rem !important; }
    [data-testid="stTab"] { font-size: 14px !important; }
    /* The highlight bar is positioned assuming a single row, so once tabs
       wrap it only ever sits under the first row regardless of which tab is
       active — misleading rather than helpful. The active tab's bold teal
       text (above) already marks it clearly, so drop the bar on mobile. */
    [data-baseweb="tab-highlight"] { display: none !important; }
}

/* Top navigation bar — one continuous bar (matching the sidebar's dark ink),
   gray clickable labels, no emoji */
.st-key-topnav {
    background: var(--ink); border-radius: 12px; width: 100% !important;
    padding: 6px 8px; margin-bottom: 22px; box-shadow: 0 2px 6px rgba(0,0,0,0.18);
}
.st-key-topnav [data-testid="stHorizontalBlock"] { gap: 2px !important; flex-wrap: nowrap !important; }
.st-key-topnav [data-testid="stColumn"] { min-width: 0 !important; }
.st-key-topnav button {
    border-radius: 8px !important; border: none !important;
    background: transparent !important; color: rgba(239,241,236,0.62) !important;
    font-family: var(--sans) !important; font-weight: 600 !important; font-size: 12.5px !important;
    padding: 8px 2px !important; min-height: 38px; white-space: nowrap !important;
    overflow: hidden !important; text-overflow: ellipsis !important; display: block !important;
    box-shadow: none !important; transition: background .12s ease, color .12s ease;
}
.st-key-topnav button p {
    overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important;
}
.st-key-topnav button:hover {
    background: rgba(255,255,255,0.10) !important; color: rgba(255,255,255,0.9) !important;
}
.st-key-topnav button[kind="primary"] {
    background: var(--teal-bright) !important; color: #FFFFFF !important; font-weight: 700 !important;
}
.st-key-topnav button[kind="primary"]:hover { background: var(--teal) !important; }

/* Top nav on narrow/mobile viewports: wrapping every button into a grid (the
   old approach) turned the nav into a tall block that pushed all real page
   content below the fold — on a phone, roughly a third of the screen was
   navigation before a student saw anything else. Scrolling the bar
   horizontally instead keeps it to one compact row, the same pattern phones
   already train people to expect from tab bars. Streamlit gives every column
   inside a horizontal block a native min-width of ~100% by default (its own
   mechanism for stacking columns on small screens), so that has to be
   overridden to fit-content or every column would still blow up to full width
   even with nowrap set. */
@media (max-width: 768px) {
    .st-key-topnav {
        padding: 8px; overflow-x: auto; -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
    }
    .st-key-topnav [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important; width: max-content !important; min-width: 100% !important;
    }
    .st-key-topnav [data-testid="stColumn"] {
        min-width: fit-content !important; width: auto !important; flex: 0 0 auto !important;
    }
    .st-key-topnav button {
        font-size: 13px !important; padding: 10px 16px !important; min-height: 44px;
        white-space: nowrap !important;
    }
}
.st-key-topnav button p { font-family: var(--sans) !important; font-weight: inherit !important; }

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
/* Plotly charts otherwise render as a bare white rectangle floating directly
   on the page background — give them the same card frame (border, radius,
   shadow) as every other surface so they read as part of the same system
   rather than a bolted-on charting library. The figures themselves are made
   transparent (see chart theming helper) so this card background shows
   through uniformly, right up to the plot's own margins. */
[data-testid="stPlotlyChart"] {
    background: var(--card); border: 1px solid var(--line); border-radius: 10px;
    padding: 10px 14px 2px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
/* Dataframes (Leaderboard, Guide reference tables) otherwise render as a
   plain square-cornered grid with no relation to the card system used
   everywhere else. The hover toolbar (search/download/column-visibility) is
   a generic-widget tell that serves no purpose on read-only reference and
   leaderboard tables here, so it's hidden rather than restyled. */
[data-testid="stDataFrame"] {
    border: 1px solid var(--line); border-radius: 10px; overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
[data-testid="stElementToolbar"] { display: none !important; }
.flashcard {
    background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 38px 28px; text-align: center; font-size: 19px; color: var(--ink);
    font-family: var(--serif); box-shadow: 0 4px 14px rgba(0,0,0,0.05); min-height: 150px;
    display: flex; align-items: center; justify-content: center;
}

/* Dashboard hero card — one high-contrast card for the single most important
   number, with quick actions living inside/right below it, rather than that
   number competing for attention as one of several equal-weight tiles. */
.hero-card {
    background: linear-gradient(135deg, var(--ink) 0%, var(--teal) 100%);
    border-radius: 16px; padding: 28px 32px; margin-bottom: 14px;
    box-shadow: 0 8px 24px rgba(20,33,63,0.25);
}
.hero-label {
    font-family: var(--mono); font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
    color: rgba(255,255,255,0.65);
}
.hero-number {
    font-family: var(--serif); font-weight: 700; font-size: 3.2rem; line-height: 1.1;
    color: #FFFFFF; margin-top: 4px;
}
.hero-sub { color: rgba(255,255,255,0.75); font-size: 14px; margin-top: 2px; }
.pill { display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; color:white; font-family: var(--sans); }
.auth-hero { max-width:380px; margin:60px auto 0; text-align:center; }
.auth-hero .mark { margin-bottom:8px; display:flex; justify-content:center; }
.auth-hero h2 { font-family: var(--serif); margin-bottom:4px; color: var(--ink); }
.auth-hero .eyebrow { font-family: var(--mono); font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color: var(--teal); margin-bottom:6px; }
.auth-hero p { color: var(--ink-soft); margin-bottom:28px; font-size:14px; }

/* Day streak milestone celebration — a quiet flame accent that only appears
   the day a streak milestone (3, 7, 14, 30...) is first reached, not a
   permanent badge competing with the number the rest of the time. Tiers
   escalate by size/glow/ember count as the streak grows, all in the
   existing gold accent rather than a new "fire" hue, and stay within the
   app's ease-out-quint, no-bounce motion language. */
@keyframes streakFlicker {
    0%, 100% { transform: scale(1) rotate(0deg); }
    25%      { transform: scale(1.04, 0.97) rotate(-2deg); }
    50%      { transform: scale(0.97, 1.05) rotate(1deg); }
    75%      { transform: scale(1.03, 0.98) rotate(-1deg); }
}
@keyframes streakPop {
    from { opacity: 0; transform: translateY(10px) scale(0.82); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes emberRise {
    0%   { opacity: 0; transform: translateY(0) scale(0.6); }
    15%  { opacity: 1; }
    100% { opacity: 0; transform: translateY(-30px) scale(1); }
}
.streak-flame-wrap {
    position: relative; display: inline-flex; align-items: center; justify-content: center;
    width: 34px; height: 34px; margin-top: 6px;
    animation: streakPop .5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.streak-flame {
    width: 100%; height: 100%; transform-origin: 50% 85%;
    animation: streakFlicker 2.6s ease-in-out infinite;
    filter: drop-shadow(0 0 6px rgba(186,143,78,0.55));
}
.streak-flame.tier-steady { width: 120%; height: 120%; filter: drop-shadow(0 0 9px rgba(186,143,78,0.7)); }
.streak-flame.tier-blaze  { width: 140%; height: 140%; filter: drop-shadow(0 0 13px rgba(186,143,78,0.85)); }
.streak-ember {
    position: absolute; bottom: 4px; width: 4px; height: 4px; border-radius: 50%;
    background: var(--gold); opacity: 0;
    animation: emberRise 1.6s ease-out infinite;
}
.streak-ember:nth-child(2) { left: 6px;  animation-delay: .3s; }
.streak-ember:nth-child(3) { left: 18px; animation-delay: .9s; }
.streak-ember:nth-child(4) { left: 24px; animation-delay: .1s; }
.streak-caption {
    font-family: var(--mono); font-size: 11px; letter-spacing: .04em; color: var(--gold);
    margin-top: 2px; animation: fadeSlideIn .4s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@media (prefers-reduced-motion: reduce) {
    .streak-flame-wrap, .streak-flame, .streak-ember, .streak-caption {
        animation: none !important;
    }
}
</style>
""", unsafe_allow_html=True)


# ── Sound effects ───────────────────────────────────────────────────────────────
# Streamlit strips <script> tags from st.markdown(), so any JS has to run inside
# a components.v1.html() iframe instead. That iframe is same-origin with the
# parent app, so a script inside it can reach window.parent.document to attach
# a listener that fires for buttons rendered in the real app DOM. Both sounds
# are synthesized on the fly with the Web Audio API — no audio asset files, no
# licensing to track. The AudioContext and the click listener are stashed on
# window.parent (not the iframe's own window) and guarded by a flag so a fresh
# iframe injected on every Streamlit rerun reuses rather than re-installs them.
_CLICK_SOUND_JS = """
<script>
(function () {
  var w = window.parent;
  function getCtx() {
    if (!w.__ucatifyAudioCtx) {
      try {
        w.__ucatifyAudioCtx = new (w.AudioContext || w.webkitAudioContext)();
      } catch (e) { return null; }
    }
    return w.__ucatifyAudioCtx;
  }
  w.__ucatifyGetAudioCtx = getCtx;

  // Browsers auto-suspend an AudioContext after a few seconds of silence to
  // save power, and resume() is asynchronous — scheduling a sound against a
  // still-suspended context (whose currentTime is frozen) silently drops it.
  // Routing every sound through this ensures the context is actually running
  // before anything gets scheduled, instead of racing resume() and losing the
  // first click after any pause in activity.
  function playTone(build) {
    var ctx = getCtx();
    if (!ctx) return;
    if (ctx.state === "suspended") {
      ctx.resume().then(function () { build(ctx); }).catch(function () {});
    } else {
      build(ctx);
    }
  }
  w.__ucatifyPlayTone = playTone;

  function playClick() {
    playTone(function (ctx) {
      var t = ctx.currentTime;
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(720, t);
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.1, t + 0.004);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.06);
    });
  }

  if (!w.__ucatifyClickListenerInstalled) {
    w.__ucatifyClickListenerInstalled = true;
    w.document.addEventListener("click", function (e) {
      var btn = e.target && e.target.closest && e.target.closest("button");
      if (btn) playClick();
    }, true);
  }
})();
</script>
"""

_DING_SOUND_JS = """
<script>
(function () {
  var w = window.parent;
  if (!w.__ucatifyPlayTone) return;
  w.__ucatifyPlayTone(function (ctx) {
    var t = ctx.currentTime;
    [660, 880, 1320].forEach(function (freq, i) {
      var start = t + i * 0.09;
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, start);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.16, start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.35);
      osc.connect(gain).connect(ctx.destination);
      osc.start(start);
      osc.stop(start + 0.4);
    });
  });
})();
</script>
"""


def _install_click_sound():
    components.html(_CLICK_SOUND_JS, height=0)


def _play_ding():
    components.html(_DING_SOUND_JS, height=0)


_install_click_sound()


# ── Site gate (optional) + per-account login ───────────────────────────────────
def _check_site_password() -> bool:
    """Optional shared password that gates the whole app before individual sign-in."""
    pwd = os.environ.get("APP_PASSWORD", "")
    if not pwd or st.session_state.get("_site_authenticated"):
        return True
    st.markdown(
        "<div class='auth-hero'>"
        f"<div class='mark'>{_logo_img(64)}</div>"
        "<div class='eyebrow'>UCATify</div>"
        "<h2>Welcome back</h2>"
        "<p>Enter the site password to continue</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        pw = st.text_input("Password", type="password", placeholder="Enter password", label_visibility="collapsed")
        if st.button("Continue", type="primary", width="stretch"):
            # Escalating delay per failed attempt (session-scoped — there's no
            # per-account identifier for this shared gate to lock out against)
            # plus a constant-time comparison, so guessing this password isn't
            # both instant and subject to a timing side-channel.
            fails = st.session_state.get("_site_gate_fails", 0)
            if fails:
                time.sleep(min(2 ** fails, 30))
            if hmac.compare_digest(pw, pwd):
                st.session_state["_site_authenticated"] = True
                st.session_state.pop("_site_gate_fails", None)
                st.rerun()
            else:
                st.session_state["_site_gate_fails"] = fails + 1
                st.error("Incorrect password — please try again.")
    st.stop()
    return False


def _check_account() -> bool:
    """Per-account sign-in/sign-up so each student's progress is tracked separately."""
    if st.session_state.get("user_id"):
        return True
    st.markdown(
        "<div class='auth-hero'>"
        f"<div class='mark'>{_logo_img(64)}</div>"
        "<div class='eyebrow'>UCATify</div>"
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
                    remaining = db.check_login_lockout(u) if u else None
                    if remaining:
                        mins = max(1, remaining // 60)
                        st.error(f"Too many failed attempts. Try again in about {mins} minute(s).")
                    else:
                        user = db.verify_user(u, p) if u and p else None
                        if user:
                            db.clear_login_attempts(u)
                            st.session_state["user_id"] = user["id"]
                            st.session_state["username"] = user["username"]
                            st.rerun()
                        else:
                            if u:
                                db.record_failed_login(u)
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
                    elif len(p2) < 8:
                        st.error("Password must be at least 8 characters.")
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


def _is_content_admin() -> bool:
    """Whether the signed-in user may add/edit/delete the SHARED question,
    flashcard and topic bank in Manage — content every user reads and studies
    from, not just their own. Configured via the ADMIN_USERNAMES env var
    (comma-separated usernames). If it's unset, every signed-in user keeps
    today's behavior (full access) rather than silently locking everyone out
    of managing content the moment this code ships to an existing deployment
    with no admin list configured yet."""
    raw = os.environ.get("ADMIN_USERNAMES", "")
    admins = {u.strip() for u in raw.split(",") if u.strip()}
    if not admins:
        return True
    return st.session_state.get("username") in admins


# ── Helpers ───────────────────────────────────────────────────────────────────
SUBJECTS = cached_subjects()
SUB_BY_ID = {s["id"]: s for s in SUBJECTS}
SUB_BY_NAME = {s["name"]: s for s in SUBJECTS}


def _esc(s):
    """Escape a string of untrusted, user-editable content (question stems/
    options, flashcard text, etc.) before it's interpolated into HTML we
    render with unsafe_allow_html — otherwise anyone who can add or edit that
    shared content (via Manage) could plant a stored XSS payload that runs in
    every other user's browser when they view it."""
    return html.escape(str(s or ""))


def pill(text, color):
    return f"<span class='pill' style='background:{color}'>{_esc(text)}</span>"


_CHART_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def _theme_fig(fig, **layout_kwargs):
    """Applies the app's palette/type to a Plotly figure so it reads as part
    of the same system as the surrounding cards, rather than a
    default-styled charting-library widget dropped onto the page. Figures
    are made transparent so the `[data-testid="stPlotlyChart"]` card frame
    (background, border, shadow) shows through instead of the plot drawing
    its own competing white rectangle."""
    defaults = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_CHART_FONT, color="#3F4C63", size=13),
        legend=dict(font=dict(color="#3F4C63")),
        hoverlabel=dict(bgcolor="#14213F", font=dict(color="#FFFFFF", family=_CHART_FONT)),
        margin=dict(t=10, b=10, l=10, r=10),
    )
    defaults.update(layout_kwargs)
    fig.update_layout(**defaults)
    fig.update_xaxes(gridcolor="#E1DCCB", zerolinecolor="#E1DCCB", linecolor="#CEC6AE",
                      title_font=dict(color="#78859C"), tickfont=dict(color="#78859C"))
    fig.update_yaxes(gridcolor="#E1DCCB", zerolinecolor="#E1DCCB", linecolor="#CEC6AE",
                      title_font=dict(color="#78859C"), tickfont=dict(color="#78859C"))
    return fig


def _plotly_chart(fig):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


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


# ── Sidebar (account + at-a-glance stats) ──────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:4px'>"
        f"{_logo_img(34)}"
        f"<span style='font-family:var(--serif);font-weight:600;font-size:1.5rem;color:#FFFFFF'>UCATify</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Signed in as **{st.session_state.get('username', '')}**")
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
    st.caption("Set an exam date in Manage to enable the countdown.")


# ── Top navigation ──────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("Dashboard", "Home"),
    ("Practice Questions", "Practice"),
    ("UCAT Guide", "Guide"),
    ("Mistakes Bank", "Fixes"),
    ("Mock Exam", "Mock"),
    ("Leaderboard", "Ranks"),
    ("Flashcards", "Cards"),
    ("Study Scheduler", "Plan"),
    ("Strategy & Skills", "Skills"),
    ("AI Tutor", "Tutor"),
    ("Manage", "Manage"),
]
st.session_state.setdefault("nav_page", NAV_ITEMS[0][0])

with st.container(key="topnav"):
    cols = st.columns(len(NAV_ITEMS))
    for col, (full_key, short) in zip(cols, NAV_ITEMS):
        active = st.session_state["nav_page"] == full_key
        with col:
            if st.button(short, key=f"nav_btn_{full_key}",
                         type="primary" if active else "secondary", width="stretch"):
                st.session_state["nav_page"] = full_key
                st.rerun()

page = st.session_state["nav_page"]


_STREAK_MILESTONES = [3, 7, 14, 30, 60, 100, 180, 365]

_STREAK_FLAME_SVG = """
<svg class="streak-flame tier-{tier}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
  <path fill="var(--gold)" d="M12 2C12 2 6.5 7.8 6.5 13.2C6.5 17.6 8.9 21 12.3 21C15.9 21 18.2 17.5 18.2 13.6C18.2 10.9 16.6 8.8 15.1 7.2C15.3 9 14.3 10.6 12.9 10.6C11.6 10.6 11.4 9 12 7.2C12.5 5.7 12 2 12 2Z"/>
  <path fill="var(--gold-wash)" opacity="0.9" d="M12.4 12C12.4 12 10.2 14.3 10.2 16.4C10.2 18.1 11.2 19.4 12.6 19.4C14.1 19.4 15.1 18 15.1 16.3C15.1 14.7 13.9 13.2 12.9 12.3C13 13 12.6 13.6 12.1 13.6C11.6 13.6 11.5 13 11.7 12.4C11.9 11.9 12.4 12 12.4 12Z"/>
</svg>
"""


def _streak_tier(days):
    if days >= 30:
        return "blaze"
    if days >= 7:
        return "steady"
    return "spark"


def _streak_milestone_html(uid, current):
    """Renders the flame + ember celebration exactly once, the day a streak
    milestone (3, 7, 14, 30...) is first reached — not a permanent badge, so
    it doesn't compete with the day count the rest of the time.

    "Already celebrated" is keyed off the current unbroken run's start date
    (today minus `current - 1` days) rather than the raw streak number, since
    a raw-number comparison can't tell "same run continuing" apart from
    "broke and rebuilt to the identical count" — e.g. a 3-day streak that
    breaks and later rebuilds to exactly 3 again is a different run and
    should celebrate again, even though 3 is not greater than 3. Two runs
    only ever share a start date if they're the same run, so this comparison
    is exact regardless of how long ago the last dashboard visit was."""
    if current <= 0:
        return ""
    run_start = (date.today() - timedelta(days=current - 1)).isoformat()
    stored_run_start = db.get_context(uid, "streak_run_start")
    last_celebrated = int(db.get_context(uid, "streak_last_celebrated") or 0)
    if stored_run_start != run_start:
        last_celebrated = 0
        db.set_context(uid, "streak_run_start", run_start)

    if current not in _STREAK_MILESTONES or current <= last_celebrated:
        return ""
    db.set_context(uid, "streak_last_celebrated", str(current))
    flame = _STREAK_FLAME_SVG.format(tier=_streak_tier(current))
    return (
        f"<div class='streak-flame-wrap'>{flame}"
        f"<span class='streak-ember'></span><span class='streak-ember'></span>"
        f"<span class='streak-ember'></span></div>"
        f"<div class='streak-caption'>{current}-day streak!</div>"
    )


# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    st.title("Dashboard")
    ss = st.session_state
    uid = ss["user_id"]
    stats = cached_overall_stats(uid)
    acc = (stats["correct"] / stats["attempts"] * 100) if stats["attempts"] else 0

    dte, exam_d = days_to_exam()

    # Hero card — the single most important number (days until the exam)
    # gets its own high-contrast, full-width treatment with quick actions
    # built in, rather than competing for attention as one of several
    # equal-weight stat tiles below.
    if dte is not None:
        if dte >= 0:
            st.markdown(
                f"<div class='hero-card'>"
                f"<div class='hero-label'>Days until your UCAT</div>"
                f"<div class='hero-number'>{dte}</div>"
                f"<div class='hero-sub'>on {exam_d.strftime('%B %d, %Y')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='hero-card'><div class='hero-label'>Exam day has passed</div>"
                "<div class='hero-sub' style='margin-top:6px'>Good luck / well done!</div></div>",
                unsafe_allow_html=True,
            )
        # Practice is the one primary action here — visually heavier (wider
        # column, filled button) than the two secondary shortcuts, so there's
        # never doubt about what to click first.
        hcols = st.columns([2, 1, 1])
        if hcols[0].button("Start practicing", width="stretch", type="primary", key="hero_practice"):
            ss["nav_page"] = "Practice Questions"
            st.rerun()
        if hcols[1].button("Take a mock", width="stretch", key="hero_mock"):
            ss["nav_page"] = "Mock Exam"
            st.rerun()
        if hcols[2].button("Read the Guide", width="stretch", key="hero_guide"):
            ss["nav_page"] = "UCAT Guide"
            st.rerun()
    else:
        st.markdown(
            "<div class='hero-card'><div class='hero-label'>Set your exam date to start your countdown</div>"
            "<div class='hero-sub' style='margin-top:6px'>Powers this countdown and your study plan.</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("Set exam date", key="hero_set_date"):
            ss["nav_page"] = "Manage"
            st.rerun()

    # First-time onboarding nudge — only for a genuinely fresh account (no
    # attempts yet and no exam date set). Dismissal is stored per-account so
    # it doesn't reappear once acted on or explicitly dismissed.
    if stats["attempts"] == 0 and dte is None and not db.get_context(uid, "onboarding_dismissed"):
        with st.container(border=True):
            st.markdown("#### New here? Start with Practice")
            st.markdown(
                "- **Answer a few practice questions** above — the fastest way to see what the UCAT actually feels like.\n"
                "- **Set your exam date** above — powers the countdown and the study plan.\n"
                "- **Skim the UCAT Guide** when you want the full playbook — useful, but practice comes first."
            )
            if st.button("Dismiss", key="dismiss_onboarding"):
                db.set_context(uid, "onboarding_dismissed", "1")
                st.rerun()

    streak = db.get_streak(uid)
    c0, c1, c2, c3, c4 = st.columns(5)
    c0.metric("Day streak", streak["current"],
              help="Consecutive days you've answered practice questions, sat a mock, or reviewed flashcards")
    milestone_html = _streak_milestone_html(uid, streak["current"])
    if milestone_html:
        c0.markdown(milestone_html, unsafe_allow_html=True)
    c1.metric("Questions answered", stats["attempts"])
    c2.metric("Accuracy", f"{acc:.0f}%")
    c3.metric("Cards mastered", f"{stats['cards_mastered']}/{stats['cards']}")
    task_pct = (stats["tasks_done"] / stats["tasks_total"] * 100) if stats["tasks_total"] else 0
    c4.metric("Study plan", f"{task_pct:.0f}%", help=f"{stats['tasks_done']} of {stats['tasks_total']} tasks done")

    if stats["attempts"]:
        pct = db.get_questions_answered_percentile(uid)
        if pct is not None:
            st.caption(f"You've answered more questions than **{pct}%** of students on this "
                       f"deployment. See the full Leaderboard for more comparisons.")

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
        st.caption(f"Indicative cognitive total: **{cog_total} / 2700** "
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
        _theme_fig(fig, yaxis_title="Accuracy (%)", yaxis_range=[0, 110], height=340)
        fig.update_traces(textfont=dict(color="#3F4C63"))
        _plotly_chart(fig)

        # Readiness — weakest subtests
        ready = df[df["attempts"] > 0].sort_values("accuracy")
        weakest = ready.head(2)["subject_name"].tolist()
        if weakest:
            st.caption(f"Focus area: your lowest accuracy is in **{', '.join(weakest)}**.")
    else:
        st.info("No practice questions answered yet. Head to **Practice Questions** to begin — your analytics will populate here.")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("### Activity (last 30 days)")
        ts = pd.DataFrame(cached_attempts_over_time(uid, 30))
        if not ts.empty:
            ts["accuracy"] = ts["correct"] / ts["attempts"] * 100
            fig2 = px.line(ts, x="day", y="attempts", markers=True)
            fig2.update_traces(line_color="#1D3E72")
            _theme_fig(fig2, height=280, yaxis_title="Questions", xaxis_title="")
            _plotly_chart(fig2)
        else:
            st.caption("No activity recorded in the last 30 days.")
    with colB:
        st.markdown("### Question bank coverage")
        qc = pd.DataFrame(cached_question_counts())
        if not qc.empty and qc["questions"].sum() > 0:
            fig3 = go.Figure(go.Pie(labels=qc["subject_name"], values=qc["questions"],
                                    marker_colors=qc["color"].tolist(), hole=0.45))
            fig3.update_traces(textfont=dict(color="#FFFFFF"))
            _theme_fig(fig3, height=320, showlegend=True,
                       legend=dict(orientation="h", yanchor="top", y=-0.1, x=0, font=dict(color="#3F4C63")))
            _plotly_chart(fig3)

    st.markdown("### Pace — average time per question")
    pace_rows = cached_daily_pace(uid, 30)
    if pace_rows:
        pace_df = pd.DataFrame(pace_rows)
        daily = pace_df.groupby("day").agg(attempts=("attempts", "sum"),
                                            total_seconds=("total_seconds", "sum")).reset_index()
        daily["avg_seconds"] = daily["total_seconds"] / daily["attempts"]
        # Blended target: each day's mix of subtests weighted by official per-question pacing.
        pace_df["target_seconds"] = pace_df["code"].map(seconds_per_question) * pace_df["attempts"]
        target_by_day = pace_df.groupby("day").agg(target_total=("target_seconds", "sum"),
                                                     attempts=("attempts", "sum")).reset_index()
        daily["target_seconds"] = target_by_day["target_total"] / target_by_day["attempts"]

        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=daily["day"], y=daily["avg_seconds"], mode="lines+markers",
                                   name="Your average", line=dict(color="#1D3E72", width=3)))
        fig4.add_trace(go.Scatter(x=daily["day"], y=daily["target_seconds"], mode="lines",
                                   name="Target (official pacing)", line=dict(color="#BA8F4E", width=2, dash="dash")))
        _theme_fig(fig4, height=300, yaxis_title="Seconds per question", xaxis_title="",
                   legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color="#3F4C63")))
        _plotly_chart(fig4)

        latest = daily.iloc[-1]
        gap = latest["avg_seconds"] - latest["target_seconds"]
        if gap > 0:
            st.caption(f"Most recently you averaged **{latest['avg_seconds']:.1f}s/question**, "
                       f"**{gap:.1f}s slower** than the blended target of {latest['target_seconds']:.1f}s. "
                       "Speed comes with repetition — keep drilling at pace.")
        else:
            st.caption(f"Most recently you averaged **{latest['avg_seconds']:.1f}s/question**, "
                       f"at or ahead of the blended target of {latest['target_seconds']:.1f}s. Keep it up.")
    else:
        st.caption("No timed attempts yet. Answer questions in **Practice Questions** or **Mock Exam** "
                   "to start tracking your pace.")

    # Upcoming tasks
    st.markdown("### Upcoming study tasks")
    tasks = [t for t in cached_study_tasks(uid) if t["status"] != "Done"][:5]
    if tasks:
        for t in tasks:
            cols = st.columns([4, 2, 2, 1])
            sub = SUB_BY_ID.get(t["subject_id"])
            cols[0].markdown(f"**{t['title']}**" + (f" · {sub['name']}" if sub else ""))
            cols[1].caption(f"{t['duration_min']} min")
            cols[2].caption(f"{t['due_date'] or '—'}")
            if cols[3].button("✓", key=f"dash_done_{t['id']}", help="Mark done"):
                db.set_task_status(uid, t["id"], "Done")
                _invalidate_tasks_cache()
                st.rerun()
    else:
        st.caption("No open tasks. Add some in **Study Scheduler**.")


# ════════════════════════════════════════════════════════════════════════════
# PRACTICE QUESTIONS
# ════════════════════════════════════════════════════════════════════════════
def _passage_units(pool):
    """Group a question pool into units so passage-linked questions stay together
    and in order — a long passage followed by its series of questions, as in real
    UCAT VR. Standalone questions become single-item units. The caller shuffles
    the units and flattens them, so passage sets are never split apart."""
    groups: dict = {}
    units: list = []
    for q in pool:
        pid = q.get("passage_id")
        if pid:
            groups.setdefault(pid, []).append(q)
        else:
            units.append([q])
    for qs in groups.values():
        qs.sort(key=lambda x: x["id"])
        units.append(qs)
    return units


def _unit_priority(unit, seen_map, mistake_ids):
    """Sort key for a quiz unit, lowest first:
      0. Unseen questions (random order among themselves) — coverage first.
      1. Unresolved mistakes (oldest-seen first) — a reliable boost over
         ordinary review, so questions you've gotten wrong come up more often,
         without displacing brand-new material entirely.
      2. Ordinary seen-and-correct review, oldest-seen first.
    Lets a student cycle through the whole bank before anything repeats, and
    surface past mistakes more often than chance, instead of every quiz
    sampling purely at random with no memory of what was already answered."""
    times = [seen_map.get(q["id"]) for q in unit]
    if all(t is None for t in times):
        return (0, random.random())
    tier = 1 if any(q["id"] in mistake_ids for q in unit) else 2
    return (tier, max(t for t in times if t is not None))


def _mixed_unit_order(pool, seen_map=None, mistake_ids=None):
    """Order a pool's units (see _passage_units) for a quiz, guaranteeing an even
    mix across subtests instead of a flat shuffle. Decision Making's standalone
    questions form far more, smaller units than VR/QR/SJT's passage sets — a
    plain shuffle can fill an entire short 'All subtests' quiz with DM alone
    before ever reaching a passage, purely because there are more small units to
    draw from. Round-robining across subtests (each subtest's own units ordered
    by _unit_priority, one drawn from each in a freshly-shuffled rotation every
    pass) means every represented subtest appears before any one repeats, and
    within each subtest unseen material and unresolved mistakes come up before
    ordinary repeats — so a short mixed quiz reliably samples new material and
    past mistakes rather than randomly re-serving whatever you just answered."""
    seen_map = seen_map or {}
    mistake_ids = mistake_ids or set()
    units = _passage_units(pool)
    by_subject: dict = {}
    for u in units:
        by_subject.setdefault(u[0]["subject_id"], []).append(u)
    for lst in by_subject.values():
        lst.sort(key=lambda u: _unit_priority(u, seen_map, mistake_ids))
    remaining = list(by_subject.keys())
    ordered = []
    while remaining:
        random.shuffle(remaining)
        for sid in list(remaining):
            ordered.append(by_subject[sid].pop(0))
            if not by_subject[sid]:
                remaining.remove(sid)
    return ordered


def _q_options(q):
    """Ordered {letter: text} for a question, skipping blank/absent options so
    each item shows exactly the number of choices its UCAT format uses — 3 for
    Verbal Reasoning's True/False/Can't Tell, 4 for most items, 5 for
    Quantitative Reasoning."""
    pairs = [("A", q.get("option_a")), ("B", q.get("option_b")), ("C", q.get("option_c")),
             ("D", q.get("option_d")), ("E", q.get("option_e"))]
    return {k: v for k, v in pairs if v not in (None, "")}


def _render_passage(q, quiz, idx):
    """Show the shared passage above a passage-linked question, and keep it
    visible for every question in the set — exactly as the real exam does."""
    if not q.get("passage_body"):
        return
    same = [i for i, qq in enumerate(quiz) if qq.get("passage_id") == q.get("passage_id")]
    with st.container(border=True):
        if q.get("passage_title"):
            st.markdown(f"**{q['passage_title']}**")
        st.markdown(q["passage_body"])
    if len(same) > 1 and idx in same:
        st.caption(f"Passage question {same.index(idx) + 1} of {len(same)} — "
                   "the passage stays visible for every question in the set.")


def _is_multi(q):
    """True for Decision Making's real 'Yes/No statements' format, where a
    question has several independently-judged statements and more than one can
    be correct — as opposed to the usual single-best-answer format."""
    return q.get("question_format") == "multi"


def _is_correct(q, chosen):
    """Grade an answer against a question's format. Multi-format answers are a
    comma-joined set of letters (the statements marked 'Yes') and must match the
    full correct set exactly, mirroring the real UCAT task where every
    statement must be judged correctly."""
    if _is_multi(q):
        picked = {x for x in (chosen or "").split(",") if x}
        return picked == set(q["correct"].split(","))
    return chosen == q["correct"]


def _answer_input(q, key, prev=None):
    """Render the answer widget matching a question's format and return the raw
    selection — a single letter for the usual single-best-answer format, or a
    sorted comma-joined set of letters marked 'Yes' for Decision Making's
    multi-statement Yes/No format. `prev` restores a previously-saved answer
    (used by the Mock Exam, where a question can be revisited via Back)."""
    options = _q_options(q)
    if _is_multi(q):
        st.caption("For each statement, check the box if it **follows** from the information above "
                   "(Yes). Leave it unchecked if it does not follow (No). More than one may be correct.")
        prev_set = {x for x in (prev or "").split(",") if x}
        picked = [k for k, v in options.items()
                  if st.checkbox(f"{k}. {v}", value=(k in prev_set), key=f"{key}_{k}")]
        return ",".join(sorted(picked))
    idx = list(options).index(prev) if prev in options else 0
    return st.radio("Choose one:", list(options.keys()),
                     format_func=lambda k: f"{k}. {options[k]}", index=idx, key=key)


def _render_answer_review(q, chosen):
    """Show the post-submit breakdown of a question's options — a per-statement
    Yes/No comparison for Decision Making's multi-format questions, or the usual
    highlighted single choice otherwise."""
    options = _q_options(q)
    if _is_multi(q):
        correct_set = set(q["correct"].split(","))
        chosen_set = {x for x in (chosen or "").split(",") if x}
        for k, v in options.items():
            your = "Yes" if k in chosen_set else "No"
            right = "Yes" if k in correct_set else "No"
            mark = "✓" if your == right else "✗"
            st.markdown(f"{mark} **{k}. {v}** — you said **{your}**, correct is **{right}**")
        return
    for k, v in options.items():
        if k == q["correct"]:
            st.markdown(f"✓ **{k}. {v}**")
        elif k == chosen:
            st.markdown(f"✗ ~~{k}. {v}~~")
        else:
            st.markdown(f"&nbsp;&nbsp;&nbsp;{k}. {_esc(v)}", unsafe_allow_html=True)


def page_practice():
    st.title("Practice Questions")
    ss = st.session_state

    with st.expander("Quiz settings", expanded="quiz" not in ss):
        c1, c2, c3 = st.columns(3)
        with c1:
            sid = subject_selectbox("Subtest", key="quiz_subject", include_all=True)
        with c2:
            difficulty = st.selectbox("Difficulty", ["All", "Easy", "Medium", "Hard"], key="quiz_diff")
        with c3:
            n = st.number_input("Questions", 1, 50, 5, key="quiz_n")
        if st.button("Start quiz", type="primary"):
            pool = cached_questions(subject_id=sid, difficulty=difficulty)
            # Keep passage sets intact and in order, round-robin across subtests
            # when mixing so a short quiz reliably samples every subtest's
            # format, prioritise unseen / least-recently-seen questions so
            # practice cycles through the bank instead of repeating at random,
            # and give unresolved mistakes a boost so they come up more often
            # until answered correctly twice in a row. Then take units until
            # reaching the requested count (a passage set may nudge the total
            # slightly over rather than be cut in half).
            seen_map = cached_last_seen(ss["user_id"])
            mistake_ids = cached_mistake_ids(ss["user_id"])
            units = _mixed_unit_order(pool, seen_map, mistake_ids)
            quiz: list = []
            for u in units:
                if len(quiz) >= int(n):
                    break
                quiz.extend(u)
            if not quiz:
                st.warning("No questions match those filters yet. Add some in Manage.")
            else:
                ss["quiz"] = quiz
                ss["quiz_idx"] = 0
                ss["quiz_answered"] = {}
                ss["quiz_correct"] = 0
                ss["quiz_times"] = {}
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
        times = ss.get("quiz_times", {})
        st.success(f"## Quiz complete — {score}/{total} correct ({score/total*100:.0f}%)")
        st.progress(score / total)
        if times:
            avg_secs = sum(times.values()) / len(times)
            target = sum(seconds_per_question(SUB_BY_ID[quiz[i]["subject_id"]]["code"]) for i in times) / len(times)
            c1, c2 = st.columns(2)
            c1.metric("Average time per question", f"{avg_secs:.1f}s",
                       delta=f"{avg_secs - target:+.1f}s vs target", delta_color="inverse")
            c2.metric("Target for this mix", f"{target:.1f}s",
                       help="Official UCAT per-question pacing, blended across the subtests in this quiz")
        if st.button("New quiz"):
            for k in ("quiz", "quiz_idx", "quiz_answered", "quiz_correct", "quiz_times"):
                ss.pop(k, None)
            st.rerun()
        return

    q = quiz[idx]
    sub = SUB_BY_ID.get(q["subject_id"])
    st.progress((idx) / len(quiz), text=f"Question {idx + 1} of {len(quiz)}")
    if sub:
        st.markdown(pill(sub["name"], sub["color"]) + f"  &nbsp; <span style='color:#888'>{q['difficulty']}</span>", unsafe_allow_html=True)
    _render_passage(q, quiz, idx)
    st.markdown(f"### {q['stem']}")

    answered = ss["quiz_answered"].get(idx)

    if answered is None:
        choice = _answer_input(q, key=f"q_{idx}")
        if st.button("Submit answer", type="primary"):
            is_correct = _is_correct(q, choice)
            elapsed = datetime.now().timestamp() - ss.get("quiz_start", datetime.now().timestamp())
            elapsed = round(elapsed, 1)
            db.record_attempt(ss["user_id"], q["id"], q["subject_id"], choice, is_correct, elapsed)
            _invalidate_stats_cache()
            ss["quiz_answered"][idx] = choice
            ss["quiz_times"][idx] = elapsed
            if is_correct:
                ss["quiz_correct"] += 1
                ss["_play_ding"] = True
            ss["quiz_start"] = datetime.now().timestamp()
            st.rerun()
    else:
        _render_answer_review(q, answered)
        if _is_correct(q, answered):
            st.success("Correct!")
            if ss.pop("_play_ding", False):
                _play_ding()
        elif _is_multi(q):
            st.error("Not fully correct — every statement must be judged correctly to score this "
                     "question, as in the real UCAT.")
        else:
            st.error(f"Not quite — the answer is **{q['correct']}**.")
        taken = ss["quiz_times"].get(idx)
        if taken is not None:
            target = seconds_per_question(SUB_BY_ID[q["subject_id"]]["code"])
            st.caption(f"Answered in **{taken:.1f}s** · target for {sub['name'] if sub else 'this subtest'}: ~{target:.0f}s")
        if q.get("explanation"):
            st.info(f"**Explanation.** {q['explanation']}")
        if st.button("Next", type="primary"):
            ss["quiz_idx"] += 1
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# MISTAKES BANK
# ════════════════════════════════════════════════════════════════════════════
def page_mistakes():
    st.title("Mistakes Bank")
    st.caption(f"Every question you get wrong lands here, and comes up more often in Practice until "
               f"you answer it correctly {db.MISTAKE_CLEAR_STREAK} times in a row.")
    ss = st.session_state
    uid = ss["user_id"]

    all_rows = cached_mistakes(uid, include_resolved=True)
    unresolved = [m for m in all_rows if not m["resolved"]]
    resolved = [m for m in all_rows if m["resolved"]]

    c1, c2 = st.columns(2)
    c1.metric("Needs work", len(unresolved))
    c2.metric("Mastered", len(resolved), help=f"Answered correctly {db.MISTAKE_CLEAR_STREAK} times in a "
              "row after missing it — cleared from the bank.")

    if not unresolved:
        st.success("No unresolved mistakes right now — nice work. Keep practising and anything you "
                   "miss will show up here.")
        return

    if st.button("Practice my mistakes", type="primary"):
        mistake_ids = {m["question_id"] for m in unresolved}
        pool = [q for q in cached_questions() if q["id"] in mistake_ids]
        seen_map = cached_last_seen(uid)
        units = _mixed_unit_order(pool, seen_map)
        quiz: list = []
        for u in units:
            quiz.extend(u)
        ss["quiz"] = quiz
        ss["quiz_idx"] = 0
        ss["quiz_answered"] = {}
        ss["quiz_correct"] = 0
        ss["quiz_times"] = {}
        ss["quiz_start"] = datetime.now().timestamp()
        ss["nav_page"] = "Practice Questions"
        st.rerun()

    st.markdown("### Needs work")
    for m in unresolved:
        with st.container(border=True):
            st.markdown(pill(m["subject_name"], m["color"]) +
                       f"&nbsp; <span style='color:#888'>{m['difficulty']}</span>", unsafe_allow_html=True)
            stem = m["stem"]
            st.markdown(f"**{stem[:160]}{'…' if len(stem) > 160 else ''}**")
            st.caption(f"Missed {m['times_wrong']}× · {m['correct_streak']}/{db.MISTAKE_CLEAR_STREAK} "
                       "correct in a row to clear")

    if resolved:
        with st.expander(f"Mastered ({len(resolved)})"):
            for m in resolved:
                st.markdown(pill(m["subject_name"], m["color"]) + f"&nbsp; {_esc(m['stem'][:120])}"
                           f"{'…' if len(m['stem']) > 120 else ''}", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# FLASHCARDS
# ════════════════════════════════════════════════════════════════════════════
def page_flashcards():
    st.title("Flashcards")
    st.caption("Spaced repetition (SM-2). Rate each card honestly — harder cards come back sooner.")
    ss = st.session_state
    uid = ss["user_id"]

    stats = cached_overall_stats(uid)
    if stats["cards"]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Mastered", f"{stats['cards_mastered']}/{stats['cards']}")
        c2.metric("Due today", stats["cards_due"])
        pct = (stats["cards_mastered"] / stats["cards"] * 100) if stats["cards"] else 0
        c3.metric("Mastery", f"{pct:.0f}%")
        st.divider()

    c1, c2 = st.columns([3, 1])
    with c1:
        sid = subject_selectbox("Subtest", key="fc_subject", include_all=True)
    with c2:
        due_only = st.toggle("Due only", value=True, key="fc_due")

    cards = cached_flashcards(uid, subject_id=sid, due_only=due_only)
    if not cards:
        if due_only:
            st.success("No cards due right now. Toggle off **Due only** to review ahead, or add cards in Manage.")
        else:
            st.info("No flashcards yet. Add some in Manage.")
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
    st.markdown(f"<div class='flashcard'><div><div style='font-size:11px;letter-spacing:1px;color:#9aa;margin-bottom:12px'>{label}</div>{_esc(face)}</div></div>", unsafe_allow_html=True)
    st.write("")

    if not ss.get("fc_show_back"):
        if st.button("Show answer", type="primary", width="stretch"):
            ss["fc_show_back"] = True
            st.rerun()
    else:
        st.caption("How well did you recall it?")
        cols = st.columns(4)
        ratings = [("Again", 0), ("Hard", 3), ("Good", 4), ("Easy", 5)]
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
    st.title("Study Scheduler")
    ss = st.session_state
    uid = ss["user_id"]

    with st.expander("Add a study task"):
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
    with st.expander("Generate a study plan"):
        st.caption("Creates a Review + Practice + Flashcards task per subtest, spread across the days you choose — "
                   "with extra practice sessions weighted toward your weakest subtests.")
        dte, _ = days_to_exam()
        default_days = min(60, max(3, dte)) if dte and dte > 0 else 14
        gc1, gc2 = st.columns(2)
        weeks = gc1.number_input("Spread over (days)", 3, 60, default_days,
                                 help="Defaults to your days-until-exam (set in Manage) when available.")
        per_day = gc2.number_input("Tasks per day", 1, 6, 2)

        acc_rows = cached_accuracy_by_subject(uid)
        attempted = [r for r in acc_rows if r["attempts"]]
        weak_ids = []
        if attempted:
            ranked = sorted(attempted, key=lambda r: r["correct"] / r["attempts"])
            weak_ids = [r["subject_id"] for r in ranked[:2]]
            st.caption(f"Extra practice sessions weighted toward your current weak areas: "
                       f"**{', '.join(SUB_BY_ID[sid]['name'] for sid in weak_ids)}**.")

        if st.button("Generate plan"):
            plan_tasks = []
            for s in SUBJECTS:
                plan_tasks.append((f"Review: {s['name']} high-yield topics", s["id"], "Review"))
                plan_tasks.append((f"Practice: {s['name']} question set", s["id"], "Practice"))
                plan_tasks.append((f"Flashcards: {s['name']}", s["id"], "Flashcards"))
                if s["id"] in weak_ids:
                    plan_tasks.append((f"Extra practice: {s['name']} (weak area)", s["id"], "Practice"))
            # Skip anything already on the plan (by title) so clicking this
            # more than once doesn't silently pile up duplicate tasks.
            existing_titles = {t["title"] for t in cached_study_tasks(uid)}
            added = skipped = 0
            for i, (title, sid, ttype) in enumerate(plan_tasks):
                if title in existing_titles:
                    skipped += 1
                    continue
                due = date.today() + timedelta(days=int(i // per_day) % int(weeks))
                db.upsert_study_task(uid, {"title": title, "subject_id": sid, "task_type": ttype,
                                           "due_date": due.isoformat(), "duration_min": 60})
                added += 1
            _invalidate_tasks_cache()
            if added:
                extra = f" ({skipped} already on your plan, skipped)" if skipped else ""
                st.success(f"Generated {added} new task(s){extra}.")
            else:
                st.info("Everything from this plan is already on your list — nothing new to add.")
            st.rerun()

    all_tasks = cached_study_tasks(uid)
    if all_tasks:
        done_n = sum(1 for t in all_tasks if t["status"] == "Done")
        st.progress(done_n / len(all_tasks), text=f"{done_n} of {len(all_tasks)} tasks done")

    filt = st.radio("Show", ["All", "Todo", "In Progress", "Done"], horizontal=True)
    tasks = cached_study_tasks(uid, status=filt)
    if not tasks:
        if all_tasks:
            st.info(f"Nothing in **{filt}** right now — try a different filter above.")
        else:
            st.info("No tasks yet — add one above, or click **Generate a study plan** "
                     "for a ready-made schedule across every subtest.")
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
        title_md = f"~~{_esc(t['title'])}~~" if done else f"**{_esc(t['title'])}**"
        badge = pill(sub["name"], sub["color"]) if sub else ""
        cols[1].markdown(f"{title_md}  {badge}", unsafe_allow_html=True)
        cols[2].caption(f"{t['task_type']} · {t['duration_min']}m")
        date_txt = t["due_date"] or "—"
        cols[3].markdown(f"<span style='color:{'#c0392b' if overdue else '#888'}'>{date_txt}{' (overdue)' if overdue else ''}</span>", unsafe_allow_html=True)
        status = cols[4].selectbox("", ["Todo", "In Progress", "Done"],
                                   index=["Todo", "In Progress", "Done"].index(t["status"]),
                                   key=f"task_status_{t['id']}", label_visibility="collapsed")
        if status != t["status"]:
            db.set_task_status(uid, t["id"], status)
            _invalidate_tasks_cache()
            st.rerun()
        if cols[5].button("×", key=f"task_del_{t['id']}", help="Delete task"):
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
        f"<div style='background:var(--paper-2,#FCFAF3);border:1px solid var(--line,#E1DCCB);"
        f"border-left:4px solid {color};border-radius:0 10px 10px 0;padding:.9rem 1.05rem;margin:.4rem 0'>"
        f"<div style='font-weight:600;margin-bottom:.4rem'>{q}</div>"
        f"<div style='color:var(--ink-soft,#3F4C63)'>{a}</div></div>",
        unsafe_allow_html=True,
    )
    if trap:
        st.markdown(
            f"<div style='background:var(--coral-wash,#F6E6E1);border-radius:8px;padding:.5rem .9rem;"
            f"font-size:.9rem;color:#8a3324;margin:.4rem 0 1.2rem'><b>Trap —</b> {trap}</div>",
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
    vr_c = SUB_BY_NAME.get("Verbal Reasoning", {}).get("color", "#3D5A80")
    dm_c = SUB_BY_NAME.get("Decision Making", {}).get("color", "#5B4B7A")
    qr_c = SUB_BY_NAME.get("Quantitative Reasoning", {}).get("color", "#3A6B58")
    sjt_c = SUB_BY_NAME.get("Situational Judgement", {}).get("color", "#8A6A3D")

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

    # ── Contents ─────────────────────────────────────────────────────────────
    # Streamlit auto-generates an id (slugified from the heading text) on every
    # st.header/st.subheader, so plain in-page anchor links work here with no
    # extra JS — this list must be kept in sync with the section headers below.
    st.markdown("#### Contents")
    _guide_toc = [
        ("01", "The exam at a glance", "the-exam-at-a-glance"),
        ("02", "Applying: registration, fees & your UCAS timeline",
         "applying-registration-fees-and-your-ucas-timeline"),
        ("03", "Scoring & what actually counts as good", "scoring-and-what-actually-counts-as-good"),
        ("04–07", "Subtest deep dives", "subtest-deep-dives"),
        ("08", "The interface & the timing doctrine", "the-interface-and-the-timing-doctrine"),
        ("09", "The preparation plan", "the-preparation-plan"),
        ("10", "Resources, ranked by usefulness", "resources-ranked-by-usefulness"),
        ("11", "Exam day", "exam-day"),
        ("12", "After the test: results, applying with your score & what's next",
         "after-the-test-results-applying-with-your-score-and-whats-next"),
        ("13", "The eleven commandments", "the-eleven-commandments"),
    ]
    toc_cols = st.columns(2)
    half = (len(_guide_toc) + 1) // 2
    for col, chunk in zip(toc_cols, (_guide_toc[:half], _guide_toc[half:])):
        with col:
            for num, title, anchor in chunk:
                st.markdown(
                    f"<a href='#{anchor}' style='text-decoration:none;display:block;padding:.25rem 0'>"
                    f"<span style='font-family:var(--mono);color:var(--teal,#1D3E72);font-weight:700;"
                    f"margin-right:.6rem'>{num}</span>"
                    f"<span style='color:var(--ink,#14213F)'>{title}</span></a>",
                    unsafe_allow_html=True,
                )

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

    # ── 02 · Application process ─────────────────────────────────────────────
    st.markdown("`02`")
    st.header("Applying: registration, fees & your UCAS timeline")
    st.markdown(
        "Sitting the UCAT is one step inside a wider application — and the admin around it (registering, "
        "booking, paying, and fitting it around UCAS) has its own deadlines that are easy to miss if you're "
        "focused purely on revision. Here's the process end to end."
    )
    application_steps = [
        ("Confirm you need it & shortlist courses", "Check every target school's requirement",
         "The UCAT is required by most UK medicine and dentistry courses (and some other health courses), but "
         "requirements, weighting and score thresholds vary by university — some set hard cut-offs, some rank, "
         "some combine it with grades. Check each target school's current published policy before you register, "
         "since it shapes what score you're actually aiming for."),
        ("Register on the official UCAT website", "One account, exact personal details",
         "Registration opens in the spring and closes in the autumn each cycle — create your account at "
         "ucat.ac.uk and enter your details **exactly** as they'll appear on your UCAS application. A mismatched "
         "name or date of birth is a common, avoidable source of admin problems later."),
        ("Book your test slot", "Pick a centre and a date inside the testing window",
         "Choose a Pearson VUE test centre and a slot within the annual testing window. Earlier slots mean "
         "you'll know your provisional score sooner and can make an informed choice of universities — but weigh "
         "that against having enough time to actually prepare."),
        ("Pay the fee, or apply for the bursary", "There's a means-tested bursary if you qualify",
         "There's a sitting fee (higher outside the UK/EU), but a bursary scheme can cover some or all of it for "
         "eligible candidates. The bursary has its **own, earlier window** — check eligibility and apply well "
         "before general registration closes, not after."),
        ("Apply for access arrangements if you need them", "Extra time or rest breaks — arranged in advance",
         "Reasonable adjustments (extra time, rest breaks, and more) are available for eligible candidates, but "
         "must be requested with supporting evidence **before** you book — this is not something you can ask "
         "for on the day."),
        ("Sit the test", "Right ID, right details, on the day",
         "Bring photo ID that matches your registration details exactly. See **Exam day** below for the "
         "on-the-day logistics and mindset."),
        ("See your provisional score immediately", "Official release to universities comes later",
         "Your raw scores for the cognitive subtests are shown on-screen the moment you finish (SJT is not "
         "scored live). Treat this as provisional — the **official** results reach your chosen universities "
         "later in the cycle."),
        ("Submit your UCAS choices using last year's thresholds", "You'll choose schools before anyone sees your score",
         "UCAS choices for medicine and dentistry are typically due **before** universities receive official "
         "UCAT results, so you're picking schools based on **published prior-year** thresholds and how each one "
         "uses the UCAT — not your actual score."),
        ("Know the retake rule", "One sitting per cycle",
         "You can only sit the UCAT **once per annual cycle**. If your score isn't what you hoped for, the next "
         "opportunity is the following year's cycle, as a new application."),
    ]
    for i, (title, tagline, body) in enumerate(application_steps, start=1):
        c1, c2 = st.columns([1, 11])
        c1.markdown(
            f"<div style='width:2.2rem;height:2.2rem;border-radius:50%;background:var(--teal,#1D3E72);"
            f"color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700'>{i}</div>",
            unsafe_allow_html=True,
        )
        with c2:
            st.markdown(f"**{title}** — {tagline}")
            st.markdown(body)
    st.info(
        "**What you'll need on hand when you register:** a valid passport or photo ID to confirm your identity, "
        "your UCAS details (so your name/DOB match exactly), and a payment method — or your bursary evidence if "
        "you're applying for financial support."
    )
    st.caption(
        "Registration windows, fees, bursary thresholds and test-centre availability change slightly every "
        "cycle — confirm the current year's exact dates and amounts at "
        "[ucat.ac.uk](https://www.ucat.ac.uk) before you register."
    )

    st.divider()

    # ── 03 · Scoring ─────────────────────────────────────────────────────────
    st.markdown("`03`")
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

    # ── 04-07 · Subtest deep dives ───────────────────────────────────────────
    st.markdown("`04–07`")
    st.header("Subtest deep dives")
    tab_vr, tab_dm, tab_qr, tab_sjt = st.tabs(["Verbal Reasoning", "Decision Making",
                                                "Quantitative Reasoning", "Situational Judgement"])
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

    # ── 08 · Timing doctrine ─────────────────────────────────────────────────
    st.markdown("`08`")
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

    # ── 09 · Preparation plan ────────────────────────────────────────────────
    st.markdown("`09`")
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
            f"<div style='width:2.2rem;height:2.2rem;border-radius:50%;background:var(--teal,#1D3E72);"
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

    # ── 10 · Resources ───────────────────────────────────────────────────────
    st.markdown("`10`")
    st.header("Resources, ranked by usefulness")
    st.markdown(
        "Start with the free official material for accuracy, add a question bank for volume, and use timed "
        "mocks to build stamina. Quality and realism matter far more than sheer quantity."
    )
    resources = [
        ("FREE · OFFICIAL", "UCAT Consortium practice materials (ucat.ac.uk)",
         "The most representative questions and the two official mock exams. The single best calibration tool "
         "— do the full mocks near the end of your prep.", True),
        ("FREE · THIS APP", "Your UCATify question bank",
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
        badge_color = "var(--teal,#1D3E72)" if free else "var(--ink-faint,#78859C)"
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

    # ── 11 · Exam day ────────────────────────────────────────────────────────
    st.markdown("`11`")
    st.header("Exam day")
    st.markdown(
        "By now the technique is built — the job is to protect it from nerves and logistics. Nothing on the "
        "day should be a first-time experience."
    )
    c1, c2 = st.columns(2)
    with c1:
        _g_block("Before you go", "#1D3E72", [
            "Sleep properly the night before — cramming past midnight costs more than it adds.",
            "Bring the **correct photo ID**; check the test-centre rules the day before.",
            "Eat something steady and hydrate; arrive early to settle your nerves.",
        ])
        _g_block("Keeping nerves in check", "#1D3E72", [
            "Slow breathing between subtests resets a racing mind faster than re-reading a question.",
            "You've rehearsed this exact format — the day is just another mock with higher stakes.",
        ])
    with c2:
        _g_block("During the test", "#1D3E72", [
            "Work one subtest at a time. A rough section is not the exam — reset and move on.",
            "Trust your pace and your “flag & move” reflex; don't renegotiate strategy mid-exam.",
            "Always spend the final seconds of each subtest filling every blank.",
        ])
        _g_block("Perspective", "#1D3E72", [
            "The UCAT is one part of your application, alongside grades, personal statement and interview.",
            "Different schools weight it differently — a strong score opens doors, but it isn't the whole decision.",
        ])

    st.divider()

    # ── 12 · After the test ──────────────────────────────────────────────────
    st.markdown("`12`")
    st.header("After the test: results, applying with your score, and what's next")
    st.markdown(
        "Finishing the UCAT is one milestone — what you do with the result is the next one. Here's when you'll "
        "actually see numbers, how universities tend to use them, and a rough steer on where a given score "
        "tends to be competitive."
    )

    st.markdown("#### When you get your results")
    _g_block("Timeline", "#1D3E72", [
        "**The moment you finish**, your raw scores for the three cognitive subtests (VR, DM, QR) are shown "
        "on-screen and scaled to 300–900 each — SJT is not scored live.",
        "You'll also receive your own **statement of results** shortly after.",
        "**Official results reach your chosen universities later**, in a batch, well after most candidates have "
        "already sat the test — so for a while, only you know your score.",
    ])

    st.markdown("#### How universities actually use your score")
    st.caption(
        "There's no single system — schools broadly fall into three approaches. The named examples below are "
        "recently published figures for illustration, **not confirmed current-cycle numbers** — always check "
        "each university's own current entry requirements before relying on any of this."
    )
    usage_modes = [
        ("THRESHOLD", "A hard minimum to clear", "Below the line, the application typically doesn't progress "
         "further regardless of everything else — but clearing it doesn't rank you within the group above it. "
         "*Recent published example: Keele has stated a total UCAT score below roughly 1700, or an SJT Band 4, "
         "would not be considered.*"),
        ("RANKING", "Sorted by score among qualifiers", "Candidates who meet the academic entry requirements are "
         "then ordered by UCAT score — e.g. for interview invitations — so within this group, a higher score "
         "directly beats a lower one. *Recent published example: Sheffield has ranked qualifying candidates by "
         "UCAT score, with a stated total threshold of roughly 1800.*"),
        ("WEIGHTED", "Blended with grades and other factors", "UCAT is one ingredient in a combined score rather "
         "than a standalone bar, so a slightly lower UCAT can be offset by other strengths. *Recent published "
         "example: Exeter has weighted UCAT at roughly 25% of shortlisting, academic performance the "
         "remaining 75%, with no fixed minimum score.*"),
    ]
    for badge, title, body in usage_modes:
        with st.container(border=True):
            c1, c2 = st.columns([1, 6])
            c1.markdown(
                f"<span style='font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;font-weight:700;"
                f"color:#fff;background:var(--teal,#1D3E72);padding:.2rem .45rem;border-radius:5px;"
                f"white-space:nowrap'>{badge}</span>", unsafe_allow_html=True,
            )
            with c2:
                st.markdown(f"**{title}**")
                st.caption(body)

    with st.container(border=True):
        st.markdown("#### What does your score suggest?")
        st.caption(
            "A quick, rough steer — not an offer prediction. Enter your total to see where it sits and which of "
            "the illustrative thresholds above it would have cleared."
        )
        post_score = st.number_input("Your total score (out of 2700)", 1200, 2700, 1880, 10, key="post_ucat_score")
        pct = _score_percentile(post_score)
        tier, desc = _score_tier(post_score)
        st.markdown(f"**{tier}** — {desc} ~{pct}th percentile.")
        cleared = [name for name, threshold in
                   (("Keele's ~1700 example", 1700), ("Sheffield's ~1800 example", 1800))
                   if post_score >= threshold]
        if cleared:
            st.caption(f"Would have cleared: {', '.join(cleared)}. Weighted schools like Exeter's example "
                       "have no fixed line to clear either way.")
        else:
            st.caption("This wouldn't have cleared either illustrative threshold example above — weighted-approach "
                       "schools (no fixed minimum) are usually the more realistic reach at this level, alongside "
                       "a broader, carefully chosen list.")
        st.caption("Purely illustrative against two example figures from a recent cycle — not a real-time lookup "
                   "against this year's actual requirements.")

    st.markdown("#### If it didn't go the way you hoped")
    _g_block("Your options", "#1D3E72", [
        "**Apply broadly, not just to reach schools** — mix threshold, ranking and weighted-approach schools so "
        "your list isn't all long shots.",
        "**Look at Gateway/Foundation year courses** — several schools run widening-access programmes with an "
        "extra foundation year and different (often lower or contextual) UCAT requirements.",
        "**Retake next cycle if it's the right call** — you can't resit within the same cycle (see the "
        "application process above), so treat a retake as a deliberate, prepared decision for next year rather "
        "than a default.",
        "**Had something go wrong on the day?** Most universities accept extenuating-circumstances claims (illness, "
        "a disrupted test session, etc.) with supporting evidence, submitted promptly and directly to each "
        "university — this doesn't change your UCAT score itself, but can change how it's read.",
    ])
    st.caption(
        "Thresholds, weightings and even which category a university falls into can change every cycle. Confirm "
        "current requirements directly with each university and at [ucat.ac.uk](https://www.ucat.ac.uk) before "
        "finalising your list."
    )

    st.divider()

    # ── 13 · Mindset ─────────────────────────────────────────────────────────
    st.markdown("`13`")
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
    st.title("Strategy & Skills")
    c1, c2 = st.columns([3, 1])
    with c1:
        sid = subject_selectbox("Subtest", key="content_subject", include_all=True)
    with c2:
        hy = st.toggle("High-yield only", value=False, key="content_hy")

    topics = cached_topics(subject_id=sid, high_yield_only=hy)
    if not topics:
        st.info("No topics found. Add review notes in Manage.")
        return

    # group by subject
    by_subject = {}
    for t in topics:
        by_subject.setdefault(t["subject_name"], []).append(t)

    for sname, items in by_subject.items():
        color = items[0]["color"]
        st.markdown(f"### {pill(sname, color)}", unsafe_allow_html=True)
        for t in items:
            label = ("High-yield — " if t["high_yield"] else "") + t["name"]
            with st.expander(label):
                if t.get("summary"):
                    st.caption(t["summary"])
                st.markdown(t.get("content") or "_No notes yet._")
                if st.button("Ask the AI Tutor about this", key=f"asktutor_{t['id']}"):
                    st.session_state["tutor_prefill"] = (
                        f'Can you help me understand "{t["name"]}"? {t.get("summary") or ""}'
                    ).strip()
                    st.session_state["nav_page"] = "AI Tutor"
                    st.rerun()


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


def _tutor_context_line(uid):
    """A short, current snapshot of the student's own performance, folded into
    the system prompt so the tutor can ground advice in their actual weak
    areas and timeline instead of staying entirely generic."""
    parts = []
    dte, _ = days_to_exam()
    if dte is not None and dte >= 0:
        parts.append(f"{dte} days until their UCAT")
    attempted = [r for r in cached_accuracy_by_subject(uid) if r["attempts"]]
    if attempted:
        weakest = min(attempted, key=lambda r: r["correct"] / r["attempts"])
        weak_acc = weakest["correct"] / weakest["attempts"] * 100
        parts.append(f"weakest subtest so far is {weakest['subject_name']} ({weak_acc:.0f}% accuracy)")
    n_mistakes = len(cached_mistake_ids(uid))
    if n_mistakes:
        parts.append(f"{n_mistakes} unresolved question(s) in their Mistakes Bank")
    if not parts:
        return ""
    return ("Student context: " + "; ".join(parts) + ". Use this to tailor advice when it's relevant "
            "(e.g. suggesting what to prioritise), but still answer whatever they actually ask.")


TUTOR_DAILY_LIMIT = 40
TUTOR_MAX_CHARS = 2000


def _tutor_messages_today(uid):
    """How many Tutor messages this user has sent today. Backed by the
    generic user_context store, keyed per-day, so it resets naturally without
    a cleanup job — old date-keys are simply never read again."""
    raw = db.get_context(uid, f"tutor_count_{date.today().isoformat()}")
    return int(raw) if raw else 0


def _tutor_increment_today(uid):
    key = f"tutor_count_{date.today().isoformat()}"
    count = _tutor_messages_today(uid) + 1
    db.set_context(uid, key, str(count))
    return count


def _tutor_api_key():
    """The Anthropic API key AI Tutor requests use — the deployment owner's
    shared ANTHROPIC_API_KEY, if configured. Every signed-in user shares it,
    capped by a daily per-user message limit (TUTOR_DAILY_LIMIT) to keep the
    deployment owner's API cost bounded."""
    return os.environ.get("ANTHROPIC_API_KEY", "")


def page_tutor():
    st.title("AI Tutor")
    uid = st.session_state["user_id"]
    api_key = _tutor_api_key()
    if not _HAS_ANTHROPIC:
        st.warning("The AI Tutor needs the `anthropic` package installed. Everything else in the app "
                   "works without it.")
        return
    if not api_key:
        st.warning("The AI Tutor isn't configured on this deployment — ask whoever runs it to set an "
                   "Anthropic API key.")
        return

    used_today = _tutor_messages_today(uid)
    cols = st.columns([4, 1])
    cols[0].caption("Ask anything — concepts, practice problems, study strategy. "
                     f"({used_today}/{TUTOR_DAILY_LIMIT} messages used today)")
    if cols[1].button("Clear chat"):
        db.clear_chat_history(uid)
        st.rerun()

    history = db.get_chat_history(uid, 40)
    for m in history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # A "Ask the AI Tutor about this" click from Strategy & Skills lands here
    # with a starter question already queued — send it once, automatically,
    # rather than making the student retype what they were just reading.
    prefill = st.session_state.pop("tutor_prefill", None)

    if used_today >= TUTOR_DAILY_LIMIT:
        st.info(f"You've used all {TUTOR_DAILY_LIMIT} of today's Tutor messages — this keeps API "
                "costs bounded for whoever is paying for this deployment. It resets tomorrow.")
        return

    # max_chars bounds the cost of a single message the same way the daily
    # count bounds the number of them — without it, one very long paste could
    # still be expensive even under the message-count limit.
    prompt = st.chat_input("e.g. Explain the difference between competitive and noncompetitive inhibition",
                            max_chars=TUTOR_MAX_CHARS)
    if prefill and not prompt:
        prompt = prefill

    if prompt:
        db.save_message(uid, "user", prompt)
        _tutor_increment_today(uid)
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                msgs = [{"role": m["role"], "content": m["content"]} for m in db.get_chat_history(uid, 20)]
                system_prompt = SYSTEM_PROMPT
                ctx = _tutor_context_line(uid)
                if ctx:
                    system_prompt = f"{SYSTEM_PROMPT}\n\n{ctx}"
                with st.spinner("Thinking…"):
                    resp = client.messages.create(
                        model="claude-opus-4-8",
                        max_tokens=1200,
                        system=system_prompt,
                        messages=msgs,
                    )
                answer = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            except Exception as e:
                # Log the real error server-side only — showing raw exception
                # text to the end user can leak internal details (request IDs,
                # SDK internals, occasionally fragments of request context).
                print(f"AI Tutor error for user {uid}: {e}")
                answer = "Sorry, the tutor hit an error processing that. Please try again in a moment."
            st.markdown(answer)
            db.save_message(uid, "assistant", answer)
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# MANAGE
# ════════════════════════════════════════════════════════════════════════════
def page_manage():
    st.title("Manage")
    uid = st.session_state["user_id"]
    is_admin = _is_content_admin()
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
                elif not new_pw or len(new_pw) < 8:
                    st.error("New password must be at least 8 characters.")
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
        if not is_admin:
            st.info("Adding, editing and deleting shared questions is limited to admins on this "
                     "deployment. You can still browse and search the bank below.")
        else:
            with st.form("add_q", clear_on_submit=True):
                st.markdown("**Add a practice question**")
                sname = st.selectbox("Subtest", [s["name"] for s in SUBJECTS], key="mq_sub")
                stem = st.text_area("Question stem")
                c = st.columns(2)
                a = c[0].text_input("Option A")
                b = c[1].text_input("Option B")
                cc = c[0].text_input("Option C")
                d = c[1].text_input("Option D")
                e = st.text_input("Option E (optional — Quantitative Reasoning uses five options)")
                c2 = st.columns(2)
                correct = c2[0].selectbox("Correct answer", ["A", "B", "C", "D", "E"])
                diff = c2[1].selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
                expl = st.text_area("Explanation")
                if st.form_submit_button("Add question", type="primary"):
                    if stem and a and b and cc and d:
                        db.upsert_question({
                            "subject_id": SUB_BY_NAME[sname]["id"], "stem": stem,
                            "option_a": a, "option_b": b, "option_c": cc, "option_d": d,
                            "option_e": e or None,
                            "correct": correct, "explanation": expl, "difficulty": diff,
                        })
                        _invalidate_content_cache()
                        st.success("Question added.")
                        st.rerun()
                    else:
                        st.warning("Fill in the stem and at least options A–D.")
        st.divider()
        qs = db.get_questions(include_inactive=True)
        search = st.text_input("Search questions", key="mq_search",
                                placeholder="Filter by keyword or subtest…")
        filtered = qs
        if search:
            needle = search.lower()
            filtered = [q for q in qs if needle in q["stem"].lower()
                       or needle in SUB_BY_ID.get(q["subject_id"], {}).get("name", "").lower()]
        st.caption(f"{len(filtered)} of {len(qs)} questions" if search else f"{len(qs)} questions in the bank")
        for q in _paginate(filtered, "mq_page"):
            retired = "" if (q.get("active") in (1, None)) else " · retired"
            with st.expander(f"[{SUB_BY_ID.get(q['subject_id'],{}).get('name','?')}] {q['stem'][:70]}{retired}"):
                locked = q.get("question_format") == "multi" or q.get("passage_id")
                edit_key = f"editq_{q['id']}"
                if not is_admin:
                    st.markdown(f"**Correct:** {q['correct']} · **Difficulty:** {q['difficulty']}{retired}")
                    st.caption(q.get("explanation") or "")
                elif locked:
                    st.markdown(f"**Correct:** {q['correct']} · **Difficulty:** {q['difficulty']}{retired}")
                    st.caption(q.get("explanation") or "")
                    st.caption("This question is part of a passage set or uses the multi-statement format — "
                               "editing those isn't supported here yet. You can still delete it.")
                    if st.button("Delete", key=f"delq_{q['id']}"):
                        db.delete_question(q["id"])
                        _invalidate_content_cache()
                        st.rerun()
                elif st.session_state.get(edit_key):
                    subj_names = [s["name"] for s in SUBJECTS]
                    cur_subj = SUB_BY_ID.get(q["subject_id"], {}).get("name", subj_names[0])
                    with st.form(f"editform_q_{q['id']}"):
                        sname_e = st.selectbox("Subtest", subj_names,
                                                index=subj_names.index(cur_subj) if cur_subj in subj_names else 0,
                                                key=f"eq_sub_{q['id']}")
                        stem_e = st.text_area("Question stem", value=q["stem"], key=f"eq_stem_{q['id']}")
                        c = st.columns(2)
                        a_e = c[0].text_input("Option A", value=q.get("option_a") or "", key=f"eq_a_{q['id']}")
                        b_e = c[1].text_input("Option B", value=q.get("option_b") or "", key=f"eq_b_{q['id']}")
                        c_e = c[0].text_input("Option C", value=q.get("option_c") or "", key=f"eq_c_{q['id']}")
                        d_e = c[1].text_input("Option D", value=q.get("option_d") or "", key=f"eq_d_{q['id']}")
                        e_e = st.text_input("Option E (optional)", value=q.get("option_e") or "", key=f"eq_e_{q['id']}")
                        c2 = st.columns(2)
                        letters = ["A", "B", "C", "D", "E"]
                        correct_e = c2[0].selectbox("Correct answer", letters,
                                                     index=letters.index(q["correct"]) if q["correct"] in letters else 0,
                                                     key=f"eq_cor_{q['id']}")
                        diffs = ["Easy", "Medium", "Hard"]
                        diff_e = c2[1].selectbox("Difficulty", diffs,
                                                  index=diffs.index(q["difficulty"]) if q["difficulty"] in diffs else 1,
                                                  key=f"eq_diff_{q['id']}")
                        expl_e = st.text_area("Explanation", value=q.get("explanation") or "", key=f"eq_expl_{q['id']}")
                        fc1, fc2 = st.columns(2)
                        if fc1.form_submit_button("Save changes", type="primary"):
                            if stem_e and a_e and b_e and c_e and d_e:
                                db.upsert_question({
                                    "id": q["id"], "subject_id": SUB_BY_NAME[sname_e]["id"], "stem": stem_e,
                                    "option_a": a_e, "option_b": b_e, "option_c": c_e, "option_d": d_e,
                                    "option_e": e_e or None, "correct": correct_e, "explanation": expl_e,
                                    "difficulty": diff_e,
                                })
                                _invalidate_content_cache()
                                st.session_state[edit_key] = False
                                st.success("Saved.")
                                st.rerun()
                            else:
                                st.warning("Fill in the stem and at least options A–D.")
                        if fc2.form_submit_button("Cancel"):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    st.markdown(f"**Correct:** {q['correct']} · **Difficulty:** {q['difficulty']}{retired}")
                    st.caption(q.get("explanation") or "")
                    bcol1, bcol2 = st.columns(2)
                    if bcol1.button("Edit", key=f"editbtn_q_{q['id']}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                    if bcol2.button("Delete", key=f"delq_{q['id']}"):
                        db.delete_question(q["id"])
                        _invalidate_content_cache()
                        st.rerun()

    # Flashcards
    with tabs[3]:
        if not is_admin:
            st.info("Adding, editing and deleting shared flashcards is limited to admins on this "
                     "deployment. You can still browse and search the bank below.")
        else:
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
        fc_search = st.text_input("Search flashcards", key="mfc_search",
                                   placeholder="Filter by keyword or subtest…")
        fc_filtered = cards
        if fc_search:
            needle = fc_search.lower()
            fc_filtered = [fc for fc in cards if needle in fc["front"].lower() or needle in fc["back"].lower()
                          or needle in SUB_BY_ID.get(fc["subject_id"], {}).get("name", "").lower()]
        st.caption(f"{len(fc_filtered)} of {len(cards)} flashcards" if fc_search else f"{len(cards)} flashcards")
        for fc in _paginate(fc_filtered, "mfc_page"):
            with st.expander(f"[{SUB_BY_ID.get(fc['subject_id'],{}).get('name','?')}] {fc['front'][:70]}"):
                edit_key = f"editfc_{fc['id']}"
                if not is_admin:
                    st.markdown(f"**Back:** {fc['back']}")
                elif st.session_state.get(edit_key):
                    subj_names = [s["name"] for s in SUBJECTS]
                    cur_subj = SUB_BY_ID.get(fc["subject_id"], {}).get("name", subj_names[0])
                    with st.form(f"editform_fc_{fc['id']}"):
                        sname_e = st.selectbox("Subtest", subj_names,
                                                index=subj_names.index(cur_subj) if cur_subj in subj_names else 0,
                                                key=f"efc_sub_{fc['id']}")
                        front_e = st.text_area("Front (prompt)", value=fc["front"], key=f"efc_front_{fc['id']}")
                        back_e = st.text_area("Back (answer)", value=fc["back"], key=f"efc_back_{fc['id']}")
                        fc1, fc2 = st.columns(2)
                        if fc1.form_submit_button("Save changes", type="primary"):
                            if front_e and back_e:
                                db.upsert_flashcard({"id": fc["id"], "subject_id": SUB_BY_NAME[sname_e]["id"],
                                                     "front": front_e, "back": back_e})
                                _invalidate_content_cache()
                                st.session_state[edit_key] = False
                                st.success("Saved.")
                                st.rerun()
                            else:
                                st.warning("Fill in both sides.")
                        if fc2.form_submit_button("Cancel"):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    st.markdown(f"**Back:** {fc['back']}")
                    bcol1, bcol2 = st.columns(2)
                    if bcol1.button("Edit", key=f"editbtn_fc_{fc['id']}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                    if bcol2.button("Delete", key=f"delfc_{fc['id']}"):
                        db.delete_flashcard(fc["id"])
                        _invalidate_content_cache()
                        st.rerun()

    # Topics
    with tabs[4]:
        if not is_admin:
            st.info("Adding, editing and deleting shared topics is limited to admins on this "
                     "deployment. You can still browse below.")
        else:
            with st.form("add_topic", clear_on_submit=True):
                st.markdown("**Add a review topic**")
                sname = st.selectbox("Subtest", [s["name"] for s in SUBJECTS], key="mt_sub")
                name = st.text_input("Topic name")
                hy = st.checkbox("High-yield")
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
            with st.expander(f"{'High-yield — ' if t['high_yield'] else ''}[{t['subject_name']}] {t['name']}"):
                edit_key = f"editt_{t['id']}"
                if not is_admin:
                    st.markdown(t.get("content") or "_No notes._")
                elif st.session_state.get(edit_key):
                    subj_names = [s["name"] for s in SUBJECTS]
                    cur_subj = t.get("subject_name") if t.get("subject_name") in subj_names else subj_names[0]
                    with st.form(f"editform_t_{t['id']}"):
                        sname_e = st.selectbox("Subtest", subj_names, index=subj_names.index(cur_subj),
                                                key=f"et_sub_{t['id']}")
                        name_e = st.text_input("Topic name", value=t["name"], key=f"et_name_{t['id']}")
                        hy_e = st.checkbox("High-yield", value=bool(t["high_yield"]), key=f"et_hy_{t['id']}")
                        summary_e = st.text_input("One-line summary", value=t.get("summary") or "",
                                                   key=f"et_sum_{t['id']}")
                        content_e = st.text_area("Notes (Markdown supported)", value=t.get("content") or "",
                                                  height=160, key=f"et_content_{t['id']}")
                        fc1, fc2 = st.columns(2)
                        if fc1.form_submit_button("Save changes", type="primary"):
                            if name_e:
                                db.upsert_topic({"id": t["id"], "subject_id": SUB_BY_NAME[sname_e]["id"],
                                                 "name": name_e, "high_yield": 1 if hy_e else 0,
                                                 "summary": summary_e, "content": content_e})
                                _invalidate_content_cache()
                                st.session_state[edit_key] = False
                                st.success("Saved.")
                                st.rerun()
                            else:
                                st.warning("Give the topic a name.")
                        if fc2.form_submit_button("Cancel"):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    st.markdown(t.get("content") or "_No notes._")
                    bcol1, bcol2 = st.columns(2)
                    if bcol1.button("Edit", key=f"editbtn_t_{t['id']}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                    if bcol2.button("Delete", key=f"delt_{t['id']}"):
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
        # Shuffle whole passage sets rather than loose questions so a passage's
        # follow-ups stay together and in order, as in the real exam.
        units = _passage_units(cached_questions(subject_id=s["id"]))
        random.shuffle(units)
        for u in units:
            questions.extend(u)
    budget = sum(seconds_per_question(SUB_BY_ID[q["subject_id"]]["code"]) for q in questions)
    return questions, int(budget)


def _mock_subtest_ranges(quiz):
    """(subject_id, start_idx, end_idx_exclusive) for each contiguous subtest
    block in the flat mock question list, in the order they appear. _build_mock
    appends whole subtests one after another, so each one is always contiguous."""
    ranges = []
    start = 0
    for i in range(1, len(quiz) + 1):
        if i == len(quiz) or quiz[i]["subject_id"] != quiz[start]["subject_id"]:
            ranges.append((quiz[start]["subject_id"], start, i))
            start = i
    return ranges


def _finish_mock(ss, elapsed):
    """Record every answered question to analytics once, then flip to the results screen."""
    if not ss.get("mock_graded"):
        times = ss.get("mock_times", {})
        batch = []
        for i, q in enumerate(ss["mock"]):
            chosen = ss["mock_answers"].get(i)
            if chosen is not None:
                batch.append((q["id"], q["subject_id"], chosen, _is_correct(q, chosen), times.get(i, 0)))
        db.record_attempts_bulk(ss["user_id"], batch)

        rows = _mock_results(ss)
        total_q = sum(r["total"] for r in rows.values())
        total_correct = sum(r["correct"] for r in rows.values())
        cog_total = None
        if any(code in COGNITIVE_CODES for code in rows):
            cog_total = sum(est_scaled_score(r["correct"] / r["total"] * 100 if r["total"] else 0)
                             for code, r in rows.items() if code in COGNITIVE_CODES)
        if total_q:
            db.record_mock_result(ss["user_id"], total_correct, total_q, cog_total)

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
        if answers.get(i) is not None and _is_correct(q, answers.get(i)):
            r["correct"] += 1
    return rows


def page_mock():
    st.title("Mock Exam")
    ss = st.session_state

    # ── Results screen ────────────────────────────────────────────────────────
    if ss.get("mock_done"):
        rows = _mock_results(ss)
        total_q = sum(r["total"] for r in rows.values())
        total_correct = sum(r["correct"] for r in rows.values())
        used = ss.get("mock_elapsed", 0)
        st.success(f"## Mock complete — {total_correct}/{total_q} correct "
                   f"({(total_correct/total_q*100) if total_q else 0:.0f}%)")
        st.caption(f"Time used: {fmt_mmss(used)} of {fmt_mmss(ss.get('mock_budget', 0))}")

        answered_times = {i: t for i, t in ss.get("mock_times", {}).items()
                           if ss["mock_answers"].get(i) and t}
        if answered_times:
            avg_secs = sum(answered_times.values()) / len(answered_times)
            target = sum(seconds_per_question(SUB_BY_ID[ss["mock"][i]["subject_id"]]["code"])
                         for i in answered_times) / len(answered_times)
            c1, c2 = st.columns(2)
            c1.metric("Average time per question", f"{avg_secs:.1f}s",
                       delta=f"{avg_secs - target:+.1f}s vs target", delta_color="inverse")
            c2.metric("Target for this mix", f"{target:.1f}s",
                       help="Official UCAT per-question pacing, blended across the subtests in this mock")

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
            st.caption(f"Indicative cognitive total: **{cog_total} / 2700**. "
                       "Estimates from accuracy only — not official UCAT scores. "
                       "All answers were saved to your analytics.")

        with st.expander("Review answers"):
            for i, q in enumerate(ss["mock"]):
                chosen = ss["mock_answers"].get(i)
                skipped = chosen is None
                ok = (not skipped) and _is_correct(q, chosen)
                mark = "✓" if ok else ("–" if skipped else "✗")
                st.markdown(f"{mark} **{q['stem'][:90]}**")
                if _is_multi(q):
                    st.caption(f"Your Yes answers: {chosen.replace(',', ', ') if chosen else '— none'} · "
                               f"Correct Yes answers: {q['correct'].replace(',', ', ')}"
                               + (" (skipped)" if skipped else ""))
                else:
                    opts = _q_options(q)
                    st.caption(f"Your answer: {chosen or '— (skipped)'} · "
                               f"Correct: {q['correct']} ({opts.get(q['correct'], '?')})")
                if q.get("explanation"):
                    st.caption(f"{q['explanation']}")

        if st.button("New mock", type="primary"):
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
                   "Add more questions in Manage to lengthen your mocks.")

        mock_summary = db.get_mock_summary(ss["user_id"])
        if mock_summary["count"]:
            c1, c2 = st.columns(2)
            c1.metric("Mocks completed", mock_summary["count"])
            c2.metric("Best score", f"{mock_summary['best_pct']:.0f}%")
        st.divider()

        mode = st.radio("Mode", ["Full mock (all subtests)", "Single subtest"], horizontal=True)
        subtest_ids = None
        if mode == "Single subtest":
            sid = subject_selectbox("Subtest", key="mock_subtest")
            subtest_ids = [sid] if sid else None

        # preview count + budget
        preview_q, preview_budget = _build_mock(subtest_ids)
        if not preview_q:
            st.warning("No questions available for that selection. Add some in Manage.")
            return
        st.info(f"{len(preview_q)} questions · {fmt_mmss(preview_budget)} total")

        if st.button("Start mock", type="primary"):
            quiz, budget = _build_mock(subtest_ids)
            ss["mock"] = quiz
            ss["mock_idx"] = 0
            ss["mock_answers"] = {}
            ss["mock_times"] = {}
            ss["mock_q_start"] = {}
            ss["mock_budget"] = budget
            # Elapsed time is tracked as accumulated-so-far + time since the
            # current running segment began, rather than a single start
            # timestamp, so pausing can freeze the clock (see the Pause/Resume
            # handling below) instead of the exam continuing to run in the
            # background while a student is away.
            ss["mock_elapsed_accum"] = 0.0
            ss["mock_segment_start"] = datetime.now().timestamp()
            ss["mock_paused"] = False
            st.rerun()
        return

    # ── In-progress exam ──────────────────────────────────────────────────────
    quiz = ss["mock"]
    budget = ss["mock_budget"]
    now = datetime.now().timestamp()
    paused = ss.get("mock_paused", False)
    elapsed = ss["mock_elapsed_accum"] if paused else ss["mock_elapsed_accum"] + (now - ss["mock_segment_start"])
    remaining = budget - elapsed

    # Time's up → grade automatically (not while paused: the clock is frozen,
    # so remaining can't have genuinely run out during a pause)
    if remaining <= 0 and not paused:
        _finish_mock(ss, budget)
        st.rerun()

    idx = ss["mock_idx"]
    if idx >= len(quiz):
        _finish_mock(ss, elapsed)
        st.rerun()

    # ── Paused screen ────────────────────────────────────────────────────────
    if paused:
        st.info(f"**Mock paused** — {fmt_mmss(remaining)} remaining · on question {idx + 1} of {len(quiz)}.")
        st.caption("The clock and your progress are frozen. Resume whenever you're ready to continue.")
        if st.button("Resume", type="primary"):
            pause_duration = datetime.now().timestamp() - ss.get("mock_paused_since", now)
            # Shift every recorded question-start timestamp forward by the
            # pause duration so the per-question pace stats computed later
            # don't count time spent paused as time spent thinking.
            for k in ss.get("mock_q_start", {}):
                ss["mock_q_start"][k] += pause_duration
            ss["mock_segment_start"] = datetime.now().timestamp()
            ss["mock_paused"] = False
            st.rerun()
        return

    ss.setdefault("mock_q_start", {}).setdefault(idx, datetime.now().timestamp())

    # Header: live countdown (cosmetic client-side ticker) + progress + pause
    top = st.columns([2, 3, 1])
    with top[0]:
        components.html(f"""
            <div id='ucat-timer' style="font:600 26px/1.2 -apple-system,Segoe UI,Roboto,sans-serif;
                 color:{'#C24A38' if remaining < 60 else '#14213F'}"></div>
            <script>
              let r = {int(remaining)};
              const el = document.getElementById('ucat-timer');
              function tick() {{
                const m = Math.floor(Math.max(0,r)/60), s = Math.max(0,r)%60;
                el.textContent = m + ':' + String(s).padStart(2,'0') + ' remaining';
                if (r > 0) {{ r--; setTimeout(tick, 1000); }}
              }}
              tick();
            </script>
        """, height=44)
    with top[1]:
        st.progress(idx / len(quiz), text=f"Question {idx + 1} of {len(quiz)}")
    with top[2]:
        if st.button("Pause", width="stretch"):
            ss["mock_elapsed_accum"] = elapsed
            ss["mock_paused_since"] = datetime.now().timestamp()
            ss["mock_paused"] = True
            st.rerun()

    # Subtest navigator — jump straight to any subtest's first question,
    # rather than only stepping one question at a time via Back/Skip/Next.
    # Only shown for a full mock; a single-subtest mock has nothing to jump to.
    ranges = _mock_subtest_ranges(quiz)
    if len(ranges) > 1:
        nav_cols = st.columns(len(ranges))
        for col, (sid, start, end) in zip(nav_cols, ranges):
            sub = SUB_BY_ID[sid]
            answered = sum(1 for i in range(start, end) if ss["mock_answers"].get(i) is not None)
            active = start <= idx < end
            with col:
                if st.button(f"{sub['name']} ({answered}/{end - start})", key=f"mockjump_{sid}",
                             type="primary" if active else "secondary", width="stretch"):
                    ss["mock_idx"] = start
                    st.rerun()

    q = quiz[idx]
    sub = SUB_BY_ID.get(q["subject_id"])
    if sub:
        st.markdown(pill(sub["name"], sub["color"]) + f"  &nbsp; <span style='color:#888'>{q['difficulty']}</span>",
                    unsafe_allow_html=True)
    _render_passage(q, quiz, idx)
    st.markdown(f"### {q['stem']}")

    prev = ss["mock_answers"].get(idx)
    choice = _answer_input(q, key=f"mock_q_{idx}", prev=prev)

    nav = st.columns([1, 1, 1, 3])
    if nav[0].button("◀ Back", disabled=idx == 0):
        ss["mock_idx"] -= 1
        st.rerun()
    if nav[1].button("Skip ▶"):
        ss["mock_idx"] += 1
        st.rerun()
    if nav[2].button("Save & next ▶", type="primary"):
        ss["mock_answers"][idx] = choice
        ss["mock_times"][idx] = round(datetime.now().timestamp() - ss["mock_q_start"].get(idx, datetime.now().timestamp()), 1)
        ss["mock_idx"] += 1
        st.rerun()
    if nav[3].button("Finish & grade"):
        if choice:
            ss["mock_answers"][idx] = choice
            ss["mock_times"][idx] = round(datetime.now().timestamp() - ss["mock_q_start"].get(idx, datetime.now().timestamp()), 1)
        _finish_mock(ss, elapsed)
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# LEADERBOARD
# ════════════════════════════════════════════════════════════════════════════
def _render_leaderboard(rows, uid, value_fmt, top_n=10):
    if not rows:
        st.info("No qualifying data yet — be the first to set a benchmark.")
        return

    medals = {1: "1st", 2: "2nd", 3: "3rd"}
    top = rows[:top_n]
    df = pd.DataFrame([
        {"Rank": medals.get(i, str(i)), "Student": r["username"] + (" (you)" if r["user_id"] == uid else ""),
         "Value": value_fmt(r["value"])}
        for i, r in enumerate(top, start=1)
    ])
    st.dataframe(df, hide_index=True, width="stretch")

    if not any(r["user_id"] == uid for r in top):
        for i, r in enumerate(rows, start=1):
            if r["user_id"] == uid:
                st.caption(f"Your rank: **#{i}** of {len(rows)} — {value_fmt(r['value'])}")
                break
        else:
            st.caption("You don't have qualifying data yet — keep practising to appear on this board.")


def page_leaderboard():
    st.title("Leaderboard")
    st.caption("See how your prep compares. Rankings are shared across every signed-in student.")
    uid = st.session_state["user_id"]

    tab1, tab2, tab3 = st.tabs(["Most Questions Answered", "Fastest Pace", "Best Mock Score"])

    with tab1:
        st.caption("Total practice + mock questions answered, all-time.")
        _render_leaderboard(cached_leaderboard_questions(), uid, lambda v: f"{int(v)}")

    with tab2:
        threshold = st.select_slider("Minimum timed questions to qualify", options=[20, 50, 100, 200], value=50)
        st.caption(f"Lowest average seconds per question, among students with at least {threshold} timed answers "
                   "— so a fast time from just a few lucky questions can't top the board.")
        _render_leaderboard(cached_leaderboard_pace(threshold), uid, lambda v: f"{v:.1f}s")

    with tab3:
        st.caption("Best indicative cognitive total (VR + DM + QR, out of 2700) from a single completed Mock Exam.")
        _render_leaderboard(cached_leaderboard_mock_scores(), uid, lambda v: f"{int(round(v))} / 2700")


# ── Router ────────────────────────────────────────────────────────────────────
PAGES = {
    "Dashboard": page_dashboard,
    "UCAT Guide": page_guide,
    "Practice Questions": page_practice,
    "Mistakes Bank": page_mistakes,
    "Mock Exam": page_mock,
    "Leaderboard": page_leaderboard,
    "Flashcards": page_flashcards,
    "Study Scheduler": page_scheduler,
    "Strategy & Skills": page_content,
    "AI Tutor": page_tutor,
    "Manage": page_manage,
}
PAGES[page]()
