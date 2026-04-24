"""
Backtesting Engine for Phase 3 Trading System.
Validates strategy using historical or simulated data.
"""

import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict


class Backtester:
    """
    Replays historical tick data to test trading strategy.
    
    Runs full pipeline: signal → strategy → risk → execution → portfolio
    Provides comprehensive backtest results and metrics.
    """
    
    def __init__(self, config, signal_engine, scoring_engine, strategy_engine, 
                 risk_manager, execution_engine, portfolio_manager, logger):
        """
        Initialize backtester with all system components.
        
        Args:
            config: Configuration module
            signal_engine: Signal engine instance
            scoring_engine: Scoring engine instance
            strategy_engine: Strategy engine instance
            risk_manager: Risk manager instance
            execution_engine: Execution engine instance
            portfolio_manager: Portfolio manager instance
            logger: Logger instance
        """
        self.config = config
        self.signal_engine = signal_engine
        self.scoring_engine = scoring_engine
        self.strategy = strategy_engine
        self.risk = risk_manager
        self.execution = execution_engine
        self.portfolio = portfolio_manager
        self.logger = logger
        
        # Backtest results
        self.results = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'avg_trade_pnl': 0.0,
            'portfolio_values': [],
            'trade_log': []
        }
    
    def run_backtest(self, tick_data: List[Dict]) -> Dict:
        """
        Run backtest on historical tick data.
        
        Args:
            tick_data: List of tick dictionaries with timestamp ordering
            
        Returns:
            Backtest results dictionary
        """
        print("Starting backtest...")
        
        # Reset all engines
        self._reset_engines()
        
        # Sort tick data by timestamp
        sorted_ticks = sorted(tick_data, key=lambda x: x.get('timestamp', 0))
        
        last_update_time = 0
        portfolio_values = []
        
        for i, tick in enumerate(sorted_ticks):
            # Process tick
            self.signal_engine.add_tick(
                tick['symbol'],
                tick['price'],
                tick['volume'],
                tick['bid'],
                tick['ask'],
                tick['timestamp']
            )
            
            # Periodic strategy execution (simulate real-time intervals)
            current_time = tick['timestamp']
            if current_time - last_update_time >= self.config.REFRESH_INTERVAL_SECONDS * 1000000:  # microseconds
                self._run_trading_cycle(current_time)
                
                # Record portfolio value
                current_prices = self._get_current_prices()
                portfolio_value = self.portfolio.get_portfolio_value(current_prices)
                portfolio_values.append({
                    'timestamp': current_time,
                    'value': portfolio_value
                })
                
                last_update_time = current_time
            
            # Progress reporting
            if (i + 1) % 10000 == 0:
                print(f"Processed {i + 1}/{len(sorted_ticks)} ticks")
        
        # Final cycle
        self._run_trading_cycle(current_time)
        
        # Calculate results
        self._calculate_results(portfolio_values)
        
        print("Backtest completed!")
        return self.results
    
    def _run_trading_cycle(self, timestamp: int) -> None:
        """
        Run one complete trading cycle.
        
        Args:
            timestamp: Current timestamp
        """
        # Get current signals for all tracked symbols
        stock_data = {}
        current_prices = self._get_current_prices()
        
        for symbol in self.signal_engine.get_tracked_symbols():
            signals = self.signal_engine.compute_all_signals(symbol)
            if signals is not None:
                stock_data[symbol] = {'signals': signals}
        
        # Score and rank stocks
        ranked = self.scoring_engine.rank_stocks(stock_data)
        
        # Apply stability filter (simplified for backtest)
        watchlist = ranked[:self.config.WATCHLIST_SIZE]
        
        # Update strategy with current positions
        self.strategy.update_positions(self.portfolio.positions)
        
        # Generate trade signals
        signals = self.strategy.generate_signals(watchlist)
        
        # Process each signal
        for signal in signals:
            symbol = signal['symbol']
            decision = signal['decision']
            quantity = signal['quantity']
            price = signal['signals']['current_price']
            score = signal['score']
            
            # Log signal
            self.logger.log_signal(symbol, score, signal['reason'], signal['signals'])
            
            # Log decision
            self.logger.log_trade_decision(symbol, decision, score, signal['reason'])
            
            # Risk check
            approved, reason = self.risk.validate_trade(symbol, decision, quantity, price, score)
            self.logger.log_risk_check(symbol, approved, reason, quantity, price)
            
            if approved:
                # Execute trade
                execution_result = self.execution.execute_trade(symbol, decision, quantity, price)
                
                if execution_result['success']:
                    # Log execution
                    self.logger.log_execution(
                        symbol, 
                        execution_result['executed_quantity'] if decision == 'BUY' else -execution_result['executed_quantity'],
                        execution_result['execution_price'],
                        execution_result['cash_before'],
                        execution_result['cash_after'],
                        execution_result['portfolio_value'],
                        self.portfolio.realized_pnl,
                        self.portfolio.unrealized_pnl
                    )
                    
                    # Record trade
                    self.strategy.record_trade(symbol)
                    self.results['total_trades'] += 1
                    
                    # Log trade in results
                    self.results['trade_log'].append({
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'decision': decision,
                        'quantity': quantity,
                        'price': price,
                        'pnl': self.portfolio.get_total_pnl()
                    })
    
    def _get_current_prices(self) -> Dict[str, float]:
        """
        Get current prices for all tracked symbols.
        
        Returns:
            Dict of symbol -> current price
        """
        prices = {}
        for symbol in self.signal_engine.get_tracked_symbols():
            signals = self.signal_engine.compute_all_signals(symbol)
            if signals:
                prices[symbol] = signals['current_price']
        return prices
    
    def _reset_engines(self) -> None:
        """Reset all engines to initial state."""
        # Reset signal engine
        self.signal_engine.tick_buffer.clear()
        
        # Reset portfolio
        self.portfolio.cash = self.config.INITIAL_CASH
        self.portfolio.positions.clear()
        self.portfolio.realized_pnl = 0.0
        self.portfolio.unrealized_pnl = 0.0
        self.portfolio.daily_trades.clear()
        
        # Reset strategy
        self.strategy.last_trade_time.clear()
        self.strategy.current_positions.clear()
        
        # Reset risk manager
        self.risk.stop_losses.clear()
        self.risk.daily_start_value = self.config.INITIAL_CASH
        
        # Reset results
        self.results = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'avg_trade_pnl': 0.0,
            'portfolio_values': [],
            'trade_log': []
        }
    
    def _calculate_results(self, portfolio_values: List[Dict]) -> None:
        """
        Calculate backtest performance metrics.
        
        Args:
            portfolio_values: List of portfolio values over time
        """
        if not portfolio_values:
            return
        
        # Basic metrics
        initial_value = self.config.INITIAL_CASH
        final_value = portfolio_values[-1]['value']
        self.results['total_pnl'] = final_value - initial_value
        
        # Win rate and average trade PnL
        if self.results['trade_log']:
            pnl_changes = []
            prev_pnl = 0
            
            for trade in self.results['trade_log']:
                current_pnl = trade['pnl']
                if len(pnl_changes) > 0:
                    trade_pnl = current_pnl - prev_pnl
                    pnl_changes.append(trade_pnl)
                    if trade_pnl > 0:
                        self.results['winning_trades'] += 1
                    else:
                        self.results['losing_trades'] += 1
                prev_pnl = current_pnl
            
            if pnl_changes:
                self.results['avg_trade_pnl'] = sum(pnl_changes) / len(pnl_changes)
                self.results['win_rate'] = self.results['winning_trades'] / len(pnl_changes)
        
        # Maximum drawdown
        peak = initial_value
        max_drawdown = 0
        
        for pv in portfolio_values:
            value = pv['value']
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        self.results['max_drawdown'] = max_drawdown
        
        # Sharpe ratio (simplified - assumes daily returns)
        if len(portfolio_values) > 1:
            returns = []
            prev_value = initial_value
            
            for pv in portfolio_values[::int(len(portfolio_values)/min(252, len(portfolio_values)))]:  # Daily samples
                ret = (pv['value'] - prev_value) / prev_value
                returns.append(ret)
                prev_value = pv['value']
            
            if returns:
                avg_return = sum(returns) / len(returns)
                std_return = (sum((r - avg_return)**2 for r in returns) / len(returns))**0.5
                if std_return > 0:
                    self.results['sharpe_ratio'] = avg_return / std_return
    
    def load_tick_data_from_file(self, filename: str) -> List[Dict]:
        """
        Load tick data from JSON file.
        
        Args:
            filename: Path to JSON file with tick data
            
        Returns:
            List of tick dictionaries
        """
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Error loading tick data: {e}")
            return []
    
    def save_results(self, filename: str) -> None:
        """
        Save backtest results to JSON file.
        
        Args:
            filename: Output filename
        """
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"Backtest results saved to {filename}")
        except Exception as e:
            print(f"Error saving results: {e}")