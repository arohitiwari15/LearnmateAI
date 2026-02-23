import streamlit as st
import requests
import json
import re
import html as html_lib

# ─────────────────────────────────────────────────────────────
# KEYS — paste yours here
# ─────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
GEMINI_API_KEY     = st.secrets["GEMINI_API_KEY"]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_URL     = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
LLAMA_MODEL    = "meta-llama/llama-3.1-8b-instruct"

SUBJECTS = ["Data Structures & Algorithms", "Mathematics", "Physics",
            "Chemistry", "Biology", "History", "Literature", "Economics"]

TUTOR_SYSTEM = """You are LearnMate AI, a warm and brilliant tutor who makes learning feel effortless.
Your style: friendly, clear, uses real-world analogies, never condescending.
Always structure explanations with:
- A simple one-line summary first
- Step-by-step breakdown  
- A real-life analogy
- Key takeaway

For practice questions, match the student level exactly:
Beginner = conceptual / definition questions
Intermediate = application questions
Advanced = analysis / problem-solving questions"""

# ─────────────────────────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────────────────────────
def call_llama(messages: list, max_tokens: int = 800) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://learnmate.ai",
        "X-Title": "LearnMate AI"
    }
    payload = {"model": LLAMA_MODEL, "messages": messages, "max_tokens": max_tokens}
    try:
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=40)
        data = r.json()
        # Show full response if unexpected
        if "choices" not in data:
            return f"⚠️ Unexpected API response: {json.dumps(data)}"
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ API Error: {str(e)}"


def generate_quiz_llm(subject: str, level: str, topic: str = "") -> list:
    topic_hint = f"focused on '{topic}'" if topic else "covering core concepts"
    prompt = f"""Generate exactly 5 multiple choice questions for a {level} student studying {subject} {topic_hint}.

Return ONLY valid JSON — no explanation, no markdown, no code fences. Just raw JSON array:
[
  {{
    "question": "question text",
    "options": {{"A": "option text", "B": "option text", "C": "option text", "D": "option text"}},
    "answer": "A",
    "topic": "subtopic name",
    "explanation": "one sentence explaining why the answer is correct"
  }}
]"""
    response = call_llama([{"role": "user", "content": prompt}], max_tokens=1400)
    # If API error, surface it
    if response.startswith("⚠️"):
        st.error(response)
        return []
    try:
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            return json.loads(json_match.group())[:5]
        else:
            st.error(f"Could not parse quiz JSON. Raw response:\n\n{response[:500]}")
    except Exception as e:
        st.error(f"JSON parse error: {e}\n\nRaw response:\n{response[:500]}")
    return []


def get_explanation(level: str, topic: str, subject: str, context: str = "") -> str:
    ctx = f"\n\nStudent notes context:\n{context[:600]}" if context else ""
    msgs = [
        {"role": "system", "content": TUTOR_SYSTEM},
        {"role": "user", "content": f"Student Level: {level}\nSubject: {subject}\nTopic: {topic}{ctx}\n\nExplain this topic clearly, then give one practice question."}
    ]
    return call_llama(msgs)


def chat_with_tutor(history: list, user_msg: str, level: str, subject: str, notes: str = "") -> str:
    msgs = [{"role": "system", "content": TUTOR_SYSTEM + f"\n\nStudent: {level} level, studying {subject}."}]
    if notes:
        msgs.append({"role": "system", "content": f"Student's notes:\n{notes[:800]}"})
    for h in history[-10:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": user_msg})
    return call_llama(msgs, max_tokens=700)


def gemini_visualize(topic: str, subject: str) -> str:
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return "⚠️ Add your Gemini API key to enable visual explanations."
    payload = {"contents": [{"parts": [{"text": f"""Create a vivid visual explanation / mental diagram of '{topic}' in {subject}.

Describe it like you're drawing on a whiteboard for a student. Include:
🔷 Core Concept (one clear sentence)
📊 Diagram Description (describe the visual structure with arrows, labels, boxes)
🔗 How the parts connect
💡 The 'aha moment' — one memorable insight
🎯 Common mistakes students make

Use emojis, arrows (→, ↓, ⟷), and clear formatting. Make it vivid and memorable."""}]}]}
    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=30)
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"⚠️ Gemini Error: {str(e)}"


def summarize_notes(text: str, subject: str) -> str:
    prompt = f"Summarize the key concepts from these student notes about {subject}. List the main topics and important points:\n\n{text[:2000]}"
    return call_llama([{"role": "user", "content": prompt}], max_tokens=400)


# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
defaults = {
    "page": "home",
    "student_name": "",
    "subject": "Mathematics",
    "level": "Beginner",
    "quiz_questions": [],
    "quiz_answers": {},
    "quiz_submitted": False,
    "score": 0,
    "weak_topics": [],
    "score_history": [],
    "attempt_count": 0,
    "chat_history": [],
    "notes_context": "",
    "notes_summary": "",
    "current_explanation": "",
    "current_topic": "",
    "visual_explanation": "",
    "dark_mode": True,   # ← theme toggle
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────
# THEME VARIABLES
# ─────────────────────────────────────────────────────────────
D = st.session_state.dark_mode

# Backgrounds
BG_APP   = "#0d0d14"      if D else "#f4f2ff"
BG_SIDE  = "#0f0f1a"      if D else "#ffffff"
BG_CARD  = "#14141f"      if D else "#ffffff"
BG_CARD2 = "#111120"      if D else "#f8f7ff"
BG_INPUT = "#111120"      if D else "#ffffff"
BG_HERO  = "linear-gradient(135deg,#180c30 0%,#0f1628 55%,#0b1c1c 100%)" if D else "linear-gradient(135deg,#ede9fe 0%,#e0f2fe 100%)"
BG_AI    = "#0e0e1e"      if D else "#f5f3ff"
BG_VIS   = "linear-gradient(135deg,#091520,#0c1820)" if D else "linear-gradient(135deg,#ecfeff,#f0f9ff)"
BG_BUSER = "linear-gradient(135deg,#2e1a6e,#231554)" if D else "linear-gradient(135deg,#ede9fe,#ddd6fe)"
BG_BAI   = "#131323"      if D else "#f8f7ff"
BG_CHIP  = "#180e30"      if D else "#ede9fe"
BG_QWRAP = "#111120"      if D else "#f8f7ff"

# Borders
BR_CARD  = "#202030"      if D else "#e2deff"
BR_SIDE  = "#1e1e30"      if D else "#ede9fe"
BR_HERO  = "#2d1b5e"      if D else "#c4b5fd"
BR_AI    = "#1e1840"      if D else "#ddd6fe"
BR_VIS   = "#164e63"      if D else "#a5f3fc"
BR_INPUT = "#1e1e32"      if D else "#ddd6fe"
BR_QWRAP = "#1c1c30"      if D else "#e2deff"

# Text
TX_MAIN  = "#e4e0f4"      if D else "#1e1440"
TX_MUT   = "#7a7498"      if D else "#6d6490"
TX_DIM   = "#4a4862"      if D else "#a09abf"
TX_HERO  = "#ede8ff"      if D else "#1e1440"
TX_CARD  = "#d8d4f0"      if D else "#2d2060"
TX_AI    = "#c4c0e0"      if D else "#2d2060"
TX_VIS   = "#94d8ee"      if D else "#0e7490"
TX_BUSER = "#ddd4ff"      if D else "#2d1b6e"
TX_BAI   = "#c8c4e0"      if D else "#1e1440"
TX_CHIP  = "#c4b5fd"      if D else "#5b21b6"
TX_QNUM  = "#4a4862"      if D else "#a09abf"
TX_QTEXT = "#d8d4f0"      if D else "#1e1440"
TX_BRAND = "#b084fc"      if D else "#7c3aed"
TX_BSUB  = "#4a4862"      if D else "#a09abf"
TX_SEC   = "#4a4862"      if D else "#9090b8"

# Accents
AC_MAIN  = "#a78bfa"      if D else "#7c3aed"
AC_BTN1  = "#5b21b6"      if D else "#6d28d9"
AC_BTN2  = "#4c1d95"      if D else "#5b21b6"
AC_HOVER = "#6d28d9"      if D else "#7c3aed"
METRIC_V = "#b084fc"      if D else "#6d28d9"
METRIC_L = "#4a4862"      if D else "#8080a8"

TOGGLE_ICON = "🌙 Dark" if not D else "☀️ Light"

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG + CSS
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="LearnMate AI", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
    font-family: 'Sora', sans-serif !important;
    background: {BG_APP} !important;
    color: {TX_MAIN} !important;
}}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding: 1.5rem 2rem 3rem 2rem !important; max-width: 1080px !important; }}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{ background: {BG_SIDE} !important; border-right: 1px solid {BR_SIDE} !important; }}
[data-testid="stSidebar"] label {{ color: {TX_DIM} !important; font-size: 0.72rem !important; letter-spacing: 0.07em; text-transform: uppercase; }}

/* ── Brand ── */
.brand {{ font-size: 1.35rem; font-weight: 700; color: {TX_BRAND} !important; letter-spacing: -0.02em; }}
.brand-sub {{ font-size: 0.68rem; color: {TX_BSUB} !important; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 1.5rem; }}

