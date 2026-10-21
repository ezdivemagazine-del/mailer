import json
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

from .database import get_conn, write_conn
from .mailer import start_job_thread

_scheduler = BackgroundScheduler()
_TW = timezone(timedelta(hours=8))


def _utcnow():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _run_schedule(schedule_id: int):
    conn = get_conn()
    s = conn.execute("SELECT * FROM schedules WHERE id=? AND status='pending'", (schedule_id,)).fetchone()
    conn.close()
    if not s:
        return

    recipients = json.loads(s["recipients"])
    bcc_batch_size = s["bcc_batch_size"] if s["bcc_batch_size"] else 50
    job_id = None
    with write_conn() as c:
        cur = c.execute(
            """INSERT INTO send_jobs
               (subject, body, send_mode, smtp_id, throttle_min, throttle_count, bcc_batch_size, total, status, created_by)
               VALUES (?,?,?,?,?,?,?,?,'pending',?)""",
            (s["subject"], s["body"], s["send_mode"], s["smtp_id"],
             s["throttle_min"], s["throttle_count"], bcc_batch_size,
             len(recipients), s["created_by"])
        )
        job_id = cur.lastrowid
        c.executemany(
            "INSERT INTO send_recipients (job_id, email) VALUES (?,?)",
            [(job_id, e) for e in recipients]
        )
        c.execute("UPDATE schedules SET status='sent' WHERE id=?", (schedule_id,))
    start_job_thread(job_id)


def _check_schedules():
    conn = get_conn()
    due = conn.execute(
        "SELECT id FROM schedules WHERE status='pending' AND scheduled_at IS NOT NULL AND scheduled_at <= ?",
        (_utcnow(),)
    ).fetchall()
    conn.close()
    for row in due:
        _run_schedule(row["id"])


def start_scheduler():
    _scheduler.add_job(_check_schedules, "interval", minutes=1, id="schedule_checker", replace_existing=True)
    if not _scheduler.running:
        _scheduler.start()


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
