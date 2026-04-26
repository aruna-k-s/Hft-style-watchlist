import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class BrokerConfig:
    name: str
    api_key: str
    api_secret: str
    access_token: str


@dataclass
class ExecutionConfig:
    slippage_pct: float
    order_timeout_sec: int
    broker: BrokerConfig


@dataclass
class RiskConfig:
    max_position_size_pct: float
    max_total_exposure_pct: float
    stop_loss_pct: float
    daily_loss_limit_pct: float


@dataclass
class CapitalConfig:
    initial_cash: float


@dataclass
class SystemConfig:
    log_level: str
    cycle_interval_sec: int


@dataclass
class DataSourceConfig:
    provider: str


@dataclass
class UpstoxConfig:
    api_key: str
    access_token: str
    instruments: List[str]
    websocket_url: str = 'wss://api.upstox.com/livefeed'


@dataclass
class TradingConfig:
    mode: str
    enable_live_trading: bool
    capital: CapitalConfig
    risk: RiskConfig
    execution: ExecutionConfig
    system: SystemConfig
    data_source: DataSourceConfig
    upstox: UpstoxConfig


DEFAULT_CONFIG = {
    'trading': {
        'mode': 'paper',
        'enable_live_trading': False,
        'capital': {
            'initial_cash': 100000
        },
        'risk': {
            'max_position_size_pct': 0.1,
            'max_total_exposure_pct': 0.5,
            'stop_loss_pct': 0.02,
            'daily_loss_limit_pct': 0.05,
        },
        'execution': {
            'slippage_pct': 0.001,
            'order_timeout_sec': 5,
            'broker': {
                'name': 'zerodha',
                'api_key': 'YOUR_API_KEY',
                'api_secret': 'YOUR_API_SECRET',
                'access_token': 'YOUR_ACCESS_TOKEN',
            },
        },
        'system': {
            'log_level': 'INFO',
            'cycle_interval_sec': 3,
        },
    },
    'data_source': {
        'provider': 'upstox'
    },
    'upstox': {
        'api_key': 'YOUR_API_KEY',
        'access_token': 'YOUR_ACCESS_TOKEN',
        'instruments': [
            'NSE_EQ|RELIANCE',
            'NSE_EQ|TCS'
        ],
        'websocket_url': 'wss://api.upstox.com/livefeed'
    }
}


def _get_value(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    current = data
    for key in path.split('.'):
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def load_trading_config(config_path: Optional[str] = None) -> TradingConfig:
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f'Configuration file not found: {config_path}')

    with open(config_path, 'r') as f:
        raw = yaml.safe_load(f) or {}

    trading = raw.get('trading', {})
    data_source = raw.get('data_source', {})
    upstox = raw.get('upstox', {})

    merged_trading = _deep_merge(DEFAULT_CONFIG['trading'], trading)
    merged_data_source = _deep_merge(DEFAULT_CONFIG['data_source'], data_source)
    merged_upstox = _deep_merge(DEFAULT_CONFIG['upstox'], upstox)

    mode = merged_trading.get('mode', 'paper')
    enable_live_trading = merged_trading.get('enable_live_trading', False)

    if mode not in {'paper', 'paper_live_data', 'live'}:
        raise ValueError(f'Unsupported trading mode: {mode}')

    if mode == 'live' and not enable_live_trading:
        raise ValueError('Live mode requires enable_live_trading: true. System will not start in live mode without explicit permission.')

    broker = merged_trading['execution']['broker']
    if mode == 'live':
        missing = [field for field in ['name', 'api_key', 'api_secret', 'access_token'] if not broker.get(field)]
        if missing:
            raise ValueError(f'Missing live broker credentials: {", ".join(missing)}')

    return TradingConfig(
        mode=mode,
        enable_live_trading=enable_live_trading,
        capital=CapitalConfig(initial_cash=float(merged_trading['capital']['initial_cash'])),
        risk=RiskConfig(
            max_position_size_pct=float(merged_trading['risk']['max_position_size_pct']),
            max_total_exposure_pct=float(merged_trading['risk']['max_total_exposure_pct']),
            stop_loss_pct=float(merged_trading['risk']['stop_loss_pct']),
            daily_loss_limit_pct=float(merged_trading['risk']['daily_loss_limit_pct']),
        ),
        execution=ExecutionConfig(
            slippage_pct=float(merged_trading['execution']['slippage_pct']),
            order_timeout_sec=int(merged_trading['execution']['order_timeout_sec']),
            broker=BrokerConfig(
                name=str(broker.get('name', 'zerodha')),
                api_key=str(broker.get('api_key', '')),
                api_secret=str(broker.get('api_secret', '')),
                access_token=str(broker.get('access_token', '')),
            )
        ),
        system=SystemConfig(
            log_level=str(merged_trading['system']['log_level']),
            cycle_interval_sec=int(merged_trading['system']['cycle_interval_sec']),
        ),
        data_source=DataSourceConfig(provider=str(merged_data_source.get('provider', 'upstox'))),
        upstox=UpstoxConfig(
            api_key=str(merged_upstox.get('api_key', 'YOUR_API_KEY')),
            access_token=str(merged_upstox.get('access_token', 'YOUR_ACCESS_TOKEN')),
            instruments=list(merged_upstox.get('instruments', [])),
            websocket_url=str(merged_upstox.get('websocket_url', 'wss://api.upstox.com/livefeed'))
        )
    )
