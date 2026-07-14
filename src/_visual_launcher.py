import sys, os, json, logging, time, traceback
LOG_FILE = '/Users/panxiao/GhostAction/logs/visual_launcher.log'
fh = logging.FileHandler(LOG_FILE, mode='a')
fh.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logging.getLogger().addHandler(fh)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('visual_launcher')
logger.info('=== LAUNCHER START ===')
logger.info('Python: %s', sys.executable)
logger.info('Version: %s', sys.version)
logger.info('CWD: %s', os.getcwd())
logger.info('PID: %d', os.getpid())
logger.info('PPID: %d', os.getppid())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
html_path = '/Users/panxiao/华为云码道专用文件/昨日重现/src/visual_editor_html/editor.html'
logger.info('html_path=%s exists=%s', html_path, os.path.exists(html_path))
blockly_path = os.path.join(os.path.dirname(html_path), 'blockly.min.js')
logger.info('blockly_path=%s exists=%s size=%s', blockly_path, os.path.exists(blockly_path), os.path.getsize(blockly_path) if os.path.exists(blockly_path) else 'N/A')
try:
    import webview
    logger.info('pywebview imported OK, version=%s', getattr(webview, '__version__', 'unknown'))
except ImportError as e:
    logger.error('pywebview import FAILED: %s', e)
    sys.exit(1)
class WinApi:
    def close(self):
        webview.windows[0].destroy()
    def minimize(self):
        webview.windows[0].minimize()
    def toggle_fullscreen(self):
        w=webview.windows[0]
        w.toggle_fullscreen()
try:
    window = webview.create_window('', html_path, width=1200, height=800, min_size=(800, 600), resizable=True, js_api=WinApi())
    logger.info('webview.create_window OK')
except Exception as e:
    logger.error('webview.create_window FAILED: %s', e)
    logger.error(traceback.format_exc())
    sys.exit(1)
try:
    logger.info('calling webview.start()...')
    webview.start()
    logger.info('webview.start() returned normally')
except Exception as e:
    logger.error('webview.start() FAILED: %s', e)
    logger.error(traceback.format_exc())
