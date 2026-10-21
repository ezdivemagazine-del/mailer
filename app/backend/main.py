import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import logging
from fastapi import FastAPI, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator
from openai import OpenAI
from dotenv import load_dotenv

from .database import init_db, get_conn, write_conn
from .crypto import encrypt, decrypt
from .mailer import test_smtp, start_job_thread
from .directmail import test_directmail
from .auth import (hash_password, verify_password, create_token,
                   get_current_user, require_admin)
from .scheduler import start_scheduler, stop_scheduler

load_dotenv()

_TW = timezone(timedelta(hours=8))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.error("422 ValidationError on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": str(exc.errors())})

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Prompts ───────────────────────────────────────────────

PERSONA_BASE = """你是一位專業的商業信件撰寫專家。根據以下發信人設，以第一人稱代表該單位撰寫對外開發信。

目標：讓收件人「舉手回應」（回信、預約通話或進一步詢問），而非當場成交。

重要規則：
- 信件結尾只需寫到「誠摯的問候，」或類似的結語，不要生成任何簽名檔、姓名、職稱、聯絡方式或佔位符（例如「[您的名字]」、「[聯絡方式]」），系統會自動附加使用者的個人簽名檔。

Output format (output ONLY these two blocks, nothing else):
[SUBJECT]
write the email subject here

[BODY]
write the email body here"""

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
    "zh-TW": (
        "【語言規定 — 最高優先級】"
        "全文（主旨與內文）必須使用繁體中文，台灣商務書信語氣。"
        "不得出現簡體字或英文（品牌名稱、專有名詞除外）。"
    ),
    "zh-CN": (
        "【语言规定 — 最高优先级】"
        "全文（主题与正文）必须使用简体中文，面向中国大陆商务伙伴的书信语气。"
        "所有中文字必须为简体字，绝对不能出现繁体字"
        "（例如：用 [办公室] 不用 [辦公室]，用 [联系] 不用 [聯繫]，用 [营销] 不用 [行銷]）。"
        "如系统描述中出现繁体字，输出时一律转换为简体字。"
    ),
    "en": (
        "[LANGUAGE RULE - HIGHEST PRIORITY] "
        "Write the ENTIRE email in English only - both subject line and body. "
        "Zero Chinese characters allowed anywhere. "
        "Use professional business English appropriate for international correspondence."
    ),
}


def parse_output(text: str) -> tuple[str, str]:
    # New format: [SUBJECT] / [BODY]
    if "[SUBJECT]" in text and "[BODY]" in text:
        parts = text.split("[BODY]")
        return parts[0].replace("[SUBJECT]", "").strip(), parts[1].strip()
    # Legacy format: 【標題】 / 【內文】
    if "【標題】" in text and "【內文】" in text:
        parts = text.split("【內文】")
        return parts[0].replace("【標題】", "").strip(), parts[1].strip()
    lines = text.strip().split("\n")
    return lines[0].strip(), "\n".join(lines[1:]).strip()


def _tw_to_utc(tw_str: str) -> str:
    """Convert Taiwan time string (YYYY-MM-DD HH:MM) to UTC string."""
    tw_dt = datetime.strptime(tw_str, "%Y-%m-%dT%H:%M")
    utc_dt = tw_dt - timedelta(hours=8)
    return utc_dt.strftime("%Y-%m-%d %H:%M:%S")


def _utc_to_tw(utc_str: str) -> str:
    """Convert UTC string to Taiwan time string."""
    if not utc_str or utc_str.upper() == "NULL":
        return ""
    try:
        utc_dt = datetime.strptime(utc_str[:16], "%Y-%m-%d %H:%M")
        tw_dt = utc_dt + timedelta(hours=8)
        return tw_dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ""


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
    channel_type: str = "smtp"

def _coerce_int(v, default):
    if v is None: return default
    try: return int(v)
    except (TypeError, ValueError): return default

