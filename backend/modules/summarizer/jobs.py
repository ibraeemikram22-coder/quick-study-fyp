"""In-memory async summarization jobs with progress (dev / single-server)."""
import threading
import uuid
from datetime import datetime

_lock = threading.Lock()
_jobs = {}


def create_job():
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Queued…",
            "createdAt": datetime.utcnow().isoformat(),
            "result": None,
            "error": None,
        }
    return job_id


def update_job(job_id, progress=None, message=None, status=None):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if progress is not None:
            job["progress"] = max(0, min(100, int(progress)))
        if message is not None:
            job["message"] = message
        if status is not None:
            job["status"] = status


def complete_job(job_id, result):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "done"
        job["progress"] = 100
        job["message"] = "Complete"
        job["result"] = result


def fail_job(job_id, error):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "error"
        job["error"] = str(error)
        job["message"] = str(error)


def get_job(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def run_in_background(job_id, target, *args, **kwargs):
    def wrapper():
        try:
            update_job(job_id, status="running", progress=2, message="Starting…")
            target(job_id, *args, **kwargs)
        except Exception as exc:
            fail_job(job_id, exc)

    threading.Thread(target=wrapper, daemon=True).start()
