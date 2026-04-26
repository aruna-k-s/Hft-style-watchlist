import os
from typing import Optional

from pathlib import Path


def load_upstox_tokens(config_path: Optional[str] = None) -> dict:
    """Load Upstox API credentials from config file or environment overrides."""
    from execution.config.config_loader import load_trading_config

    if config_path is None:
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'python_engine', 'execution', 'config', 'config.yaml'))

    config = load_trading_config(config_path)
    upstox_cfg = getattr(config, 'upstox', None)

    api_key = os.getenv('UPSTOX_API_KEY') or (upstox_cfg.api_key if upstox_cfg else None)
    access_token = os.getenv('UPSTOX_ACCESS_TOKEN') or (upstox_cfg.access_token if upstox_cfg else None)
    provider = os.getenv('DATA_SOURCE_PROVIDER') or (config.data_source.provider if hasattr(config, 'data_source') else 'upstox')

    return {
        'provider': provider,
        'api_key': api_key,
        'access_token': access_token,
        'config_path': config_path
    }


def reload_tokens_if_expired(current_tokens: dict) -> dict:
    """Reload tokens from config file / environment on expiry."""
    config_path = current_tokens.get('config_path')
    return load_upstox_tokens(config_path)
