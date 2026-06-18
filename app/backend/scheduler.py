import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

from .database import get_conn
from .mailer import start_job_thread

_scheduler = BackgroundScheduler()


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _run_schedule(schedule_id: int):
    conn = get_conn()
    s = conn.execute("SELECT * FROM schedules WHERE id=? AND active=1", (schedule_id,)).fetchone()
    if not s:
        conn.close()
        return

    recipients = json.loads(s["recipients"])
    cur = conn.execute(
        """INSERT INTO send_jobs
           (subject, body, send_mode, smtp_id, throttle_min, throttle_count, total, status, created_by)
           VALUES (?,?,?,?,?,?,?,'pending',?)""",
        (s["subject"], s["body"], s["send_mode"], s["smtp_id"],
         s["throttle_min"], s["throttle_count"], len(recipients), s["created_by"])
    )
    job_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO send_recipients (job_id, email) VALUES (?,?)",
        [(job_id, e) for e in recipients]
    )

    next_run = (datetime.utcnow() + timedelta(days=s["interval_days"])).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE schedules SET next_run=? WHERE id=?", (next_run, schedule_id))
    conn.commit()
    conn.close()

    start_job_thread(job_id)


def _check_schedules():
    conn = get_conn()
    due = conn.execute(
        "SELECT id FROM schedules WHERE active=1 AND next_run <= ?", (_now(),)
    ).fetchall()
    conn.close()
    for row in due:
        _run_schedule(row["id"])


def start_scheduler():
    _scheduler.add_job(_check_schedules, "interval", minutes=5, id="schedule_checker", replace_existing=True)
    if not _scheduler.running:
        _scheduler.start()


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
