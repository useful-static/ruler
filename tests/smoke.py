#!/usr/bin/env python3
"""Smoke tests for the ruler — run before every push.

Launches headless Chromium and asserts the invariants that have broken in
the past: sane default sizes, physical zoom-invariance, reload consistency,
estimate self-healing, calibration round-trips, and visible number labels.

Usage:
    python3 tests/smoke.py                # tests public/index.html from this repo
    python3 tests/smoke.py --url URL      # e.g. https://ruler.free after a deploy

No dependencies beyond python3 and a chromium/chrome binary on PATH.
"""
import argparse, base64, json, os, shutil, socket, struct
import subprocess, sys, tempfile, time, urllib.request

# ---------- minimal CDP websocket client (no pip deps) ----------
class WS:
    def __init__(self, url):
        host, rest = url.split("://", 1)[1].split("/", 1)
        host, port = host.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET /{rest} HTTP/1.1\r\nHost: {host}:{port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        assert b"101" in buf.split(b"\r\n", 1)[0], "websocket handshake failed"

    def send(self, text):
        data = text.encode()
        mask = os.urandom(4)
        head = b"\x81"
        n = len(data)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("websocket closed")
            buf += chunk
        return buf

    def recv(self):
        while True:
            b0, b1 = self._read(2)
            op, ln = b0 & 0x0F, b1 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read(8))[0]
            data = self._read(ln)
            if op == 1:
                return data.decode()
            if op == 8:
                raise ConnectionError("websocket closed by peer")
            # ignore ping/pong/continuation for this use


class CDP:
    def __init__(self, port):
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(
                    f"http://localhost:{port}/json", timeout=2))
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("no CDP page target")
        self.ws = WS(page["webSocketDebuggerUrl"])
        self.mid = 0

    def cmd(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method,
                                 "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.cmd("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        res = r["result"]
        if res.get("subtype") == "error":
            raise RuntimeError("JS: " + res.get("description", "?"))
        return res.get("value")

    def nav(self, url):
        self.cmd("Page.navigate", {"url": url})
        time.sleep(1.2)

    def zoom(self, dsf, w, h):   # emulate browser zoom: viewport/dsf scale together
        self.cmd("Emulation.setDeviceMetricsOverride", {
            "width": w, "height": h, "deviceScaleFactor": dsf, "mobile": False})
        time.sleep(1.2)          # let the resolution-MQ watcher redraw

    def unzoom(self):
        self.cmd("Emulation.clearDeviceMetricsOverride")
        time.sleep(1.2)

    def dbg(self):
        return self.js("JSON.stringify(RULER_DEBUG())") and \
               json.loads(self.js("JSON.stringify(RULER_DEBUG())"))


# ---------- the tests ----------
FAILS = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + ("" if cond else f" — {detail}"))
    if not cond:
        FAILS.append(name)


def approx(a, b, tol):
    return abs(a - b) <= tol


def label_ink(c):
    """Count accent-coloured (number-label) pixels on the canvas."""
    return c.js("""
      (() => {
        const cv = document.getElementById('ruler');
        const g = cv.getContext('2d');
        const d = g.getImageData(0, 0, cv.width, cv.height).data;
        let n = 0;
        for (let i = 0; i < d.length; i += 4)
          if (d[i] > 150 && d[i+1] < 130 && d[i+2] < 130 && d[i+3] > 100) n++;
        return n;
      })()""")


