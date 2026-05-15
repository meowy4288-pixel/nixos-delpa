"""Web UI server for aider. Zero external dependencies — uses Python stdlib only."""

import json
import os
import queue
import sys
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from .main import run_goal
from .ui import add_output_callback, remove_output_callback


# ── HTML page (inlined, zero external files) ──

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>aider</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --font: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
  }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    line-height: 1.5;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }

  /* ── Header ── */
  header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }
  header h1 {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.5px;
  }
  header h1 span { color: var(--accent); }
  header .status {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-dim);
  }
  .status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--green);
  }
  .status-dot.running { background: var(--yellow); animation: pulse 1s infinite; }
  .status-dot.error { background: var(--red); }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

  /* ── Controls ── */
  .controls {
    display: flex;
    gap: 8px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
    flex-wrap: wrap;
  }
  .controls input, .controls select {
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px;
    border-radius: 6px;
    font-family: var(--font);
    font-size: 13px;
    outline: none;
    transition: border-color .15s;
  }
  .controls input:focus { border-color: var(--accent); }
  .controls input[type="text"] { flex: 1; min-width: 200px; }
  .controls input[type="text"].goal { flex: 3; }
  .controls button {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 8px 20px;
    border-radius: 6px;
    font-family: var(--font);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity .15s;
  }
  .controls button:hover { opacity: .85; }
  .controls button:disabled { opacity: .4; cursor: not-allowed; }
  .controls button.danger { background: var(--red); }
  .controls button.secondary {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
  }
  .controls button.secondary:hover { border-color: var(--text-dim); }
  .controls label {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-dim);
    font-size: 12px;
  }
  .controls label input[type="checkbox"] { accent-color: var(--accent); }

  /* ── Output ── */
  .output {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .output:empty::after {
    content: "Type a task and press Run to start.";
    color: var(--text-dim);
    font-style: italic;
  }
  .output .line { padding: 0; }
  .output .dim { color: var(--text-dim); }
  .output .green { color: var(--green); }
  .output .red { color: var(--red); }
  .output .yellow { color: var(--yellow); }
  .output .blue { color: var(--accent); }
  .output .magenta { color: #d2a8ff; }
  .output .cyan { color: #39d2c0; }
  .output .bold { font-weight: 600; }
  .output .italic { font-style: italic; }
  .output .separator {
    border: none;
    border-top: 1px solid var(--border);
    margin: 8px 0;
  }

  /* ── Scrollbar ── */
  .output::-webkit-scrollbar { width: 6px; }
  .output::-webkit-scrollbar-track { background: transparent; }
  .output::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* ── History side panel ── */
  .history-toggle {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-dim);
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--font);
  }
</style>
</head>
<body>

<header>
  <h1><span>▲</span> aider</h1>
  <div class="status">
    <span class="status-dot" id="statusDot"></span>
    <span id="statusText">Idle</span>
  </div>
</header>

<div class="controls">
  <input type="text" class="goal" id="goal" placeholder="Task description e.g. fix bug in auth.py" autofocus>
  <input type="text" id="project" placeholder="Project path (default: current dir)">
  <label><input type="checkbox" id="private" onclick="togglePrivate()"> Private</label>
  <label><input type="checkbox" id="dryRun"> Dry-run</label>
  <button id="runBtn" onclick="run()">Run</button>
  <button class="secondary" id="stopBtn" onclick="stop()" disabled>Stop</button>
  <button class="danger" onclick="clearOutput()">Clear</button>
</div>

<div class="output" id="output"></div>

<script>
let eventSource = null;
let running = false;

function addLine(text, cls = "") {
  const out = document.getElementById("output");
  const div = document.createElement("div");
  div.className = "line" + (cls ? " " + cls : "");
  div.textContent = text;
  out.appendChild(div);
  out.scrollTop = out.scrollHeight;
}

function setStatus(text, state) {
  document.getElementById("statusText").textContent = text;
  const dot = document.getElementById("statusDot");
  dot.className = "status-dot" + (state ? " " + state : "");
}

function clearOutput() {
  document.getElementById("output").innerHTML = "";
}

function togglePrivate() {
  document.getElementById("private").checked = !document.getElementById("private").checked;
}

function stop() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  running = false;
  document.getElementById("runBtn").disabled = false;
  document.getElementById("stopBtn").disabled = true;
  addLine("── Cancelled ──", "red bold");
  setStatus("Cancelled", "");
}