class SendJobCreate(BaseModel):
    subject: str
    body: str
    recipients: list[str]
    send_mode: str = "individual"
    smtp_id: int
    throttle_min: float = 5
    throttle_count: int = 50
    bcc_batch_size: int = 50

    @validator('throttle_count', 'bcc_batch_size', pre=True, always=True)
    def coerce_ints_job(cls, v, field):
        return _coerce_int(v, field.default)

class ScheduleCreate(BaseModel):
    name: str
    subject: str
    body: str
    recipients: list[str]
    send_mode: str = "individual"
    smtp_id: int
    throttle_min: float = 5
    throttle_count: int = 50
    bcc_batch_size: int = 50
    scheduled_at: str  # "YYYY-MM-DDTHH:MM" Taiwan time (datetime-local format)

    @validator('throttle_count', 'bcc_batch_size', pre=True, always=True)
    def coerce_ints_sched(cls, v, field):
        return _coerce_int(v, field.default)

class ScheduleUpdate(BaseModel):
    name: str = ""
    subject: str = ""
    body: str = ""
    recipients: list[str] = []
    smtp_id: int = 0
    send_mode: str = ""
    throttle_min: int = 0
    throttle_count: int = 0
    bcc_batch_size: int = 0
    scheduled_at: str = ""

class SignatureCreate(BaseModel):
    name: str
    content: str
    is_default: bool = False


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


# ── 使用者管理 ─────────────────────────────────────────────

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
    existing = get_conn().execute("SELECT id FROM users WHERE username=?", (req.username,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="帳號名稱已存在")
    with write_conn() as c:
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                  (req.username, hash_password(req.password), req.role))
    return {"message": f"帳號 {req.username} 建立成功"}

@app.post("/api/users/{user_id}/toggle")
def toggle_user(user_id: int, admin=Security(require_admin)):
    user = get_conn().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="找不到此帳號")
    if user["username"] == "admin":
        raise HTTPException(status_code=400, detail="無法停用 admin 帳號")
    new_state = 0 if user["active"] else 1
    with write_conn() as c:
        c.execute("UPDATE users SET active=? WHERE id=?", (new_state, user_id))
    return {"active": new_state}

@app.post("/api/users/{user_id}/reset-password")
def reset_password(user_id: int, req: ResetPasswordRequest, admin=Security(require_admin)):
    with write_conn() as c:
        c.execute("UPDATE users SET password=? WHERE id=?", (hash_password(req.new_password), user_id))
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
    with write_conn() as c:
        c.execute("INSERT OR IGNORE INTO user_smtp (user_id, smtp_id) VALUES (?,?)", (user_id, smtp_id))
    return {"message": "已授權"}

@app.delete("/api/users/{user_id}/smtp/{smtp_id}")
def revoke_smtp(user_id: int, smtp_id: int, admin=Security(require_admin)):
    with write_conn() as c:
        c.execute("DELETE FROM user_smtp WHERE user_id=? AND smtp_id=?", (user_id, smtp_id))
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


# ── SMTP ──────────────────────────────────────────────────

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
    new_id = None
    with write_conn() as c:
        cur = c.execute(
            "INSERT INTO smtp_accounts (label, host, port, username, password, channel_type, verified) VALUES (?,?,?,?,?,?,1)",
            (req.label, req.host, req.port, req.username, encrypt(req.password), req.channel_type)
        )
        new_id = cur.lastrowid
    return {"id": new_id, "message": f"{'DirectMail' if req.channel_type == 'directmail' else '信箱'}串接成功，{msg}"}

@app.delete("/api/smtp/{smtp_id}")
def delete_smtp(smtp_id: int, admin=Security(require_admin)):
    with write_conn() as c:
        c.execute("DELETE FROM smtp_accounts WHERE id=?", (smtp_id,))
    return {"message": "已刪除"}


# ── 發送任務 ──────────────────────────────────────────────

