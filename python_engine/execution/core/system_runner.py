import os
import sys
from typing import Optional

from execution.config.config_loader import load_trading_config
from execution.execution_factory import get_execution_engine
from config import *
from signal_engine import SignalEngine
from scoring import ScoringEngine
from strategy import StrategyEngine
from risk_manager import RiskManager
from portfolio import PortfolioManager
from logger import TradeLogger


class SystemRunner:
    """Entry point for the Phase 4 trading system."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

        self.trading_config = load_trading_config(config_path)
        self.config_module = sys.modules['config']
        self.signal_engine = SignalEngine(self.config_module)
        self.scoring_engine = ScoringEngine(self.config_module)

        self.portfolio = PortfolioManager(self.trading_config.capital.initial_cash)
        self.logger = TradeLogger(self.config_module.LOG_CSV_FILE, self.config_module.LOG_JSON_FILE)
        self.strategy = StrategyEngine(self.config_module)
        self.risk_manager = RiskManager(self.config_module, self.portfolio, self.trading_config)
        self.execution_engine = get_execution_engine(self.trading_config, self.portfolio, self.risk_manager)

    def run(self) -> None:
        self._show_startup()
        engine = self._create_watchlist_engine()
        engine.run()

    def _show_startup(self) -> None:
        print('=' * 80)
        print('   HFT-Style Watchlist: Phase 4 Trading System')
        print('=' * 80)
        print(f'[PHASE 4] Trading mode: {self.trading_config.mode}')
        print(f'[PHASE 4] Live trading enabled: {self.trading_config.enable_live_trading}')
        print(f'[PHASE 4] Initial cash: ${self.trading_config.capital.initial_cash:,.2f}')
        print(f'[PHASE 4] Risk limits: max position {self.trading_config.risk.max_position_size_pct*100:.1f}%, max exposure {self.trading_config.risk.max_total_exposure_pct*100:.1f}%')
        print(f'[PHASE 4] Execution slippage: {self.trading_config.execution.slippage_pct*100:.2f}%')
        print(f'[PHASE 4] System cycle interval: {self.trading_config.system.cycle_interval_sec}s')
        print('=' * 80)

    def _create_watchlist_engine(self) -> 'WatchlistEngine':
        from main import WatchlistEngine
        return WatchlistEngine(self.trading_config)
