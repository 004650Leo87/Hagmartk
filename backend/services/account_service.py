from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import MetaTrader5 as mt5


class AccountService:
    """
    Serviço responsável por consultar os dados reais da conta
    atualmente conectada ao terminal MetaTrader 5.
    """

    @staticmethod
    def _ensure_connection() -> None:
        """
        Confirma que o Python está conectado ao terminal MetaTrader 5.

        O initialize() reutiliza a sessão já aberta do terminal quando
        possível. Em caso de falha, uma exceção clara é gerada.
        """
        terminal = mt5.terminal_info()

        if terminal is not None:
            return

        if not mt5.initialize():
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                "Não foi possível conectar ao MetaTrader 5. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

    @staticmethod
    def _safe_float(value: Any) -> float:
        """
        Converte um valor numérico para float sem deixar None quebrar
        a resposta da API.
        """
        if value is None:
            return 0.0

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        """
        Converte um valor numérico para inteiro.
        """
        if value is None:
            return 0

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _position_type_name(position_type: int) -> str:
        """
        Traduz o tipo numérico de posição do MetaTrader.
        """
        if position_type == mt5.POSITION_TYPE_BUY:
            return "BUY"

        if position_type == mt5.POSITION_TYPE_SELL:
            return "SELL"

        return "UNKNOWN"

    @staticmethod
    def _deal_type_name(deal_type: int) -> str:
        """
        Traduz o tipo de negócio registrado no histórico.
        """
        deal_types = {
            mt5.DEAL_TYPE_BUY: "BUY",
            mt5.DEAL_TYPE_SELL: "SELL",
            mt5.DEAL_TYPE_BALANCE: "BALANCE",
            mt5.DEAL_TYPE_CREDIT: "CREDIT",
            mt5.DEAL_TYPE_CHARGE: "CHARGE",
            mt5.DEAL_TYPE_CORRECTION: "CORRECTION",
            mt5.DEAL_TYPE_BONUS: "BONUS",
            mt5.DEAL_TYPE_COMMISSION: "COMMISSION",
            mt5.DEAL_TYPE_COMMISSION_DAILY: "COMMISSION_DAILY",
            mt5.DEAL_TYPE_COMMISSION_MONTHLY: "COMMISSION_MONTHLY",
            mt5.DEAL_TYPE_COMMISSION_AGENT_DAILY:
                "COMMISSION_AGENT_DAILY",
            mt5.DEAL_TYPE_COMMISSION_AGENT_MONTHLY:
                "COMMISSION_AGENT_MONTHLY",
            mt5.DEAL_TYPE_INTEREST: "INTEREST",
            mt5.DEAL_TYPE_BUY_CANCELED: "BUY_CANCELED",
            mt5.DEAL_TYPE_SELL_CANCELED: "SELL_CANCELED",
            mt5.DEAL_TYPE_DIVIDEND: "DIVIDEND",
            mt5.DEAL_TYPE_DIVIDEND_FRANKED:
                "DIVIDEND_FRANKED",
            mt5.DEAL_TYPE_TAX: "TAX",
        }

        return deal_types.get(deal_type, "UNKNOWN")

    @staticmethod
    def _deal_entry_name(entry_type: int) -> str:
        """
        Traduz se o negócio abriu, fechou ou alterou uma posição.
        """
        entry_types = {
            mt5.DEAL_ENTRY_IN: "IN",
            mt5.DEAL_ENTRY_OUT: "OUT",
            mt5.DEAL_ENTRY_INOUT: "INOUT",
            mt5.DEAL_ENTRY_OUT_BY: "OUT_BY",
        }

        return entry_types.get(entry_type, "UNKNOWN")

    def account_info(self) -> dict[str, Any]:
        """
        Retorna os dados principais da conta conectada.
        """
        self._ensure_connection()

        account = mt5.account_info()

        if account is None:
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                "Não foi possível obter os dados da conta. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

        terminal = mt5.terminal_info()
        version = mt5.version()

        return {
            "connected": True,
            "login": self._safe_int(account.login),
            "name": getattr(account, "name", "") or "",
            "server": account.server or "",
            "company": account.company or "",
            "currency": account.currency or "",
            "currency_digits": self._safe_int(
                account.currency_digits
            ),
            "leverage": self._safe_int(account.leverage),
            "trade_mode": self._safe_int(account.trade_mode),
            "trade_allowed": bool(account.trade_allowed),
            "trade_expert": bool(account.trade_expert),
            "fifo_close": bool(account.fifo_close),
            "limit_orders": self._safe_int(account.limit_orders),

            "balance": self._safe_float(account.balance),
            "credit": self._safe_float(account.credit),
            "equity": self._safe_float(account.equity),
            "profit": self._safe_float(account.profit),

            "margin": self._safe_float(account.margin),
            "margin_free": self._safe_float(
                account.margin_free
            ),
            "margin_level": self._safe_float(
                account.margin_level
            ),
            "margin_initial": self._safe_float(
                account.margin_initial
            ),
            "margin_maintenance": self._safe_float(
                account.margin_maintenance
            ),
            "margin_so_call": self._safe_float(
                account.margin_so_call
            ),
            "margin_so_so": self._safe_float(
                account.margin_so_so
            ),

            "assets": self._safe_float(account.assets),
            "liabilities": self._safe_float(
                account.liabilities
            ),
            "commission_blocked": self._safe_float(
                account.commission_blocked
            ),

            "terminal": {
                "connected": bool(
                    getattr(terminal, "connected", False)
                ),
                "trade_allowed": bool(
                    getattr(terminal, "trade_allowed", False)
                ),
                "tradeapi_disabled": bool(
                    getattr(
                        terminal,
                        "tradeapi_disabled",
                        False,
                    )
                ),
                "path": getattr(terminal, "path", "") or "",
                "data_path": getattr(
                    terminal,
                    "data_path",
                    "",
                ) or "",
                "commondata_path": getattr(
                    terminal,
                    "commondata_path",
                    "",
                ) or "",
                "build": (
                    version[1]
                    if version and len(version) > 1
                    else None
                ),
                "version": (
                    ".".join(str(item) for item in version)
                    if version
                    else ""
                ),
            },

            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    def positions(self) -> list[dict[str, Any]]:
        """
        Retorna todas as posições abertas da conta.
        """
        self._ensure_connection()

        positions = mt5.positions_get()

        if positions is None:
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                "Não foi possível obter as posições abertas. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

        result: list[dict[str, Any]] = []

        for position in positions:
            result.append(
                {
                    "ticket": self._safe_int(
                        position.ticket
                    ),
                    "identifier": self._safe_int(
                        position.identifier
                    ),
                    "symbol": position.symbol,
                    "type": self._position_type_name(
                        position.type
                    ),
                    "type_code": self._safe_int(
                        position.type
                    ),
                    "magic": self._safe_int(
                        position.magic
                    ),
                    "reason": self._safe_int(
                        position.reason
                    ),

                    "volume": self._safe_float(
                        position.volume
                    ),
                    "price_open": self._safe_float(
                        position.price_open
                    ),
                    "price_current": self._safe_float(
                        position.price_current
                    ),
                    "stop_loss": self._safe_float(
                        position.sl
                    ),
                    "take_profit": self._safe_float(
                        position.tp
                    ),

                    "profit": self._safe_float(
                        position.profit
                    ),
                    "swap": self._safe_float(
                        position.swap
                    ),

                    "time": datetime.fromtimestamp(
                        position.time,
                        tz=timezone.utc,
                    ).isoformat(),
                    "time_msc": self._safe_int(
                        position.time_msc
                    ),

                    "comment": position.comment or "",
                    "external_id": (
                        position.external_id or ""
                    ),
                }
            )

        return result

    def account_summary(self) -> dict[str, Any]:
        """
        Retorna um resumo pronto para o dashboard.
        """
        account = self.account_info()
        positions = self.positions()

        floating_profit = sum(
            self._safe_float(position["profit"])
            for position in positions
        )

        total_volume = sum(
            self._safe_float(position["volume"])
            for position in positions
        )

        buy_positions = sum(
            1
            for position in positions
            if position["type"] == "BUY"
        )

        sell_positions = sum(
            1
            for position in positions
            if position["type"] == "SELL"
        )

        return {
            "connected": account["connected"],
            "login": account["login"],
            "name": account["name"],
            "server": account["server"],
            "company": account["company"],
            "currency": account["currency"],
            "leverage": account["leverage"],

            "balance": account["balance"],
            "equity": account["equity"],
            "profit": account["profit"],
            "credit": account["credit"],

            "margin": account["margin"],
            "margin_free": account["margin_free"],
            "margin_level": account["margin_level"],

            "positions_count": len(positions),
            "buy_positions": buy_positions,
            "sell_positions": sell_positions,
            "total_volume": total_volume,
            "floating_profit": floating_profit,

            "trade_allowed": account["trade_allowed"],
            "trade_expert": account["trade_expert"],
            "terminal": account["terminal"],

            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    def daily_history(self) -> dict[str, Any]:
        """
        Retorna o resultado das negociações registradas desde
        o início do dia em UTC.
        """
        self._ensure_connection()

        now = datetime.now(timezone.utc)
        start_of_day = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        deals = mt5.history_deals_get(
            start_of_day,
            now + timedelta(seconds=1),
        )

        if deals is None:
            error_code, error_message = mt5.last_error()

            raise RuntimeError(
                "Não foi possível obter o histórico diário. "
                f"Código: {error_code}. Mensagem: {error_message}"
            )

        deal_list: list[dict[str, Any]] = []

        gross_profit = 0.0
        gross_loss = 0.0
        commission = 0.0
        swap = 0.0
        fee = 0.0
        net_profit = 0.0
        winning_deals = 0
        losing_deals = 0

        for deal in deals:
            profit = self._safe_float(deal.profit)
            deal_commission = self._safe_float(
                deal.commission
            )
            deal_swap = self._safe_float(deal.swap)
            deal_fee = self._safe_float(deal.fee)

            if profit > 0:
                gross_profit += profit
                winning_deals += 1
            elif profit < 0:
                gross_loss += abs(profit)
                losing_deals += 1

            commission += deal_commission
            swap += deal_swap
            fee += deal_fee

            deal_net = (
                profit
                + deal_commission
                + deal_swap
                + deal_fee
            )

            net_profit += deal_net

            deal_list.append(
                {
                    "ticket": self._safe_int(
                        deal.ticket
                    ),
                    "order": self._safe_int(
                        deal.order
                    ),
                    "position_id": self._safe_int(
                        deal.position_id
                    ),
                    "symbol": deal.symbol or "",
                    "type": self._deal_type_name(
                        deal.type
                    ),
                    "entry": self._deal_entry_name(
                        deal.entry
                    ),
                    "volume": self._safe_float(
                        deal.volume
                    ),
                    "price": self._safe_float(
                        deal.price
                    ),
                    "profit": profit,
                    "commission": deal_commission,
                    "swap": deal_swap,
                    "fee": deal_fee,
                    "net_profit": deal_net,
                    "magic": self._safe_int(
                        deal.magic
                    ),
                    "comment": deal.comment or "",
                    "time": datetime.fromtimestamp(
                        deal.time,
                        tz=timezone.utc,
                    ).isoformat(),
                }
            )

        closed_results = winning_deals + losing_deals

        win_rate = (
            winning_deals / closed_results * 100
            if closed_results > 0
            else 0.0
        )

        return {
            "period": {
                "from": start_of_day.isoformat(),
                "to": now.isoformat(),
                "timezone": "UTC",
            },
            "deals_count": len(deal_list),
            "winning_deals": winning_deals,
            "losing_deals": losing_deals,
            "win_rate": round(win_rate, 2),

            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "commission": round(commission, 2),
            "swap": round(swap, 2),
            "fee": round(fee, 2),
            "net_profit": round(net_profit, 2),

            "deals": deal_list,
            "updated_at": now.isoformat(),
        }