def run(url):
    port = 9333
    prof = tempfile.mkdtemp(prefix="ruler-smoke-")
    chrome = shutil.which("chromium") or shutil.which("chromium-browser") \
        or shutil.which("google-chrome")
    assert chrome, "no chromium/chrome on PATH"
    proc = subprocess.Popen([
        chrome, "--headless", f"--remote-debugging-port={port}", "--no-sandbox",
        "--hide-scrollbars", "--window-size=1600,900",
        f"--user-data-dir={prof}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        c = CDP(port)
        c.cmd("Page.enable")
        c.cmd("Network.enable")
        c.cmd("Network.setCacheDisabled", {"cacheDisabled": True})

        print("T0 old-schema storage is wiped once")
        c.nav(url)
        c.js("localStorage.clear();"
             "localStorage.setItem('ruler.ppi.v1','40');"
             "localStorage.setItem('ruler.devppi.v1','660');"
             "localStorage.setItem('ruler.calres.v1','{\"w\":9600,\"h\":5400}')")
        c.nav(url)
        check("v1 keys wiped",
              c.js("Object.keys(localStorage).filter(k =>"
                   " k.startsWith('ruler.') && k.includes('.v1')).length") == 0)
        check("schema stamped",
              c.js("localStorage.getItem('ruler.schema')") == "2")
        t0 = c.dbg()
        check("defaults after wipe", approx(t0["devPpi"], t0["defaultPpi"], 0.5),
              str(t0["devPpi"]))

        print("T1 clean load at 100%")
        c.nav(url)
        c.js("localStorage.clear()")
        c.nav(url)
        t1 = c.dbg()
        check("default devPpi == device-class default",
              approx(t1["devPpi"], t1["defaultPpi"], 0.5), json.dumps(t1))
        check("ppi == devPpi at dpr 1", approx(t1["ppi"], t1["devPpi"], 0.5))
        k1 = t1["ppi"] / 96
        check("band thickness == 160·k",
              approx(t1["bandCss"]["h"], round(160 * k1), 2), str(t1["bandCss"]))
        check("band spans ~95% of viewport",
              approx(t1["bandCss"]["w"], 0.95 * c.js("innerWidth"), 30))
        check("nothing persisted without user action",
              c.js("Object.keys(localStorage).filter(k =>"
                   " k.startsWith('ruler.') && k !== 'ruler.schema').length") == 0)
        check("number labels drawn", label_ink(c) > 100)

        print("T2 zoom to 500% after load (dynamic tracking)")
        c.zoom(5, 320, 180)
        t2 = c.dbg()
        check("dpr tracked without reload", t2["dpr"] == 5, str(t2["dpr"]))
        check("ppi drops by the zoom", approx(t2["ppi"], t1["ppi"] / 5, 0.5))
        check("physical width constant",
              approx(t2["bandDev"]["w"], t1["bandDev"]["w"], 10),
              f'{t2["bandDev"]} vs {t1["bandDev"]}')
        check("physical thickness constant",
              approx(t2["bandDev"]["h"], t1["bandDev"]["h"], 10))
        check("labels still drawn zoomed", label_ink(c) > 100)

        print("T3 reload while zoomed (zoom-independent estimate)")
        c.nav(url)
        t3 = c.dbg()
        check("state identical to pre-reload",
              approx(t3["ppi"], t2["ppi"], 0.5) and
              approx(t3["bandDev"]["w"], t2["bandDev"]["w"], 10), json.dumps(t3))
        check("native res not multiplied by zoom",
              t3["calRes"]["w"] == t1["calRes"]["w"], str(t3["calRes"]))

        print("T4 back to 100% (round trip)")
        c.unzoom()
        t4 = c.dbg()
        check("returns to the original render",
              approx(t4["ppi"], t1["ppi"], 0.5) and
              t4["bandCss"] == t1["bandCss"], json.dumps(t4))

        print("T5 stale stored estimates are discarded at load")
        c.js("localStorage.clear();"
             "localStorage.setItem('ruler.devppi.est.v2','660');"
             "localStorage.setItem('ruler.calres.v2','{\"w\":6400,\"h\":3600}')")
        c.nav(url)
        t5 = c.dbg()
        check("stored estimate ignored (fresh default)",
              approx(t5["devPpi"], t5["defaultPpi"], 0.5), str(t5["devPpi"]))
        check("stored res estimate ignored (fresh detect)",
              t5["calRes"]["w"] == c.js("screen.width"), str(t5["calRes"]))
        check("both stale keys deleted",
              c.js("localStorage.getItem('ruler.devppi.est.v2')") is None and
              c.js("localStorage.getItem('ruler.calres.v2')") is None)
        c.js("localStorage.clear();"
             "localStorage.setItem('ruler.devppi.v2','2000')")   # impossible calibration
        c.nav(url)
        t5c = c.dbg()
        check("garbage calibration discarded",
              not t5c["calibrated"] and approx(t5c["devPpi"], t5c["defaultPpi"], 0.5),
              json.dumps({"cal": t5c["calibrated"], "devPpi": t5c["devPpi"]}))

        print("T6 calibration round trip")
        c.js("localStorage.clear()")
        c.nav(url)
        c.js("(() => { const s = document.getElementById('calSlider');"
             " s.value = 600; s.dispatchEvent(new Event('input'));"
             " document.getElementById('saveCal').click(); })()")
        t6 = c.dbg()
        check("slider calibrates (600 dev px card)",
              approx(t6["devPpi"], 600 / 3.3701, 1) and t6["calibrated"],
              str(t6["devPpi"]))
        c.js("document.querySelector('#infoSize .act').click()")
        t6b = c.dbg()
        check("↺ reset restores the estimate",
              approx(t6b["devPpi"], t6b["defaultPpi"], 0.5) and not t6b["calibrated"],
              str(t6b["devPpi"]))
        c.js("document.querySelector('#infoRes .hot').click()")
        c.js("(() => { const i = document.querySelectorAll('#infoRes input.editin');"
             " i[0].value='2560'; i[1].value='1440';"
             " i[1].dispatchEvent(new KeyboardEvent('keydown',"
             "   {key:'Enter', bubbles:true})); })()")
        time.sleep(0.4)
        c.nav(url)
        t6c = c.dbg()
        check("user-typed native res survives reload",
              t6c["calRes"]["w"] == 2560, str(t6c["calRes"]))
        c.js("document.querySelector('#infoRes .act').click()")
        t6d = c.dbg()
        check("↺ redetect restores detected res",
              t6d["calRes"]["w"] == c.js("screen.width"), str(t6d["calRes"]))

        print("T6b calculation exactness: drawn scale == devPpi to <0.1%")
        c.js("localStorage.clear()")
        c.nav(url)
        calc = json.loads(c.js(
            "(() => { const d = RULER_DEBUG();"
            " return JSON.stringify({"
            "  ppi: d.ppi, devPpi: d.devPpi, dpr: d.dpr,"
            "  cmDev: d.ppi / 2.54 * d.dpr,"          # drawn cm in device px
            "  trueCmDev: d.devPpi / 2.54 }); })()"))
        check("1 drawn cm == devPpi/2.54 device px (no scale drift)",
              approx(calc["cmDev"], calc["trueCmDev"], calc["trueCmDev"] * 0.001),
              json.dumps(calc))
        # touch devices must not engage the outer/inner zoom snap (a misfired
        # 0.9 snap would inflate the estimate ~11%)
        c.cmd("Emulation.setTouchEmulationEnabled",
              {"enabled": True, "maxTouchPoints": 5})
        c.cmd("Emulation.setDeviceMetricsOverride", {
            "width": 393, "height": 852, "deviceScaleFactor": 3, "mobile": True})
        c.js("localStorage.clear()")
        c.nav(url)
        tt = c.dbg()
        check("touch: estimate == default × dpr exactly (zoom snap pinned to 1)",
              approx(tt["devPpi"], tt["defaultPpi"] * 3, 0.5),
              json.dumps({"devPpi": tt["devPpi"], "default": tt["defaultPpi"]}))
        c.cmd("Emulation.clearDeviceMetricsOverride")
        c.cmd("Emulation.setTouchEmulationEnabled",
              {"enabled": False, "maxTouchPoints": 1})
        c.js("localStorage.clear()")
        c.nav(url)

        print("T6c real-ruler cross-check calibrates")
        c.js("localStorage.clear()")
        c.nav(url)
        base = c.dbg()["devPpi"]
        c.js("document.getElementById('toggleCal').click();"
             "document.getElementById('ckSite').value='30';"
             "document.getElementById('ckReal').value='30.4';"
             "document.getElementById('ckApply').click()")
        t6e = c.dbg()
        check("devPpi scaled by 30/30.4 and saved",
              approx(t6e["devPpi"], base * 30 / 30.4, 0.5) and t6e["calibrated"],
              f'{t6e["devPpi"]} vs {base * 30 / 30.4}')

        print("T6d known device (UA-CH model) gets its exact panel density")
        c.js("localStorage.clear()")
        c.cmd("Emulation.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36"
                         " (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
            "userAgentMetadata": {
                "brands": [{"brand": "Chromium", "version": "126"}],
                "fullVersionList": [{"brand": "Chromium", "version": "126.0.0.0"}],
                "platform": "Android", "platformVersion": "14",
                "architecture": "", "model": "SM-S928B", "mobile": True,
                "bitness": "", "wow64": False}})
        c.cmd("Emulation.setTouchEmulationEnabled",
              {"enabled": True, "maxTouchPoints": 5})
        c.cmd("Emulation.setDeviceMetricsOverride", {
            "width": 412, "height": 915, "deviceScaleFactor": 3.5, "mobile": True})
        c.nav(url)
        time.sleep(1.0)                              # async UA-CH lookup + redraw
        t6f = c.dbg()
        import math
        exp = math.hypot(412 * 3.5, 915 * 3.5) / 6.79
        check("S24 Ultra density from 6.79in diagonal",
              approx(t6f["devPpi"], exp, 2), f'{t6f["devPpi"]} vs {exp:.0f}')
        c.cmd("Emulation.clearDeviceMetricsOverride")
        c.cmd("Emulation.setTouchEmulationEnabled",
              {"enabled": False, "maxTouchPoints": 1})
        c.cmd("Emulation.setUserAgentOverride", {"userAgent": ""})
        c.js("localStorage.clear()")
        c.nav(url)

        print("T7 fresh load at any zoom gives the same physical ruler")
        for dsf, w, h in [(5, 320, 180), (2, 800, 450), (0.5, 3200, 1800)]:
            c.js("localStorage.clear()")
            c.zoom(dsf, w, h)
            c.nav(url)
            tz = c.dbg()
            check(f"load at {int(dsf*100)}%: devPpi zoom-independent",
                  approx(tz["devPpi"], t1["devPpi"], 1),
                  f'{tz["devPpi"]} vs {t1["devPpi"]}')
            check(f"load at {int(dsf*100)}%: native res stable",
                  tz["calRes"]["w"] == t1["calRes"]["w"], str(tz["calRes"]))
            c.unzoom()
        c.js("localStorage.clear()")
        c.nav(url)

        print("T8 orientation")
        c.js("localStorage.clear()")
        c.nav(url)
        c.js("document.getElementById('ruler').click()")
        time.sleep(0.4)
        t7 = c.dbg()
        check("canvas click rotates", t7["orientation"] == "vertical")
        check("orientation persists",
              c.js("localStorage.getItem('ruler.orient.v1')") == "vertical")
        check("vertical band thickness == 220·k",
              approx(t7["bandCss"]["w"], round(220 * t7["ppi"] / 96), 2),
              str(t7["bandCss"]))
        c.js("localStorage.clear()")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(prof, ignore_errors=True)

    print(f"\n{'FAIL' if FAILS else 'PASS'}: "
          f"{len(FAILS)} failure(s)" + (f" — {FAILS}" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--url", default=f"file://{repo}/public/index.html")
    args = ap.parse_args()
    sys.exit(run(args.url))