@app.post("/api/jobs")
def create_job(req: SendJobCreate, user=Security(get_current_user)):
    smtp = get_conn().execute("SELECT id FROM smtp_accounts WHERE id=? AND verified=1", (req.smtp_id,)).fetchone()
    if not smtp:
        raise HTTPException(status_code=400, detail="找不到已驗證的寄件信箱")
    job_id = None
    with write_conn() as c:
        cur = c.execute(
            """INSERT INTO send_jobs
               (subject, body, send_mode, smtp_id, throttle_min, throttle_count, bcc_batch_size, total, status, created_by)
               VALUES (?,?,?,?,?,?,?,?,'pending',?)""",
            (req.subject, req.body, req.send_mode, req.smtp_id,
             req.throttle_min, req.throttle_count, req.bcc_batch_size, len(req.recipients), user["sub"])
        )
        job_id = cur.lastrowid
        c.executemany("INSERT INTO send_recipients (job_id, email) VALUES (?,?)",
                      [(job_id, e) for e in req.recipients])
    start_job_thread(job_id)
    return {"job_id": job_id, "message": f"任務已建立，開始發送 {len(req.recipients)} 封"}

@app.get("/api/jobs")
def list_jobs(user=Security(get_current_user)):
    conn = get_conn()
    if user["role"] == "admin":
        rows = conn.execute(
            "SELECT j.id, j.subject, j.send_mode, j.status, j.total, j.sent, j.failed, "
            "u.username as created_by_name, "
            "datetime(j.created_at, '+8 hours') as created_at, "
            "datetime(j.updated_at, '+8 hours') as updated_at "
            "FROM send_jobs j LEFT JOIN users u ON u.id = j.created_by "
            "ORDER BY j.id DESC LIMIT 100"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, subject, send_mode, status, total, sent, failed, "
            "NULL as created_by_name, "
            "datetime(created_at, '+8 hours') as created_at, "
            "datetime(updated_at, '+8 hours') as updated_at "
            "FROM send_jobs WHERE created_by=? ORDER BY id DESC LIMIT 50",
            (user["sub"],)
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
    with write_conn() as c:
        c.execute("UPDATE send_jobs SET status='cancelled' WHERE id=? AND status='running'", (job_id,))
    return {"message": "已送出取消指令"}


# ── 排程 ──────────────────────────────────────────────────

@app.get("/api/schedules")
def list_schedules(user=Security(get_current_user)):
    conn = get_conn()
    if user["role"] == "admin":
        rows = conn.execute(
            "SELECT id, name, subject, send_mode, scheduled_at, status, created_at FROM schedules ORDER BY scheduled_at ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, subject, send_mode, scheduled_at, status, created_at FROM schedules WHERE created_by=? ORDER BY scheduled_at ASC",
            (user["sub"],)
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["scheduled_at_tw"] = _utc_to_tw(d.get("scheduled_at", ""))
        result.append(d)
    return result

@app.get("/api/schedules/{schedule_id}")
def get_schedule(schedule_id: int, user=Security(get_current_user)):
    conn = get_conn()
    s = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    conn.close()
    if not s:
        raise HTTPException(status_code=404, detail="找不到此排程")
    d = dict(s)
    d["scheduled_at_tw"] = _utc_to_tw(d.get("scheduled_at", ""))
    d["recipients_list"] = json.loads(d.get("recipients", "[]"))
    return d

@app.post("/api/schedules")
def create_schedule(req: ScheduleCreate, user=Security(get_current_user)):
    try:
        scheduled_at_utc = _tw_to_utc(req.scheduled_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="時間格式錯誤，請用 YYYY-MM-DDTHH:MM")
    new_id = None
    with write_conn() as c:
        cur = c.execute(
            """INSERT INTO schedules
               (name, subject, body, recipients, send_mode, smtp_id,
                throttle_min, throttle_count, bcc_batch_size, interval_days,
                next_run, scheduled_at, status, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,0,?,?,'pending',?)""",
            (req.name, req.subject, req.body, json.dumps(req.recipients),
             req.send_mode, req.smtp_id, req.throttle_min, req.throttle_count,
             req.bcc_batch_size, scheduled_at_utc, scheduled_at_utc, user["sub"])
        )
        new_id = cur.lastrowid
    return {"id": new_id, "message": "排程建立成功"}

@app.put("/api/schedules/{schedule_id}")
def update_schedule(schedule_id: int, req: ScheduleUpdate, user=Security(get_current_user)):
    s = get_conn().execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not s:
        raise HTTPException(status_code=404, detail="找不到此排程")
    if s["status"] != "pending":
        raise HTTPException(status_code=400, detail="只能編輯待發排程")

    updates = {}
    if req.name:        updates["name"] = req.name
    if req.subject:     updates["subject"] = req.subject
    if req.body:        updates["body"] = req.body
    if req.recipients:  updates["recipients"] = json.dumps(req.recipients)
    if req.smtp_id:     updates["smtp_id"] = req.smtp_id
    if req.send_mode:   updates["send_mode"] = req.send_mode
    if req.throttle_min:   updates["throttle_min"] = req.throttle_min
    if req.throttle_count: updates["throttle_count"] = req.throttle_count
    if req.bcc_batch_size: updates["bcc_batch_size"] = req.bcc_batch_size
    if req.scheduled_at:
        try:
            updates["scheduled_at"] = _tw_to_utc(req.scheduled_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="時間格式錯誤")

    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with write_conn() as c:
            c.execute(f"UPDATE schedules SET {set_clause} WHERE id=?",
                      (*updates.values(), schedule_id))
    return {"message": "排程已更新"}

@app.post("/api/schedules/{schedule_id}/cancel")
def cancel_schedule(schedule_id: int, user=Security(get_current_user)):
    s = get_conn().execute("SELECT status FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    if not s:
        raise HTTPException(status_code=404, detail="找不到此排程")
    if s["status"] != "pending":
        raise HTTPException(status_code=400, detail="只能取消待發排程")
    with write_conn() as c:
        c.execute("UPDATE schedules SET status='cancelled' WHERE id=?", (schedule_id,))
    return {"message": "排程已取消"}

@app.delete("/api/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user=Security(get_current_user)):
    with write_conn() as c:
        c.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
    return {"message": "排程已刪除"}


# ── 簽名檔 ────────────────────────────────────────────────

@app.get("/api/signatures")
def list_signatures(user=Security(get_current_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, content, is_default, created_at FROM signatures WHERE user_id=? ORDER BY is_default DESC, id DESC",
        (user["sub"],)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/signatures")
def create_signature(req: SignatureCreate, user=Security(get_current_user)):
    new_id = None
    with write_conn() as c:
        if req.is_default:
            c.execute("UPDATE signatures SET is_default=0 WHERE user_id=?", (user["sub"],))
        cur = c.execute(
            "INSERT INTO signatures (user_id, name, content, is_default) VALUES (?,?,?,?)",
            (user["sub"], req.name, req.content, 1 if req.is_default else 0)
        )
        new_id = cur.lastrowid
    return {"id": new_id, "message": "簽名檔已建立"}

@app.put("/api/signatures/{sig_id}")
def update_signature(sig_id: int, req: SignatureCreate, user=Security(get_current_user)):
    with write_conn() as c:
        if req.is_default:
            c.execute("UPDATE signatures SET is_default=0 WHERE user_id=?", (user["sub"],))
        c.execute(
            "UPDATE signatures SET name=?, content=?, is_default=? WHERE id=? AND user_id=?",
            (req.name, req.content, 1 if req.is_default else 0, sig_id, user["sub"])
        )
    return {"message": "簽名檔已更新"}

@app.delete("/api/signatures/{sig_id}")
def delete_signature(sig_id: int, user=Security(get_current_user)):
    with write_conn() as c:
        c.execute("DELETE FROM signatures WHERE id=? AND user_id=?", (sig_id, user["sub"]))
    return {"message": "已刪除"}


# ── Health ────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# ── Static ────────────────────────────────────────────────

_frontend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
