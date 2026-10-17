import sys, os, json, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from pterm import Term

PLUGIN = os.path.join(os.path.dirname(__file__), "..", "spacue.zsh")
PLUGIN = os.path.abspath(PLUGIN)
DEMO = "/tmp/spacue-demo"

shutil.rmtree(DEMO, ignore_errors=True)
os.makedirs(f"{DEMO}/alpha")
os.makedirs(f"{DEMO}/beta")
os.makedirs(f"{DEMO}/gamma")
os.makedirs(f"{DEMO}/Documents/Projects")
with open(f"{DEMO}/package.json", "w") as f:
    json.dump({"name": "demo", "scripts": {
        "dev": "vite --port 3000",
        "build": "tsc -b",
        "test": "vitest",
    }}, f)

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send(f"PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.8)
t.send(f"cd {DEMO}\n")
t.wait_idle(0.5)

print("=== 1) cd <space> ===")
t.send("cd ")
t.wait_idle(0.8)
print(t.screen.text())

print("=== 2) Down + Enter ===")
t.send_keys("Down", "Enter")
t.wait_idle(0.6)
print(t.screen.text())

print("=== 3) npm <space> ===")
t.send_keys("C-u")
t.wait_idle(0.3)
t.send("npm ")
t.wait_idle(0.8)
print(t.screen.text())
t.close()
