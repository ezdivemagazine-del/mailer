import smtplib
import time
import threading
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime, timezone, timedelta

from .database import get_conn, write_conn
from .crypto import decrypt
from .directmail import send_one_directmail, test_directmail

_TW = timezone(timedelta(hours=8))


def _now():
    return datetime.now(_TW).strftime("%Y-%m-%d %H:%M:%S")


def _make_parts(body: str) -> list:
    """Return MIME parts. HTML body gets plain-text fallback."""
    if body.strip().startswith('<'):
        plain = re.sub(r'<[^>]+>', ' ', body)
        plain = re.sub(r'&nbsp;', ' ', plain)
        plain = re.sub(r'&amp;', '&', plain)
        plain = re.sub(r'&lt;', '<', plain)
        plain = re.sub(r'&gt;', '>', plain)
        plain = re.sub(r'\s+', ' ', plain).strip()
        html_doc = (
            '<!DOCTYPE html><html><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '</head><body style="font-family:-apple-system,Arial,sans-serif;'
            'font-size:14px;line-height:1.8;color:#333;max-width:680px;margin:0 auto;padding:20px;">'
            + body +
            '</body></html>'
        )
        return [MIMEText(plain, "plain", "utf-8"), MIMEText(html_doc, "html", "utf-8")]
    return [MIMEText(body, "plain", "utf-8")]


def test_smtp(host: str, port: int, username: str, password: str) -> tuple[bool, str]:
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        server.login(username, password)
        server.quit()
        return True, "連線成功"
    except smtplib.SMTPAuthenticationError:
        return False, "帳號或密碼錯誤"
    except Exception as e:
        return False, str(e)


def send_one(host: str, port: int, username: str, password: str,
             from_addr: str, to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = str(Header(subject, "utf-8"))
        msg["From"] = from_addr
        msg["To"] = to_addr
        for part in _make_parts(body):
            msg.attach(part)
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(username, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        return True, ""
    except Exception as e:
        return False, str(e)


def send_bcc(host: str, port: int, username: str, password: str,
             from_addr: str, recipients: list[str], subject: str, body: str) -> tuple[bool, str]:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = str(Header(subject, "utf-8"))
        msg["From"] = from_addr
        msg["To"] = "undisclosed-recipients:;"
        msg["Bcc"] = ", ".join(recipients)
        for part in _make_parts(body):
            msg.attach(part)
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(username, password)
        server.sendmail(from_addr, recipients, msg.as_string())
        server.quit()
        return True, ""
    except Exception as e:
        return False, str(e)


def _db_write(sql: str, params: tuple):
    with write_conn() as c:
        c.execute(sql, params)

def _db_write_many(ops: list):
    with write_conn() as c:
        for sql, params in ops:
            c.execute(sql, params)

def _db_check_cancelled(job_id: int) -> bool:
    c = get_conn()
    row = c.execute("SELECT status FROM send_jobs WHERE id=?", (job_id,)).fetchone()
    c.close()
    return row and row["status"] == "cancelled"

def run_job(job_id: int):
    # ── 1. Fetch all needed data upfront, then close connection ──
    conn = get_conn()
    job  = conn.execute("SELECT * FROM send_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close(); return

    smtp = conn.execute("SELECT * FROM smtp_accounts WHERE id=?", (job["smtp_id"],)).fetchone()
    smtp = dict(smtp) if smtp else None
    if not smtp:
        conn.close()
        _db_write("UPDATE send_jobs SET status='failed', updated_at=? WHERE id=?", (_now(), job_id))
        return

    pending = conn.execute(
        "SELECT * FROM send_recipients WHERE job_id=? AND status='pending'", (job_id,)
    ).fetchall()
    pending = [dict(r) for r in pending]
    conn.close()  # ← release lock before any long operation

    host     = smtp["host"]
    port     = smtp["port"]
    username = smtp["username"]
    password = decrypt(smtp["password"])
    throttle_count = job["throttle_count"]
    throttle_min   = job["throttle_min"]
    send_mode      = job["send_mode"]
    subject        = job["subject"]
    body           = job["body"]

    _db_write("UPDATE send_jobs SET status='running', updated_at=? WHERE id=?", (_now(), job_id))

    # ── 2. Send loop — each DB update uses its own short-lived connection ──
    if send_mode == "bcc":
        bcc_batch_size = job["bcc_batch_size"] or 50
        emails = [r["email"] for r in pending]
        for batch_start in range(0, len(emails), bcc_batch_size):
            if _db_check_cancelled(job_id): return
            batch_emails = emails[batch_start:batch_start + bcc_batch_size]
            batch_rows   = pending[batch_start:batch_start + bcc_batch_size]
            ok, err = send_bcc(host, port, username, password, username, batch_emails, subject, body)
            status = "sent" if ok else "failed"
            delta  = len(batch_emails) if ok else 0
            ops = [("UPDATE send_recipients SET status=?, error=?, sent_at=? WHERE id=?",
                    (status, err if not ok else None, _now(), r["id"])) for r in batch_rows]
            ops.append(("UPDATE send_jobs SET sent=sent+?, failed=failed+?, updated_at=? WHERE id=?",
                        (delta, len(batch_emails) - delta, _now(), job_id)))
            _db_write_many(ops)
            if batch_start + bcc_batch_size < len(emails):
                time.sleep(throttle_min * 60)
    else:
        batch = []
        for i, r in enumerate(pending):
            batch.append(r)
            if len(batch) >= throttle_count or i == len(pending) - 1:
                for rec in batch:
                    if _db_check_cancelled(job_id): return
                    if smtp.get("channel_type") == "directmail":
                        ok, err = send_one_directmail(username, password, host, rec["email"], subject, body)
                    else:
                        ok, err = send_one(host, port, username, password, username, rec["email"], subject, body)
                    if ok:
                        _db_write_many([
                            ("UPDATE send_recipients SET status='sent', sent_at=? WHERE id=?", (_now(), rec["id"])),
                            ("UPDATE send_jobs SET sent=sent+1, updated_at=? WHERE id=?", (_now(), job_id)),
                        ])
                    else:
                        _db_write_many([
                            ("UPDATE send_recipients SET status='failed', error=? WHERE id=?", (err, rec["id"])),
                            ("UPDATE send_jobs SET failed=failed+1, updated_at=? WHERE id=?", (_now(), job_id)),
                        ])
                batch = []
                if i < len(pending) - 1:
                    time.sleep(throttle_min * 60)

    _db_write("UPDATE send_jobs SET status='completed', updated_at=? WHERE id=?", (_now(), job_id))


def start_job_thread(job_id: int):
    t = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    t.start()
