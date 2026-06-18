import smtplib
import time
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime

from .database import get_conn
from .crypto import decrypt
from .directmail import send_one_directmail, test_directmail


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


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
        msg.attach(MIMEText(body, "plain", "utf-8"))

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
        msg["To"] = from_addr
        msg.attach(MIMEText(body, "plain", "utf-8"))

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


def run_job(job_id: int):
    conn = get_conn()
    job = conn.execute("SELECT * FROM send_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        return

    smtp = conn.execute("SELECT * FROM smtp_accounts WHERE id=?", (job["smtp_id"],)).fetchone()
    smtp = dict(smtp) if smtp else None
    if not smtp:
        conn.execute("UPDATE send_jobs SET status='failed', updated_at=? WHERE id=?", (_now(), job_id))
        conn.commit()
        conn.close()
        return

    host = smtp["host"]
    port = smtp["port"]
    username = smtp["username"]
    password = decrypt(smtp["password"])

    conn.execute("UPDATE send_jobs SET status='running', updated_at=? WHERE id=?", (_now(), job_id))
    conn.commit()

    pending = conn.execute(
        "SELECT * FROM send_recipients WHERE job_id=? AND status='pending'", (job_id,)
    ).fetchall()

    throttle_count = job["throttle_count"]
    throttle_min   = job["throttle_min"]
    send_mode      = job["send_mode"]
    subject        = job["subject"]
    body           = job["body"]

    if send_mode == "bcc":
        emails = [r["email"] for r in pending]
        ok, err = send_bcc(host, port, username, password, username, emails, subject, body)
        status = "sent" if ok else "failed"
        for r in pending:
            conn.execute(
                "UPDATE send_recipients SET status=?, error=?, sent_at=? WHERE id=?",
                (status, err if not ok else None, _now(), r["id"])
            )
        delta = 1 if ok else 0
        conn.execute(
            "UPDATE send_jobs SET sent=sent+?, failed=failed+?, updated_at=? WHERE id=?",
            (delta * len(emails), (1 - delta) * len(emails), _now(), job_id)
        )
    else:
        batch = []
        for i, r in enumerate(pending):
            batch.append(r)
            if len(batch) >= throttle_count or i == len(pending) - 1:
                for rec in batch:
                    # re-check job isn't cancelled
                    current = conn.execute("SELECT status FROM send_jobs WHERE id=?", (job_id,)).fetchone()
                    if current and current["status"] == "cancelled":
                        conn.close()
                        return
                    if smtp.get("channel_type") == "directmail":
                        ok, err = send_one_directmail(username, password, host, rec["email"], subject, body)
                    else:
                        ok, err = send_one(host, port, username, password, username, rec["email"], subject, body)
                    if ok:
                        conn.execute(
                            "UPDATE send_recipients SET status='sent', sent_at=? WHERE id=?",
                            (_now(), rec["id"])
                        )
                        conn.execute("UPDATE send_jobs SET sent=sent+1, updated_at=? WHERE id=?", (_now(), job_id))
                    else:
                        conn.execute(
                            "UPDATE send_recipients SET status='failed', error=? WHERE id=?",
                            (err, rec["id"])
                        )
                        conn.execute("UPDATE send_jobs SET failed=failed+1, updated_at=? WHERE id=?", (_now(), job_id))
                    conn.commit()
                batch = []
                if i < len(pending) - 1:
                    time.sleep(throttle_min * 60)

    conn.execute("UPDATE send_jobs SET status='completed', updated_at=? WHERE id=?", (_now(), job_id))
    conn.commit()
    conn.close()


def start_job_thread(job_id: int):
    t = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    t.start()
