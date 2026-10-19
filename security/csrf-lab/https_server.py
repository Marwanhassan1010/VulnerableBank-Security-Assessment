import http.server
import ssl
from http.cookies import SimpleCookie
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CERT = ROOT / '.runtime/csrf-tls/localhost.crt'
KEY = ROOT / '.runtime/csrf-tls/localhost.key'
LAB_HOST = 'localhost:9443'


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Never log request headers, cookie values, or user-controlled URLs.
        pass

    def reply(self, status, body, set_cookie=False):
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        if set_cookie:
            self.send_header('Set-Cookie',
                'vb005_lab=synthetic-session; Path=/; Secure; HttpOnly; SameSite=None')
        self.end_headers()
        self.wfile.write(body)

    def isolated_cookies(self):
        if self.headers.get('Host', '').lower() != LAB_HOST:
            self.reply(421, b'Use https://localhost:9443 only')
            return None
        cookies = SimpleCookie()
        raw = self.headers.get('Cookie', '')
        # Check names before parsing; never return or log cookie values.
        names = {part.strip().split('=', 1)[0] for part in raw.split(';')}
        if 'vb_session' in names:
            self.reply(409, b'FAIL: banking session cookie present; stop laboratory')
            return None
        cookies.load(raw)
        return cookies

    def do_GET(self):
        if self.isolated_cookies() is None:
            return
        self.reply(200, b'PASS: banking session cookie absent; HTTPS laboratory ready', True)

    def do_POST(self):
        cookies = self.isolated_cookies()
        if cookies is None:
            return
        authenticated = ('vb005_lab' in cookies
                         and cookies['vb005_lab'].value == 'synthetic-session')
        self.reply(200 if authenticated else 401,
                   b'PASS: banking session cookie absent; synthetic HTTPS POST received'
                   if authenticated else b'Laboratory cookie missing or invalid')


def main():
    server = http.server.HTTPServer(('127.0.0.1', 9443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(CERT), keyfile=str(KEY))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print('VB-005 HTTPS laboratory: https://localhost:9443 (loopback only)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('VB-005 HTTPS laboratory stopped', flush=True)
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
