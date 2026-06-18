import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Security
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from .database import init_db, get_conn
from .crypto import encrypt, decrypt
from .mailer import test_smtp, start_job_thread
from .directmail import test_directmail
from .auth import (hash_password, verify_password, create_token,
                   get_current_user, require_admin)
from .scheduler import start_scheduler, stop_scheduler

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(lifespan=lifespan)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Prompts ───────────────────────────────────────────────

PERSONA_BASE = """你是一位專業的商業信件撰寫專家。根據以下發信人設，以第一人稱代表該單位撰寫對外開發信。

目標：讓收件人「舉手回應」（回信、預約通話或進一步詢問），而非當場成交。

輸出格式（只輸出這兩個區塊，不要加其他文字）：
【標題】
在這裡填入信件主旨

【內文】
在這裡填入信件正文"""

PERSONAS = {
    "創意種籽": {
        "display": "創意種籽 — 國際潛水品牌台灣總代理",
        "prompt": """發信人設 — 創意種籽：
創意種籽是國際潛水品牌在台灣的總代理與市場推廣夥伴。核心任務是協助優質潛水品牌拓展台灣市場，建立穩定且長期的銷售通路網絡。代理品牌：Cressi、Seac、Alpha Oceano（均為義大利品牌）。
發信時以品牌代表的身份進行溝通，展現對產品、市場與產業的專業理解。著重合作機會、通路發展、市場需求與品牌價值。語氣專業、誠懇且具服務精神，以建立長期合作關係為目標。避免過度推銷、價格競爭或短期促銷導向，強調品牌發展、市場成長與雙方共贏。""",
    },
    "DRT SHOW": {
        "display": "DRT SHOW — 亞洲潛水產業展覽平台",
        "prompt": """發信人設 — DRT SHOW：
DRT SHOW 的業務並不單只是在販售展位，而是在協助品牌進入亞洲潛水市場。思維核心不是「如何賣出攤位」，而是「如何幫助品牌接觸更多潛水消費者與產業買家」。
發信時以產業顧問的角度出發，展現對潛水產業、生態趨勢、品牌發展與市場機會的理解。著重合作價值、市場曝光、品牌發展及長期合作關係。語氣專業、國際化且具有商業思維，讓收件人感受到 DRT SHOW 是亞洲潛水產業的重要平台與合作夥伴。避免過度銷售或急於成交，以建立信任與創造雙方價值為優先目標。""",
    },
    "EZDIVE": {
        "display": "EZDIVE — 潛水產業媒體與內容平台",
        "prompt": """發信人設 — EZDIVE：
EZDIVE 的業務並非只是廣告銷售員，而是協助品牌建立市場認知與專業形象的內容顧問。相信好的品牌需要被看見，也需要被正確地理解。
發信時以媒體與內容策略的角度出發，思考如何透過故事、專題、教育內容與產業觀點，幫助品牌與潛水員建立連結。語氣專業、親切且具有媒體人的敏銳度。著重品牌故事、市場教育、內容合作及長期品牌經營，避免過度商業化或硬性推銷，以提升品牌影響力為主要出發點。""",
    },
    "DIWA": {
        "display": "DIWA — 潛水教育認證機構",
        "prompt": """發信人設 — DIWA：
DIWA 的業務不只是在販售課程或證照，而是在協助教練、潛店與學員建立更好的教育生態系。
發信時以教育發展夥伴的身份與思維進行溝通，重視人才培育、產業成長與教學品質。著重如何降低經營門檻、創造更多教學機會、提升學員體驗以及建立永續的教學模式。語氣親切、專業且具有教育工作者的熱忱，讓收件人感受到 DIWA 真正關心的是教練與潛店的長期發展，而不是單純追求發證數量。避免過度商業化或競爭性的語言，強調合作、支持與共同成長的價值。""",
    },
    "GOGOSCUBA": {
        "display": "GOGOSCUBA — 潛水器材與通路平台",
        "prompt": """發信人設 — GOGOSCUBA：
GOGOSCUBA 的業務並非單純只有銷售商品，而是協助潛水員、教練、潛店與品牌找到最適合的產品與通路解決方案。每天接觸市場、產品與消費者。
發信時展現對產品、使用情境與市場需求的理解。以實際價值、產品特色、市場需求及合作機會為核心，讓收件人感受到具備第一線市場經驗與專業判斷能力。語氣務實、專業且具有服務精神，避免誇大宣傳或價格導向的推銷方式。以解決問題、創造銷售機會與建立長期合作關係為主要思維，而非一次性的交易行為。""",
    },
}

LANGUAGE_MAP = {
    "zh-TW": "請用繁體中文（台灣商務語氣）撰寫",
    "zh-CN": "請用簡體中文（面向中國大陸通路的商務語氣）撰寫",
    "en":    "Please write in English (professional B2B tone)",
}


def parse_output(text: str) -> tuple[str, str]:
    if "【標題】" in text and "【內文】" in text:
        parts = text.split("【內文】")
        return parts[0].replace("【標題】", "").strip(), parts[1].strip()
    lines = text.strip().split("\n")
    return lines[0].strip(), "\n".join(lines[1:]).strip()


