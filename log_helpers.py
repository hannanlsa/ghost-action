import time
import logging
import functools
import inspect

action_log = logging.getLogger("action")
sync_log = logging.getLogger("sync")


def log_call(module, op_type="CALL", level="debug"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log_fn = getattr(action_log, level, action_log.debug)
            t0 = time.time()
            func_name = func.__qualname__
            sig_parts = []
            try:
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                for p in params[:5]:
                    if p == "self":
                        continue
                    v = bound.arguments.get(p)
                    if v is not None:
                        sv = repr(v)
                        if len(sv) > 80:
                            sv = sv[:77] + "..."
                        sig_parts.append(f"{p}={sv}")
            except Exception:
                pass
            args_str = ", ".join(sig_parts) if sig_parts else ""
            log_fn("[%s] %s %s(%s)", module, op_type, func_name, args_str)
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.time() - t0) * 1000
                if elapsed_ms > 50:
                    action_log.info("[%s] %s_DONE %s elapsed=%.1fms", module, op_type, func_name, elapsed_ms)
                else:
                    log_fn("[%s] %s_DONE %s elapsed=%.1fms", module, op_type, func_name, elapsed_ms)
                return result
            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000
                action_log.error("[%s] %s_FAIL %s elapsed=%.1fms error=%s", module, op_type, func_name, elapsed_ms, e)
                raise
        return wrapper
    return decorator


def log_step(module, step_type, detail="", elapsed_ms=None):
    if elapsed_ms is not None:
        if elapsed_ms > 100:
            action_log.info("[%s] STEP %s %s elapsed=%.1fms", module, step_type, detail, elapsed_ms)
        else:
            action_log.debug("[%s] STEP %s %s elapsed=%.1fms", module, step_type, detail, elapsed_ms)
    else:
        action_log.debug("[%s] STEP %s %s", module, step_type, detail)


def log_error(module, error_type, detail="", exception=None):
    if exception:
        action_log.error("[%s] ERROR %s %s exception=%s", module, error_type, detail, exception)
    else:
        action_log.error("[%s] ERROR %s %s", module, error_type, detail)


def log_warn(module, warn_type, detail=""):
    action_log.warning("[%s] WARN %s %s", module, warn_type, detail)


def log_sync(module, event_type, detail="", elapsed_ms=None):
    if elapsed_ms is not None:
        sync_log.debug("[%s] %s %s elapsed=%.1fms", module, event_type, detail, elapsed_ms)
    else:
        sync_log.debug("[%s] %s %s", module, event_type, detail)


class StepTimer:
    def __init__(self, module, step_name):
        self.module = module
        self.step_name = step_name
        self.t0 = None

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.t0) * 1000
        if exc_type:
            action_log.error("[%s] TIMER_FAIL %s elapsed=%.1fms error=%s", self.module, self.step_name, elapsed_ms, exc_val)
        elif elapsed_ms > 100:
            action_log.info("[%s] TIMER %s elapsed=%.1fms", self.module, self.step_name, elapsed_ms)
        else:
            action_log.debug("[%s] TIMER %s elapsed=%.1fms", self.module, self.step_name, elapsed_ms)
        return False