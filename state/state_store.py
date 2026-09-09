# state/state_store.py
import json
from pathlib import Path

class StateStore:
    """Persists last-alerted candle per symbol+timeframe+strategy,
    so restarts don't re-alert on the same candle."""

    def __init__(self, path: str = "state/state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(exist_ok=True)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def already_alerted(self, key: str, candle_ts) -> bool:
        return str(self.data.get(key)) == str(candle_ts)

    def mark_alerted(self, key: str, candle_ts):
        self.data[key] = str(candle_ts)
        self.path.write_text(json.dumps(self.data))