# ── Schemas ───────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class GenerateRequest(BaseModel):
    messages: list[Message]
    language: str = "zh-TW"
    persona: str = "創意種籽"

class GenerateResponse(BaseModel):
    subject: str
    body: str
    raw: str

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "member"

class ResetPasswordRequest(BaseModel):
    new_password: str

class SmtpCreate(BaseModel):
    label: str
    host: str
    port: int = 465
    username: str
    password: str
    channel_type: str = "smtp"  # "smtp" 或 "directmail"

class SendJobCreate(BaseModel):
    subject: str
    body: str
    recipients: list[str]
    send_mode: str = "individual"
    smtp_id: int
    throttle_min: int = 5
    throttle_count: int = 50

class ScheduleCreate(BaseModel):
    name: str
    subject: str
    body: str
    recipients: list[str]
    send_mode: str = "individual"
    smtp_id: int
    throttle_min: int = 5
    throttle_count: int = 50
    interval_days: int
    start_date: str = ""


# ── Auth ──────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND active=1", (req.username,)
    ).fetchone()
    conn.close()
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    token = create_token(user["id"], user["username"], user["role"])
    return {"token": token, "username": user["username"], "role": user["role"]}

@app.get("/api/auth/me")
def me(user=Security(get_current_user)):
    return user


# ── 使用者管理（admin only）───────────────────────────────

@app.get("/api/users")
def list_users(admin=Security(require_admin)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, active, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/users")
def create_user(req: CreateUserRequest, admin=Security(require_admin)):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM users WHERE username=?", (req.username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="帳號名稱已存在")
    conn.execute(
        "INSERT INTO users (username, password, role) VALUES (?,?,?)",
        (req.username, hash_password(req.password), req.role)
    )
    conn.commit(); conn.close()
    return {"message": f"帳號 {req.username} 建立成功"}

@app.post("/api/users/{user_id}/toggle")
def toggle_user(user_id: int, admin=Security(require_admin)):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close(); raise HTTPException(status_code=404, detail="找不到此帳號")
    if user["username"] == "admin":
        conn.close(); raise HTTPException(status_code=400, detail="無法停用 admin 帳號")
    new_state = 0 if user["active"] else 1
    conn.execute("UPDATE users SET active=? WHERE id=?", (new_state, user_id))
    conn.commit(); conn.close()
    return {"active": new_state, "message": "已啟用" if new_state else "已停用"}

@app.post("/api/users/{user_id}/reset-password")
def reset_password(user_id: int, req: ResetPasswordRequest, admin=Security(require_admin)):
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(req.new_password), user_id))
    conn.commit(); conn.close()
    return {"message": "密碼已重設"}

@app.get("/api/users/{user_id}/smtp")
def get_user_smtp(user_id: int, admin=Security(require_admin)):
    conn = get_conn()
    granted = {r["smtp_id"] for r in conn.execute("SELECT smtp_id FROM user_smtp WHERE user_id=?", (user_id,)).fetchall()}
    all_smtp = conn.execute("SELECT id, label, username FROM smtp_accounts WHERE verified=1").fetchall()
    conn.close()
    return [{"id": r["id"], "label": r["label"], "username": r["username"], "granted": r["id"] in granted} for r in all_smtp]

@app.post("/api/users/{user_id}/smtp/{smtp_id}")
def grant_smtp(user_id: int, smtp_id: int, admin=Security(require_admin)):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO user_smtp (user_id, smtp_id) VALUES (?,?)", (user_id, smtp_id))
    conn.commit(); conn.close()
    return {"message": "已授權"}

@app.delete("/api/users/{user_id}/smtp/{smtp_id}")
def revoke_smtp(user_id: int, smtp_id: int, admin=Security(require_admin)):
    conn = get_conn()
    conn.execute("DELETE FROM user_smtp WHERE user_id=? AND smtp_id=?", (user_id, smtp_id))
    conn.commit(); conn.close()
    return {"message": "已撤銷"}


# ── AI ────────────────────────────────────────────────────

