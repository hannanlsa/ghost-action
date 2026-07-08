#!/usr/bin/env python3
"""GhostAction - 通用桌面RPA自动化工具"""
import os
import sys
import logging
import logging.handlers
import time
import faulthandler
import traceback

if hasattr(sys, 'stderr') and sys.stderr is not None:
    faulthandler.enable()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(os.path.expanduser("~"), "GhostAction", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

sys.path.insert(0, os.path.join(BASE_DIR, "src"))


def setup_logging():
    log_format = "%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(log_format, datefmt=date_format)

    main_log = os.path.join(LOGS_DIR, "app.log")
    fh = logging.handlers.RotatingFileHandler(main_log, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)

    error_log = os.path.join(LOGS_DIR, "error.log")
    eh = logging.handlers.RotatingFileHandler(error_log, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    eh.setFormatter(formatter)
    eh.setLevel(logging.ERROR)

    crash_log = os.path.join(LOGS_DIR, "crash.log")
    crash_fh = logging.handlers.RotatingFileHandler(crash_log, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    crash_fh.setFormatter(formatter)
    crash_fh.setLevel(logging.CRITICAL)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(eh)
    root.addHandler(crash_fh)

    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        root.addHandler(console)

    for name in ["recorder", "player", "gui", "accessibility"]:
        logging.getLogger(name).setLevel(logging.DEBUG)

    logging.info("=" * 60)
    logging.info("GhostAction 启动")
    logging.info("PID=%d CWD=%s", os.getpid(), BASE_DIR)
    logging.info("=" * 60)


def handle_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.critical("未捕获异常: %s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def handle_threading_exception(args):
    logging.critical("线程异常: %s\n%s", args.exc_value, "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))


if __name__ == "__main__":
    setup_logging()
    sys.excepthook = handle_exception
    try:
        import threading
        threading.excepthook = handle_threading_exception
    except Exception:
        pass

    try:
        from gui import main
        main()
    except Exception as e:
        logging.critical("主循环崩溃: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        logging.info("GhostAction 退出")
