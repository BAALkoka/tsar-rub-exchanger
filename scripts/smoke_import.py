"""Smoke: бот-модуль парсится, стартовый хендлер на месте."""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

src = (ROOT / "src/bot/main.py").read_text(encoding="utf-8")
ast.parse(src)
print("OK: src/bot/main.py parses")

handlers = sorted(p.name for p in (ROOT / "src/bot/handlers").glob("*.py"))
print("handlers:", handlers)
assert "start.py" in handlers, "start handler missing"

for p in (ROOT / "src/bot/handlers").glob("*.py"):
    ast.parse(p.read_text(encoding="utf-8"))
print("OK: all handlers parse")
