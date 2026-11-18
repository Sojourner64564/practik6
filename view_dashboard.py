"""Запуск локального сервера и открытие дашборда в браузере (с поддержкой Range для перемотки видео)."""
import functools
import os
import re
import socket
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config as cfg
import dashboard


class RangeHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler без Range ломает перемотку <video> в Chrome — добавляем."""
    _remaining = None

    def log_message(self, *a):
        pass

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        m = re.match(r"bytes=(\d*)-(\d*)$", rng or "")
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        a, b = m.groups()
        if a == "":
            start, end = max(0, size - int(b or 0)), size - 1
        else:
            start, end = int(a), min(int(b) if b else size - 1, size - 1)
        if start >= size or start > end:
            self.send_error(416, "Requested Range Not Satisfiable")
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        try:
            if self._remaining is None:
                return super().copyfile(source, outputfile)
            left = self._remaining
            while left > 0:
                chunk = source.read(min(64 * 1024, left))
                if not chunk:
                    break
                outputfile.write(chunk)
                left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


def free_port() -> int:
    for p in (*cfg.SERVER_PORTS, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("нет свободных портов")


def main():
    dashboard.build()  # всегда пересобираем — дёшево и данные свежие
    port = free_port()
    handler = functools.partial(RangeHandler, directory=str(cfg.ROOT))
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/out/dashboard.html"
    print(f"Дашборд: {url}\nОстановить: Ctrl+C")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
