"""Smoke: бот отвечает в Telegram — getMe + getUpdates, /start готов."""
import json
import os
import sys

import httpx

token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not token:
    print("SMOKE FAIL: TELEGRAM_BOT_TOKEN secret is empty")
    sys.exit(1)

api = f"https://api.telegram.org/bot{token}"
client = httpx.Client(timeout=25.0)

me = client.get(f"{api}/getMe").json()
if not me.get("ok"):
    print("SMOKE FAIL: getMe ->", json.dumps(me, ensure_ascii=False)[:300])
    sys.exit(1)
bot = me["result"]
print("getMe OK: id=%s username=@%s name=%s" % (bot.get("id"), bot.get("username"), bot.get("first_name")))

upd = client.get(f"{api}/getUpdates", params={"timeout": 0, "limit": 5}).json()
print("getUpdates ok=%s updates=%s" % (upd.get("ok"), len(upd.get("result", []) or [])))

admin = os.environ.get("ADMIN_CHAT_ID", "")
if admin:
    sent = client.post(f"{api}/sendMessage", json={
        "chat_id": admin,
        "text": "✅ smoke: бот ЦАРЬ на связи. /start готов.",
    }).json()
    print("sendMessage to admin ok=%s" % sent.get("ok"))
else:
    print("ADMIN_CHAT_ID empty — уведомление пропущено")

print("SMOKE OK: bot @%s reachable" % bot.get("username"))