function run() {
  const goal = document.getElementById("goal").value.trim();
  if (!goal) { addLine("Please enter a task.", "yellow"); return; }

  clearOutput();
  running = true;
  document.getElementById("runBtn").disabled = true;
  document.getElementById("stopBtn").disabled = false;
  setStatus("Running", "running");

  const project = document.getElementById("project").value.trim();
  const isPrivate = document.getElementById("private").checked;
  const dryRun = document.getElementById("dryRun").checked;

  const params = new URLSearchParams({ goal, project, private: isPrivate, dry_run: dryRun });
  addLine("▲ aider", "cyan bold");
  addLine("──", "dim");
  addLine("Goal: " + goal, "blue");
  if (project) addLine("Project: " + project, "dim");
  if (dryRun) addLine("Dry run — no changes will be made", "yellow italic");
  addLine("");

  // Connect SSE
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/stream?" + Date.now());
  eventSource.onmessage = (e) => {
    if (e.data === "__DONE__") {
      eventSource.close();
      eventSource = null;
      running = false;
      document.getElementById("runBtn").disabled = false;
      document.getElementById("stopBtn").disabled = true;
      setStatus("Done", "");
      return;
    }
    if (e.data === "__FAIL__") {
      eventSource.close();
      eventSource = null;
      running = false;
      document.getElementById("runBtn").disabled = false;
      document.getElementById("stopBtn").disabled = true;
      setStatus("Failed", "error");
      return;
    }
    addLine(e.data);
  };
  eventSource.onerror = () => {
    if (!running) return;
    addLine("");
    addLine(" Connection lost. The task may have timed out or crashed.", "red");
    addLine(" Try a smaller project or a simpler task.", "dim");
    addLine(" You can also run from CLI: aider \"your task\" --project /path", "dim");
    running = false;
    document.getElementById("runBtn").disabled = false;
    document.getElementById("stopBtn").disabled = true;
    setStatus("Error", "error");
  };

  // POST the task
  fetch("/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal, project, private: isPrivate, dry_run: dryRun })
  }).catch(e => addLine("Request failed: " + e, "red"));
}

// Run on Enter
document.getElementById("goal").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !running) run();
});
</script>
</body>
</html>"""


# ── Output capture ──

_output_queue: queue.Queue = queue.Queue()
_stream_clients: list[queue.Queue] = []
_stream_lock = threading.Lock()


def _broadcast(text: str):
    with _stream_lock:
        dead: list[queue.Queue] = []
        for q in _stream_clients:
            try:
                q.put_nowait(text)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _stream_clients.remove(q)


def _ui_callback(text: str):
    _broadcast(text)


# ── HTTP Request Handler ──

class AiderHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default HTTP log

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── Routes ──

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "" or path == "/index.html":
            self._send_html(HTML_PAGE)
        elif path == "/stream":
            self._handle_sse()
        elif path == "/health":
            self._send_json({"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/run":
            self._handle_run()
        else:
            self.send_response(404)
            self.end_headers()

    # ── SSE handler ──

    def _handle_sse(self):
        q: queue.Queue = queue.Queue(maxsize=500)
        with _stream_lock:
            _stream_clients.append(q)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        idle_timeout = 300  # 5 min with no data = close
        idle_elapsed = 0.0

        try:
            while not self.server._stop_event.is_set():
                try:
                    text = q.get(timeout=2)
                    idle_elapsed = 0.0
                    for line in text.split("\n"):
                        if line.strip():
                            self.wfile.write(f"data: {line}\n".encode())
                        else:
                            self.wfile.write(b"data: \n")
                    self.wfile.write(b"\n")
                    self.wfile.flush()
                except queue.Empty:
                    idle_elapsed += 2.0
                    if idle_elapsed >= idle_timeout:
                        self.wfile.write(b"event: error\ndata: Timeout - no output for 5 minutes\n\n")
                        self.wfile.flush()
                        break
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _stream_lock:
                if q in _stream_clients:
                    _stream_clients.remove(q)

    # ── Run handler ──

    def _handle_run(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode())
        except (json.JSONDecodeError, ValueError, OSError) as e:
            self._send_json({"error": str(e)}, 400)
            return

        goal = body.get("goal", "").strip()
        if not goal:
            self._send_json({"error": "goal is required"}, 400)
            return

        project = body.get("project", "").strip()
        if not project:
            project = os.getcwd()
        project = os.path.abspath(project)
        if not os.path.isdir(project):
            self._send_json({"error": f"project not found: {project}"}, 400)
            return

        private = body.get("private", False)
        dry_run = body.get("dry_run", False)

        self._send_json({"status": "started", "goal": goal, "project": project})

        # Run in background thread
        t = threading.Thread(
            target=self._run_task,
            args=(goal, project, private, dry_run),
            daemon=True,
        )
        t.start()

    def _run_task(self, goal: str, project: str, private: bool, dry_run: bool):
        add_output_callback(_ui_callback)
        try:
            success = run_goal(goal, project, private, dry_run)
            _broadcast("\n" + ("✔ Done" if success else "✘ Failed"))
            _broadcast("__DONE__" if success else "__FAIL__")
        except Exception as e:
            _broadcast(f"\n✘ Error: {e}")
            _broadcast("__FAIL__")
        finally:
            remove_output_callback(_ui_callback)


# ── Server ──

def start_server(host: str = "127.0.0.1", port: int = 8712):
    server = ThreadingHTTPServer((host, port), AiderHandler)
    server._stop_event = threading.Event()

    url = f"http://{host}:{port}"
    print(f"  ▲ aider web UI running at: {url}", file=sys.stderr)

    # Open browser
    import webbrowser
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server._stop_event.set()
        server.server_close()
        print("\nServer stopped.", file=sys.stderr)
