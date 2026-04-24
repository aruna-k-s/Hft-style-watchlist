"""
Trade Logger for Phase 3 Trading System.
Records all system actions for debugging and analysis.
"""

import csv
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import threading


class TradeLogger:
    """
    Lightweight logger for trading system actions.
    
    Logs to both CSV (for analysis) and JSON (for structured debugging).
    Thread-safe for concurrent access.
    """
    
    def __init__(self, csv_file: str = "trades.csv", json_file: str = "trades.json"):
        """
        Initialize logger with output files.
        
        Args:
            csv_file: Path to CSV log file
            json_file: Path to JSON log file
        """
        self.csv_file = csv_file
        self.json_file = json_file
        self.lock = threading.Lock()
        
        # Initialize CSV file with headers if it doesn't exist
        self._init_csv()
        
        # Initialize JSON file as empty array if it doesn't exist
        self._init_json()
        
    def _init_csv(self) -> None:
        """Initialize CSV file with headers."""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'action', 'symbol', 'decision', 'quantity', 'price', 
                    'reason', 'score', 'cash_before', 'cash_after', 
                    'portfolio_value', 'pnl_realized', 'pnl_unrealized'
                ])
    
    def _init_json(self) -> None:
        """Initialize JSON file as empty array."""
        if not os.path.exists(self.json_file):
            with open(self.json_file, 'w') as f:
                json.dump([], f)
    
    def log_signal(self, symbol: str, score: float, reason: str, signals: Dict[str, Any]) -> None:
        """
        Log signal generation.
        
        Args:
            symbol: Stock symbol
            score: Computed score
            reason: Scoring reason
            signals: Signal dictionary
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'SIGNAL',
            'symbol': symbol,
            'score': round(score, 2),
            'reason': reason,
            'signals': signals
        }
        
        self._write_entry(entry)
    
    def log_trade_decision(self, symbol: str, decision: str, score: float, reason: str) -> None:
        """
        Log trade decision from strategy engine.
        
        Args:
            symbol: Stock symbol
            decision: BUY, SELL, or HOLD
            score: Stock score
            reason: Decision reason
        """
        print(f"[LOGGER] Logging decision: {decision} {symbol}")
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'DECISION',
            'symbol': symbol,
            'decision': decision,
            'score': round(score, 2),
            'reason': reason
        }
        
        self._write_entry(entry)
    
    def log_risk_check(self, symbol: str, approved: bool, reason: str, 
                      quantity: Optional[float] = None, price: Optional[float] = None) -> None:
        """
        Log risk management validation.
        
        Args:
            symbol: Stock symbol
            approved: Whether trade was approved
            reason: Approval/rejection reason
            quantity: Trade quantity
            price: Trade price
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'RISK_CHECK',
            'symbol': symbol,
            'approved': approved,
            'reason': reason,
            'quantity': quantity,
            'price': price
        }
        
        self._write_entry(entry)
    
    def log_execution(self, symbol: str, quantity: float, price: float, 
                     cash_before: float, cash_after: float, portfolio_value: float,
                     pnl_realized: float, pnl_unrealized: float) -> None:
        """
        Log trade execution.
        
        Args:
            symbol: Stock symbol
            quantity: Trade quantity
            price: Execution price
            cash_before: Cash before trade
            cash_after: Cash after trade
            portfolio_value: Total portfolio value after trade
            pnl_realized: Realized PnL
            pnl_unrealized: Unrealized PnL
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'EXECUTION',
            'symbol': symbol,
            'quantity': round(quantity, 2),
            'price': round(price, 2),
            'cash_before': round(cash_before, 2),
            'cash_after': round(cash_after, 2),
            'portfolio_value': round(portfolio_value, 2),
            'pnl_realized': round(pnl_realized, 2),
            'pnl_unrealized': round(pnl_unrealized, 2)
        }
        
        self._write_entry(entry)
    
    def log_portfolio_update(self, portfolio_summary: Dict[str, Any]) -> None:
        """
        Log portfolio state update.
        
        Args:
            portfolio_summary: Portfolio summary dictionary
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'PORTFOLIO_UPDATE',
            'portfolio_summary': portfolio_summary
        }
        
        self._write_entry(entry)
    
    def log_error(self, error_type: str, message: str, details: Optional[Dict] = None) -> None:
        """
        Log system errors.
        
        Args:
            error_type: Type of error
            message: Error message
            details: Additional error details
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'ERROR',
            'error_type': error_type,
            'message': message,
            'details': details or {}
        }
        
        self._write_entry(entry)
    
    def _write_entry(self, entry: Dict[str, Any]) -> None:
        """
        Write entry to both CSV and JSON files.
        
        Args:
            entry: Log entry dictionary
        """
        with self.lock:
            # Write to CSV
            self._write_csv(entry)
            
            # Write to JSON
            self._write_json(entry)
    
    def _write_csv(self, entry: Dict[str, Any]) -> None:
        """Write entry to CSV file."""
        try:
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                
                # Extract relevant fields for CSV
                row = [
                    entry.get('timestamp', ''),
                    entry.get('action', ''),
                    entry.get('symbol', ''),
                    entry.get('decision', ''),  # Add decision field
                    entry.get('quantity', ''),
                    entry.get('price', ''),
                    entry.get('reason', ''),
                    entry.get('score', ''),
                    entry.get('cash_before', ''),
                    entry.get('cash_after', ''),
                    entry.get('portfolio_value', ''),
                    entry.get('pnl_realized', ''),
                    entry.get('pnl_unrealized', '')
                ]
                
                writer.writerow(row)
                print(f"[LOGGER] Wrote CSV entry for {entry.get('action', 'UNKNOWN')}")
                
        except Exception as e:
            print(f"[LOGGER ERROR] Failed to write to CSV: {e}")
    
    def _write_json(self, entry: Dict[str, Any]) -> None:
        """Write entry to JSON file."""
        try:
            # Read existing entries
            with open(self.json_file, 'r') as f:
                entries = json.load(f)
            
            # Append new entry
            entries.append(entry)
            
            # Write back
            with open(self.json_file, 'w') as f:
                json.dump(entries, f, indent=2)
                
        except Exception as e:
            print(f"[LOGGER ERROR] Failed to write to JSON: {e}")
    
    def get_log_summary(self) -> Dict[str, Any]:
        """
        Get summary of logged activities.
        
        Returns:
            Summary dictionary with trade counts, etc.
        """
        try:
            with open(self.json_file, 'r') as f:
                entries = json.load(f)
            
            summary = {
                'total_entries': len(entries),
                'signals': 0,
                'decisions': 0,
                'executions': 0,
                'errors': 0
            }
            
            for entry in entries:
                action = entry.get('action', '')
                if action == 'SIGNAL':
                    summary['signals'] += 1
                elif action == 'DECISION':
                    summary['decisions'] += 1
                elif action == 'EXECUTION':
                    summary['executions'] += 1
                elif action == 'ERROR':
                    summary['errors'] += 1
            
            return summary
            
        except Exception as e:
            return {'error': f'Failed to read log summary: {e}'}