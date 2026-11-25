from datetime import date, datetime, timedelta
import html
import io
import collections
import random
import re
import sqlite3
import subprocess
import sys
import json
import uuid
import hashlib
import secrets
from pathlib import Path
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from agrobridge import render_agrobridge
import streamlit as st

import streamlit as st

# LifeBridgeAI — local-first educational app.
# AI integrations are intentionally disabled; no API key is read or transmitted.

APP_DIR = Path(__file__).resolve().parent

# Secure Gemini configuration
load_dotenv(APP_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    try:
        GEMINI_API_KEY = str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-3.5-flash-lite"

gemini_client = (
    genai.Client(api_key=GEMINI_API_KEY)
    if GEMINI_API_KEY
    else None
)

DATA_DIR = APP_DIR / "lifebridge_data"
DATA_DIR = APP_DIR / "lifebridge_data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "lifebridge.db"

st.set_page_config(
    page_title="LifeBridge AI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------- GEMINI AI ENGINE ----------------------------

def gemini_generate(prompt, temperature=0.3, image_bytes=None, mime_type='image/jpeg', max_output_tokens=6000):
    """Generate text securely through the server-side Gemini client."""
    if gemini_client is None:
        raise RuntimeError("Gemini API key not found. Check your .env file.")

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt if image_bytes is None else [prompt, types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
        config={
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        },
    )

    result = (response.text or "").strip()
    if not result:
        raise RuntimeError("Gemini returned an empty response. Please try again.")

    return result


def ai_make_note_pack(topic, chapter, style):
    """Create structured revision notes grounded in supplied study material."""
    prompt = f"""
You are LifeBridgeAI, a careful school learning assistant.

Create {style} revision notes for:
Topic: {topic}

Use ONLY the supplied material as the factual source.
Do not invent facts, definitions, formulas, examples or measurements.
If information is missing, clearly mention that the student should
check their textbook or ask their teacher.

Use clear headings, bullet points, important definitions,
formulas where supplied, and active-recall questions.

Study material:
{chapter[:40000]}
"""
    return gemini_generate(prompt), detect_subject(topic)


def ai_topic_questions(topic, limit=10):
    """Generate topic-based MCQs with answer keys."""
    prompt = f"""
You are a school examination question setter.

Create exactly {limit} multiple-choice questions about:
{topic}

Suitable for Class 10 students.
Use accurate, syllabus-appropriate information.
Each question must have four distinct options and one correct answer.
Avoid ambiguous questions and repeated questions.

Return ONLY valid JSON in this format:
[
  {{
    "question": "Question text",
    "options": ["A", "B", "C", "D"],
    "answer": "Correct option text",
    "explanation": "Short explanation"
  }}
]
"""
    return parse_gemini_questions(prompt, limit)


def ai_passage_questions(passage, limit=10):
    """Generate questions using only the supplied passage."""
    prompt = f"""
You are a careful school examination question setter.

Create exactly {limit} MCQs from the supplied study material.
Questions and answers must be supported by the passage.
Do not introduce outside facts.
Each question must have four distinct options and one correct answer.

Return ONLY valid JSON:
[
  {{
    "question": "Question text",
    "options": ["A", "B", "C", "D"],
    "answer": "Correct option text",
    "explanation": "Explanation supported by the passage"
  }}
]

Study material:
{passage[:40000]}
"""
    return parse_gemini_questions(prompt, limit)


def parse_gemini_questions(prompt, limit):
    """Validate AI-generated questions before showing them to students."""
    raw = gemini_generate(prompt, temperature=0.2)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
        data = json.loads(cleaned)

    if not isinstance(data, list):
        raise ValueError("Gemini returned an invalid question format.")

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue

        question = item.get("question")
        options = item.get("options")
        answer = item.get("answer")
        explanation = item.get("explanation", "")

        if not isinstance(question, str) or not question.strip():
            continue
        if not isinstance(options, list) or len(options) != 4:
            continue
        if not all(isinstance(option, str) and option.strip() for option in options):
            continue
        if len({option.strip().casefold() for option in options}) != 4:
            continue
        if not isinstance(answer, str) or answer.strip() not in options:
            continue

        questions.append({
            "question": question.strip(),
            "options": options,
            "answer": answer.strip(),
            "explanation": explanation if isinstance(explanation, str) else "",
        })

        if len(questions) >= limit:
            break

    if len(questions) < 3:
        raise ValueError("Gemini did not produce enough valid questions. Please try again.")

    return questions

def generate_quiz_questions(source, limit=10, from_topic=False):
    try:
        if from_topic:
            questions = ai_topic_questions(source, limit)
        else:
            questions = ai_passage_questions(source, limit)
        st.success("Questions generated with Gemini.")
        return questions
    except Exception as ai_error:
        st.warning(f"Gemini unavailable; using offline quiz generation instead: {ai_error}")
        if from_topic:
            return topic_questions(source, limit)
        return passage_questions(source, limit)


# ---------------------------- DATABASE ----------------------------

def db():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            grade TEXT NOT NULL DEFAULT 'Class 10',
            school TEXT DEFAULT '',
            language TEXT NOT NULL DEFAULT 'English',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            subject TEXT DEFAULT 'General',
            due_date TEXT DEFAULT '',
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            subject TEXT DEFAULT 'General',
            body TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            attempted_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            studied_on TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS agro_assessments (
            assessment_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT 'Plant Assessment',
            crop TEXT DEFAULT '',
            symptoms_json TEXT NOT NULL DEFAULT '[]',
            details TEXT DEFAULT '',
            report TEXT NOT NULL,
            image_data BLOB,
            image_mime TEXT DEFAULT 'image/jpeg',
            chat_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS accounts (
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            student_id TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id)
                ON DELETE CASCADE
        );
        """)
        con.commit()


def query_all(sql, params=()):
    with db() as con:
        return con.execute(sql, params).fetchall()


def execute(sql, params=()):
    with db() as con:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid


init_db()

# ---------------------------- STYLE ----------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root{--sage:#718C78;--sage-dark:#506B57;--paper:#FAFBF9;--ink:#26332B;--muted:#748078;--line:#E5EAE5}
.stApp{background:var(--paper);color:var(--ink);font-family:'DM Sans',sans-serif}
.block-container{max-width:1180px;padding-top:1.7rem;padding-bottom:3rem}
h1,h2,h3{font-family:Manrope,sans-serif!important;color:var(--ink)!important;letter-spacing:-.5px}
[data-testid="stSidebar"]{background:#F7F9F7;border-right:1px solid var(--line)}\n[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border:1px solid var(--line);border-radius:15px;padding:10px;margin:8px 0}\n
[data-testid="stSidebar"] *{color:var(--ink)}
.stButton>button,.stFormSubmitButton>button{border-radius:10px;border:1px solid var(--sage);background:var(--sage);color:white;font-weight:650;min-height:2.55rem}
.stButton>button:hover,.stFormSubmitButton>button:hover{background:var(--sage-dark);border-color:var(--sage-dark);color:white}
/* Sidebar navigation: quiet GPT-inspired list with a soft active state. */
[data-testid="stSidebar"] [data-testid="stButton"]>button{
  width:100%;min-height:2.45rem;justify-content:flex-start;text-align:left;
  padding:.45rem .75rem;border:1px solid transparent;border-radius:10px;
  background:transparent;color:#4D5B51;font-weight:500;box-shadow:none;
}
[data-testid="stSidebar"] [data-testid="stButton"]>button:hover{
  background:#EDF2ED;border-color:#EDF2ED;color:#26332B;
}
[data-testid="stSidebar"] [data-testid="stButton"]>button[kind="primary"]{
  background:#E7EEE7;border-color:#E7EEE7;color:#26332B;font-weight:650;
}
[data-testid="stSidebar"] [data-testid="stButton"]>button[kind="primary"]:hover{
  background:#E1EAE1;border-color:#E1EAE1;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{
  margin-bottom:.35rem;
}
.stFormSubmitButton>button{border-radius:10px;border:1px solid var(--sage);background:var(--sage);color:white;font-weight:650;min-height:2.55rem}
.stFormSubmitButton>button:hover{background:var(--sage-dark);border-color:var(--sage-dark);color:white}
.stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"],.stNumberInput input{border-radius:10px!important;border-color:#DCE4DC!important}
.lb-card{background:white;border:1px solid var(--line);border-radius:15px;padding:18px 20px;margin:8px 0}
.lb-muted{color:var(--muted);font-size:.9rem}
.lb-kicker{font-size:.75rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--sage-dark);font-weight:700}
.lb-hero{background:#EEF3EE;border:1px solid #E0E8E0;border-radius:20px;padding:26px 28px;margin:8px 0 22px}
.lb-hero h1{font-size:clamp(2rem,4vw,3.1rem);margin:.35rem 0}
.lb-stat{background:white;border:1px solid var(--line);border-radius:13px;padding:15px}
.lb-stat small{color:var(--muted)}
.lb-stat strong{display:block;font-size:1.65rem;color:var(--ink);margin-top:4px}
hr{border-color:var(--line)}
footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ---------------------------- SESSION / HELPERS ----------------------------

def esc(value):
    return html.escape(str(value or ""))


def now_text():
    return datetime.now().isoformat(timespec="seconds")


def current_student():
    sid = st.session_state.get("student_id")
    if not sid:
        return None
    rows = query_all("SELECT * FROM students WHERE student_id=?", (sid,))
    return rows[0] if rows else None


def create_student(name, grade, school, language):
    sid = "LB-" + uuid.uuid4().hex[:8].upper()
    execute(
        "INSERT INTO students(student_id,name,grade,school,language,created_at) VALUES(?,?,?,?,?,?)",
        (sid, name.strip(), grade, school.strip(), language, now_text()),
    )
    st.session_state.student_id = sid
    st.session_state.page = "Dashboard"


def ensure_page():
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"



def password_digest(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        310000,
    ).hex()


def create_account(name, grade, school, language, username, password):
    sid = "LB-" + uuid.uuid4().hex[:8].upper()
    salt = secrets.token_hex(16)
    password_hash = password_digest(password, salt)

    with db() as con:
        con.execute(
            """INSERT INTO students
            (student_id,name,grade,school,language,created_at)
            VALUES(?,?,?,?,?,?)""",
            (sid, name.strip(), grade, school.strip(),
             language, now_text()),
        )
        con.execute(
            """INSERT INTO accounts
            (username,student_id,password_salt,password_hash,created_at)
            VALUES(?,?,?,?,?)""",
            (username.strip(), sid, salt, password_hash, now_text()),
        )
        con.commit()

    st.session_state.student_id = sid
    st.session_state.page = "Dashboard"


def login_account(username, password):
    rows = query_all(
        """SELECT student_id,password_salt,password_hash
        FROM accounts WHERE username=? COLLATE NOCASE""",
        (username.strip(),),
    )

    if not rows:
        return False

    account = rows[0]
    attempted_hash = password_digest(password, account["password_salt"])

    if not secrets.compare_digest(
        attempted_hash, account["password_hash"]
    ):
        return False

    st.session_state.student_id = account["student_id"]
    st.session_state.page = "Dashboard"
    return True


ensure_page()
student = current_student()

# Require authentication before showing student data or app pages.
if not student:
    st.markdown("""
    <div class="lb-hero">
      <div class="lb-kicker">Your personal learning space</div>
      <h1>Welcome to LifeBridgeAI</h1>
      <div class="lb-muted">
        Sign in to continue learning, or create an account to get started.
      </div>
    </div>
    """, unsafe_allow_html=True)

    login_tab, register_tab = st.tabs(["Log in", "Create account"])

    with login_tab:
        with st.form("account_login_form"):
            login_username = st.text_input("Username")
            login_password = st.text_input(
                "Password", type="password"
            )
            login_submit = st.form_submit_button(
                "Log in", use_container_width=True
            )

        if login_submit:
            if not login_username.strip() or not login_password:
                st.error("Enter your username and password.")
            elif login_account(login_username, login_password):
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with register_tab:
        with st.form("account_register_form"):
            new_name = st.text_input("Student name")
            new_username = st.text_input("Choose a username")
            new_password = st.text_input(
                "Create password", type="password"
            )
            confirm_password = st.text_input(
                "Confirm password", type="password"
            )
            new_grade = st.selectbox(
                "Class / grade",
                ["Class 8", "Class 9", "Class 10",
                 "Class 11", "Class 12", "Other"],
                index=2,
            )
            new_school = st.text_input("School (optional)")
            new_language = st.selectbox(
                "Preferred language", ["English", "Hindi", "Punjabi"]
            )
            register_submit = st.form_submit_button(
                "Create my account", use_container_width=True
            )

        if register_submit:
            username = new_username.strip()

            if not new_name.strip():
                st.error("Enter your name.")
            elif not re.fullmatch(r"[A-Za-z0-9_.-]{3,24}", username):
                st.error(
                    "Username must be 3–24 characters using letters, "
                    "numbers, dots, underscores or hyphens."
                )
            elif len(new_password) < 8:
                st.error("Password must contain at least 8 characters.")
            elif new_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    create_account(
                        new_name, new_grade, new_school, new_language,
                        username, new_password
                    )
                    st.success("Account created successfully.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error(
                        "That username is already taken. Choose another."
                    )

    st.stop()


# ---------------------------- SIDEBAR ----------------------------

def sidebar_link(label, page, icon_name):
    current = st.session_state.get("page", "Dashboard")
    selected = current == page
    if st.button(
        label,
        key=f"sidebar_nav_{page.lower().replace(' ', '_')}",
        type="primary" if selected else "secondary",
        icon=f":material/{icon_name}:",
        use_container_width=True,
    ):
        st.session_state.page = page
        st.rerun()


with st.sidebar:
    st.image(str(APP_DIR / "lifebridgeai_logo.png"), width=190)
    st.caption("Your learning space")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    sidebar_link("Dashboard", "Dashboard", "space_dashboard")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    sidebar_link("Learning Studio", "Learning Studio", "school")

    st.markdown("<div style='height:14px'></div><div style='font-size:.68rem;font-weight:700;letter-spacing:1.1px;color:#879188;padding:0 10px 7px'>AGROBRIDGE</div>", unsafe_allow_html=True)
    sidebar_link("AgroBridge", "AgroBridge", "eco")

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    sidebar_link("Merycle Chatbot", "Merycle Chatbot", "chat")
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    st.divider()
    sidebar_link("My Profile", "My Profile", "account_circle")
    if student:
        st.markdown(f"<div style='padding:10px 9px 2px;font-weight:650'>{esc(student['name'])}</div>", unsafe_allow_html=True)
        st.caption(f"{student['student_id']} · {esc(student['grade'])}")
    else:
        st.caption("Create a learner profile to save your work.")
    st.caption("Local-first · AI integration paused")

    if st.button("Log out", key="account_logout",
                 use_container_width=True):
        st.session_state.pop("student_id", None)
        st.rerun()



def require_student():
    if student:
        return True
    st.warning("Create your learner profile first. Your notes, tasks and scores will then be saved on this device.")
    return False


def stat_card(label, value, suffix=""):
    st.markdown(
        f'<div class="lb-stat"><small>{esc(label)}</small><strong>{esc(value)}{esc(suffix)}</strong></div>',
        unsafe_allow_html=True,
    )


def detect_subject(topic):
    t = topic.lower()
    groups = {
        "Chemistry": ["chemical", "chemistry", "atom", "bond", "reaction", "acid", "base", "element", "periodic"],
        "Physics": ["physics", "motion", "force", "energy", "gravity", "electric", "current", "wave", "light"],
        "Mathematics": ["math", "algebra", "equation", "quadratic", "geometry", "trigonometry", "probability"],
        "Biology": ["biology", "cell", "photosynthesis", "respiration", "plant", "animal", "genetics", "ecosystem"],
        "Computer Science": ["python", "programming", "computer", "algorithm", "database", "coding", "network"],
        "History": ["history", "revolution", "empire", "war", "independence", "colonial", "ancient", "mughal"],
    }
    for subject, words in groups.items():
        if any(word in t for word in words):
            return subject
    return "General"


def make_note_pack(topic, chapter, style):
    """Create evidence-based revision notes from supplied text only."""
    subject = detect_subject(topic)
    raw = (chapter or "").replace("\r", "\n")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    sentences = [x.strip() for x in re.split(r"(?<=[.!?।])\s+", re.sub(r"\s+", " ", raw)) if len(x.strip()) > 18]
    limit = 40 if style == "Detailed" else 20 if style == "Exam-focused" else 10
    lines = [f"# {topic} — Revision Notes", "", f"**Subject:** {subject}", f"**Style:** {style}", "",
             "> Built from the material you supplied. This tool organises information; it does not verify facts or add outside facts.", ""]
    if not raw:
        lines += ["## Study outline", "", f"- Define {topic} using your textbook.", "- List the main concepts and explain each one.",
                  "- Add textbook examples, diagrams, formulas and units.", "- Write one real-world application."]
    else:
        # A short extractive overview: use the opening sentences, not invented content.
        lines += ["## Quick overview", ""]
        lines += ["- " + x for x in sentences[:2]] if sentences else ["- Review the key points below."]
        # Preserve clear headings and bullet-style source lines where possible.
        headings, equations, definition_lines = [], [], []
        for line in raw.splitlines():
            item = line.strip().strip("•*- ")
            if not item:
                continue
            if len(item) < 90 and (item.endswith(":") or (item.isupper() and len(item.split()) <= 9)):
                headings.append(item.rstrip(":"))
            if len(item) < 180 and any(sym in item for sym in ["=", "→", "⇌", "↔", "≠", "≤", "≥"]):
                equations.append(item)
            if re.search(r"\b(is defined as|refers to|means|is the process of|are called)\b", item, re.I):
                definition_lines.append(item)
        if headings:
            lines += ["", "## Headings detected", ""] + [f"- {h}" for h in dict.fromkeys(headings)][:15]
        if definition_lines:
            lines += ["", "## Definitions and explanations", ""] + [f"- {x}" for x in dict.fromkeys(definition_lines)][:12]
        lines += ["", "## Key points", ""]
        if sentences:
            lines += [f"- {x}" for x in sentences[:limit]]
        else:
            lines += [f"- {x}" for x in paragraphs[:limit]]
        if equations:
            lines += ["", "## Formulas, symbols and processes", ""] + [f"- `{x}`" for x in dict.fromkeys(equations)][:20]
        # Extract likely subject terms without pretending they are a definitive glossary.
        words = re.findall(r"\b[A-Za-z][A-Za-z-]{4,}\b", raw.lower())
        stop = set("about above after again against also among another because before being between could during each from further have having into its more most other over same should some such than that their them then there these they this those through under until very were what when where which while with would your their using used into".split())
        counts = collections.Counter(w for w in words if w not in stop)
        key_terms = [w for w, _ in counts.most_common(8)]
        if key_terms:
            lines += ["", "## Repeated key terms", "", "- " + ", ".join(key_terms)]
    lines += ["", "## Active recall", "", f"1. Explain {topic} in your own words.",
              "2. Which three ideas are most important?", "3. Explain one definition or process without looking.",
              "4. Which formula, example or diagram should you revise?", "", "## My own additions", "",
              "- Example from class/textbook:", "- Diagram to practise:", "- Doubt to ask my teacher:"]
    return "\n".join(lines), subject



def passage_questions(passage, limit=10):
    """Build answerable multiple-choice questions by masking terms in supplied text."""
    clean = re.sub(r"\s+", " ", (passage or "")).strip()
    sentences = [x.strip(" \t-•") for x in re.split(r"(?<=[.!?।])\s+|\n+", clean) if len(x.strip()) >= 35]
    stop = set("about above after again also among and are because been before being between both but can could does each from have into its more most other our should some such than that the their them then there these they this those through was were what when where which while with would your using used".split())
    candidates = []
    for sentence in sentences:
        words = re.findall(r"[A-Za-z][A-Za-z-]{3,}|[0-9]+(?:\.[0-9]+)?", sentence)
        useful = [w for w in words if w.lower() not in stop and len(w) >= 4]
        if useful:
            # Prefer a meaningful term from the middle/end rather than repeatedly blanking the first word.
            answer = max(useful, key=lambda w: (len(w), w.lower() not in {"which", "when", "where", "because"}))
            if answer.lower() not in stop:
                candidates.append((sentence, answer))
    # Build distractors from other terms in the supplied passage.
    vocab = []
    for sentence in sentences:
        for word in re.findall(r"[A-Za-z][A-Za-z-]{3,}|[0-9]+(?:\.[0-9]+)?", sentence):
            if word.lower() not in stop and word.lower() not in {v.lower() for v in vocab}:
                vocab.append(word)
    questions, seen = [], set()
    for sentence, answer in candidates:
        if answer.lower() in seen:
            continue
        seen.add(answer.lower())
        distractors = [w for w in vocab if w.lower() != answer.lower() and w.lower() not in sentence.lower()]
        # Prefer similar-length terms to avoid obvious answer cues.
        distractors.sort(key=lambda w: abs(len(w) - len(answer)))
        distractors = distractors[:3]
        if len(distractors) < 3:
            continue
        options = [answer] + distractors
        # Deterministic shuffle per question keeps correct positions varied.
        random.Random(answer.lower() + sentence[:12]).shuffle(options)
        masked = re.sub(r"\b" + re.escape(answer) + r"\b", "________", sentence, count=1, flags=re.I)
        questions.append({
            "question": "According to the supplied material, complete the statement:\n\n" + masked,
            "options": options, "answer": answer,
            "explanation": "The supplied text states: " + sentence
        })
        if len(questions) >= limit:
            break
    return questions


def topic_questions(topic, limit=10):
    """Offline starter bank for selected common school topics; no unsupported claims for unknown topics."""
    key = re.sub(r"[^a-z0-9 ]", "", (topic or "").lower()).strip()
    banks = {
        "photosynthesis": [
            ("Which green pigment absorbs light energy for photosynthesis?", ["Chlorophyll", "Haemoglobin", "Melanin", "Keratin"], "Chlorophyll absorbs light energy in plant cells."),
            ("Which gas is taken in by plants during photosynthesis?", ["Carbon dioxide", "Oxygen", "Nitrogen", "Hydrogen"], "Plants use carbon dioxide as a raw material."),
            ("Which gas is released during photosynthesis?", ["Oxygen", "Carbon dioxide", "Nitrogen", "Methane"], "Oxygen is released during the process."),
            ("In which cell structure does photosynthesis mainly occur?", ["Chloroplast", "Mitochondrion", "Nucleus", "Ribosome"], "Chloroplasts contain chlorophyll and are the main site."),
            ("Which two substances are raw materials for photosynthesis?", ["Water and carbon dioxide", "Oxygen and glucose", "Protein and oxygen", "Nitrogen and glucose"], "Water and carbon dioxide are used to make glucose."),
        ],
        "solar system": [
            ("Which star is at the centre of our solar system?", ["The Sun", "Sirius", "Polaris", "Proxima Centauri"], "The Sun is the star at the centre of our solar system."),
            ("Which planet is known for its prominent ring system?", ["Saturn", "Mercury", "Mars", "Venus"], "Saturn has the most prominent visible ring system."),
            ("Which planet is closest to the Sun?", ["Mercury", "Venus", "Earth", "Mars"], "Mercury is the innermost planet."),
            ("Which planet is the largest in our solar system?", ["Jupiter", "Saturn", "Neptune", "Earth"], "Jupiter is the largest planet."),
            ("What keeps planets in orbit around the Sun?", ["Gravity", "Sound", "Magnetism alone", "Friction"], "The Sun's gravitational attraction governs planetary orbits."),
        ],
        "water cycle": [
            ("What is the change from liquid water to water vapour called?", ["Evaporation", "Condensation", "Precipitation", "Collection"], "Evaporation changes liquid water into vapour."),
            ("What happens when water vapour cools and forms tiny droplets?", ["Condensation", "Evaporation", "Infiltration", "Transpiration"], "Condensation forms liquid droplets from water vapour."),
            ("What is water falling from clouds called?", ["Precipitation", "Collection", "Evaporation", "Melting"], "Rain, snow and hail are forms of precipitation."),
            ("Which energy source drives much of the water cycle?", ["The Sun", "The Moon", "Earth's core", "Ocean tides alone"], "Solar energy drives evaporation."),
            ("What is the process by which plants release water vapour?", ["Transpiration", "Condensation", "Freezing", "Precipitation"], "Plants release water vapour through transpiration."),
        ],
        "cell biology": [
            ("What is commonly called the basic structural and functional unit of life?", ["Cell", "Tissue", "Organ", "Organ system"], "The cell is the basic unit of life."),
            ("Which cell structure contains most of the genetic material in a typical plant or animal cell?", ["Nucleus", "Cell wall", "Vacuole", "Cytoplasm"], "The nucleus contains most of the cell's genetic material."),
            ("Which structure controls what enters and leaves a cell?", ["Cell membrane", "Ribosome", "Nucleolus", "Chromosome"], "The cell membrane regulates movement into and out of the cell."),
            ("Which organelle is a major site of aerobic respiration?", ["Mitochondrion", "Chloroplast", "Golgi apparatus", "Vacuole"], "Mitochondria are a major site of aerobic respiration."),
            ("Which structures make proteins in cells?", ["Ribosomes", "Lysosomes", "Vacuoles", "Centrioles"], "Ribosomes are the sites of protein synthesis."),
        ],
        "python": [
            ("Which Python keyword defines a function?", ["def", "class", "return", "import"], "The def keyword begins a function definition."),
            ("Which Python data type stores an ordered, changeable collection?", ["list", "tuple", "str", "bool"], "Lists are ordered and mutable collections."),
            ("Which symbol begins a single-line comment in Python?", ["#", "//", "<!--", "**"], "Python uses # to begin a single-line comment."),
            ("Which built-in function displays output in Python?", ["print()", "input()", "len()", "type()"], "print() writes output to the console."),
            ("What does len() return for a sequence?", ["Number of items", "Memory address", "Data type", "Last item"], "len() returns the number of items in a sequence."),
        ],
    }
    selected = banks.get(key)
    if not selected:
        # Accept common aliases without pretending the app knows every possible subject.
        aliases = {"photosynthesis": "photosynthesis", "solar system": "solar system", "water cycle": "water cycle", "cell": "cell biology", "cells": "cell biology", "python programming": "python"}
        selected = banks.get(aliases.get(key, ""))
    if not selected:
        return []
    result = []
    for question, options, explanation in selected[:limit]:
        result.append({"question": question, "options": options, "answer": options[0], "explanation": explanation})
    return result

def extract_pdf_text(uploaded_file):
    data = io.BytesIO(uploaded_file.getvalue())
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    reader = PdfReader(data)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError("This PDF is password-protected. Please upload an unlocked copy.")
    if len(reader.pages) > 100:
        raise ValueError("Please use a PDF with 100 pages or fewer.")
    extracted = "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if not extracted.strip():
        raise ValueError("No selectable text was found. This may be a scanned PDF; try the Picture tab or use a text-based PDF.")
    return extracted[:250000]


def extract_image_text(uploaded_file):
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        raise RuntimeError("Image text extraction needs Pillow and pytesseract. Install them with: python -m pip install pillow pytesseract")
    image = Image.open(io.BytesIO(uploaded_file.getvalue())).convert("RGB")
    if image.width * image.height > 25000000:
        image.thumbnail((5000, 5000))
    try:
        return pytesseract.image_to_string(image, lang="eng").strip()
    except Exception as exc:
        raise RuntimeError("The Tesseract OCR engine is not installed or could not be found. Install Tesseract OCR, then restart LifeBridgeAI. " + str(exc))

# ---------------------------- PAGE: DASHBOARD ----------------------------

page = st.session_state.page


if page == "Dashboard":
    st.markdown("""
    <style>
    /* Dashboard-only premium visual identity */
    .lb-premium-hero {
        position: relative;
        overflow: hidden;
        padding: 38px 38px 34px;
        margin: 8px 0 30px;
        border-radius: 25px;
        color: #F5F8F3;
        background:
            radial-gradient(ellipse at 88% 8%, rgba(166,202,157,.24), transparent 35%),
            radial-gradient(ellipse at 8% 100%, rgba(113,140,120,.25), transparent 40%),
            linear-gradient(120deg, #173B2B 0%, #244B37 55%, #315B40 100%);
        border: 1px solid rgba(255,255,255,.12);
        box-shadow: 0 16px 38px rgba(30,62,43,.14);
    }
    .lb-premium-hero:after {
        content: "";
        position: absolute;
        width: 230px;
        height: 230px;
        right: -65px;
        bottom: -125px;
        border: 1px solid rgba(235,246,228,.19);
        border-radius: 50%;
        box-shadow: 0 0 0 24px rgba(235,246,228,.035),
                    0 0 0 49px rgba(235,246,228,.025);
    }
    .lb-premium-eyebrow {
        color: #C5D9C2;
        font-size: .75rem;
        letter-spacing: 2.2px;
        font-weight: 750;
        text-transform: uppercase;
    }
    .lb-premium-hero h1 {
        color: #FFFFFF !important;
        font-size: clamp(2.35rem,5vw,3.7rem);
        letter-spacing: -2px;
        line-height: 1.08;
        margin: 15px 0 12px;
        max-width: 720px;
    }
    .lb-premium-hero p {
        color: #D6E3D6;
        font-size: 1.02rem;
        line-height: 1.7;
        max-width: 650px;
        margin: 0;
    }
    .lb-domain-card {
        min-height: 275px;
        padding: 25px 25px 21px;
        border-radius: 21px;
        border: 1px solid #E1E9E1;
        background: linear-gradient(145deg,#FFFFFF 0%,#F4F8F3 100%);
        box-shadow: 0 7px 22px rgba(39,62,44,.045);
        margin: 5px 0 10px;
    }
    .lb-domain-card.agriculture {
        background: linear-gradient(145deg,#F4F8F0 0%,#EAF2E5 100%);
        border-color: #DCE8D5;
    }
    .lb-domain-icon {
        display: inline-flex;
        width: 48px;
        height: 48px;
        align-items: center;
        justify-content: center;
        border-radius: 15px;
        background: #E6EEE5;
        color: #365C40;
        font-size: 25px;
        margin-bottom: 17px;
    }
    .lb-domain-card.agriculture .lb-domain-icon {
        background: #DCEBD5;
        color: #315D36;
    }
    .lb-domain-label {
        font-size: .72rem;
        text-transform: uppercase;
        letter-spacing: 1.6px;
        color: #718477;
        font-weight: 750;
    }
    .lb-domain-card h3 {
        font-size: 1.55rem;
        margin: 5px 0 8px;
        letter-spacing: -.7px;
    }
    .lb-domain-card p {
        color: #657369;
        line-height: 1.65;
        font-size: .91rem;
        min-height: 48px;
    }
    .lb-domain-features {
        color: #506255;
        font-size: .83rem;
        line-height: 1.9;
        padding-top: 8px;
        border-top: 1px solid rgba(95,120,96,.14);
    }
    .lb-section-heading {
        font-size: 1.45rem;
        font-weight: 750;
        letter-spacing: -.7px;
        color: #263B2D;
        margin: 25px 0 3px;
    }
    .lb-section-subtitle {
        color: #7A887E;
        font-size: .9rem;
        margin-bottom: 16px;
    }
    .lb-metric {
        background: linear-gradient(145deg,#FFFFFF,#F7F9F6);
        border: 1px solid #E4EAE3;
        border-radius: 17px;
        padding: 18px 17px;
        min-height: 112px;
        box-shadow: 0 5px 15px rgba(39,62,44,.035);
    }
    .lb-metric-label {
        color: #758278;
        font-size: .78rem;
        font-weight: 600;
    }
    .lb-metric-value {
        color: #294633;
        font-family: Manrope,sans-serif;
        font-weight: 800;
        font-size: 1.9rem;
        letter-spacing: -1px;
        margin-top: 8px;
    }
    .lb-capability {
        border: 1px solid #E3EAE1;
        border-radius: 15px;
        padding: 17px 18px;
        min-height: 108px;
        margin-bottom: 10px;
        background: #FFFFFF;
    }
    .lb-capability strong {
        color: #344D39;
        font-size: .96rem;
    }
    .lb-capability p {
        color: #77847A;
        font-size: .84rem;
        line-height: 1.55;
        margin: 7px 0 0;
    }
    .lb-premium-hero + div { margin-top: 0; }
    @media(max-width:700px) {
        .lb-premium-hero {padding:27px 23px;border-radius:20px}
        .lb-domain-card {min-height:0}
        .lb-premium-hero h1 {letter-spacing:-1.2px}
    }
    
    /* LifeBridgeAI premium motion system */

    /* LifeBridgeAI premium motion system */

    @keyframes lbFadeUp {
        from {
            opacity: 0;
            transform: translateY(18px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes lbSoftReveal {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    .lb-premium-hero {
        animation: lbFadeUp .85s cubic-bezier(.2,.75,.25,1) both;
    }

    .lb-domain-card {
        animation: lbFadeUp .75s cubic-bezier(.2,.75,.25,1) .12s both;
        transition:
            transform .35s cubic-bezier(.2,.75,.25,1),
            box-shadow .35s ease,
            border-color .35s ease;
        will-change: transform;
    }

    .lb-domain-card.agriculture {
        animation-delay: .22s;
    }

    .lb-domain-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 17px 35px rgba(35,65,43,.12);
        border-color: #C7D8C6;
    }

    .lb-domain-icon {
        transition: transform .4s cubic-bezier(.2,.75,.25,1),
                    background .3s ease;
    }

    .lb-domain-card:hover .lb-domain-icon {
        transform: scale(1.08) rotate(-4deg);
    }

    .lb-metric {
        animation: lbFadeUp .65s cubic-bezier(.2,.75,.25,1) both;
        transition:
            transform .3s ease,
            box-shadow .3s ease,
            border-color .3s ease;
    }

    .lb-metric:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 25px rgba(35,65,43,.09);
        border-color: #C9D9C8;
    }

    .lb-capability {
        animation: lbSoftReveal .65s ease both;
        transition:
            transform .3s ease,
            box-shadow .3s ease,
            border-color .3s ease;
    }

    .lb-capability:hover {
        transform: translateY(-3px);
        box-shadow: 0 9px 20px rgba(35,65,43,.07);
        border-color: #C9D9C8;
    }

    /* Dashboard buttons only */
    .stMain .stButton > button {
        transition:
            transform .22s ease,
            box-shadow .22s ease,
            background-color .22s ease,
            border-color .22s ease;
    }

    .stMain .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(45,83,53,.13);
    }

    .stMain .stButton > button:active {
        transform: scale(.985);
        box-shadow: none;
    }

    @media (prefers-reduced-motion: reduce) {
        .lb-premium-hero,
        .lb-domain-card,
        .lb-metric,
        .lb-capability {
            animation: none !important;
            transition: none !important;
        }

        .lb-domain-card:hover,
        .lb-metric:hover,
        .lb-capability:hover,
        .lb-domain-card:hover .lb-domain-icon,
        .stMain .stButton > button:hover,
        .stMain .stButton > button:active {
            transform: none !important;
        }
    }

    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="lb-premium-hero">
      <div class="lb-premium-eyebrow">LIFEBRIDGEAI &nbsp; / &nbsp; INTELLIGENCE FOR EVERYDAY PROGRESS</div>
      <h1>Ideas into action.<br>Knowledge into impact.</h1>
      <p>One connected platform for learning, discovery and smarter agricultural awareness.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="lb-section-heading">Explore your world</div>', unsafe_allow_html=True)
    st.markdown('<div class="lb-section-subtitle">Two meaningful domains. One place to move forward.</div>', unsafe_allow_html=True)

    edu_col, agro_col = st.columns(2, gap="large")

    with edu_col:
        st.markdown("""
        <div class="lb-domain-card">
          <div class="lb-domain-icon">✳</div>
          <div class="lb-domain-label">Knowledge · Skills · Progress</div>
          <h3>Education</h3>
          <p>A focused space to understand concepts, practise skills and build lasting knowledge.</p>
          <div class="lb-domain-features">
            Guided lessons &nbsp; · &nbsp; Revision notes<br>
            Quizzes &nbsp; · &nbsp; Learning games &nbsp; · &nbsp; Progress
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Enter Learning Studio  →", key="dashboard_open_education", use_container_width=True):
            st.session_state.page = "Learning Studio"
            st.rerun()

    with agro_col:
        st.markdown("""
        <div class="lb-domain-card agriculture">
          <div class="lb-domain-icon">❋</div>
          <div class="lb-domain-label">Nature · Technology · Awareness</div>
          <h3>Agriculture</h3>
          <p>Bring intelligent technology closer to crop observations and practical care awareness.</p>
          <div class="lb-domain-features">
            Leaf observations &nbsp; · &nbsp; Health reports<br>
            Crop monitoring &nbsp; · &nbsp; Care guidance
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Enter AgroBridge  →", key="dashboard_open_agriculture", use_container_width=True):
            st.session_state.page = "AgroBridge"
            st.rerun()

    st.markdown('<div class="lb-section-heading">Your learning overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="lb-section-subtitle">A snapshot of your learning activity and progress.</div>', unsafe_allow_html=True)

    if not student:
        st.markdown(
            '<div class="lb-card"><b>Welcome to LifeBridgeAI</b>'
            '<p class="lb-muted">Create a learner profile to save notes, tasks, quizzes and learning progress. You can explore AgroBridge without creating a profile.</p></div>',
            unsafe_allow_html=True,
        )
        with st.form("create_profile_dashboard"):
            name = st.text_input("Student name")
            grade = st.selectbox("Class / grade", ["Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Other"])
            school = st.text_input("School (optional)")
            language = st.selectbox("Preferred language", ["English", "Hindi", "Punjabi"])
            submitted = st.form_submit_button("Create my profile")
        if submitted:
            if not name.strip():
                st.error("Please enter your name.")
            else:
                create_student(name, grade, school, language)
                st.rerun()
    else:
        tasks = query_all(
            "SELECT * FROM tasks WHERE student_id=? ORDER BY completed,due_date,id DESC",
            (student["student_id"],),
        )
        notes_count = query_all(
            "SELECT COUNT(*) n FROM notes WHERE student_id=?",
            (student["student_id"],),
        )[0]["n"]
        attempts = query_all(
            "SELECT * FROM attempts WHERE student_id=? ORDER BY attempted_at DESC",
            (student["student_id"],),
        )
        total_score = sum(r["score"] for r in attempts)
        total_q = sum(r["total"] for r in attempts)
        done = sum(r["completed"] for r in tasks)

        metric_values = [
            ("TASKS COMPLETED", done),
            ("SAVED NOTES", notes_count),
            ("QUIZ ATTEMPTS", len(attempts)),
            ("QUIZ ACCURACY", f"{round(100 * total_score / total_q) if total_q else 0}%"),
        ]
        metric_cols = st.columns(4, gap="medium")
        for metric_col, (metric_label, metric_value) in zip(metric_cols, metric_values):
            with metric_col:
                st.markdown(
                    f'<div class="lb-metric"><div class="lb-metric-label">{metric_label}</div>'
                    f'<div class="lb-metric-value">{esc(metric_value)}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="lb-section-heading">Today\'s focus</div>', unsafe_allow_html=True)
        st.markdown('<div class="lb-section-subtitle">Small steps, consistent progress.</div>', unsafe_allow_html=True)

        with st.form("quick_task"):
            c1, c2 = st.columns([3, 1])
            with c1:
                task_title = st.text_input("Add a study task", placeholder="e.g. Revise chemical reactions")
            with c2:
                task_subject = st.selectbox(
                    "Subject",
                    ["General", "Science", "Mathematics", "Social Science", "English", "Computer"],
                )
            if st.form_submit_button("Add task"):
                if task_title.strip():
                    execute(
                        "INSERT INTO tasks(student_id,title,subject,due_date,created_at) VALUES(?,?,?,?,?)",
                        (student["student_id"], task_title.strip(), task_subject, date.today().isoformat(), now_text()),
                    )
                    st.success("Task added.")
                    st.rerun()
                else:
                    st.warning("Enter a task title.")

        if tasks:
            for task in tasks[:8]:
                col_a, col_b = st.columns([5, 1])
                col_a.write(
                    ("Done: " if task["completed"] else "Pending: ")
                    + task["title"] + f" | {task['subject']}"
                )
                if not task["completed"] and col_b.button("Done", key=f"dash_done_{task['id']}"):
                    execute(
                        "UPDATE tasks SET completed=1 WHERE id=? AND student_id=?",
                        (task["id"], student["student_id"]),
                    )
                    st.rerun()
        else:
            st.caption("No tasks yet. Add your first study task above.")

        st.markdown('<div class="lb-section-heading">Continue learning</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        if c1.button("Organise a lesson", key="dashboard_lesson", use_container_width=True):
            st.session_state.page = "Lesson Organizer"
            st.rerun()
        if c2.button("Make revision notes", key="dashboard_notes", use_container_width=True):
            st.session_state.page = "Note Maker"
            st.rerun()
        if c3.button("Start a quiz", key="dashboard_quiz", use_container_width=True):
            st.session_state.page = "Quiz Center"
            st.rerun()

    st.markdown('<div class="lb-section-heading">Agriculture at a glance</div>', unsafe_allow_html=True)
    st.markdown('<div class="lb-section-subtitle">Explore the tools available in your AgroBridge workspace.</div>', unsafe_allow_html=True)

    ag1, ag2 = st.columns(2, gap="medium")
    with ag1:
        st.markdown("""
        <div class="lb-capability">
          <strong>Leaf Disease Analysis</strong>
          <p>Record crop symptoms and receive an AI-assisted educational assessment.</p>
        </div>
        <div class="lb-capability">
          <strong>Crop Health Reports</strong>
          <p>Review the latest assessment available in your current session.</p>
        </div>
        """, unsafe_allow_html=True)
    with ag2:
        st.markdown("""
        <div class="lb-capability">
          <strong>Crop Monitoring</strong>
          <p>Record growth-stage and field observations during your session.</p>
        </div>
        <div class="lb-capability">
          <strong>Treatment Guidance</strong>
          <p>Explore general crop-care practices and when to consult an expert.</p>
        </div>
        """, unsafe_allow_html=True)

    st.caption("Report history and monitoring history are not yet stored permanently.")

    if st.button("Open AgroBridge workspace  →", key="dashboard_agro_footer", use_container_width=True):
        st.session_state.page = "AgroBridge"
        st.rerun()
elif page == "Learning Studio":
    st.markdown("""
    <style>
    .ls-hero {
        position: relative;
        overflow: hidden;
        padding: 36px 34px;
        margin: 4px 0 30px;
        border-radius: 23px;
        color: #f7faf5;
        background: linear-gradient(120deg, #173d32, #245443 58%, #315f4d);
        animation: lsFadeUp .65s ease both;
    }
    .ls-hero:before {
        content: "";
        z-index: 0;
        position: absolute;
        width: 260px;
        height: 260px;
        right: -75px;
        top: -135px;
        border-radius: 50%;
        background: rgba(220,239,218,.10);
        box-shadow: 0 0 0 38px rgba(220,239,218,.035),
                    0 0 0 76px rgba(220,239,218,.025);
    }
    .ls-hero > * {
        position: relative;
        z-index: 1;
    }
    .ls-eyebrow {
        color: #c5dfc9;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 12px;
    }
    .ls-hero h2 {
        color: white !important;
        -webkit-text-fill-color: white;
        font-family: 'Manrope', sans-serif;
        font-size: clamp(27px, 4vw, 39px);
        font-weight: 800;
        letter-spacing: -1.3px;
        line-height: 1.15;
        margin: 0 0 12px;
    }
    .ls-hero p {
        color: #e0ebe2;
        font-size: 14px;
        line-height: 1.7;
        max-width: 590px;
        margin: 0;
    }
    .ls-section-label {
        color: #688477;
        font-size: 11px;
        font-weight: 750;
        letter-spacing: 1.8px;
        text-transform: uppercase;
        margin: 0 0 5px 2px;
    }
    .ls-section-heading {
        color: #203b30;
        font-family: 'Manrope', sans-serif;
        font-size: 23px;
        font-weight: 800;
        margin: 0 0 5px 2px;
    }
    .ls-section-subtitle {
        color: #78867e;
        font-size: 13px;
        margin: 0 0 19px 2px;
    }
    .ls-tool-card {
        min-height: 145px;
        padding: 19px 19px 15px;
        margin: 0 0 8px;
        border: 1px solid #e5ebe5;
        border-radius: 17px;
        background: white;
        transition: transform .24s ease, box-shadow .24s ease,
                    border-color .24s ease;
        animation: lsFadeUp .55s ease both;
    }
    .ls-tool-card:hover {
        transform: translateY(-4px);
        border-color: #b8cdbd;
        box-shadow: 0 12px 28px rgba(35,75,54,.09);
    }
    .ls-tool-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 13px;
    }
    .ls-tool-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 13px;
        color: #315c47;
        background: #edf4ed;
        font-size: 23px;
        transition: transform .24s ease, background .24s ease;
    }
    .ls-tool-card:hover .ls-tool-icon {
        transform: scale(1.08) rotate(-4deg);
        background: #e1eee2;
    }
    .ls-tool-number {
        color: #a2b1a7;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .ls-tool-card h3 {
        color: #263d31;
        font-family: 'Manrope', sans-serif;
        font-size: 17px;
        font-weight: 750;
        margin: 0 0 5px;
    }
    .ls-tool-card p {
        color: #78847c;
        font-size: 12px;
        line-height: 1.55;
        margin: 0;
    }
    div[class*="st-key-learning_studio_open_"] button {
        border-radius: 11px;
        border: 1px solid #dce7dd;
        color: #315c47;
        background: #f5f8f4;
        font-weight: 650;
        transition: background .2s ease, transform .2s ease;
    }
    div[class*="st-key-learning_studio_open_"] button:hover {
        color: white;
        background: #315c47;
        border-color: #315c47;
        transform: translateY(-1px);
    }
    .ls-tool-card {
        position: relative;
        overflow: hidden;
        min-height: 168px;
        padding: 21px 21px 18px;
        border: 1px solid #e4ebe4;
        border-radius: 20px;
        background: linear-gradient(145deg, #ffffff 0%, #f7faf6 100%);
        box-shadow: 0 4px 15px rgba(34, 66, 46, .045);
        transition: transform .26s ease, box-shadow .26s ease, border-color .26s ease;
    }
    .ls-tool-card:before {
        content: "";
        position: absolute;
        top: 0;
        left: 21px;
        width: 43px;
        height: 3px;
        border-radius: 0 0 5px 5px;
        background: #6b9877;
    }
    .ls-tool-card:after {
        content: "";
        position: absolute;
        width: 145px;
        height: 145px;
        right: -75px;
        top: -82px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(112, 151, 119, .10), transparent 70%);
        pointer-events: none;
    }
    .ls-tool-card > * { position: relative; z-index: 1; }
    .ls-tool-card:hover {
        transform: translateY(-5px);
        border-color: #c8d8ca;
        box-shadow: 0 15px 32px rgba(35, 75, 54, .11);
    }
    .ls-tool-top { margin-bottom: 17px; }
    .ls-tool-icon {
        width: 49px;
        height: 49px;
        border-radius: 16px;
        font-size: 25px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.8), 0 4px 10px rgba(40,70,48,.06);
        transition: transform .26s ease, box-shadow .26s ease;
    }
    .ls-tool-card:hover .ls-tool-icon {
        transform: translateY(-2px) scale(1.07) rotate(-3deg);
        box-shadow: 0 7px 15px rgba(40,70,48,.12);
    }
    .ls-tool-number {
        padding: 6px 9px;
        border-radius: 20px;
        background: #f0f4ef;
        color: #809187;
        font-size: 10px;
    }
    .ls-tool-card h3 { font-size: 18px; letter-spacing: -.35px; margin-bottom: 6px; }
    .ls-tool-card p { font-size: 12.5px; line-height: 1.6; }
    .ls-tool-card-1:before { background: #639b72; }
    .ls-tool-card-1 .ls-tool-icon { background: linear-gradient(135deg,#e8f4e9,#d5ead8); }
    .ls-tool-card-2:before { background: #8585bd; }
    .ls-tool-card-2 .ls-tool-icon { background: linear-gradient(135deg,#efedfa,#dedcf4); }
    .ls-tool-card-3:before { background: #c89a4f; }
    .ls-tool-card-3 .ls-tool-icon { background: linear-gradient(135deg,#fbf2df,#f3e4c3); }
    .ls-tool-card-4:before { background: #6395b8; }
    .ls-tool-card-4 .ls-tool-icon { background: linear-gradient(135deg,#e5f1f8,#d1e5f2); }
    .ls-tool-card-5:before { background: #55a09a; }
    .ls-tool-card-5 .ls-tool-icon { background: linear-gradient(135deg,#e2f3f0,#cce9e4); }
    .ls-tool-card-6:before { background: #d08069; }
    .ls-tool-card-6 .ls-tool-icon { background: linear-gradient(135deg,#faece7,#f3d9d0); }
    .ls-tool-card-7:before { background: #6e9c83; }
    .ls-tool-card-7 .ls-tool-icon { background: linear-gradient(135deg,#e7f2eb,#d3e7da); }
    .ls-tool-card-8:before { background: #b18b51; }
    .ls-tool-card-8 .ls-tool-icon { background: linear-gradient(135deg,#f6f0e3,#eae0c9); }
    @media (prefers-reduced-motion: reduce) {
        .ls-tool-card, .ls-tool-icon { transition: none !important; }
    }
    @keyframes lsFadeUp {
        from { opacity: 0; transform: translateY(13px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @media (prefers-reduced-motion: reduce) {
        .ls-hero, .ls-tool-card { animation: none !important; }
        .ls-tool-card, .ls-tool-icon,
        div[class*="st-key-learning_studio_open_"] button {
            transition: none !important;
        }
    }
    </style>
    <div class="ls-hero">
        <div class="ls-eyebrow">Your personal learning space</div>
        <h2>Learn with clarity.<br>Grow with confidence.</h2>
        <p>Everything you need to explore ideas, build understanding
        and make every study session count — all in one place.</p>
    </div>
    <div class="ls-section-label">The learning workspace</div>
    <div class="ls-section-heading">Explore your tools</div>
    <div class="ls-section-subtitle">
        Choose a space and pick up where your curiosity takes you.
    </div>
    """, unsafe_allow_html=True)

    studio_tools = [
        ("Lessons", "Lesson Organizer", "\U0001F4D8",
         "Explore topics with guided lessons."),
        ("Note Maker", "Note Maker", "\U0001F4DD",
         "Create and organize revision notes."),
        ("Quiz Center", "Quiz Center", "\U0001F3AF",
         "Practise questions and test your understanding."),
        ("Calculator", "Calculator", "\U0001F9EE",
         "Work through everyday calculations."),
        ("Translator", "Translator", "\U0001F310",
         "Translate text between languages."),
        ("Learning Games", "Learning Games", "\U0001F3AE",
         "Learn through interactive games."),
        ("Progress", "Progress Detector", "\U0001F4C8",
         "Review your learning progress."),
        ("Leaderboard", "Leaderboard", "\U0001F3C6",
         "View learning rankings."),
    ]

    columns = st.columns(2, gap="medium")
    for index, (label, target, icon, description) in enumerate(studio_tools):
        with columns[index % 2]:
            st.markdown(
                f"""
                <div class="ls-tool-card ls-tool-card-{index + 1}">
                    <div class="ls-tool-top">
                        <span class="ls-tool-icon">
                            {icon}
                        </span>
                        <span class="ls-tool-number">
                            {index + 1:02d} / 08
                        </span>
                    </div>
                    <h3>{label}</h3>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                f"Open {label}  →",
                key=f"learning_studio_open_{target}",
                use_container_width=True,
            ):
                st.session_state.page = target
                st.rerun()

# ---------------------------- PAGE: LESSON ORGANIZER ----------------------------

elif page == "Lesson Organizer":
    st.title("Lesson Organizer")
    st.caption("Organise lesson text or extract readable text from a PDF into smaller study points.")
    topic = st.text_input("Lesson title", placeholder="e.g. The human eye", key="lesson_topic")
    subject = st.selectbox("Subject", ["General", "Science", "Mathematics", "Social Science", "English", "Computer"], key="lesson_subject")

    paste_tab, pdf_tab = st.tabs(["Paste lesson text", "Add PDF"])
    with paste_tab:
        passage = st.text_area("Lesson or reading passage", height=210,
                               placeholder="Paste text from your class notes or textbook...", key="lesson_passage")
        if st.button("Organize pasted lesson", key="organize_pasted_lesson", use_container_width=True):
            if not passage.strip():
                st.warning("Paste some lesson text first.")
            else:
                parts = [part.strip() for part in re.split(r"(?<=[.!?।])\s+", passage.strip()) if part.strip()]
                st.session_state.organized_lesson = {
                    "topic": topic.strip() or "Your lesson", "subject": subject,
                    "parts": parts, "source": "Pasted text"
                }

    with pdf_tab:
        st.caption("Upload a text-based PDF. The app extracts its text locally; the PDF is not sent to an AI service.")
        pdf_file = st.file_uploader("Choose a PDF", type=["pdf"], key="lesson_pdf_upload",
                                    help="Maximum file size: 15 MB. Scanned image-only PDFs need OCR and are not supported in this version.")
        if pdf_file is not None:
            st.caption(f"Selected: {pdf_file.name} · {pdf_file.size / 1024:.0f} KB")
            if st.button("Extract and organize PDF", key="organize_pdf_lesson", use_container_width=True):
                if pdf_file.size > 15 * 1024 * 1024:
                    st.error("This PDF is larger than 15 MB. Please choose a smaller file.")
                else:
                    try:
                        from io import BytesIO
                        try:
                            from pypdf import PdfReader
                        except ImportError:
                            from PyPDF2 import PdfReader
                        reader = PdfReader(BytesIO(pdf_file.getvalue()))
                        if reader.is_encrypted:
                            try:
                                unlocked = reader.decrypt("")
                            except Exception:
                                unlocked = 0
                            if not unlocked:
                                raise ValueError("This PDF is password-protected. Please upload an unlocked copy.")
                        if len(reader.pages) > 100:
                            raise ValueError("This PDF has more than 100 pages. Please split it into smaller files.")
                        page_text = []
                        for page_number, pdf_page in enumerate(reader.pages, start=1):
                            extracted = (pdf_page.extract_text() or "").strip()
                            if extracted:
                                page_text.append(f"[Page {page_number}]\n{extracted}")
                        extracted_text = "\n\n".join(page_text).strip()
                        if not extracted_text:
                            raise ValueError("No selectable text was found. This may be a scanned/image-only PDF; OCR support is not included yet.")
                        if len(extracted_text) > 250000:
                            extracted_text = extracted_text[:250000]
                            st.warning("The extracted text was limited to the first 250,000 characters.")
                        parts = [part.strip() for part in re.split(r"(?<=[.!?।])\s+", extracted_text) if part.strip()]
                        st.session_state.organized_lesson = {
                            "topic": topic.strip() or Path(pdf_file.name).stem or "PDF lesson",
                            "subject": subject, "parts": parts,
                            "source": f"PDF · {pdf_file.name}"
                        }
                        st.success(f"Extracted text from {len(page_text)} page(s).")
                    except ImportError:
                        st.error("PDF support needs the pypdf package. In CMD, run: python -m pip install pypdf")
                    except Exception as exc:
                        st.error(f"Could not read this PDF: {exc}")

    lesson = st.session_state.get("organized_lesson")
    if lesson:
        st.divider()
        st.subheader(lesson["topic"])
        st.caption(f"{len(lesson['parts'])} reading points · {lesson['subject']} · {lesson.get('source', 'Lesson text')}")
        for i, part in enumerate(lesson["parts"], 1):
            st.markdown(f'<div class="lb-card"><b>{i:02d}</b> &nbsp; {esc(part)}</div>', unsafe_allow_html=True)
        if require_student() and st.button("Add this lesson to my tasks", key="add_organized_lesson_task"):
            execute("INSERT INTO tasks(student_id,title,subject,due_date,created_at) VALUES(?,?,?,?,?)",
                    (student["student_id"], "Study: " + lesson["topic"], lesson["subject"], "", now_text()))
            st.success("Lesson added to your task list.")

# ---------------------------- PAGE: NOTE MAKER ----------------------------

elif page == "Note Maker":
    st.title("Smart Note Maker")
    st.caption("Turn paragraphs, textbook pictures or PDFs into clear, editable revision notes.")
    st.markdown("<div class='lb-card'><b>Three ways to create notes</b><br><span class='lb-muted'>Paste text · Upload a picture · Upload a PDF</span></div>", unsafe_allow_html=True)

    topic = st.text_input("Topic / chapter name", placeholder="e.g. Chemical Reactions", key="note_topic_input")
    subject_choice = st.selectbox("Subject", ["Auto-detect", "Science", "Mathematics", "Social Science", "English", "Computer", "General"], key="note_subject_input")
    style = st.selectbox("Note format", ["Exam-focused", "Quick Revision", "Detailed"], key="note_style_input")

    paste_tab, picture_tab, pdf_tab = st.tabs(["① Paste text", "② Upload picture", "③ Upload PDF"])
    with paste_tab:
        pasted_text = st.text_area("Paste your paragraph or class notes", height=220,
                                   placeholder="Paste one or more paragraphs from your textbook or class notes...", key="note_pasted_text")
        if st.button("Create notes from text", key="make_notes_from_text", use_container_width=True):
            if not pasted_text.strip():
                st.warning("Paste some text first.")
            else:
                final_topic = topic.strip() or "Chapter revision"
                try:
                    note, detected = ai_make_note_pack(final_topic, pasted_text, style)
                    st.success("AI-powered notes created with Gemini.")
                except Exception as ai_error:
                    note, detected = make_note_pack(final_topic, pasted_text, style)
                    st.warning(f"Gemini unavailable. Offline notes generated instead: {ai_error}")

                if not topic.strip():
                    detected = detect_subject(pasted_text[:500])

                subject_name = detected if subject_choice == "Auto-detect" else subject_choice
                st.session_state.generated_note = {"title": final_topic, "subject": subject_name, "body": note, "source": "Pasted text", "editor_key": uuid.uuid4().hex}
                st.success("Your notes are ready. You can edit them below.")
    with picture_tab:
        st.caption("Upload a clear JPG, JPEG or PNG photo. Text is read locally using OCR.")
        picture = st.file_uploader("Choose a picture", type=["png", "jpg", "jpeg"], key="note_picture_upload")
        if picture:
            st.image(picture, caption=picture.name, use_container_width=True)
        if st.button("Read picture and create notes", key="make_notes_from_picture", use_container_width=True):
            if not picture:
                st.warning("Upload a picture first.")
            else:
                try:
                    with st.spinner("Reading text from picture..."):
                        extracted = extract_image_text(picture)
                    if not extracted:
                        st.warning("No readable text was detected. Try a sharper, well-lit picture with the page facing the camera.")
                    else:
                        final_topic = topic.strip() or Path(picture.name).stem.replace("_", " ") or "Picture notes"
                        try:
                            note, detected = ai_make_note_pack(final_topic, extracted, style)
                            st.success("AI-powered notes created with Gemini.")
                        except Exception as ai_error:
                            note, detected = make_note_pack(final_topic, extracted, style)
                            st.warning(f"Gemini unavailable. Offline notes generated instead: {ai_error}")
                        if not topic.strip(): detected = detect_subject(extracted[:500])
                        subject_name = detected if subject_choice == "Auto-detect" else subject_choice
                        st.session_state.generated_note = {"title": final_topic, "subject": subject_name, "body": note, "source": picture.name, "editor_key": uuid.uuid4().hex}
                        st.success("Picture text extracted and notes created. Review OCR accuracy before saving.")
                except Exception as exc:
                    st.error(str(exc))
    with pdf_tab:
        st.caption("Upload a text-based PDF. Maximum 15 MB and 100 pages. Scanned PDFs need OCR first.")
        pdf_file = st.file_uploader("Choose a PDF", type=["pdf"], key="note_pdf_upload")
        if st.button("Extract PDF and create notes", key="make_notes_from_pdf", use_container_width=True):
            if not pdf_file:
                st.warning("Upload a PDF first.")
            elif pdf_file.size > 15 * 1024 * 1024:
                st.error("The PDF is larger than 15 MB. Please use a smaller file.")
            else:
                try:
                    with st.spinner("Extracting PDF text..."):
                        extracted = extract_pdf_text(pdf_file)
                    final_topic = topic.strip() or Path(pdf_file.name).stem.replace("_", " ") or "PDF notes"
                    try:
                        note, detected = ai_make_note_pack(final_topic, extracted, style)
                        st.success("AI-powered notes created with Gemini.")
                    except Exception as ai_error:
                        note, detected = make_note_pack(final_topic, extracted, style)
                        st.warning(f"Gemini unavailable. Offline notes generated instead: {ai_error}")
                    if not topic.strip(): detected = detect_subject(extracted[:500])
                    subject_name = detected if subject_choice == "Auto-detect" else subject_choice
                    st.session_state.generated_note = {"title": final_topic, "subject": subject_name, "body": note, "source": pdf_file.name, "editor_key": uuid.uuid4().hex}
                    st.success("PDF extracted and notes created. Review the result before saving.")
                except Exception as exc:
                    st.error(f"Could not process this PDF: {exc}")

    generated = st.session_state.get("generated_note")
    if generated:
        st.divider()
        st.subheader("Your interactive notes")
        st.caption(f"Source: {generated.get('source', 'Text')} · {generated['subject']}")
        edit_tab, preview_tab = st.tabs(["Edit notes", "Preview"])
        with edit_tab:
            edited_body = st.text_area("Edit, add or remove anything", value=generated["body"], height=420, key=f"generated_note_editor_{generated.get('editor_key', 'default')}")
            st.session_state.generated_note["body"] = edited_body
        with preview_tab:
            st.markdown(st.session_state.generated_note["body"])
        current_body = st.session_state.generated_note["body"]
        col_download, col_copy = st.columns(2)
        col_download.download_button("Download notes (.md)", current_body, file_name="lifebridge_notes.md", mime="text/markdown", use_container_width=True)
        col_copy.caption("You can edit the notes above before downloading or saving.")
        if require_student():
            with st.form("save_note_form"):
                saved_title = st.text_input("Save note as", value=generated["title"])
                save = st.form_submit_button("Save to my library")
            if save:
                execute("INSERT INTO notes(student_id,title,subject,body,updated_at) VALUES(?,?,?,?,?)",
                        (student["student_id"], saved_title.strip() or generated["title"], generated["subject"], current_body, now_text()))
                st.success("Note saved to your library.")
    if require_student():
        st.divider()
        st.subheader("My saved notes")
        saved_notes = query_all("SELECT * FROM notes WHERE student_id=? ORDER BY updated_at DESC", (student["student_id"],))
        if not saved_notes:
            st.caption("Your saved notes will appear here.")
        for row in saved_notes:
            with st.expander(f"{row['title']} · {row['subject']}"):
                st.markdown(row["body"])
                st.download_button("Download", row["body"], file_name=f"note_{row['id']}.md", key=f"note_dl_{row['id']}")
                if st.button("Delete note", key=f"note_del_{row['id']}"):
                    execute("DELETE FROM notes WHERE id=? AND student_id=?", (row["id"], student["student_id"]))
                    st.rerun()

# ---------------------------- PAGE: QUIZ CENTER ----------------------------

elif page == "Quiz Center":
    st.title("Smart Quiz Center")
    st.caption("Build a practice quiz from a topic, your pasted text, a textbook picture or a PDF.")
    if not require_student():
        st.stop()

    quiz_topic = st.text_input("Quiz title / topic", placeholder="e.g. Photosynthesis", key="quiz_topic_input")
    count = st.selectbox("Number of questions", [5, 10], index=0, key="quiz_question_count")
    st.markdown("<div class='lb-card'><b>Choose your quiz source</b><br><span class='lb-muted'>Gemini can generate quizzes from any topic or your supplied learning material.</span></div>", unsafe_allow_html=True)
    title_tab, text_tab, picture_tab, pdf_tab = st.tabs(["① Topic title", "② Paste paragraph", "③ Upload picture", "④ Upload PDF"])

    source_text = ""
    source_name = ""
    with title_tab:
        st.info("Gemini generates questions directly from your topic title. If Gemini is unavailable, LifeBridgeAI tries its offline question bank.")
        if st.button("Create quiz from title", key="quiz_from_title", use_container_width=True):
            if not quiz_topic.strip():
                st.warning("Enter a topic title first.")
            else:
                pool = generate_quiz_questions(quiz_topic, count, from_topic=True)
                if not pool:
                    st.warning("This topic is not in the offline starter bank yet. Paste a paragraph or upload a picture/PDF about this topic to create a source-based quiz.")
                else:
                    st.session_state.active_quiz = {"topic": quiz_topic.strip(), "questions": pool[:count], "started": now_text(), "source": "Offline topic bank"}
                    st.session_state.quiz_result = None
                    st.rerun()
    with text_tab:
        pasted = st.text_area("Paste your textbook paragraph or class notes", height=190, key="quiz_source_text", placeholder="Paste one or more paragraphs. The quiz will be built from details in this text...")
        if st.button("Generate quiz from paragraph", key="quiz_from_text", use_container_width=True):
            if not pasted.strip():
                st.warning("Paste some text first.")
            else:
                pool = generate_quiz_questions(pasted, count)
                if len(pool) < 3:
                    st.warning("There is not enough extractable information for a reliable quiz. Paste a longer passage with complete sentences and factual details.")
                else:
                    st.session_state.active_quiz = {"topic": quiz_topic.strip() or "Paragraph practice", "questions": pool[:min(count, len(pool))], "started": now_text(), "source": "Pasted paragraph"}
                    st.session_state.quiz_result = None
                    st.rerun()
    with picture_tab:
        st.caption("Upload a clear JPG, JPEG or PNG image. Text is extracted locally with OCR.")
        picture = st.file_uploader("Choose a textbook picture", type=["png", "jpg", "jpeg"], key="quiz_picture_upload")
        if picture is not None:
            st.image(picture, caption=picture.name, use_container_width=True)
        if st.button("Read picture and generate quiz", key="quiz_from_picture", use_container_width=True):
            if picture is None:
                st.warning("Upload a picture first.")
            else:
                try:
                    with st.spinner("Reading the picture..."):
                        extracted = extract_image_text(picture)
                    pool = generate_quiz_questions(extracted, count)
                    if len(pool) < 3:
                        st.warning("The picture did not contain enough clear text to build a reliable quiz. Try a sharper, well-lit image.")
                    else:
                        st.session_state.active_quiz = {"topic": quiz_topic.strip() or picture.name, "questions": pool[:min(count, len(pool))], "started": now_text(), "source": picture.name}
                        st.session_state.quiz_result = None
                        st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    with pdf_tab:
        st.caption("Upload a text-based PDF. Scanned PDFs need OCR and may not work in this version.")
        pdf_file = st.file_uploader("Choose a PDF", type=["pdf"], key="quiz_pdf_upload")
        if pdf_file is not None:
            st.caption(f"Selected: {pdf_file.name} · {pdf_file.size / 1024:.0f} KB")
        if st.button("Extract PDF and generate quiz", key="quiz_from_pdf", use_container_width=True):
            if pdf_file is None:
                st.warning("Upload a PDF first.")
            elif pdf_file.size > 15 * 1024 * 1024:
                st.error("This PDF is larger than 15 MB. Please choose a smaller file.")
            else:
                try:
                    with st.spinner("Extracting PDF text..."):
                        extracted = extract_pdf_text(pdf_file)
                    pool = generate_quiz_questions(extracted, count)
                    if len(pool) < 3:
                        st.warning("The PDF did not contain enough extractable text for a reliable quiz. Try a longer text-based PDF.")
                    else:
                        st.session_state.active_quiz = {"topic": quiz_topic.strip() or pdf_file.name, "questions": pool[:min(count, len(pool))], "started": now_text(), "source": pdf_file.name}
                        st.session_state.quiz_result = None
                        st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    active_quiz = st.session_state.get("active_quiz")
    if active_quiz:
        st.divider()
        st.subheader(active_quiz["topic"] + " · Practice quiz")
        st.caption(f"{len(active_quiz['questions'])} questions · Source: {active_quiz.get('source', 'Study material')}")
        if not st.session_state.get("quiz_result"):
            with st.form("answer_quiz"):
                answers = []
                for i, q in enumerate(active_quiz["questions"], 1):
                    st.markdown(f"**Question {i} of {len(active_quiz['questions'])}**")
                    st.write(q["question"])
                    answers.append(st.radio("Choose an answer", q["options"], index=None, key=f"ans_{active_quiz['started']}_{i}", label_visibility="collapsed"))
                    st.divider()
                submit = st.form_submit_button("Submit answers", use_container_width=True)
            if submit:
                if any(a is None for a in answers):
                    st.error("Answer every question before submitting.")
                else:
                    score = sum(a == q["answer"] for a, q in zip(answers, active_quiz["questions"]))
                    st.session_state.quiz_result = {"score": score, "answers": answers}
                    execute("INSERT INTO attempts(student_id,topic,score,total,attempted_at) VALUES(?,?,?,?,?)",
                            (student["student_id"], active_quiz["topic"], score, len(answers), now_text()))
                    st.rerun()
        result = st.session_state.get("quiz_result")
        if result:
            score, total = result["score"], len(active_quiz["questions"])
            st.subheader("Your result")
            st.metric("Score", f"{score}/{total}", f"{round(score/total*100)}%")
            st.progress(score / total)
            for i, (q, answer) in enumerate(zip(active_quiz["questions"], result["answers"]), 1):
                correct = answer == q["answer"]
                st.markdown(f"**{i}. {'Correct' if correct else 'Review this answer'}**")
                st.caption("Your answer: " + answer)
                if not correct:
                    st.write("Correct answer: " + q["answer"])
                st.write(q["explanation"])
            if st.button("Start another quiz", key="reset_quiz"):
                st.session_state.active_quiz = None
                st.session_state.quiz_result = None
                st.rerun()

# ---------------------------- PAGE: LEARNING GAMES ----------------------------

elif page == "Learning Games":
    st.title("Learning Arcade")
    st.caption("Choose a world. Play a challenge. Grow your knowledge.")

    arcade_games = [
        {"id": "Code & Conquer", "name": "Code & Conquer", "emoji": "⚔️", "tag": "ADVENTURE RPG", "desc": "Defeat dungeon monsters with Maths, Science and Vocabulary.", "theme": "#30234f"},
        {"id": "Cipher Heist: Codebreaker", "name": "Cipher Heist", "emoji": "🔐", "tag": "LOGIC MYSTERY", "desc": "Crack secret codes, patterns and clues to unlock the vault.", "theme": "#173d4b"},
        {"id": "Flashcard practice", "name": "Memory Sprint", "emoji": "🃏", "tag": "MEMORY TRAINING", "desc": "Memorize and identify 16 science diagrams.", "theme": "#49321f"},
        {"id": "Quick maths", "name": "Maths Rush", "emoji": "⚡", "tag": "MATHS ARCADE", "desc": "Solve fresh calculations and sharpen number skills.", "theme": "#174437"},
        {"id": "Science word scramble", "name": "Science Scramble", "emoji": "🧪", "tag": "SCIENCE PUZZLE", "desc": "Unscramble scientific words using smart clues.", "theme": "#47294f"},
    ]

    if "selected_arcade_game" not in st.session_state:
        st.session_state.selected_arcade_game = None

    selected_game = st.session_state.selected_arcade_game

    if selected_game is None:
        st.markdown("""
        <style>
        .arcade-intro{padding:17px 18px;border-radius:18px;background:linear-gradient(120deg,rgba(91,75,160,.18),rgba(30,145,130,.12));border:1px solid rgba(130,130,160,.22);margin:8px 0 16px}
        .arcade-intro strong{font-size:1.08rem;letter-spacing:-.3px}
        .arcade-card{min-height:174px;border-radius:18px;padding:16px;color:#fff;display:flex;flex-direction:column;justify-content:space-between;border:1px solid rgba(255,255,255,.13);box-shadow:0 8px 22px rgba(0,0,0,.12);margin-bottom:8px}
        .arcade-card .arcade-icon{font-size:2rem;line-height:1.2}
        .arcade-card .arcade-tag{font-size:.64rem;letter-spacing:1.15px;font-weight:800;opacity:.78;margin-top:9px}
        .arcade-card .arcade-name{font-size:1.18rem;font-weight:800;letter-spacing:-.45px;margin-top:4px}
        .arcade-card .arcade-desc{font-size:.79rem;line-height:1.4;opacity:.84;margin-top:5px}
        div.stButton>button[kind="secondary"]{border-radius:12px;font-weight:700;min-height:42px}
        </style>
        <div class="arcade-intro"><div style="font-size:.68rem;font-weight:800;letter-spacing:1.3px;opacity:.7">LIFEBRIDGE ARCADE</div><strong>Pick your next challenge</strong><div style="font-size:.82rem;opacity:.75;margin-top:4px">Five games. Five ways to train your brain.</div></div>
        """, unsafe_allow_html=True)

        for row_start in range(0, len(arcade_games), 2):
            cols = st.columns(2, gap="medium")
            for offset, col in enumerate(cols):
                idx = row_start + offset
                if idx >= len(arcade_games):
                    continue
                item = arcade_games[idx]
                with col:
                    st.markdown(
                        f"""<div class="arcade-card" style="background:linear-gradient(145deg,{item['theme']},#171923)">
                        <div><div class="arcade-icon">{item['emoji']}</div><div class="arcade-tag">{item['tag']}</div>
                        <div class="arcade-name">{esc(item['name'])}</div><div class="arcade-desc">{esc(item['desc'])}</div></div></div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button("PLAY NOW  →", key=f"arcade_open_{idx}", type="secondary", use_container_width=True):
                        st.session_state.selected_arcade_game = item["id"]
                        st.rerun()
        st.caption("Your game results continue to save to your existing progress records when supported.")

    else:
        selected_meta = next((g for g in arcade_games if g["id"] == selected_game), None)
        if selected_meta is None:
            st.session_state.selected_arcade_game = None
            st.rerun()
        back_col, title_col = st.columns([1, 3])
        with back_col:
            if st.button("← Arcade", key="back_to_arcade"):
                st.session_state.selected_arcade_game = None
                st.rerun()
        with title_col:
            st.markdown(f"<div style='padding:7px 0 0;font-weight:800;font-size:1.1rem'>{selected_meta['emoji']} {esc(selected_meta['name'])}</div>", unsafe_allow_html=True)

        if selected_game == "Code & Conquer":
            # Questions are deliberately authored locally. No network or AI service is used.
            dungeon_bank = {
                "Mathematics": [
                    ("What is 12 × 7?", ["72", "84", "96", "81"], "84", "12 groups of 7 make 84."),
                    ("What is the square root of 144?", ["10", "11", "12", "14"], "12", "12 × 12 = 144."),
                    ("What is 25% of 200?", ["25", "40", "50", "75"], "50", "25% is one quarter; 200 ÷ 4 = 50."),
                    ("Solve: 3x = 27", ["6", "8", "9", "12"], "9", "Divide both sides by 3: x = 9."),
                    ("What is the area of a rectangle 8 cm by 5 cm?", ["13 cm²", "26 cm²", "40 cm²", "80 cm²"], "40 cm²", "Area = length × breadth = 8 × 5 = 40 cm²."),
                ],
                "Science": [
                    ("Which gas do plants absorb during photosynthesis?", ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], "Carbon dioxide", "Plants use carbon dioxide and water to make sugars using light energy."),
                    ("What is the SI unit of force?", ["Joule", "Watt", "Newton", "Pascal"], "Newton", "Force is measured in newtons (N)."),
                    ("Which part of a cell contains most genetic material?", ["Cell wall", "Nucleus", "Cytoplasm", "Vacuole"], "Nucleus", "In typical plant and animal cells, most genetic material is in the nucleus."),
                    ("At standard atmospheric pressure, water boils at what temperature?", ["0°C", "50°C", "100°C", "150°C"], "100°C", "At standard atmospheric pressure, water boils at 100°C."),
                    ("Which particle has a negative electric charge?", ["Proton", "Neutron", "Electron", "Nucleus"], "Electron", "Electrons carry a negative electric charge."),
                ],
                "Vocabulary": [
                    ("Which word is closest in meaning to 'rapid'?", ["Slow", "Quick", "Quiet", "Weak"], "Quick", "Rapid means happening at a fast speed."),
                    ("What is the opposite of 'ancient'?", ["Old", "Historic", "Modern", "Traditional"], "Modern", "Modern means relating to the present or recent times."),
                    ("Choose the correctly spelled word.", ["Enviroment", "Envirnoment", "Environment", "Environmant"], "Environment", "Environment is the standard spelling."),
                    ("A person who writes poems is a...", ["Painter", "Poet", "Pilot", "Editor"], "Poet", "A poet writes poetry."),
                    ("What does 'observe' mean?", ["To notice carefully", "To forget", "To damage", "To predict randomly"], "To notice carefully", "To observe is to watch or examine carefully."),
                ],
            }

            if "dungeon_run" not in st.session_state:
                st.session_state.dungeon_run = None

            run = st.session_state.dungeon_run
            if run is None:
                st.subheader("Prepare your hero")
                hero_class = st.radio("Choose your class", ["Mage", "Rogue", "Warrior"], horizontal=True,
                                      help="Mage: extra damage on Science. Rogue: extra damage on Vocabulary. Warrior: extra damage on Mathematics.")
                subject = st.selectbox("Choose your study path", list(dungeon_bank.keys()))
                st.caption({"Mage": "Arcane focus · bonus damage on Science questions", "Rogue": "Quick thinking · bonus damage on Vocabulary questions", "Warrior": "Mighty intellect · bonus damage on Mathematics questions"}[hero_class])
                if st.button("Enter the dungeon", type="primary", use_container_width=True):
                    st.session_state.dungeon_run = {
                        "hero": hero_class, "subject": subject, "hp": 5, "max_hp": 5,
                        "gold": 0, "wins": 0, "streak": 0, "floor": 1,
                        "monster_hp": 1, "boss": False, "boss_stage": 0,
                        "gear": ["Apprentice cloak"], "question": random.choice(dungeon_bank[subject]),
                        "question_id": uuid.uuid4().hex, "finished": False, "victory": False,
                        "feedback": "", "last_reward": ""
                    }
                    st.rerun()
            else:
                run = st.session_state.dungeon_run
                if run["finished"]:
                    st.subheader("Dungeon complete" if run["victory"] else "Adventure ended")
                    st.metric("Gold collected", run["gold"])
                    st.write(f"Rooms cleared: {run['wins']} · Gear collected: {len(run['gear'])}")
                    st.write("Your gear: " + " · ".join(run["gear"]))
                    if student and not run.get("saved"):
                        execute("INSERT INTO attempts(student_id,topic,score,total,attempted_at) VALUES(?,?,?,?,?)",
                                (student["student_id"], "Syntax Dungeon · " + run["subject"], run["wins"], max(1, run["wins"] + (1 if not run["victory"] else 0)), now_text()))
                        run["saved"] = True
                        st.caption("Adventure result saved to your progress.")
                    if st.button("Start a new adventure", type="primary"):
                        st.session_state.dungeon_run = None
                        st.rerun()
                else:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1: st.metric("Health", f"{run['hp']}/{run['max_hp']} ❤️")
                    with col2: st.metric("Gold", f"{run['gold']} 🪙")
                    with col3: st.metric("Combo", f"{run['streak']} 🔥")
                    with col4: st.metric("Floor", run["floor"])
                    st.caption(f"{run['hero']} · {run['subject']} path · Gear: {', '.join(run['gear'])}")

                    if run["boss"]:
                        st.markdown(f"### 🐉 Dungeon Boss · Stage {run['boss_stage']}/3")
                        st.progress(run["boss_stage"] / 3)
                        st.write("Three consecutive correct answers are needed to defeat the boss. A wrong answer breaks your combo.")
                    else:
                        st.markdown(f"### ⚔️ Floor {run['floor']} · Shadow Sentinel")
                        st.caption("The monster blocks the passage. Answer correctly to strike!")

                    q = run["question"]
                    with st.form("dungeon_question_" + run["question_id"]):
                        st.markdown("#### " + q[0])
                        choice = st.radio("Choose your answer", q[1], key="dungeon_answer_" + run["question_id"])
                        submitted = st.form_submit_button("Cast attack", type="primary", use_container_width=True)
                    if submitted:
                        correct = choice == q[2]
                        if correct:
                            run["streak"] += 1
                            bonus = 1 if ((run["hero"] == "Mage" and run["subject"] == "Science") or (run["hero"] == "Rogue" and run["subject"] == "Vocabulary") or (run["hero"] == "Warrior" and run["subject"] == "Mathematics")) else 0
                            damage = 1 + bonus + (1 if run["streak"] >= 3 else 0)
                            run["gold"] += 10 + (5 if run["streak"] >= 3 else 0)
                            run["wins"] += 1
                            run["feedback"] = "hit"
                            run["last_reward"] = f"Correct! Your attack dealt {damage} damage. {q[3]}"
                            if run["boss"]:
                                run["boss_stage"] += 1
                                if run["boss_stage"] >= 3:
                                    run["finished"] = True
                                    run["victory"] = True
                                    run["gold"] += 50
                                    run["gear"].append("Dragonheart crown")
                            else:
                                run["floor"] += 1
                                if run["wins"] % 3 == 0:
                                    loot = random.choice(["Scholar's ring", "Focus crystal", "Ironbound boots", "Rune-bound staff"])
                                    if loot not in run["gear"]: run["gear"].append(loot)
                                    run["last_reward"] += f" Loot found: {loot}!"
                                if run["wins"] >= 5:
                                    run["boss"] = True
                                    run["boss_stage"] = 0
                        else:
                            run["hp"] -= 1
                            run["streak"] = 0
                            run["feedback"] = "miss"
                            run["last_reward"] = f"The monster counterattacks! Correct answer: {q[2]}. {q[3]}"
                            if run["boss"]:
                                run["boss_stage"] = 0
                            if run["hp"] <= 0:
                                run["finished"] = True
                                run["victory"] = False
                        if not run["finished"]:
                            run["question"] = random.choice(dungeon_bank[run["subject"]])
                            run["question_id"] = uuid.uuid4().hex
                        st.rerun()

                    if run["feedback"]:
                        if run["feedback"] == "hit": st.success(run["last_reward"])
                        else: st.warning(run["last_reward"])
                    if st.button("Leave dungeon", key="leave_dungeon"):
                        run["finished"] = True
                        run["victory"] = False
                        st.rerun()

        else:
            game = selected_game
            if game == "Flashcard practice":
                import time as _time

                diagrams = [
                    {"id": "plant", "name": "Plant cell", "tier": "Foundation",
                     "svg": '<svg viewBox="0 0 160 105"><rect x="12" y="12" width="136" height="81" rx="18" fill="#d8f0c8" stroke="#397b45" stroke-width="4"/><circle cx="48" cy="48" r="15" fill="#8bcf76" stroke="#397b45" stroke-width="2"/><circle cx="48" cy="48" r="6" fill="#397b45"/><ellipse cx="101" cy="51" rx="29" ry="19" fill="#b7dff0" stroke="#4285a5" stroke-width="2"/><circle cx="121" cy="27" r="6" fill="#e3a34b"/></svg>'},
                    {"id": "animal", "name": "Animal cell", "tier": "Foundation",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M23 55 C15 22 57 8 91 19 C132 7 151 42 133 73 C113 101 47 99 25 76Z" fill="#f5d7dc" stroke="#a64f70" stroke-width="3"/><circle cx="79" cy="52" r="19" fill="#b9a3df" stroke="#7459a5" stroke-width="2"/><circle cx="79" cy="52" r="7" fill="#7459a5"/><ellipse cx="42" cy="39" rx="10" ry="5" fill="#e5a35b"/><ellipse cx="111" cy="69" rx="11" ry="5" fill="#e5a35b"/></svg>'},
                    {"id": "heart", "name": "Human heart", "tier": "Foundation",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M80 87 C65 72 27 49 39 25 C48 7 70 16 80 33 C91 14 116 8 126 27 C139 52 101 76 80 87Z" fill="#dc6870" stroke="#8e3444" stroke-width="3"/><path d="M77 34 L77 14 M91 34 L101 12 M66 48 L54 35" stroke="#376c9c" stroke-width="7" stroke-linecap="round"/><path d="M83 40 L87 70" stroke="#f5b2ad" stroke-width="4"/></svg>'},
                    {"id": "brain", "name": "Human brain", "tier": "Foundation",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M78 17 C58 3 43 20 47 34 C26 32 24 58 42 66 C33 86 59 96 75 80 C91 98 115 83 109 68 C134 59 126 35 109 32 C108 12 88 8 78 17Z" fill="#e9a7b5" stroke="#995b75" stroke-width="3"/><path d="M79 18 Q69 37 80 51 Q68 65 76 83 M51 35 Q69 40 62 54 M107 34 Q91 40 100 55 M44 67 Q61 61 67 77 M111 66 Q94 61 92 81" fill="none" stroke="#995b75" stroke-width="2.5"/></svg>'},
                    {"id": "neuron", "name": "Neuron", "tier": "Foundation",
                     "svg": '<svg viewBox="0 0 160 105"><circle cx="65" cy="52" r="17" fill="#f2c66d" stroke="#a77a27" stroke-width="3"/><circle cx="65" cy="52" r="6" fill="#a77a27"/><g stroke="#b27c30" stroke-width="3" fill="none" stroke-linecap="round"><path d="M50 40 L31 22 L16 20 M49 53 L25 53 L12 43 M52 65 L31 82 L17 88 M78 52 L111 52 L128 42 L145 42 M97 52 L111 65 L127 65"/></g><g fill="#f2c66d" stroke="#a77a27" stroke-width="2"><circle cx="31" cy="22" r="4"/><circle cx="16" cy="20" r="3"/><circle cx="12" cy="43" r="3"/></g></svg>'},
                    {"id": "lungs", "name": "Human lungs", "tier": "Foundation",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M78 12 L78 46 M84 12 L84 46" stroke="#d49a55" stroke-width="7"/><path d="M80 40 L54 56 M80 40 L106 56" stroke="#d49a55" stroke-width="5" fill="none"/><path d="M53 32 C30 30 18 69 31 88 C43 101 66 86 70 62 L70 45Z" fill="#ef9d9d" stroke="#a94f61" stroke-width="3"/><path d="M107 32 C130 30 142 69 129 88 C117 101 94 86 90 62 L90 45Z" fill="#ef9d9d" stroke="#a94f61" stroke-width="3"/></svg>'},
                    {"id": "kidney", "name": "Kidney", "tier": "Core",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M85 13 C45 3 25 35 34 69 C42 99 78 91 88 69 C99 48 78 42 78 29 C78 21 91 23 101 31 C111 15 98 12 85 13Z" fill="#b85d65" stroke="#783b49" stroke-width="3"/><path d="M84 48 Q110 49 112 78 L112 96" fill="none" stroke="#e0b65e" stroke-width="6"/><path d="M83 49 L102 44" stroke="#e0b65e" stroke-width="4"/></svg>'},
                    {"id": "eye", "name": "Human eye", "tier": "Core",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M13 53 Q80 -1 147 53 Q80 107 13 53Z" fill="#f5f5ed" stroke="#55758a" stroke-width="3"/><circle cx="80" cy="53" r="25" fill="#72b7bd" stroke="#39747d" stroke-width="3"/><circle cx="80" cy="53" r="12" fill="#263d51"/><circle cx="88" cy="44" r="5" fill="white"/></svg>'},
                    {"id": "ear", "name": "Human ear", "tier": "Core",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M93 89 C62 105 49 78 57 60 C35 40 51 11 79 12 C115 10 127 46 108 64 C98 74 100 84 93 89Z" fill="#e8b5a0" stroke="#9a675c" stroke-width="3"/><path d="M91 76 C78 83 69 68 79 56 C96 43 92 27 78 28 C66 28 62 39 68 47 M79 67 Q90 58 84 49" fill="none" stroke="#9a675c" stroke-width="4" stroke-linecap="round"/></svg>'},
                    {"id": "skeleton", "name": "Human skeleton", "tier": "Core",
                     "svg": '<svg viewBox="0 0 160 105"><g stroke="#8b8170" stroke-width="4" fill="none" stroke-linecap="round"><circle cx="80" cy="16" r="11" fill="#eee7d7"/><path d="M80 28 L80 65 M62 38 L98 38 M62 38 L48 65 M98 38 L112 65 M80 65 L61 91 M80 65 L99 91"/><path d="M69 42 Q80 53 91 42 M69 49 Q80 60 91 49 M70 57 Q80 67 90 57"/></g></svg>'},
                    {"id": "digestive", "name": "Digestive system", "tier": "Core",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M77 8 L77 35" stroke="#d49a55" stroke-width="7"/><path d="M77 35 C54 35 48 55 66 62 C85 70 107 51 96 42 C90 37 83 42 82 48" fill="#e99c75" stroke="#9d5d49" stroke-width="3"/><path d="M72 64 C42 58 46 91 70 88 C94 85 112 91 115 73 C117 58 97 61 91 72 C83 84 65 72 72 64Z" fill="none" stroke="#b77c57" stroke-width="6"/></svg>'},
                    {"id": "flower", "name": "Flower structure", "tier": "Core",
                     "svg": '<svg viewBox="0 0 160 105"><g fill="#e9a4c2" stroke="#a65d83" stroke-width="2"><ellipse cx="80" cy="25" rx="12" ry="20"/><ellipse cx="80" cy="65" rx="12" ry="20"/><ellipse cx="58" cy="45" rx="20" ry="12"/><ellipse cx="102" cy="45" rx="20" ry="12"/></g><circle cx="80" cy="45" r="11" fill="#efc75c" stroke="#a77d27" stroke-width="2"/><path d="M80 76 L80 102 M80 88 Q54 75 48 88 M80 92 Q104 75 111 87" stroke="#498b55" stroke-width="4" fill="none"/></svg>'},
                    {"id": "dna", "name": "DNA double helix", "tier": "Challenge",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M48 8 C125 28 35 76 112 97 M112 8 C35 28 125 76 48 97" fill="none" stroke="#4c8bb5" stroke-width="5"/><g stroke="#c58b45" stroke-width="3"><path d="M61 17 L99 17 M70 31 L90 31 M70 46 L90 46 M61 61 L99 61 M53 77 L107 77 M49 91 L111 91"/></g></svg>'},
                    {"id": "circuit", "name": "Electric circuit", "tier": "Challenge",
                     "svg": '<svg viewBox="0 0 160 105"><g stroke="#527e9a" stroke-width="3" fill="none"><path d="M20 52 L48 52 M70 52 L91 52 M112 52 L140 52 L140 84 L20 84 L20 52"/><path d="M48 42 L48 62 M58 35 L58 69"/></g><path d="M91 52 L98 42 L105 62 L112 52" fill="none" stroke="#bd8542" stroke-width="3"/><circle cx="101" cy="84" r="9" fill="#f3cf69" stroke="#a77d27" stroke-width="2"/></svg>'},
                    {"id": "leaf", "name": "Leaf structure", "tier": "Challenge",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M20 82 C27 20 92 4 140 17 C132 74 75 104 20 82Z" fill="#9bcf85" stroke="#4d8b52" stroke-width="3"/><path d="M20 82 Q76 56 140 17 M62 65 L52 39 M83 55 L91 30 M104 42 L122 45 M45 72 L37 59" fill="none" stroke="#4d8b52" stroke-width="2.5"/></svg>'},
                    {"id": "stomata", "name": "Stomata", "tier": "Challenge",
                     "svg": '<svg viewBox="0 0 160 105"><path d="M66 15 C26 14 29 91 66 89 C79 87 78 17 66 15Z" fill="#8bcf8c" stroke="#43834e" stroke-width="3"/><path d="M94 15 C134 14 131 91 94 89 C81 87 82 17 94 15Z" fill="#8bcf8c" stroke="#43834e" stroke-width="3"/><path d="M80 24 L80 80" stroke="#4b8d56" stroke-width="3" stroke-dasharray="4 4"/><circle cx="49" cy="50" r="3" fill="#43834e"/><circle cx="111" cy="50" r="3" fill="#43834e"/></svg>'}
                ]

                if "memory_sprint_run" not in st.session_state:
                    st.session_state.memory_sprint_run = None

                run = st.session_state.memory_sprint_run

                st.markdown("""
                <style>
                .ms-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}
                .ms-tile{background:#fff;border:1px solid #dce5df;border-radius:13px;padding:8px;text-align:center;min-width:0}
                .ms-art svg{width:100%;height:88px}
                .ms-name{font-size:12px;font-weight:700;color:#34463b;padding:3px 0 5px}
                .ms-number{font-size:22px;font-weight:800;color:#426b55;padding:14px 0}
                .ms-intro{background:#eef4ef;border:1px solid #dce7dd;border-radius:15px;padding:18px;margin:10px 0}
                @media(max-width:600px){.ms-grid{gap:6px}.ms-art svg{height:65px}.ms-tile{padding:5px}.ms-name{font-size:10px}}
                </style>
                """, unsafe_allow_html=True)

                if run is None:
                    st.markdown(
                        '<div class="ms-intro"><h3>🧠 Science Diagram Memory Challenge</h3>'
                        '<p>Study 16 original science diagrams, memorize their positions in 3 seconds, '
                        'then identify each one from a numbered grid.</p>'
                        '<b>16 questions · 100 points each · No repeated questions</b></div>',
                        unsafe_allow_html=True
                    )
                    if st.button("Start Memory Sprint", key="memory_sprint_start", use_container_width=True):
                        cards = [dict(item) for item in diagrams]
                        positions = random.sample(range(1, 17), 16)
                        for item, slot in zip(cards, positions):
                            item["slot"] = slot
                        questions = []
                        for tier in ("Foundation", "Core", "Challenge"):
                            group = [item for item in cards if item["tier"] == tier]
                            questions.extend(random.sample(group, len(group)))
                        st.session_state.memory_sprint_run = {
                            "cards": cards, "questions": questions, "index": 0,
                            "score": 0, "phase": "memorize", "selected": None,
                            "saved": False
                        }
                        st.rerun()

                else:
                    if run["phase"] == "memorize":
                        st.markdown("### Memorize the diagrams")
                        st.caption("Look carefully at each diagram and its position. You have 3 seconds once you start the scan.")
                        ordered = sorted(run["cards"], key=lambda item: item["slot"])
                        tiles = []
                        for item in ordered:
                            tiles.append(
                                '<div class="ms-tile"><div class="ms-art">' + item["svg"] +
                                '</div><div class="ms-name">' + esc(item["name"]) + '</div></div>'
                            )
                        st.markdown('<div class="ms-grid">' + ''.join(tiles) + '</div>', unsafe_allow_html=True)
                        if st.button("Start 3-second scan", key="memory_sprint_scan", use_container_width=True):
                            timer = st.empty()
                            for remaining in (3, 2, 1):
                                timer.progress((4 - remaining) / 3, text=f"Memorize the diagrams · {remaining}")
                                _time.sleep(1)
                            timer.empty()
                            run["phase"] = "question"
                            st.rerun()

                    elif run["phase"] == "question":
                        index = run["index"]
                        question = run["questions"][index]
                        st.progress(index / 16, text=f"Question {index + 1} of 16")
                        st.markdown(f"### Which card showed the **{esc(question['name'])}**?")
                        st.caption(f"Difficulty: {question['tier']} · Choose one numbered card.")
                        st.markdown('<div class="ms-grid">' + ''.join(
                            f'<div class="ms-tile"><div class="ms-number">{n:02d}</div></div>'
                            for n in range(1, 17)
                        ) + '</div>', unsafe_allow_html=True)

                        for row in range(4):
                            cols = st.columns(4)
                            for col_index, col in enumerate(cols):
                                slot = row * 4 + col_index + 1
                                with col:
                                    if st.button(f"Card {slot:02d}", key=f"memory_pick_{index}_{slot}", use_container_width=True):
                                        run["selected"] = slot
                                        run["correct"] = slot == question["slot"]
                                        if run["correct"]:
                                            run["score"] += 1
                                        run["phase"] = "feedback"
                                        st.rerun()

                    elif run["phase"] == "feedback":
                        index = run["index"]
                        question = run["questions"][index]
                        if run["correct"]:
                            st.success("Correct! +100 points")
                        else:
                            st.error(f"Not quite. The {question['name']} was card {question['slot']:02d}.")
                        st.markdown(f"**Your choice:** Card {run['selected']:02d} · **Correct card:** {question['slot']:02d}")
                        st.markdown(f"**Score:** {run['score'] * 100} points")
                        st.progress((index + 1) / 16, text=f"Completed {index + 1} of 16 questions")
                        if st.button("Next question →", key="memory_next", use_container_width=True):
                            run["index"] += 1
                            run["selected"] = None
                            if run["index"] >= 16:
                                run["phase"] = "complete"
                            else:
                                run["phase"] = "question"
                            st.rerun()

                    elif run["phase"] == "complete":
                        if not run["saved"]:
                            execute(
                                "INSERT INTO attempts(student_id,topic,score,total,attempted_at) VALUES(?,?,?,?,?)",
                                (student["student_id"], "Memory Sprint — Science Diagrams",
                                 run["score"], 16, now_text())
                            )
                            run["saved"] = True

                        points = run["score"] * 100
                        accuracy = round(run["score"] * 100 / 16)
                        st.balloons()
                        st.markdown("### Challenge complete!")
                        st.metric("Total points", f"{points:,} / 1,600")
                        c1, c2 = st.columns(2)
                        c1.metric("Correct answers", f"{run['score']} / 16")
                        c2.metric("Accuracy", f"{accuracy}%")
                        st.progress(run["score"] / 16, text="Your final accuracy")
                        st.caption("Your completed run has been added to your existing progress records.")
                        if st.button("Play again", key="memory_play_again", use_container_width=True):
                            st.session_state.memory_sprint_run = None
                            st.rerun()
            elif game == "Quick maths":
                if "math_game" not in st.session_state:
                    a, b = random.randint(2, 15), random.randint(2, 12)
                    st.session_state.math_game = {"a": a, "b": b, "answer": a*b}
                m = st.session_state.math_game
                st.markdown(f"### ⚡ {m['a']} × {m['b']} = ?")
                guess = st.number_input("Your answer", min_value=0, max_value=1000, step=1, key="math_guess")
                if st.button("Check answer", key="check_math_game"):
                    if int(guess) == m["answer"]: st.success("Correct. Your calculation speed is improving!")
                    else: st.info("Not quite. Try again, or generate a new question.")
                if st.button("New maths question", key="new_math_game"):
                    a, b = random.randint(2, 15), random.randint(2, 12)
                    st.session_state.math_game = {"a": a, "b": b, "answer": a*b}
                    st.rerun()

            elif game == "Science word scramble":
                pairs = [("chlorophyll", "Green pigment that helps plants absorb light"), ("gravity", "Attractive force between masses"),
                         ("evaporation", "Liquid changing into vapour"), ("friction", "Force that opposes motion"),
                         ("condensation", "Gas changing into liquid")]
                if "scramble" not in st.session_state:
                    word, clue = random.choice(pairs)
                    st.session_state.scramble = {"word": word, "clue": clue}
                item = st.session_state.scramble
                scrambled = "".join(random.sample(item["word"], len(item["word"])))
                st.markdown(f"### 🧩 Unscramble: `{scrambled}`")
                st.caption("Clue: " + item["clue"])
                guess = st.text_input("Your word", key="scramble_guess")
                if st.button("Check word", key="check_scramble"):
                    if guess.strip().lower() == item["word"]: st.success("Correct! Science vocabulary unlocked.")
                    else: st.info("Not quite. Use the clue and try again.")
                if st.button("New word", key="new_scramble"):
                    word, clue = random.choice(pairs)
                    st.session_state.scramble = {"word": word, "clue": clue}
                    st.rerun()

            else:  # Cipher Heist — standalone 2D Pygame experience
                st.markdown("""
                <style>
                .heist-banner{padding:22px;border-radius:18px;background:linear-gradient(120deg,#102b42,#18213d 62%,#34244d);border:1px solid rgba(95,205,220,.25);color:#f4f8ff}
                .heist-banner .eyebrow{font-size:.68rem;font-weight:800;letter-spacing:1.5px;color:#71e2dc}
                .heist-banner h2{margin:.45rem 0;font-size:1.65rem}
                .heist-banner p{margin:0;color:#c1d0e3;max-width:650px}
                </style>
                <div class="heist-banner"><div class="eyebrow">2D PUZZLE ADVENTURE · PYGAME</div>
                <h2>🔐 Cipher Heist: The Knowledge Vault</h2>
                <p>Enter a hand-built 2D vault world. Crack five security layers using patterns, number ciphers and logic. Earn points, use one hint token, and unlock the vault.</p></div>
                """, unsafe_allow_html=True)
                game_script = APP_DIR / "CipherHeist_Enhanced.py"
                result_file = DATA_DIR / "cipher_heist_result.json"
                left, right = st.columns(2)
                with left:
                    st.markdown("**MISSION BRIEFING**")
                    st.write("• 5 illustrated puzzle rooms")
                    st.write("• Keyboard and mouse controls")
                    st.write("• 20 points per clean solve; 10 with a hint")
                    st.write("• Your completed score can be imported into Progress")
                with right:
                    st.markdown("**BEFORE YOU PLAY**")
                    st.write("The game opens in a separate desktop window. Keep LifeBridgeAI running in the background.")
                    st.caption("First-time setup requires the free Pygame package.")
                if st.button("🚀 Launch 2D Cipher Heist", type="primary", use_container_width=True, key="launch_pygame_cipher"):
                    if not game_script.exists():
                        st.error("cipher_heist_game.py is missing. Place it beside app.py in your LifeBridgeAI folder.")
                    else:
                        try:
                            subprocess.Popen([sys.executable, str(game_script)], cwd=str(APP_DIR))
                            st.success("Cipher Heist launched. Finish the game in its separate window, then return here to import your score.")
                        except Exception as exc:
                            st.error(f"Could not launch Pygame: {exc}")
                if st.button("📥 Import latest completed score", key="import_pygame_cipher"):
                    if not result_file.exists():
                        st.info("No completed game result found yet. Finish a run in the Pygame window first.")
                    else:
                        try:
                            result = json.loads(result_file.read_text(encoding="utf-8"))
                            run_id = str(result.get("run_id", ""))
                            imported = st.session_state.get("cipher_imported_runs", [])
                            if not run_id or run_id in imported:
                                st.info("This result has already been imported.")
                            else:
                                score = max(0, min(100, int(result.get("score", 0))))
                                if student:
                                    execute("INSERT INTO attempts(student_id,topic,score,total,attempted_at) VALUES(?,?,?,?,?)",
                                            (student["student_id"], "Cipher Heist: Pygame", score, 100, now_text()))
                                    st.session_state.cipher_imported_runs = imported + [run_id]
                                    st.success(f"Imported: {score}/100 points ({score}/100 points) saved to your progress.")
                                else:
                                    st.warning("Create a learner profile to save this score. The result file is still available.")
                        except (OSError, ValueError, TypeError, KeyError) as exc:
                            st.error(f"Could not read the game result: {exc}")
                st.caption("Pygame is a separate desktop game window; the rest of LifeBridgeAI continues to run in Streamlit.")

# ---------------------------- PAGE: PROGRESS ----------------------------

elif page == "Progress Detector":
    st.title("Progress Detector")
    if not require_student():
        st.stop()
    attempts = query_all("SELECT * FROM attempts WHERE student_id=? ORDER BY attempted_at", (student["student_id"],))
    tasks = query_all("SELECT * FROM tasks WHERE student_id=?", (student["student_id"],))
    sessions = query_all("SELECT * FROM study_sessions WHERE student_id=? ORDER BY studied_on", (student["student_id"],))
    total_q = sum(x["total"] for x in attempts)
    total_correct = sum(x["score"] for x in attempts)
    accuracy = round(100 * total_correct / total_q) if total_q else 0
    cols = st.columns(3)
    with cols[0]: stat_card("Quiz accuracy", accuracy, "%")
    with cols[1]: stat_card("Quiz attempts", len(attempts))
    with cols[2]: stat_card("Tasks completed", sum(x["completed"] for x in tasks))
    st.subheader("Quiz history")
    if attempts:
        import pandas as pd
        frame = pd.DataFrame([{"Attempt": i+1, "Topic": a["topic"], "Score (%)": round(100*a["score"]/a["total"]), "Date": a["attempted_at"][:10]} for i, a in enumerate(attempts)])
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.line_chart(frame.set_index("Attempt")["Score (%)"])
    else:
        st.info("Complete a quiz to start building your progress history.")
    st.subheader("Study time")
    with st.form("study_log"):
        subject = st.selectbox("Subject studied", ["Science", "Mathematics", "Social Science", "English", "Computer", "Other"])
        minutes = st.number_input("Minutes studied", min_value=5, max_value=600, value=30, step=5)
        log = st.form_submit_button("Save study session")
    if log:
        execute("INSERT INTO study_sessions(student_id,subject,minutes,studied_on) VALUES(?,?,?,?)",
                (student["student_id"], subject, int(minutes), date.today().isoformat()))
        st.success("Study session saved.")
        st.rerun()
    if sessions:
        st.metric("Total logged study time", f"{sum(x['minutes'] for x in sessions)} minutes")
        import pandas as pd
        study_frame = pd.DataFrame([{"Date": x["studied_on"], "Minutes": x["minutes"], "Subject": x["subject"]} for x in sessions])
        st.bar_chart(study_frame.groupby("Subject")["Minutes"].sum())

# ---------------------------- PAGE: LEADERBOARD ----------------------------

elif page == "Leaderboard":
    st.title("Leaderboard")
    st.caption("Rankings are calculated only from learner profiles saved in this app's local database. They are not global or online rankings.")
    rows = query_all("""
        SELECT s.student_id,s.name,s.grade,
               COALESCE(SUM(a.score),0) AS points,
               COALESCE(SUM(a.total),0) AS questions,
               COUNT(a.id) AS attempts
        FROM students s LEFT JOIN attempts a ON a.student_id=s.student_id
        GROUP BY s.student_id
        ORDER BY points DESC, attempts DESC, s.name COLLATE NOCASE
        LIMIT 50
    """)
    if rows:
        for rank, row in enumerate(rows, 1):
            mark = "🏆" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
            st.markdown(
                f'<div class="lb-card"><b>{mark} &nbsp; {esc(row["name"])}</b>'
                f'<span class="lb-muted"> · {esc(row["grade"])}</span>'
                f'<div class="lb-muted">{row["points"]} correct answers · {row["attempts"]} quiz attempts · {row["questions"]} questions</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Create a profile and complete a quiz to appear here.")

# ---------------------------- PAGE: PROFILE ----------------------------

elif page == "My Profile":
    st.title("My Profile")
    if not require_student():
        with st.form("create_profile_profile"):
            name = st.text_input("Student name")
            grade = st.selectbox("Class / grade", ["Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Other"])
            school = st.text_input("School (optional)")
            language = st.selectbox("Preferred language", ["English", "Hindi", "Punjabi"])
            submit = st.form_submit_button("Create profile")
        if submit:
            if name.strip():
                create_student(name, grade, school, language)
                st.rerun()
            else:
                st.error("Enter your name.")
    else:
        st.markdown('<div class="lb-card">', unsafe_allow_html=True)
        st.write("**Student name:**", student["name"])
        st.write("**Student ID:**", student["student_id"])
        st.write("**Class:**", student["grade"])
        st.write("**School:**", student["school"] or "Not provided")
        st.write("**Preferred language:**", student["language"])
        st.write("**Profile created:**", student["created_at"][:10])
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Your information is stored locally in lifebridge_data/lifebridge.db on this computer.")
        with st.form("edit_profile"):
            new_name = st.text_input("Update name", value=student["name"])
            new_grade = st.selectbox("Update class", ["Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Other"], index=["Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Other"].index(student["grade"]) if student["grade"] in ["Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Other"] else 5)
            new_school = st.text_input("Update school", value=student["school"])
            new_language = st.selectbox("Update language", ["English", "Hindi", "Punjabi"], index=["English", "Hindi", "Punjabi"].index(student["language"]) if student["language"] in ["English", "Hindi", "Punjabi"] else 0)
            save = st.form_submit_button("Save profile")
        if save:
            if new_name.strip():
                execute("UPDATE students SET name=?,grade=?,school=?,language=? WHERE student_id=?",
                        (new_name.strip(), new_grade, new_school.strip(), new_language, student["student_id"]))
                st.success("Profile updated.")
                st.rerun()
            else:
                st.error("Name cannot be empty.")



# ---------------------------- PAGE: MERYCLE CHATBOT ----------------------------



elif page == "Calculator":
    import ast
    import math
    import re

    st.markdown("""
    <style>
    .calc-display {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 18px;
        padding: 20px 22px;
        min-height: 88px;
        text-align: right;
        margin-bottom: 12px;
    }
    .calc-expression {
        color: var(--text-color);
        font-size: 30px;
        font-weight: 600;
        overflow-wrap: anywhere;
    }
    div.stButton > button {
        border-radius: 16px;
        min-height: 48px;
        font-size: 16px;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("Scientific Calculator")
    st.caption("Everyday and scientific calculations in one place.")

    if "calc_expression" not in st.session_state:
        st.session_state.calc_expression = ""

    if "calc_answer" not in st.session_state:
        st.session_state.calc_answer = 0

    if "calc_history" not in st.session_state:
        st.session_state.calc_history = []

    if "calc_degrees" not in st.session_state:
        st.session_state.calc_degrees = True

    def calc_press(value):
        current = st.session_state.calc_expression

        if value == "AC":
            st.session_state.calc_expression = ""
        elif value == "DEL":
            st.session_state.calc_expression = current[:-1]
        elif value == "Ans":
            st.session_state.calc_expression += str(st.session_state.calc_answer)
        elif value == "π":
            st.session_state.calc_expression += "pi"
        elif value == "e":
            st.session_state.calc_expression += "e"
        elif value == "√":
            st.session_state.calc_expression += "sqrt("
        elif value in ("sin", "cos", "tan", "ln", "log", "abs"):
            st.session_state.calc_expression += value + "("
        elif value == "x!":
            st.session_state.calc_expression += "!"
        elif value == "xʸ":
            st.session_state.calc_expression += "^"
        elif value == "EXP":
            st.session_state.calc_expression += "*10^"
        elif value == "Deg/Rad":
            st.session_state.calc_degrees = not st.session_state.calc_degrees
        elif value == "=":
            calculate_expression()
        else:
            st.session_state.calc_expression += value

    def calculate_expression():
        expression = st.session_state.calc_expression.strip()

        if not expression:
            return

        if len(expression) > 200:
            st.error("Expression is too long.")
            return

        expression = expression.replace("×", "*").replace("÷", "/")
        expression = expression.replace("^", "**")
        expression = re.sub(r"(?<=\d)\s*%", "/100", expression)
        expression = re.sub(r"(\d+(?:\.\d+)?)!", r"factorial(\1)", expression)

        if st.session_state.calc_degrees:
            expression = re.sub(
                r"\b(sin|cos|tan)\(([^()]*)\)",
                lambda m: f"{m.group(1)}(radians({m.group(2)}))",
                expression
            )

        allowed_functions = {
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "ln": math.log,
            "log": math.log10,
            "abs": abs,
            "factorial": math.factorial,
            "radians": math.radians,
        }

        allowed_names = {
            "pi": math.pi,
            "e": math.e,
            "Ans": st.session_state.calc_answer,
        }

        try:
            tree = ast.parse(expression, mode="eval")

            def evaluate(node, depth=0):
                if depth > 30:
                    raise ValueError("Expression is too complex.")

                if isinstance(node, ast.Expression):
                    return evaluate(node.body, depth + 1)

                if isinstance(node, ast.Constant):
                    if type(node.value) not in (int, float):
                        raise ValueError("Invalid number.")
                    return node.value

                if isinstance(node, ast.Name):
                    if node.id not in allowed_names:
                        raise ValueError("Unknown symbol.")
                    return allowed_names[node.id]

                if isinstance(node, ast.UnaryOp):
                    value = evaluate(node.operand, depth + 1)
                    if isinstance(node.op, ast.UAdd):
                        return value
                    if isinstance(node.op, ast.USub):
                        return -value
                    raise ValueError("Unsupported operation.")

                if isinstance(node, ast.BinOp):
                    left = evaluate(node.left, depth + 1)
                    right = evaluate(node.right, depth + 1)

                    if isinstance(node.op, ast.Add):
                        return left + right
                    if isinstance(node.op, ast.Sub):
                        return left - right
                    if isinstance(node.op, ast.Mult):
                        return left * right
                    if isinstance(node.op, ast.Div):
                        return left / right
                    if isinstance(node.op, ast.Mod):
                        return left % right
                    if isinstance(node.op, ast.Pow):
                        if abs(right) > 12 or abs(left) > 1e12:
                            raise ValueError("Power is outside the allowed range.")
                        return left ** right

                    raise ValueError("Unsupported operation.")

                if isinstance(node, ast.Call):
                    if not isinstance(node.func, ast.Name):
                        raise ValueError("Unsupported function.")
                    function = allowed_functions.get(node.func.id)
                    if function is None or node.keywords or len(node.args) != 1:
                        raise ValueError("Unsupported function or arguments.")
                    return function(evaluate(node.args[0], depth + 1))

                raise ValueError("Invalid expression.")

            result = evaluate(tree)

            if type(result) not in (int, float) or not math.isfinite(result):
                raise ValueError("Result is outside the supported range.")

            if abs(result) > 1e100:
                raise ValueError("Result is too large.")

            st.session_state.calc_answer = result
            formatted = f"{result:,.12g}"
            st.session_state.calc_history.insert(
                0, (st.session_state.calc_expression, formatted)
            )
            st.session_state.calc_history = st.session_state.calc_history[:10]
            st.session_state.calc_expression = formatted

        except ZeroDivisionError:
            st.error("Cannot divide by zero.")
        except (ValueError, SyntaxError, OverflowError):
            st.error("Invalid expression. Please check your calculation.")

    st.markdown(
        f'<div class="calc-display"><div class="calc-expression">'
        f'{st.session_state.calc_expression or "0"}</div></div>',
        unsafe_allow_html=True
    )

    rows = [
        ["Deg/Rad", "x!", "(", ")", "%", "DEL", "AC"],
        ["Inv", "sin", "ln", "7", "8", "9", "÷"],
        ["π", "cos", "log", "4", "5", "6", "×"],
        ["e", "tan", "√", "1", "2", "3", "−"],
        ["Ans", "EXP", "xʸ", "0", ".", "=", "+"],
    ]

    for row_index, row in enumerate(rows):
        columns = st.columns(7, gap="small")
        for column_index, label in enumerate(row):
            with columns[column_index]:
                if label == "Deg/Rad":
                    shown_label = "Deg" if st.session_state.calc_degrees else "Rad"
                elif label == "−":
                    shown_label = "−"
                else:
                    shown_label = label

                st.button(
                    shown_label,
                    key=f"calc_key_{row_index}_{column_index}",
                    use_container_width=True,
                    type="primary" if label == "=" else "secondary",
                    on_click=calc_press,
                    args=(label,)
                )

    if st.session_state.calc_history:
        with st.expander("Calculation history"):
            for old_expression, old_answer in st.session_state.calc_history:
                st.write(f"{old_expression} = **{old_answer}**")

    st.caption("Scientific functions · DEG/RAD · Powers · Percentages · History")

elif page == "Translator":
    st.title("Translator")
    st.caption("Translate text between languages with Merycle's AI engine.")

    languages = [
        "Auto-detect", "English", "Hindi", "Punjabi", "Urdu",
        "Spanish", "French", "German", "Arabic", "Chinese",
        "Japanese", "Korean", "Portuguese", "Russian",
        "Bengali", "Gujarati", "Marathi", "Tamil", "Telugu"
    ]

    source_language = st.selectbox(
        "Translate from",
        languages,
        index=0,
        key="life_translator_source"
    )

    target_language = st.selectbox(
        "Translate into",
        [language for language in languages if language != "Auto-detect"],
        index=0,
        key="life_translator_target"
    )

    translation_text = st.text_area(
        "Enter text to translate",
        height=180,
        max_chars=5000,
        placeholder="Type or paste your text here...",
        key="life_translator_input"
    )

    if st.button("Translate", type="primary"):
        if not translation_text.strip():
            st.warning("Please enter some text first.")
        else:
            language_instruction = (
                "Detect the source language automatically"
                if source_language == "Auto-detect"
                else f"The source language is {source_language}"
            )

            prompt = f"""
Translate the following text accurately into {target_language}.
{language_instruction}.

Preserve the original meaning, tone, names, numbers, and formatting.
Return only the translated text. Do not add explanations.

TEXT:
{translation_text}
"""

            try:
                with st.spinner("Merycle is translating..."):
                    translated = gemini_generate(prompt, temperature=0.1)

                st.session_state["life_translator_result"] = translated
                st.success("Translation complete.")

            except Exception as error:
                st.error(f"Translation failed: {error}")

    translated_result = st.session_state.get("life_translator_result", "")

    if translated_result:
        st.markdown("### Translation")
        st.text_area(
            "Translated text",
            value=translated_result,
            height=180,
            key="life_translator_output"
        )

elif page == "Merycle Chatbot":

    import html

    st.markdown("""
    <style>
    /* MERYCLE — custom conversation interface */

    .merycle-header {
        display:flex;
        align-items:center;
        justify-content:space-between;
        padding:8px 0 19px;
        margin-bottom:25px;
        border-bottom:1px solid rgba(130,140,155,.16);
    }

    .merycle-brand {
        display:flex;
        flex-direction:column;
        gap:3px;
    }

    .merycle-title {
        font-size:1.22rem;
        font-weight:750;
        letter-spacing:-.7px;
        color:var(--text-color);
    }

    .merycle-subtitle {
        font-size:.76rem;
        color:rgba(130,140,150,.95);
    }

    .merycle-welcome {
        max-width:680px;
        margin:100px auto 65px;
        text-align:center;
    }

    .merycle-welcome h1 {
        font-size:clamp(2rem,5vw,2.8rem)!important;
        line-height:1.18!important;
        letter-spacing:-1.8px!important;
        font-weight:650!important;
        color:var(--text-color)!important;
        margin-bottom:15px!important;
    }

    .merycle-welcome p {
        font-size:.98rem;
        line-height:1.8;
        color:rgba(130,140,150,.95);
        max-width:480px;
        margin:0 auto;
    }

    /* User message bubble */
    .merycle-user-bubble {
        display:block;
        width:fit-content;
        max-width:100%;
        margin:0 0 0 auto;
        padding:12px 18px;
        border-radius:20px 20px 5px 20px;
        background:var(--secondary-background-color);
        border:1px solid rgba(130,145,165,.13);
        color:var(--text-color);
        font-size:.96rem;
        line-height:1.7;
        overflow-wrap:anywhere;
    }

    /* Assistant response */
    .merycle-assistant-label {
        color:rgba(130,140,150,.9);
        font-size:.69rem;
        font-weight:750;
        letter-spacing:1.5px;
        margin:2px 0 9px;
    }

    .merycle-assistant-content {
        font-size:.97rem;
        line-height:1.8;
        color:var(--text-color);
        overflow-wrap:anywhere;
    }

    .merycle-assistant-content p {
        line-height:1.8;
        margin-bottom:12px;
    }

    .merycle-assistant-content ul,
    .merycle-assistant-content ol {
        padding-left:23px;
        margin-bottom:13px;
    }

    /* Streamlit chat input */
    [data-testid="stChatInput"] {
        border:1px solid rgba(130,145,165,.27)!important;
        border-radius:19px!important;
        background:var(--secondary-background-color)!important;
        box-shadow:0 7px 28px rgba(20,35,55,.055)!important;
    }

    [data-testid="stChatInput"]:focus-within {
        border-color:#9AADC7!important;
        box-shadow:0 0 0 3px rgba(105,135,175,.09)!important;
    }

    [data-testid="stChatInput"] textarea {
        font-size:.96rem!important;
    }

    /* Remove default chat avatars if any remain */
    [data-testid="chatAvatarIcon-user"],
    [data-testid="chatAvatarIcon-assistant"] {
        display:none!important;
    }

    [data-testid="stButton"] button {
        border-radius:10px!important;
    }

    @media(max-width:650px) {
        .merycle-welcome {
            margin:65px auto 45px;
        }

        .merycle-user-bubble {
            max-width:100%;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="merycle-header">
        <div class="merycle-brand">
            <div class="merycle-title">Merycle</div>
            <div class="merycle-subtitle">Your personal learning companion</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if "merycle_messages" not in st.session_state:
        st.session_state.merycle_messages = []

    if st.session_state.merycle_messages:
        left, right = st.columns([5, 1])
        with right:
            if st.button("New chat", key="merycle_clear_chat", use_container_width=True):
                st.session_state.merycle_messages = []
                st.rerun()

    else:
        st.markdown("""
        <div class="merycle-welcome">
            <h1>What can I help you understand?</h1>
            <p>
                Bring your questions, ideas and curiosity.
                Let's work through them together.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Render existing conversation with custom left/right alignment.
    for message in st.session_state.merycle_messages:

        if message["role"] == "user":
            left, right = st.columns([1.3, 4.7], gap="small")
            safe_content = html.escape(message["content"]).replace("\\n", "<br>")

            with right:
                st.markdown(
                    f'<div class="merycle-user-bubble">{safe_content}</div>',
                    unsafe_allow_html=True
                )

        else:
            left, right = st.columns([5.2, 0.8], gap="small")

            with left:
                st.markdown(
                    '<div class="merycle-assistant-label">MERYCLE</div>',
                    unsafe_allow_html=True
                )
                st.markdown(message["content"])

    prompt = st.chat_input(
        "Message Merycle...",
        max_chars=3000,
    )

    if prompt:
        st.session_state.merycle_messages.append({
            "role": "user",
            "content": prompt,
        })

        left, right = st.columns([1.3, 4.7], gap="small")
        safe_prompt = html.escape(prompt).replace("\\n", "<br>")

        with right:
            st.markdown(
                f'<div class="merycle-user-bubble">{safe_prompt}</div>',
                unsafe_allow_html=True
            )

        recent_messages = st.session_state.merycle_messages[-12:]

        conversation = "\\n".join(
            f"{'Student' if item['role'] == 'user' else 'Merycle'}: {item['content']}"
            for item in recent_messages
        )

        ai_prompt = f"""
You are Merycle, a friendly, patient and knowledgeable student study assistant.

Your teaching rules:
1. Explain concepts in simple, clear language, using Class 10 level as the default.
2. Adapt to the student's language: English, Hindi or Hinglish.
3. Explain the reasoning step by step instead of giving only the final answer.
4. For maths and science problems, show the method and important steps.
5. Use short examples when they make an explanation easier.
6. If a question is unclear, ask one brief clarifying question.
7. Never invent facts. Admit when you are uncertain.
8. Keep answers organised and easy for students to understand.
9. Help students learn rather than simply encouraging them to copy answers.

Conversation:
{conversation}

Reply to the latest student message as Merycle.
"""

        left, right = st.columns([5.2, 0.8], gap="small")

        with left:
            st.markdown(
                '<div class="merycle-assistant-label">MERYCLE</div>',
                unsafe_allow_html=True
            )

            with st.spinner("Thinking..."):
                try:
                    answer = gemini_generate(ai_prompt, temperature=0.4)
                except Exception as e:
                    print('MERYCLE GEMINI ERROR:', type(e).__name__, str(e), flush=True)
                    answer = (
                        "I'm unable to connect to Gemini right now. "
                        "Please check your internet connection and try again. "
                        "Your question is still visible in this conversation."
                    )
                    st.warning("Merycle couldn't reach the AI service.")

            st.markdown(answer)

        st.session_state.merycle_messages.append({
            "role": "assistant",
            "content": answer,
        })

elif page == "AgroBridge":
    render_agrobridge(gemini_generate, student, query_all, execute)
