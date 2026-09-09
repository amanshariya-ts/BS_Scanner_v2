# main.py
import logging
import os
import time
import threading

from config.config_loader import load_config
from data.fetcher import create_fetcher
from data.candle_poller import CandlePoller
from strategies.liquidity_pinbars import LiquidityPinBars
from alerts.telegram import TelegramAlert
from state.state_store import StateStore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("framework")

RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
BACKFILL_BARS = int(os.getenv("BACKFILL_BARS", "12"))

STRATEGY_REGISTRY = {
    LiquidityPinBars.name: LiquidityPinBars,
}


def build_strategies(symbol, timeframe, strategy_cfgs):
    return [STRATEGY_REGISTRY[s["name"]](symbol, timeframe, s.get("params", {}))
            for s in strategy_cfgs
            if s.get("enabled", True) and s["name"] in STRATEGY_REGISTRY]


def check_market(cfg, tg, state, symbol, timeframe, exchange_name):
    """Fetch data and evaluate strategies over the backfill window. Returns nothing."""
    fetcher = create_fetcher(exchange_name)
    strategies = build_strategies(symbol, timeframe, cfg["strategies"])
    log.info(f"[{symbol} {timeframe} @ {exchange_name}] watching with {len(strategies)} strategy/ies")

    df = fetcher.fetch_ohlcv(symbol, timeframe,
                             cfg["polling"]["lookback_bars"]).iloc[:-1]

    for strat in strategies:
        for i in range(-BACKFILL_BARS, 0):
            window = df.iloc[:len(df) + i] if i != -1 else df
            if len(window) < 50:
                continue
            try:
                signal = strat.evaluate(window)
            except Exception as e:
                log.error(f"[{symbol} {timeframe}] evaluate error: {e}")
                continue
            if signal is None:
                continue
            key = f"{signal.symbol}|{signal.timeframe}|{strat.name}"
            if state.already_alerted(key, signal.timestamp):
                continue
            signal.strategy = strat.name
            age = (df.iloc[-1]["timestamp"] - signal.timestamp).total_seconds() / 60
            log.info(f"SIGNAL: {signal.side} {signal.symbol} {signal.timeframe} "
                     f"@ {signal.price} (candle {signal.timestamp}, {age:.0f}m old)")
            if tg.send(signal):
               state.mark_alerted(key, signal.timestamp)
else:
    log.warning(f"Send failed — will retry on next run: {key} {signal.timestamp}")


def run_market(cfg, tg, state, symbol, timeframe, exchange_name):
    if RUN_ONCE:
        try:
            check_market(cfg, tg, state, symbol, timeframe, exchange_name)
        except Exception as e:
            log.error(f"[{symbol} {timeframe}] one-shot error: {e}")
        return

    # Daemon mode (local): poll forever.
    fetcher = create_fetcher(exchange_name)
    strategies = build_strategies(symbol, timeframe, cfg["strategies"])
    poller = CandlePoller(fetcher, symbol, timeframe,
                          interval=cfg["polling"]["interval_seconds"],
                          lookback=cfg["polling"]["lookback_bars"])
    for candle in poller.poll_forever():
        try:
            check_market(cfg, tg, state, symbol, timeframe, exchange_name)
        except Exception as e:
            log.error(f"[{symbol} {timeframe}] loop error: {e}")


def main():
    cfg = load_config()
    tg = TelegramAlert(
        os.getenv("TELEGRAM_BOT_TOKEN", cfg["alerts"]["telegram"]["bot_token"]),
        os.getenv("TELEGRAM_CHAT_ID", cfg["alerts"]["telegram"]["chat_id"]),
    )
    state = StateStore()

    threads = []
    for market in cfg["markets"]:
        default_exchange = cfg.get("exchange", {}).get("name", "binance")
        exchange_name = market.get("exchange", default_exchange)
        t = threading.Thread(target=run_market,
                             args=(cfg, tg, state, market["symbol"],
                                   market["timeframe"], exchange_name),
                             daemon=True)
        t.start()
        threads.append(t)

    log.info(f"Watching {len(cfg['markets'])} market(s) in parallel (run_once={RUN_ONCE})")

    if RUN_ONCE:
        for t in threads:
            t.join(timeout=180)
        return

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopped by user (Ctrl+C)")


if __name__ == "__main__":
    main()
