"""Silent static file server for the typhoon dashboard.

Launched by open_dashboard.vbs through pythonw.exe (no console window).
pythonw sets sys.stdout/sys.stderr to None, which makes http.server's
logging crash on every request, so both streams and log_message are
neutralised here.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8080
BIND = '127.0.0.1'

os.chdir(ROOT)
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass


def main():
    try:
        httpd = ThreadingHTTPServer((BIND, PORT), QuietHandler)
    except OSError:
        return 1  # port already in use: another instance is serving
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
