from typing import Any

from .paper_execution import PaperExecution
from .live_execution import LiveExecution


def get_execution_engine(config: Any, portfolio_manager: Any, risk_manager: Any) -> Any:
    """Return the correct execution engine based on trading mode."""
    mode = getattr(config, 'mode', 'paper')

    if mode in ('paper', 'paper_live_data'):
        return PaperExecution(config, portfolio_manager, risk_manager)

    if mode == 'live':
        if not getattr(config, 'enable_live_trading', False):
            raise Exception('Live trading not enabled. Set enable_live_trading: true in config.yaml to proceed.')
        return LiveExecution(config, portfolio_manager, risk_manager)

    raise Exception(f'Unsupported trading mode: {mode}')