/* ── Cards ── */
.card {{
    background: {BG_CARD};
    border: 1px solid {BR_CARD};
    border-radius: 14px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 0.9rem;
    transition: border-color 0.2s, transform 0.15s;
}}
.card:hover {{ border-color: #5b21b6; transform: translateY(-1px); }}
.card-purple {{
    background: {"linear-gradient(135deg,#1c0f38 0%,#13101e 100%)" if D else "linear-gradient(135deg,#ede9fe,#f5f3ff)"};
    border: 1px solid {"#4c1d95" if D else "#c4b5fd"};
    border-radius: 14px; padding: 1.3rem 1.5rem; margin-bottom: 0.9rem;
}}
.card-teal {{
    background: {"linear-gradient(135deg,#0a1e22,#0d1520)" if D else "linear-gradient(135deg,#ecfeff,#f0f9ff)"};
    border: 1px solid {"#164e63" if D else "#a5f3fc"};
    border-radius: 14px; padding: 1.3rem 1.5rem; margin-bottom: 0.9rem;
}}

/* ── Hero ── */
.hero {{
    background: {BG_HERO};
    border: 1px solid {BR_HERO};
    border-radius: 18px; padding: 2.2rem 2.2rem; margin-bottom: 1.5rem;
    position: relative; overflow: hidden;
}}
.hero::after {{
    content: ''; position: absolute; top: -60%; right: -10%;
    width: 380px; height: 380px;
    background: radial-gradient(circle, rgba(139,92,246,0.1) 0%, transparent 68%);
    pointer-events: none;
}}
.hero h1 {{ font-size: 2rem; font-weight: 700; color: {TX_HERO}; letter-spacing: -0.04em; margin: 0 0 0.5rem 0; line-height: 1.2; }}
.hero p {{ color: {TX_MUT}; font-size: 0.93rem; margin: 0; line-height: 1.65; }}
.accent {{ color: {AC_MAIN}; }}

/* ── Section label ── */
.sec {{ font-size: 0.67rem; letter-spacing: 0.12em; text-transform: uppercase; color: {TX_SEC}; margin-bottom: 0.7rem; font-weight: 600; }}

/* ── Badges ── */
.badge {{ display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.28rem 0.8rem; border-radius: 99px; font-size: 0.76rem; font-weight: 600; }}
.b-beg {{ background: {"#1e0a0a" if D else "#fef2f2"}; border: 1px solid {"#7f1d1d" if D else "#fca5a5"}; color: {"#fca5a5" if D else "#b91c1c"}; }}
.b-int {{ background: {"#1a140a" if D else "#fffbeb"}; border: 1px solid {"#78350f" if D else "#fcd34d"}; color: {"#fcd34d" if D else "#92400e"}; }}
.b-adv {{ background: {"#0a1a0e" if D else "#f0fdf4"}; border: 1px solid {"#14532d" if D else "#6ee7b7"}; color: {"#6ee7b7" if D else "#065f46"}; }}

/* ── Question cards ── */
.q-wrap {{ background: {BG_QWRAP}; border: 1px solid {BR_QWRAP}; border-radius: 12px; padding: 1.1rem 1.3rem; margin-bottom: 0.5rem; transition: border-color 0.15s; }}
.q-wrap:hover {{ border-color: #4c1d95; }}
.q-num {{ font-size: 0.65rem; color: {TX_QNUM}; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.35rem; }}
.q-text {{ font-size: 0.93rem; color: {TX_QTEXT}; font-weight: 500; }}

/* ── Buttons ── */
.stButton > button {{
    background: linear-gradient(135deg, {AC_BTN1}, {AC_BTN2}) !important;
    color: #ede8ff !important; border: none !important;
    border-radius: 10px !important; padding: 0.6rem 1.4rem !important;
    font-family: 'Sora', sans-serif !important; font-weight: 600 !important;
    font-size: 0.86rem !important; transition: all 0.2s !important;
}}
.stButton > button:hover {{
    background: linear-gradient(135deg, {AC_HOVER}, {AC_BTN1}) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 22px rgba(91,33,182,0.35) !important;
}}
.stButton > button:active {{ transform: translateY(0) !important; }}

/* ── Radio buttons — FIXED: show option text properly ── */
.stRadio > div[role="radiogroup"] {{ gap: 0.3rem !important; display: flex !important; flex-direction: column !important; }}
.stRadio > div[role="radiogroup"] > label {{
    display: flex !important; align-items: center !important;
    background: {BG_INPUT} !important; border: 1px solid {BR_INPUT} !important;
    border-radius: 9px !important; padding: 0.55rem 1rem !important;
    font-size: 0.88rem !important; color: {TX_MAIN} !important;
    cursor: pointer !important; transition: all 0.15s !important;
    width: 100% !important; margin: 0 !important;
}}
.stRadio > div[role="radiogroup"] > label:hover {{
    border-color: #6d28d9 !important; 
    color: {"#d4c8ff" if D else "#4c1d95"} !important;
    background: {"#1a1030" if D else "#f5f3ff"} !important;
}}
.stRadio > div[role="radiogroup"] > label > div {{
    color: {TX_MAIN} !important; font-size: 0.88rem !important;
}}
.stRadio > div[role="radiogroup"] > label > div > p {{
    color: {TX_MAIN} !important; margin: 0 !important; font-size: 0.88rem !important;
}}
/* Make sure radio circle + text are both visible */
.stRadio label span {{ color: {TX_MAIN} !important; }}
.stRadio label p {{ color: {TX_MAIN} !important; display: block !important; }}

/* ── Chat ── */
.bubble-user {{
    background: {BG_BUSER}; border: 1px solid {"#4c1d95" if D else "#c4b5fd"};
    border-radius: 14px 14px 4px 14px; padding: 0.85rem 1.1rem;
    margin: 0.5rem 0 0.5rem 18%; font-size: 0.88rem; color: {TX_BUSER}; line-height: 1.65;
}}
.bubble-ai {{
    background: {BG_BAI}; border: 1px solid {"#1c1c34" if D else "#e2deff"};
    border-radius: 14px 14px 14px 4px; padding: 0.85rem 1.1rem;
    margin: 0.5rem 18% 0.5rem 0; font-size: 0.88rem; color: {TX_BAI}; line-height: 1.75;
}}
.sender {{ font-size: 0.65rem; color: {TX_DIM}; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.3rem; }}

/* ── AI / Visual boxes ── */
.ai-box {{
    background: {BG_AI}; border: 1px solid {BR_AI};
    border-left: 3px solid #7c3aed; border-radius: 0 12px 12px 0;
    padding: 1.3rem 1.5rem; margin-top: 0.8rem;
    font-size: 0.9rem; line-height: 1.8; color: {TX_AI}; white-space: pre-wrap;
}}
.vis-box {{
    background: {BG_VIS}; border: 1px solid {BR_VIS};
    border-left: 3px solid #06b6d4; border-radius: 0 12px 12px 0;
    padding: 1.3rem 1.5rem; margin-top: 0.8rem;
    font-size: 0.88rem; line-height: 1.85; color: {TX_VIS}; white-space: pre-wrap;
}}

/* ── Metrics ── */
[data-testid="metric-container"] {{
    background: {BG_CARD2} !important; border: 1px solid {BR_CARD} !important;
    border-radius: 12px !important; padding: 1rem 1.2rem !important;
}}
[data-testid="stMetricValue"] {{ color: {METRIC_V} !important; font-family: 'Sora', sans-serif !important; font-weight: 700 !important; }}
[data-testid="stMetricLabel"] {{ color: {METRIC_L} !important; font-size: 0.72rem !important; }}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea textarea,
.stChatInput textarea {{
    background: {BG_INPUT} !important; border: 1px solid {BR_INPUT} !important;
    border-radius: 10px !important; color: {TX_MAIN} !important;
    font-family: 'Sora', sans-serif !important; font-size: 0.88rem !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus {{
    border-color: #6d28d9 !important;
    box-shadow: 0 0 0 3px rgba(109,40,217,0.18) !important;
}}
.stSelectbox > div > div {{
    background: {BG_INPUT} !important; border: 1px solid {BR_INPUT} !important;
    border-radius: 10px !important; color: {TX_MAIN} !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{ background: transparent !important; border-bottom: 1px solid {BR_CARD} !important; }}
.stTabs [data-baseweb="tab"] {{ background: transparent !important; color: {TX_DIM} !important; font-family: 'Sora', sans-serif !important; font-size: 0.84rem !important; }}
.stTabs [aria-selected="true"] {{ color: {AC_MAIN} !important; border-bottom: 2px solid #7c3aed !important; background: transparent !important; }}

/* ── Progress ── */
.stProgress > div > div > div {{ background: linear-gradient(90deg,#5b21b6,#c084fc) !important; border-radius: 99px !important; }}

/* ── File uploader ── */
[data-testid="stFileUploader"] section {{ background: {BG_INPUT} !important; border: 1px dashed {"#2a2a42" if D else "#c4b5fd"} !important; border-radius: 12px !important; }}

/* ── Divider ── */
hr {{ border-color: {BR_CARD} !important; margin: 1rem 0 !important; }}

/* ── Topic chip ── */
.chip {{ display: inline-flex; background: {BG_CHIP}; border: 1px solid {"#3b1f7a" if D else "#c4b5fd"}; border-radius: 6px; padding: 0.22rem 0.65rem; font-size: 0.76rem; color: {TX_CHIP}; margin: 0.15rem; }}

/* ── Score ── */
.score-num {{ font-size: 3.2rem; font-weight: 700; letter-spacing: -0.05em; line-height: 1; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-track {{ background: {BG_APP}; }}
::-webkit-scrollbar-thumb {{ background: {"#252540" if D else "#c4b5fd"}; border-radius: 4px; }}

/* ── Alert ── */
.stAlert {{ border-radius: 10px !important; }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand + theme toggle on same row
    top_l, top_r = st.columns([3, 2])
    with top_l:
        st.markdown('<div class="brand">🌱 LearnMate</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-sub">AI Study Companion</div>', unsafe_allow_html=True)
    with top_r:
        st.markdown("<div style='margin-top:0.6rem'></div>", unsafe_allow_html=True)
        if st.button(TOGGLE_ICON, key="theme_toggle", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    name_val = st.text_input("Your name", value=st.session_state.student_name, placeholder="e.g. Priya")
    if name_val != st.session_state.student_name:
        st.session_state.student_name = name_val

    subj_idx = SUBJECTS.index(st.session_state.subject) if st.session_state.subject in SUBJECTS else 0
    new_subj = st.selectbox("Subject", SUBJECTS, index=subj_idx)
    if new_subj != st.session_state.subject:
        st.session_state.subject = new_subj
        st.session_state.quiz_questions = []

    st.markdown("---")
    st.markdown('<div class="sec">Navigate</div>', unsafe_allow_html=True)
    nav_items = [("🏠", "Home", "home"), ("📝", "Quiz", "quiz"), ("💬", "Chat Tutor", "chat"), ("📄", "My Notes", "notes")]
    for icon, label, pg in nav_items:
        if st.button(f"{icon}  {label}", key=f"nav_{pg}", use_container_width=True):
            st.session_state.page = pg
            st.rerun()

    st.markdown("---")
    if st.session_state.score_history:
        st.markdown('<div class="sec">Your Stats</div>', unsafe_allow_html=True)
        best = max(st.session_state.score_history)
        avg = sum(st.session_state.score_history) / len(st.session_state.score_history)
        st.markdown(f"""
        <div style="font-size:0.82rem; color:#7a7498; line-height:2.2">
        🏆 Best: <strong style="color:#d4d0f0">{best}/5</strong><br>
        📊 Avg: <strong style="color:#d4d0f0">{avg:.1f}/5</strong><br>
        🔄 Quizzes: <strong style="color:#d4d0f0">{st.session_state.attempt_count}</strong>
        </div>""", unsafe_allow_html=True)

    if st.session_state.level:
        bmap = {"Beginner": "b-beg", "Intermediate": "b-int", "Advanced": "b-adv"}
        imap = {"Beginner": "🌱", "Intermediate": "⚡", "Advanced": "🔥"}
        lvl = st.session_state.level
        st.markdown(f'<div style="margin-top:0.8rem"><span class="badge {bmap.get(lvl)}">{imap.get(lvl)} {lvl}</span></div>', unsafe_allow_html=True)

    if st.session_state.notes_summary:
        st.markdown("---")
        st.markdown('<div class="sec">Notes Active ✓</div>', unsafe_allow_html=True)
        st.caption(st.session_state.notes_summary[:100] + "…")


# ─────────────────────────────────────────────────────────────
# PAGE: HOME
# ─────────────────────────────────────────────────────────────
if st.session_state.page == "home":
    greeting = f"Hey {st.session_state.student_name}! 👋" if st.session_state.student_name else "Hey there 👋"
    st.markdown(f"""
    <div class="hero">
        <h1>{greeting}<br><span class="accent">Ready to learn something?</span></h1>
        <p>Your personal AI tutor — diagnoses your level, explains concepts in your language, and adapts to you as you grow.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""<div class="card">
        <div style="font-size:1.7rem;margin-bottom:0.5rem">📝</div>
        <div style="font-weight:600;color:#d8d4f0;margin-bottom:0.4rem">Smart Quiz</div>
        <div style="font-size:0.8rem;color:#5a5870;line-height:1.65">AI writes 5 questions tailored to your subject. We find your gaps, then fix them right away.</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Take a Quiz →", key="h_quiz", use_container_width=True):
            st.session_state.page = "quiz"; st.rerun()

    with c2:
        st.markdown("""<div class="card">
        <div style="font-size:1.7rem;margin-bottom:0.5rem">💬</div>
        <div style="font-weight:600;color:#d8d4f0;margin-bottom:0.4rem">Chat Tutor</div>
        <div style="font-size:0.8rem;color:#5a5870;line-height:1.65">Ask anything. Get clear answers with analogies, examples, step-by-step breakdowns — not textbook walls.</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Open Chat →", key="h_chat", use_container_width=True):
            st.session_state.page = "chat"; st.rerun()

    with c3:
        st.markdown("""<div class="card">
        <div style="font-size:1.7rem;margin-bottom:0.5rem">📄</div>
        <div style="font-weight:600;color:#d8d4f0;margin-bottom:0.4rem">Upload Notes</div>
        <div style="font-size:0.8rem;color:#5a5870;line-height:1.65">Paste your notes or upload a text file. The tutor will reference them to give you personalised help.</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Upload Notes →", key="h_notes", use_container_width=True):
            st.session_state.page = "notes"; st.rerun()

    if st.session_state.score_history:
        st.markdown("---")
        st.markdown('<div class="sec">Your Progress</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Latest", f"{st.session_state.score}/5")
        with m2: st.metric("Best", f"{max(st.session_state.score_history)}/5")
        with m3: st.metric("Average", f"{sum(st.session_state.score_history)/len(st.session_state.score_history):.1f}/5")
        with m4: st.metric("Quizzes taken", st.session_state.attempt_count)
        if len(st.session_state.score_history) >= 2:
            st.markdown('<div class="sec" style="margin-top:1rem">Score trend</div>', unsafe_allow_html=True)
            st.line_chart({"Attempt": list(range(1, len(st.session_state.score_history)+1)), "Score": st.session_state.score_history},
                          x="Attempt", y="Score", height=180, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="sec">Quick Explain</div>', unsafe_allow_html=True)
    qc1, qc2 = st.columns([5, 1])
    with qc1:
        qt = st.text_input("Quick explain topic", placeholder=f"Type any topic in {st.session_state.subject}…  e.g. recursion, photosynthesis, supply & demand",
                           label_visibility="collapsed", key="quick_t")
    with qc2:
        qbtn = st.button("Explain 🔮", key="quick_btn", use_container_width=True)

    if qbtn and qt:
        with st.spinner("Thinking…"):
            exp = get_explanation(st.session_state.level or "Beginner", qt, st.session_state.subject, st.session_state.notes_context)
            st.session_state.current_explanation = exp
            st.session_state.current_topic = qt
            st.session_state.visual_explanation = ""

    if st.session_state.current_explanation:
        st.markdown(f'<div class="sec" style="margin-top:0.5rem">📖 {st.session_state.current_topic}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-box">{st.session_state.current_explanation}</div>', unsafe_allow_html=True)
        if st.button("🎨  Visualize with Gemini", key="h_vis"):
            with st.spinner("Gemini is building a mental diagram…"):
                st.session_state.visual_explanation = gemini_visualize(st.session_state.current_topic, st.session_state.subject)
        if st.session_state.visual_explanation:
            st.markdown('<div class="sec" style="margin-top:0.8rem">🎨 Visual Breakdown</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="vis-box">{st.session_state.visual_explanation}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# PAGE: QUIZ
# ─────────────────────────────────────────────────────────────
elif st.session_state.page == "quiz":
    st.markdown(f"""<div class="hero" style="padding:1.7rem 2rem">
    <h1 style="font-size:1.6rem">📝 Diagnostic Quiz</h1>
    <p>Subject: <span class="accent">{st.session_state.subject}</span> — AI generates 5 fresh questions every time</p>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.quiz_submitted:
        if not st.session_state.quiz_questions:
            # Quiz setup
            if not st.session_state.student_name:
                st.warning("👈 Enter your name in the sidebar first!")
            else:
                sc1, sc2 = st.columns([1, 2])
                with sc1:
                    lvl_pick = st.selectbox("Your comfort level", ["Beginner", "Intermediate", "Advanced"])
                with sc2:
                    thint = st.text_input("Focus topic (optional)", placeholder="e.g. arrays, limits, thermodynamics…")

                if st.button("🎲  Generate My Quiz", key="gen_btn"):
                    st.session_state.level = lvl_pick
                    with st.spinner(f"✍️  Writing 5 {lvl_pick.lower()} questions on {st.session_state.subject}…"):
                        qs = generate_quiz_llm(st.session_state.subject, lvl_pick, thint)
                    if qs:
                        st.session_state.quiz_questions = qs
                        st.session_state.quiz_answers = {}
                        st.rerun()
                    else:
                        st.error("Couldn't generate questions. Check your API key and try again.")
        else:
            questions = st.session_state.quiz_questions
            answered = sum(1 for i in range(5) if st.session_state.quiz_answers.get(i) is not None)
            st.progress(answered / 5)
            st.markdown(f'<div style="font-size:0.78rem;color:#4a4862;margin-bottom:1rem">{answered} of 5 answered</div>', unsafe_allow_html=True)

            for i, q in enumerate(questions):
                opts = q.get("options", {})
                st.markdown(f"""<div class="q-wrap">
                <div class="q-num">Q{i+1} &nbsp;·&nbsp; {q.get("topic","")}</div>
                <div class="q-text">{q["question"]}</div>
                </div>""", unsafe_allow_html=True)

                choice = st.radio(
                    label=f"q{i}", options=list(opts.keys()),
                    format_func=lambda k, o=opts: f"{k})   {o.get(k,'')}",
                    index=None, key=f"qz_{i}", label_visibility="collapsed"
                )
                if choice != st.session_state.quiz_answers.get(i):
                    st.session_state.quiz_answers[i] = choice
                st.markdown("")

            rc1, rc2 = st.columns([1, 4])
            with rc1:
                if st.button("✅  Submit", key="submit_q", use_container_width=True):
                    if any(st.session_state.quiz_answers.get(i) is None for i in range(5)):
                        st.warning("Answer all 5 questions first!")
                    else:
                        score = 0; weak = []
                        for i, q in enumerate(questions):
                            if st.session_state.quiz_answers.get(i) == q["answer"]:
                                score += 1
                            else:
                                weak.append(q.get("topic", f"Topic {i+1}"))
                        lvl = "Beginner" if score <= 2 else "Intermediate" if score == 3 else "Advanced"
                        st.session_state.score = score
                        st.session_state.level = lvl
                        st.session_state.weak_topics = weak or ["All topics — excellent!"]
                        st.session_state.attempt_count += 1
                        st.session_state.score_history.append(score)
                        st.session_state.quiz_submitted = True
                        st.rerun()
            with rc2:
                if st.button("🔁  Generate new questions", key="regen_q"):
                    st.session_state.quiz_questions = []; st.session_state.quiz_answers = {}; st.rerun()

    else:
        # ── RESULTS PAGE ──
        questions = st.session_state.quiz_questions
        score = st.session_state.score
        level = st.session_state.level
        weak = st.session_state.weak_topics

        bmap = {"Beginner": "b-beg", "Intermediate": "b-int", "Advanced": "b-adv"}
        imap = {"Beginner": "🌱", "Intermediate": "⚡", "Advanced": "🔥"}
        col = "#6ee7b7" if score >= 4 else "#fcd34d" if score == 3 else "#fca5a5"

        st.markdown(f"""<div class="hero">
        <div style="display:flex;align-items:center;gap:2.5rem;flex-wrap:wrap">
            <div>
                <div class="sec">Score</div>
                <div class="score-num" style="color:{col}">{score}<span style="font-size:1.4rem;color:#3a3858">/5</span></div>
                <div style="font-size:0.78rem;color:#5a5870;margin-top:0.2rem">{score*20}% correct</div>
            </div>
            <div>
                <div class="sec">Level Detected</div>
                <span class="badge {bmap.get(level)}">{imap.get(level)} {level}</span>
                <div style="margin-top:0.7rem;font-size:0.82rem;color:#7a7498">
                {"🎉 Outstanding! You've really got this." if score >= 4 else "💪 Solid work — almost there!" if score == 3 else "🔧 No worries — let's fix the gaps right now."}
                </div>
            </div>
        </div></div>""", unsafe_allow_html=True)

        # Answer review
        st.markdown('<div class="sec">Answer Review</div>', unsafe_allow_html=True)
        for i, q in enumerate(questions):
            ua = st.session_state.quiz_answers.get(i)
            correct = ua == q["answer"]
            opts = q.get("options", {})
            bg = "#0a1a0e" if correct else "#180808"
            bc = "#166534" if correct else "#7f1d1d"
            tc = "#6ee7b7" if correct else "#fca5a5"
            icon = "✅" if correct else "❌"
            exp = html_lib.escape(q.get("explanation", ""))
            correct_ans_text = html_lib.escape(opts.get(q["answer"], q["answer"]))
            user_ans_text    = html_lib.escape(opts.get(ua, ua or "Not answered"))
            q_text           = html_lib.escape(q["question"])
            q_topic          = html_lib.escape(q.get("topic", ""))

            st.markdown(f"""<div style="background:{bg};border:1px solid {bc};border-radius:10px;padding:0.9rem 1.2rem;margin-bottom:0.5rem">
            <div style="font-size:0.65rem;color:#4a4862;margin-bottom:0.3rem">Q{i+1} · {q_topic}</div>
            <div style="font-size:0.88rem;color:#d4d0f0;margin-bottom:0.4rem">{q_text}</div>
            <div style="font-size:0.82rem;color:{tc}">{icon} Your answer: {user_ans_text}</div>
            {"" if correct else f'<div style="font-size:0.82rem;color:#6ee7b7;margin-top:0.15rem">✔ Correct: {correct_ans_text}</div>'}
            {f'<div style="font-size:0.78rem;color:#5a5870;margin-top:0.4rem;font-style:italic">💡 {exp}</div>' if exp else ""}
            </div>""", unsafe_allow_html=True)

        # Weak topics + AI
        if weak and "All topics" not in weak[0]:
            st.markdown("---")
            st.markdown('<div class="sec">AI Tutoring — Improve These Topics</div>', unsafe_allow_html=True)
            st.markdown("".join([f'<span class="chip">{t}</span>' for t in weak]), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            sel = st.selectbox("Get explanation for:", weak, key="r_topic")
            ec1, ec2 = st.columns(2)
            with ec1:
                if st.button("📖  Explain This Topic", key="r_explain"):
                    with st.spinner(f"Explaining {sel}…"):
                        st.session_state.current_explanation = get_explanation(level, sel, st.session_state.subject, st.session_state.notes_context)
                        st.session_state.current_topic = sel
                        st.session_state.visual_explanation = ""
            with ec2:
                if st.button("🎨  Visualize with Gemini", key="r_vis"):
                    with st.spinner("Building mental diagram…"):
                        st.session_state.visual_explanation = gemini_visualize(sel, st.session_state.subject)

            if st.session_state.current_explanation and st.session_state.current_topic in weak:
                st.markdown(f'<div class="ai-box">{st.session_state.current_explanation}</div>', unsafe_allow_html=True)
            if st.session_state.visual_explanation:
                st.markdown('<div class="sec" style="margin-top:1rem">🎨 Visual Breakdown</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="vis-box">{st.session_state.visual_explanation}</div>', unsafe_allow_html=True)

        st.markdown("---")
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("🔄 Retake Same Quiz", use_container_width=True):
                st.session_state.quiz_submitted = False; st.session_state.quiz_answers = {}
                st.session_state.current_explanation = ""; st.session_state.visual_explanation = ""; st.rerun()
        with b2:
            if st.button("🎲 New Quiz", use_container_width=True):
                st.session_state.quiz_submitted = False; st.session_state.quiz_questions = []
                st.session_state.quiz_answers = {}; st.session_state.current_explanation = ""
                st.session_state.visual_explanation = ""; st.rerun()
        with b3:
            if st.button("💬 Ask Tutor", use_container_width=True):
                st.session_state.page = "chat"; st.rerun()


# ─────────────────────────────────────────────────────────────
# PAGE: CHAT
# ─────────────────────────────────────────────────────────────
elif st.session_state.page == "chat":
    st.markdown(f"""<div class="hero" style="padding:1.6rem 2rem">
    <h1 style="font-size:1.5rem">💬 Chat with your Tutor</h1>
    <p>Ask anything about <span class="accent">{st.session_state.subject}</span>. Your level: <span class="accent">{st.session_state.level or "not set yet"}</span></p>
    </div>""", unsafe_allow_html=True)

    if st.session_state.notes_context:
        st.markdown('<div style="font-size:0.76rem;color:#6ee7b7;margin-bottom:0.8rem">📄 Your notes are active — the tutor will reference them.</div>', unsafe_allow_html=True)

    # Display chat history
    if not st.session_state.chat_history:
        nm = st.session_state.student_name or "there"
        lvl = st.session_state.level or "Beginner"
        st.markdown(f"""<div class="bubble-ai">
        <div class="sender">🌱 LearnMate</div>
        Hey {nm}! I'm your AI tutor for <strong>{st.session_state.subject}</strong>.<br>
        I'll match your <strong>{lvl}</strong> level — clear, simple, no jargon unless you want it.<br><br>
        What would you like to understand today? Ask me anything. 🙂
        </div>""", unsafe_allow_html=True)

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="bubble-user"><div class="sender" style="color:#7b6ea8">You</div>{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            content = msg["content"].replace("\n", "<br>")
            st.markdown(f'<div class="bubble-ai"><div class="sender">🌱 LearnMate</div>{content}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Suggestion chips
    suggs = {
        "Data Structures & Algorithms": ["Explain recursion", "What's Big O notation?", "How does a hash table work?"],
        "Mathematics": ["Explain derivatives visually", "What is integration?", "How to solve quadratics?"],
        "Physics": ["Explain Newton's laws simply", "What is entropy?", "How does electricity work?"],
        "Chemistry": ["What are covalent bonds?", "Explain the periodic table", "What is a mole?"],
        "Biology": ["How does DNA replication work?", "Explain natural selection", "What is osmosis?"],
        "History": ["Why did WW1 start?", "What caused the fall of Rome?", "Explain colonialism"],
        "Literature": ["What's the difference between theme and plot?", "Explain narrative structure", "What is a metaphor?"],
        "Economics": ["Explain supply and demand", "What causes inflation?", "What is GDP?"],
    }
    chips = suggs.get(st.session_state.subject, ["Explain the basics", "Give me a real example", "Quiz me on this"])
    st.markdown('<div class="sec">Quick starters</div>', unsafe_allow_html=True)
    ccols = st.columns(len(chips))
    for ci, (chip, ccol) in enumerate(zip(chips, ccols)):
        with ccol:
            if st.button(chip, key=f"chip_{ci}", use_container_width=True):
                with st.spinner("Thinking…"):
                    reply = chat_with_tutor(st.session_state.chat_history, chip,
                                            st.session_state.level or "Beginner",
                                            st.session_state.subject, st.session_state.notes_context)
                st.session_state.chat_history += [{"role": "user", "content": chip}, {"role": "assistant", "content": reply}]
                st.rerun()

    user_msg = st.chat_input(f"Ask about {st.session_state.subject}…")
    if user_msg:
        with st.spinner("🤔 Thinking…"):
            reply = chat_with_tutor(st.session_state.chat_history, user_msg,
                                    st.session_state.level or "Beginner",
                                    st.session_state.subject, st.session_state.notes_context)
        st.session_state.chat_history += [{"role": "user", "content": user_msg}, {"role": "assistant", "content": reply}]
        st.rerun()

    if st.session_state.chat_history:
        if st.button("🗑  Clear chat", key="clr_chat"):
            st.session_state.chat_history = []; st.rerun()


# ─────────────────────────────────────────────────────────────
# PAGE: NOTES
# ─────────────────────────────────────────────────────────────
elif st.session_state.page == "notes":
    st.markdown("""<div class="hero" style="padding:1.6rem 2rem">
    <h1 style="font-size:1.5rem">📄 Your Notes</h1>
    <p>Paste text, upload a .txt file, or type anything. The tutor will use your notes to personalise every explanation and quiz question.</p>
    </div>""", unsafe_allow_html=True)

    t1, t2 = st.tabs(["📋 Paste Text", "📁 Upload .txt File"])

    with t1:
        st.markdown('<div class="sec">Paste your notes</div>', unsafe_allow_html=True)
        pasted = st.text_area("Paste notes", placeholder="Paste your class notes, textbook text, any study material…",
                              height=240, label_visibility="collapsed", key="paste_area")
        if st.button("✨  Process Notes", key="proc_paste") and pasted.strip():
            with st.spinner("Reading your notes…"):
                summ = summarize_notes(pasted, st.session_state.subject)
            st.session_state.notes_context = pasted
            st.session_state.notes_summary = summ
            st.success("✅ Notes loaded! Your tutor will now reference these.")
            st.markdown('<div class="sec" style="margin-top:1rem">Summary</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ai-box">{summ}</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="sec">Upload a plain text file</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Upload file", type=["txt", "md"], label_visibility="collapsed", key="file_up")
        if uploaded:
            content = uploaded.read().decode("utf-8", errors="ignore")
            st.markdown(f'<div style="font-size:0.78rem;color:#4a4862;margin-bottom:0.5rem">📄 {uploaded.name} — {len(content):,} characters</div>', unsafe_allow_html=True)
            with st.expander("Preview first 800 chars"):
                st.code(content[:800] + ("…" if len(content) > 800 else ""), language=None)
            if st.button("✨  Process This File", key="proc_file"):
                with st.spinner("Analysing…"):
                    summ = summarize_notes(content, st.session_state.subject)
                st.session_state.notes_context = content
                st.session_state.notes_summary = summ
                st.success("✅ File loaded into your tutor!")
                st.markdown(f'<div class="ai-box">{summ}</div>', unsafe_allow_html=True)

    if st.session_state.notes_context:
        st.markdown("---")
        st.markdown('<div class="sec">Active Notes</div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="card-purple">
        <div style="font-size:0.76rem;color:#a78bfa;margin-bottom:0.4rem">✅ Notes Active</div>
        <div style="font-size:0.82rem;color:#7a7498;line-height:1.6">{st.session_state.notes_summary[:280]}…</div>
        </div>""", unsafe_allow_html=True)

        nc1, nc2, nc3 = st.columns(3)
        with nc1:
            if st.button("🗑  Clear Notes", key="clr_notes"):
                st.session_state.notes_context = ""; st.session_state.notes_summary = ""; st.rerun()
        with nc2:
            if st.button("📝  Quiz Me on My Notes", key="n_quiz"):
                st.session_state.quiz_questions = []; st.session_state.page = "quiz"; st.rerun()
        with nc3:
            if st.button("💬  Chat About My Notes", key="n_chat"):
                st.session_state.page = "chat"; st.rerun()

        st.markdown("---")
        st.markdown('<div class="sec">Ask something about your notes</div>', unsafe_allow_html=True)
        nq1, nq2 = st.columns([5, 1])
        with nq1:
            nq = st.text_input("Ask about notes", placeholder="e.g. What are the key points? What should I memorise?",
                               label_visibility="collapsed", key="n_ask")
        with nq2:
            nask = st.button("Ask →", key="n_ask_btn", use_container_width=True)
        if nask and nq:
            with st.spinner("Reading your notes…"):
                reply = chat_with_tutor([], nq, st.session_state.level or "Beginner",
                                        st.session_state.subject, st.session_state.notes_context)
            st.markdown(f'<div class="ai-box">{reply}</div>', unsafe_allow_html=True)
