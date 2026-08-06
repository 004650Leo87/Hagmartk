import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from backend.services.account_service import AccountService

@patch("backend.services.account_service.mt5")
def test_daily_history_safe_reads(mock_mt5):
    """Testa leitura segura de profit, commission, swap, e fee no histórico diário"""
    mock_mt5.initialize.return_value = True
    mock_mt5.terminal_info.return_value = MagicMock()
    
    class MockDeal:
        def __init__(self, profit, commission, swap, fee, deal_type, entry, time_ts):
            self.profit = profit
            self.commission = commission
            self.swap = swap
            self.fee = fee
            self.type = deal_type
            self.entry = entry
            self.time = time_ts
            self.ticket = 1
            self.order = 1
            self.position_id = 1
            self.symbol = "EURUSD"
            self.volume = 1.0
            self.price = 1.0
            self.magic = 123
            self.comment = ""
            
    now_ts = int(datetime.now(timezone.utc).timestamp())
    
    mock_deal_1 = MockDeal(10.5, -1.0, -0.5, None, mock_mt5.DEAL_TYPE_BUY, mock_mt5.DEAL_ENTRY_OUT, now_ts)
    
    class MockDealMissingAttrs:
        def __init__(self, deal_type, entry, time_ts):
            self.type = deal_type
            self.entry = entry
            self.time = time_ts
            self.ticket = 2
            self.order = 2
            self.position_id = 2
            self.symbol = "EURUSD"
            self.volume = 1.0
            self.price = 1.0
            self.magic = 123
            self.comment = ""
            # profit, commission, swap, fee not defined
            
    mock_deal_2 = MockDealMissingAttrs(mock_mt5.DEAL_TYPE_SELL, mock_mt5.DEAL_ENTRY_IN, now_ts)
    
    mock_mt5.history_deals_get.return_value = [mock_deal_1, mock_deal_2]
    
    service = AccountService()
    
    result = service.daily_history()
    
    assert result["deals_count"] == 2
    
    assert result["deals"][0]["profit"] == 10.5
    assert result["deals"][0]["commission"] == -1.0
    assert result["deals"][0]["swap"] == -0.5
    assert result["deals"][0]["fee"] == 0.0
    assert result["deals"][0]["net_profit"] == 9.0
    
    assert result["deals"][1]["profit"] == 0.0
    assert result["deals"][1]["commission"] == 0.0
    assert result["deals"][1]["swap"] == 0.0
    assert result["deals"][1]["fee"] == 0.0
    assert result["deals"][1]["net_profit"] == 0.0
