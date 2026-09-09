# main.py
import logging
import time
import threading

from config.config_loader import load_config
from data.fetcher import OHLCVFetcher, create_fetcher
from data.candle_poller import CandlePoller
from strategies.liquidity_pinbars import LiquidityPinBars
from alerts.telegram import TelegramAlert
from state.state_store import StateStore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("framework")

STRATEGY_REGISTRY = {
    LiquidityPinBars.name: LiquidityPinBars,
}


def build_strategies(symbol, timeframe, strategy_cfgs):
    strategies = []
    for s in strategy_cfgs:
        if s.get("enabled", True) and s["name"] in STRATEGY_REGISTRY:
            strategies.append(STRATEGY_REGISTRY[s["name"]](
                symbol, timeframe, s.get("params", {})))
    return strategies


def run_market(cfg, tg, state, symbol, timeframe, exchange_name):
    """One independent watcher per symbol+timeframe+exchange. Own thread, own fetcher."""
    fetcher = create_fetcher(exchange_name)  # per-market fetcher (binance / fxcm / yf_oil)
    strategies = build_strategies(symbol, timeframe, cfg["strategies"])
    poller = CandlePoller(fetcher, symbol, timeframe,
                          interval=cfg["polling"]["interval_seconds"],
                          lookback=cfg["polling"]["lookback_bars"])
    log.info(f"[{symbol} {timeframe} @ {exchange_name}] watching with {len(strategies)} strategy/ies")

    for candle in poller.poll_forever():
        try:
            df = fetcher.fetch_ohlcv(symbol, timeframe,
                                     cfg["polling"]["lookback_bars"]).iloc[:-1]
            for strat in strategies:
                signal = strat.evaluate(df)
                if signal is None:
                    continue  # No-signal candle: silently ignored
                key = f"{signal.symbol}|{signal.timeframe}|{strat.name}"
                if state.already_alerted(key, signal.timestamp):
                    continue
                signal.strategy = strat.name
                log.info(f"SIGNAL: {signal.side} {signal.symbol} "
                         f"{signal.timeframe} @ {signal.price}")
                tg.send(signal)
                state.mark_alerted(key, signal.timestamp)
        except Exception as e:
            log.error(f"[{symbol} {timeframe}] loop error: {e}")


def main():
    cfg = load_config()
    tg = TelegramAlert(cfg["alerts"]["telegram"]["bot_token"],
                       cfg["alerts"]["telegram"]["chat_id"])
    state = StateStore()

    threads = []
    for market in cfg["markets"]:
        # per-market exchange; falls back to global cfg["exchange"]["name"]
        default_exchange = cfg.get("exchange", {}).get("name", "binance")
        exchange_name = market.get("exchange", default_exchange)

        t = threading.Thread(
            target=run_market,
            args=(cfg, tg, state,
                  market["symbol"], market["timeframe"], exchange_name),
            daemon=True,
        )
        t.start()
        threads.append(t)

    log.info(f"Watching {len(cfg['markets'])} market(s) in parallel")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopped by user (Ctrl+C)")


if __name__ == "__main__":
    main()
