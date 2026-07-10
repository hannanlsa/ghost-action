import json
import os
import time
import threading
import logging
import re

_SCHEDULER_FILE = os.path.join(os.path.expanduser("~"), "GhostAction", "scheduler.json")

logger = logging.getLogger("scheduler")


class Scheduler:
    def __init__(self, scripts_dir=None):
        self.scripts_dir = scripts_dir or os.path.join(os.path.expanduser("~"), "GhostAction", "scripts")
        self._jobs = {}
        self._threads = {}
        self._running = False
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(_SCHEDULER_FILE):
            try:
                with open(_SCHEDULER_FILE, "r", encoding="utf-8") as f:
                    self._jobs = json.load(f)
            except Exception as e:
                logger.error("加载调度配置失败: %s", e)
                self._jobs = {}

    def _save(self):
        os.makedirs(os.path.dirname(_SCHEDULER_FILE), exist_ok=True)
        with self._lock:
            tmp = _SCHEDULER_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._jobs, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _SCHEDULER_FILE)

    def add_job(self, script_name, cron_expr, enabled=True, params=None):
        job_id = f"{script_name}_{int(time.time())}"
        self._jobs[job_id] = {
            "script_name": script_name,
            "cron_expr": cron_expr,
            "enabled": enabled,
            "params": params or {},
            "last_run": None,
            "next_run": None,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._update_next_run(job_id)
        self._save()
        if self._running:
            self._start_job_thread(job_id)
        return job_id

    def remove_job(self, job_id):
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save()
        if job_id in self._threads:
            self._threads[job_id]["stop"] = True

    def update_job(self, job_id, **kwargs):
        if job_id not in self._jobs:
            return False
        for k, v in kwargs.items():
            if k in ("cron_expr", "enabled", "params"):
                self._jobs[job_id][k] = v
        self._update_next_run(job_id)
        self._save()
        return True

    def toggle_job(self, job_id):
        if job_id not in self._jobs:
            return False
        self._jobs[job_id]["enabled"] = not self._jobs[job_id]["enabled"]
        self._save()
        return self._jobs[job_id]["enabled"]

    def list_jobs(self):
        return dict(self._jobs)

    def get_jobs_for_script(self, script_name):
        return {k: v for k, v in self._jobs.items() if v.get("script_name") == script_name}

    def start(self, on_trigger=None):
        self._running = True
        self._on_trigger = on_trigger
        for job_id in self._jobs:
            if self._jobs[job_id].get("enabled", True):
                self._start_job_thread(job_id)
        logger.info("调度器已启动, %d个任务", len(self._jobs))

    def stop(self):
        self._running = False
        for job_id in list(self._threads.keys()):
            self._threads[job_id]["stop"] = True
        self._threads.clear()
        logger.info("调度器已停止")

    def _start_job_thread(self, job_id):
        if job_id in self._threads:
            self._threads[job_id]["stop"] = True
        t = threading.Thread(target=self._job_loop, args=(job_id,), daemon=True)
        self._threads[job_id] = {"thread": t, "stop": False}
        t.start()

    def _job_loop(self, job_id):
        while self._running and not self._threads.get(job_id, {}).get("stop"):
            job = self._jobs.get(job_id)
            if not job or not job.get("enabled", True):
                time.sleep(10)
                continue
            next_run = job.get("next_run")
            if not next_run:
                time.sleep(10)
                continue
            now = time.time()
            if now >= next_run:
                logger.info("定时触发: %s (%s)", job["script_name"], job_id)
                if self._on_trigger:
                    try:
                        self._on_trigger(job["script_name"], job.get("params", {}))
                    except Exception as e:
                        logger.error("定时执行失败 %s: %s", job_id, e)
                self._jobs[job_id]["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._update_next_run(job_id)
                self._save()
                time.sleep(60)
            else:
                wait = min(next_run - now, 30)
                time.sleep(max(wait, 1))

    def _update_next_run(self, job_id):
        job = self._jobs.get(job_id)
        if not job:
            return
        cron_expr = job.get("cron_expr", "")
        next_t = self._parse_cron(cron_expr)
        self._jobs[job_id]["next_run"] = next_t

    def _parse_cron(self, cron_expr):
        now = time.time()
        try:
            parts = cron_expr.strip().split()
            if len(parts) == 1:
                interval = self._parse_duration(parts[0])
                return now + interval
            if len(parts) >= 5:
                return self._parse_5field_cron(parts, now)
        except Exception as e:
            logger.error("解析cron表达式失败 '%s': %s", cron_expr, e)
        return now + 3600

    def _parse_duration(self, s):
        m = re.match(r'^(\d+)([smhd])$', s.lower())
        if not m:
            return 3600
        val = int(m.group(1))
        unit = m.group(2)
        if unit == 's':
            return val
        elif unit == 'm':
            return val * 60
        elif unit == 'h':
            return val * 3600
        elif unit == 'd':
            return val * 86400
        return 3600

    def _parse_5field_cron(self, parts, now):
        import datetime
        minute, hour, dom, month, dow = parts
        dt = datetime.datetime.fromtimestamp(now)
        for offset in range(1, 1441):
            candidate = dt + datetime.timedelta(minutes=offset)
            if self._cron_field_match(minute, candidate.minute, 0, 59) and \
               self._cron_field_match(hour, candidate.hour, 0, 23) and \
               self._cron_field_match(dom, candidate.day, 1, 31) and \
               self._cron_field_match(month, candidate.month, 1, 12) and \
               self._cron_field_match(dow, candidate.isoweekday() % 7, 0, 6):
                return candidate.timestamp()
        return now + 3600

    def _cron_field_match(self, field, value, lo, hi):
        if field == '*':
            return True
        for part in field.split(','):
            if '/' in part:
                base, step = part.split('/', 1)
                step = int(step)
                start = lo if base == '*' else int(base)
                if value >= start and (value - start) % step == 0:
                    return True
            elif '-' in part:
                a, b = part.split('-', 1)
                if int(a) <= value <= int(b):
                    return True
            else:
                if value == int(part):
                    return True
        return False