@app.get("/api/personas")
def list_personas(user=Security(get_current_user)):
    return [{"key": k, "display": v["display"]} for k, v in PERSONAS.items()]


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, user=Security(get_current_user)):
    persona = PERSONAS.get(req.persona, PERSONAS["創意種籽"])
    lang = LANGUAGE_MAP.get(req.language, LANGUAGE_MAP["zh-TW"])
    system = f"{PERSONA_BASE}\n\n{persona['prompt']}\n\n語言指示：{lang}"
    msgs = [{"role": "system", "content": system}]
    for m in req.messages:
        msgs.append({"role": m.role, "content": m.content})
    try:
        resp = client.chat.completions.create(model=MODEL, messages=msgs, temperature=0.8)
        raw = resp.choices[0].message.content
        subject, body = parse_output(raw)
        return GenerateResponse(subject=subject, body=body, raw=raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── SMTP 信箱管理 ──────────────────────────────────────────

@app.get("/api/smtp")
def list_smtp(user=Security(get_current_user)):
    conn = get_conn()
    if user["role"] == "admin":
        rows = conn.execute("SELECT id, label, host, port, username, verified, created_at FROM smtp_accounts").fetchall()
    else:
        rows = conn.execute(
            """SELECT s.id, s.label, s.host, s.port, s.username, s.verified, s.created_at
               FROM smtp_accounts s
               JOIN user_smtp us ON us.smtp_id = s.id
               WHERE us.user_id = ? AND s.verified = 1""", (user["sub"],)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/smtp")
def create_smtp(req: SmtpCreate, admin=Security(require_admin)):
    if req.channel_type == "directmail":
        ok, msg = test_directmail(req.username, req.password, req.host)
    else:
        ok, msg = test_smtp(req.host, req.port, req.username, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=f"連線測試失敗：{msg}")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO smtp_accounts (label, host, port, username, password, channel_type, verified) VALUES (?,?,?,?,?,?,1)",
        (req.label, req.host, req.port, req.username, encrypt(req.password), req.channel_type)
    )
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return {"id": new_id, "message": f"{'DirectMail' if req.channel_type == 'directmail' else '信箱'}串接成功，{msg}"}

@app.delete("/api/smtp/{smtp_id}")
def delete_smtp(smtp_id: int, admin=Security(require_admin)):
    conn = get_conn()
    conn.execute("DELETE FROM smtp_accounts WHERE id=?", (smtp_id,))
    conn.commit(); conn.close()
    return {"message": "已刪除"}


# ── 發送任務 ──────────────────────────────────────────────

@app.post("/api/jobs")
def create_job(req: SendJobCreate, user=Security(get_current_user)):
    conn = get_conn()
    smtp = conn.execute(
        "SELECT id FROM smtp_accounts WHERE id=? AND verified=1", (req.smtp_id,)
    ).fetchone()
    if not smtp:
        conn.close(); raise HTTPException(status_code=400, detail="找不到已驗證的寄件信箱")
    cur = conn.execute(
        """INSERT INTO send_jobs
           (subject, body, send_mode, smtp_id, throttle_min, throttle_count, total, status, created_by)
           VALUES (?,?,?,?,?,?,?,'pending',?)""",
        (req.subject, req.body, req.send_mode, req.smtp_id,
         req.throttle_min, req.throttle_count, len(req.recipients), user["sub"])
    )
    job_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO send_recipients (job_id, email) VALUES (?,?)",
        [(job_id, e) for e in req.recipients]
    )
    conn.commit(); conn.close()
    start_job_thread(job_id)
    return {"job_id": job_id, "message": f"任務已建立，開始發送 {len(req.recipients)} 封"}

@app.get("/api/jobs")
def list_jobs(user=Security(get_current_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, subject, send_mode, status, total, sent, failed, created_at, updated_at FROM send_jobs ORDER BY id DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, user=Security(get_current_user)):
    conn = get_conn()
    job = conn.execute("SELECT * FROM send_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close(); raise HTTPException(status_code=404, detail="找不到此任務")
    recipients = conn.execute(
        "SELECT email, status, error, sent_at FROM send_recipients WHERE job_id=? ORDER BY id",
        (job_id,)
    ).fetchall()
    conn.close()
    return {"job": dict(job), "recipients": [dict(r) for r in recipients]}

@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: int, user=Security(get_current_user)):
    conn = get_conn()
    conn.execute(
        "UPDATE send_jobs SET status='cancelled' WHERE id=? AND status='running'", (job_id,)
    )
    conn.commit(); conn.close()
    return {"message": "已送出取消指令"}


# ── 排程 ──────────────────────────────────────────────────

@app.get("/api/schedules")
def list_schedules(user=Security(get_current_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, subject, send_mode, interval_days, next_run, active, created_at FROM schedules ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/schedules")
def create_schedule(req: ScheduleCreate, user=Security(get_current_user)):
    if req.start_date:
        try:
            next_run = datetime.strptime(req.start_date, "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式錯誤，請用 YYYY-MM-DD")
    else:
        next_run = (datetime.utcnow() + timedelta(days=req.interval_days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO schedules
           (name, subject, body, recipients, send_mode, smtp_id,
            throttle_min, throttle_count, interval_days, next_run, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (req.name, req.subject, req.body, json.dumps(req.recipients),
         req.send_mode, req.smtp_id, req.throttle_min, req.throttle_count,
         req.interval_days, next_run, user["sub"])
    )
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return {"id": new_id, "message": "排程建立成功", "next_run": next_run}

@app.post("/api/schedules/{schedule_id}/toggle")
def toggle_schedule(schedule_id: int, user=Security(get_current_user)):
    conn = get_conn()
    s = conn.execute("SELECT active FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not s:
        conn.close(); raise HTTPException(status_code=404, detail="找不到此排程")
    new_state = 0 if s["active"] else 1
    conn.execute("UPDATE schedules SET active=? WHERE id=?", (new_state, schedule_id))
    conn.commit(); conn.close()
    return {"active": new_state}

@app.delete("/api/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user=Security(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
    conn.commit(); conn.close()
    return {"message": "排程已刪除"}


# ── Health ────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Static ────────────────────────────────────────────────

_frontend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
