"""Run API on loopback and Streamlit on Render's public port; fail together."""
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_config():
    required = ('PROCUREMENT_DATABASE_URL', 'GROQ_API_KEY', 'TAVILY_API_KEY', 'PROCUREMENT_TEAM_PASSWORD')
    missing = [name for name in required if not os.getenv(name, '').strip()]
    if missing:
        raise RuntimeError('Missing environment variables: ' + ', '.join(missing))
    if len(os.environ['PROCUREMENT_TEAM_PASSWORD']) < 24:
        raise RuntimeError('Use a generated team password of at least 24 characters.')


def check_database():
    # Read-only validation. Never automatically migrate or recreate the database.
    from sqlalchemy import text
    from app.procurement.pg_database import get_engine
    tables = ('procurement_entries', 'shipping_line_contacts', 'shipping_line_aliases',
              'port_aliases', 'lane_origin_scope', 'requests', 'request_destinations', 'drafts')
    with get_engine().connect() as conn:
        for table in tables:
            conn.execute(text('SELECT 1 FROM procurement.' + table + ' LIMIT 1'))
    get_engine().dispose()


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    check_config()
    check_database()
    # Internal API credentials are random on each container start and shared only
    # by its two child processes. The API is not bound to the public interface.
    os.environ['PROCUREMENT_API_TOKEN'] = secrets.token_urlsafe(48)
    os.environ['API_BASE_URL'] = 'http://127.0.0.1:8000'
    port = int(os.getenv('PORT', '10000'))
    if not 1024 <= port <= 65535 or port == 8000:
        raise RuntimeError('PORT must be 1024–65535 and different from the internal API port 8000.')
    children = []
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn',
            'app.procurement.demo_api:app', '--host', '127.0.0.1', '--port', '8000',
            '--no-access-log']))
        deadline = time.monotonic() + 60
        ready = False
        while time.monotonic() < deadline and not stopping:
            if children[0].poll() is not None:
                raise RuntimeError('API exited during startup.')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2) as response:
                    ready = response.status == 200
                if ready:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        if stopping:
            return
        if not ready:
            raise RuntimeError('API readiness timed out.')
        children.append(subprocess.Popen([sys.executable, '-m', 'streamlit', 'run',
            'frontend/procurement_hosted.py', '--server.address=0.0.0.0',
            f'--server.port={port}', '--server.headless=true',
            '--server.enableXsrfProtection=true', '--server.enableCORS=true',
            '--browser.gatherUsageStats=false', '--server.fileWatcherType=none']))
        while not stopping:
            if any(p.poll() is not None for p in children):
                raise RuntimeError('A server exited. Restarting the complete service is required.')
            time.sleep(0.5)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Database exceptions can contain connection details; print only the type.
        if isinstance(exc, RuntimeError):
            print(str(exc), file=sys.stderr)
        else:
            print('Startup failed: ' + type(exc).__name__ + '. Check configuration and database access.', file=sys.stderr)
        sys.exit(1)
