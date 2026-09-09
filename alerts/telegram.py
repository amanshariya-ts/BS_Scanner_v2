# alerts/telegram.py
import requests
import logging
import os

log = logging.getLogger(__name__)

class TelegramAlert:
    def __init__(self, bot_token: str, chat_id: str):
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", bot_token)
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", chat_id)
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id

    def send(self, signal) -> None:
        ts = signal.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        if signal.side == "BUY":
            header = "🟢 Bullish Liq_Cron"
        else:
            header = "🔴 Bearish Liq_Cron"

        msg = (
            f"{header}\n"
            f"Symbol: {signal.symbol}\n"
            f"Timeframe: {signal.timeframe}\n"
              )
        try:
            r = requests.post(self.url, json={
                "chat_id": self.chat_id,
                "text": msg,
            }, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.error(f"Telegram send failed: {e}")

        # send() is only ever called with a real Signal object.
        # "No signal" bars return None in the strategy and never get here.
