"""Tiny pty driver + ANSI screen emulator used by Spacue's tests.

No external dependencies. Feeds raw pty output into a minimal VT100
interpreter and exposes the rendered screen as text.
"""
import codecs
import fcntl
import os
import pty
import re
import select
import struct
import termios
import time

KEYS = {
    "Up": b"\x1b[A",
    "Down": b"\x1b[B",
    "Right": b"\x1b[C",
    "Left": b"\x1b[D",
    "Enter": b"\r",
    "Esc": b"\x1b",
    "Tab": b"\t",
    "BS": b"\x7f",
    "Space": b" ",
    "C-a": b"\x01",
    "C-c": b"\x03",
    "C-g": b"\x07",
    "C-n": b"\x0e",
    "C-p": b"\x10",
    "C-r": b"\x12",
    "C-u": b"\x15",
    "C-w": b"\x17",
}


class Screen:
    def __init__(self, cols=100, rows=30):
        self.cols, self.rows = cols, rows
        self.grid = [[" "] * cols for _ in range(rows)]
        self.cy = self.cx = 0
        self.saved = (0, 0)
        self.top, self.bottom = 0, rows - 1
        self._tail = ""
        self._dec = codecs.getincrementaldecoder("utf-8")("replace")

    # -- public ------------------------------------------------------------
    def feed(self, data: bytes):
        text = self._tail + self._dec.decode(data)
        self._tail = ""
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch == "\x1b":
                ni = self._esc(text, i + 1)
                if ni is None:
                    self._tail = text[i:]
                    return
                i = ni
            elif ch == "\r":
                self.cx = 0
                i += 1
            elif ch == "\n":
                self._linefeed()
                i += 1
            elif ch == "\b":
                self.cx = max(0, self.cx - 1)
                i += 1
            elif ch == "\t":
                self.cx = min(self.cols - 1, (self.cx // 8 + 1) * 8)
                i += 1
            elif ch in ("\x07", "\x00"):
                i += 1
            else:
                self._put(ch)
                i += 1

    def text(self) -> str:
        return "\n".join("".join(row).rstrip() for row in self.grid).rstrip()

    def contains(self, s: str) -> bool:
        return s in self.text()

    def line(self, y: int) -> str:
        return "".join(self.grid[y]).rstrip()

    def find(self, s: str):
        """Return (row, col) of first occurrence or None."""
        for y, row in enumerate(self.grid):
            line = "".join(row)
            x = line.find(s)
            if x >= 0:
                return y, x
        return None

    # -- escapes -----------------------------------------------------------
    def _esc(self, t, i):
        if i >= len(t):
            return None
        c = t[i]
        if c == "[":
            j = i + 1
            while j < len(t) and not ("@" <= t[j] <= "~"):
                j += 1
            if j >= len(t):
                return None
            self._csi(t[i + 1:j], t[j])
            return j + 1
        if c == "]":  # OSC ... BEL | ST
            j = i + 1
            while j < len(t):
                if t[j] == "\x07":
                    return j + 1
                if t[j] == "\x1b" and j + 1 < len(t) and t[j + 1] == "\\":
                    return j + 2
                j += 1
            return None
        if c == "7":
            self.saved = (self.cy, self.cx)
        elif c == "8":
            self.cy, self.cx = self.saved
        elif c == "M":
            self._rev_index()
        elif c == "D":
            self._linefeed()
        elif c == "E":
            self._linefeed()
            self.cx = 0
        elif c in "()#=%>":
            return i + 2
        return i + 1

    def _csi(self, params, final):
        params = params.lstrip("?>!")
        p = [int(x) if x else 0 for x in re.split(r"[;:]", params)] if params else []
        n = p[0] if p else 0
        if final == "A":
            self.cy = max(self.top, self.cy - max(1, n))
        elif final == "B":
            self.cy = min(self.bottom, self.cy + max(1, n))
        elif final == "C":
            self.cx = min(self.cols - 1, self.cx + max(1, n))
        elif final == "D":
            self.cx = max(0, self.cx - max(1, n))
        elif final == "E":
            self.cy = min(self.bottom, self.cy + max(1, n))
            self.cx = 0
        elif final == "F":
            self.cy = max(self.top, self.cy - max(1, n))
            self.cx = 0
        elif final == "G":
            self.cx = min(self.cols - 1, max(0, n - 1))
        elif final == "d":
            self.cy = min(self.rows - 1, max(0, n - 1))
        elif final in "Hf":
            row = p[0] if p else 0
            col = p[1] if len(p) > 1 else 0
            self.cy = min(self.rows - 1, max(0, (row or 1) - 1))
            self.cx = min(self.cols - 1, max(0, (col or 1) - 1))
        elif final == "J":
            self._erase_display(n)
        elif final == "K":
            self._erase_line(n)
        elif final == "L":
            self._insert_lines(max(1, n))
        elif final == "M":
            self._delete_lines(max(1, n))
        elif final == "S":
            self._scroll_up(max(1, n))
        elif final == "T":
            self._scroll_down(max(1, n))
        elif final == "r":
            top = p[0] if p else 0
            bot = p[1] if len(p) > 1 else 0
            self.top = max(0, (top or 1) - 1)
            self.bottom = min(self.rows - 1, (bot or self.rows) - 1)
            self.cy, self.cx = self.top, 0
        elif final == "s":
            self.saved = (self.cy, self.cx)
        elif final == "u":
            self.cy, self.cx = self.saved
        # m (SGR), h/l (modes), etc. are ignored

    # -- primitives --------------------------------------------------------
    def _put(self, ch):
        if self.cx >= self.cols:
            self.cx = 0
            self._linefeed()
        if 0 <= self.cy < self.rows:
            self.grid[self.cy][self.cx] = ch
        self.cx += 1

    def _linefeed(self):
        if self.cy == self.bottom:
            self._scroll_up(1)
        else:
            self.cy = min(self.rows - 1, self.cy + 1)

    def _rev_index(self):
        if self.cy == self.top:
            self._scroll_down(1)
        else:
            self.cy = max(0, self.cy - 1)

    def _scroll_up(self, n):
        for _ in range(min(n, self.bottom - self.top + 1)):
            self.grid.insert(self.bottom + 1, [" "] * self.cols)
            del self.grid[self.top]
            if self.cy > self.top:
                self.cy -= 1

    def _scroll_down(self, n):
        for _ in range(min(n, self.bottom - self.top + 1)):
            self.grid.insert(self.top, [" "] * self.cols)
            del self.grid[self.bottom + 1]
            if self.cy < self.bottom:
                self.cy += 1

    def _erase_display(self, n):
        if n in (2, 3):
            self.grid = [[" "] * self.cols for _ in range(self.rows)]
        elif n == 1:
            for y in range(self.cy + 1):
                self._erase_line(2, y)
            self._erase_line(0)
        else:
            self._erase_line(0)
            for y in range(self.cy + 1, self.rows):
                self._erase_line(2, y)

    def _erase_line(self, n, y=None):
        y = self.cy if y is None else y
        if n == 2:
            for x in range(self.cols):
                self.grid[y][x] = " "
        elif n == 1:
            for x in range(self.cx + 1):
                self.grid[y][x] = " "
        else:
            for x in range(self.cx, self.cols):
                self.grid[y][x] = " "

    def _insert_lines(self, n):
        for _ in range(min(n, self.bottom - self.cy + 1)):
            self.grid.insert(self.cy, [" "] * self.cols)
            del self.grid[self.bottom + 1]

    def _delete_lines(self, n):
        for _ in range(min(n, self.bottom - self.cy + 1)):
            del self.grid[self.cy]
            self.grid.insert(self.bottom, [" "] * self.cols)


class Term:
    def __init__(self, cmd, cols=100, rows=30, env=None, cwd=None):
        self.cols, self.rows = cols, rows
        pid, fd = pty.fork()
        if pid == 0:
            env2 = dict(os.environ)
            env2.update(env or {})
            env2.setdefault("TERM", "xterm-256color")
            os.environ.clear()
            os.environ.update(env2)
            fcntl.ioctl(0, termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, cols, 0, 0))
            if cwd:
                os.chdir(cwd)
            os.execvp(cmd[0], cmd)
            os._exit(127)
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0))
        self.screen = Screen(cols, rows)
        self.raw = b""

    def send(self, data):
        if isinstance(data, str):
            data = data.encode()
        os.write(self.fd, data)

    def send_keys(self, *seqs):
        for s in seqs:
            if isinstance(s, str) and len(s) == 3 and s[:2] == "C-" and s[2].isalpha():
                self.send(bytes([ord(s[2].lower()) - 96]))
            else:
                self.send(KEYS.get(s, s))

    def pump(self, timeout=0.4):
        """Read everything available; wait until `timeout` of silence."""
        end = time.time() + 10
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], timeout)
            if not r:
                return
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                return
            if not data:
                return
            self.raw += data
            self.screen.feed(data)

    def wait_for(self, text, timeout=6):
        end = time.time() + timeout
        while time.time() < end:
            self.pump(0.15)
            if text in self.screen.text():
                return True
        return False

    def wait_gone(self, text, timeout=6):
        end = time.time() + timeout
        while time.time() < end:
            self.pump(0.15)
            if text not in self.screen.text():
                return True
        return False

    def wait_idle(self, quiet=0.35, timeout=8):
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], quiet)
            if not r:
                return
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                return
            if not data:
                return
            self.raw += data
            self.screen.feed(data)

    def close(self):
        try:
            os.kill(self.pid, 9)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.waitpid(self.pid, 0)
        except OSError:
            pass


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", s)
