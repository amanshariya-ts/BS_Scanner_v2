# data/yf_oil_fetcher.py
"""
STOPGAP oil fetcher — Yahoo Finance WTI futures (CL=F).
Delayed/unofficial data; replace with FXCMFetcher once demo token is ready.
Returns the same DataFrame schema as OHLCVFetcher:
timestamp (UTC datetime64), open, high, low, close, volume.
"""
import numpy as np
import pandas as pd
import yfinance as yf


class YFOilFetcher:
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        interval, period = self._map(timeframe, limit)
        df = yf.download(symbol, interval=interval, period=period,
                         progress=False, prepost=True, auto_adjust=False)
        df = df.reset_index()

        # Robust flatten: force every column to strict 1-D regardless of
        # MultiIndex / tuple-column layout differences across yfinance versions.
        flat = {}
        for col in df.columns:
            name = str(col[0]) if isinstance(col, tuple) else str(col)
            flat[name] = np.asarray(df[col]).ravel()
        df = pd.DataFrame(flat)

        out = pd.DataFrame({
            "timestamp": pd.to_datetime(df["Datetime"], utc=True),
            "open":   df["Open"].astype(float),
            "high":   df["High"].astype(float),
            "low":    df["Low"].astype(float),
            "close":  df["Close"].astype(float),
            "volume": df["Volume"].astype(float),
        })
        return out.tail(limit).reset_index(drop=True)

    @staticmethod
    def _map(timeframe: str, limit: int):
        n, unit = int(timeframe[:-1]), timeframe[-1]
        if unit == "m":
            if n >= 30:
                return f"{n}m", f"{limit * n // (60 * 24) + 2}d"
            return f"{n}m", f"{limit * n // (60 * 8) + 2}d"
        raise ValueError(f"Unsupported yf timeframe: {timeframe}")

    @staticmethod
    def timeframe_to_seconds(tf: str) -> int:
        multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
        return int(tf[:-1]) * multipliers[tf[-1]]
