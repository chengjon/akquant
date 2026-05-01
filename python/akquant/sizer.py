from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .akquant import StrategyContext


class Sizer(ABC):
    """
    仓位管理基类 (Sizer Base Class).

    用于计算下单数量.
    """

    @abstractmethod
    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """
        计算下单数量.

        Args:
            price (float): 当前价格
            cash (float): 当前可用资金
            context (StrategyContext): 策略上下文
            symbol (str): 标的代码

        Returns:
            float: 下单数量
        """
        pass


class FixedSize(Sizer):
    """
    固定数量 Sizer.

    每次交易固定数量.
    """

    def __init__(self, size: float = 100.0):
        """
        Initialize FixedSize.

        :param size: The fixed size for each trade.
        """
        self.size = size

    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """Return the fixed size."""
        return self.size


class PercentSizer(Sizer):
    """
    百分比 Sizer.

    使用当前资金的一定百分比买入.
    """

    def __init__(self, percents: float = 10.0):
        """
        Initialize PercentSizer.

        Args:
            percents (float): 资金百分比 (0-100).
        """
        self.percents = percents

    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """Calculate order size based on percentage of cash."""
        if price <= 0:
            return 0.0

        target_cash = cash * (self.percents / 100.0)
        return int(target_cash / price)


class AllInSizer(Sizer):
    """
    全仓 Sizer.

    使用所有可用资金买入.
    """

    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """Calculate order size using all available cash."""
        if price <= 0:
            return 0.0
        return int(cash / price)


class ATRSizer(Sizer):
    """
    ATR Sizer.

    Size based on ATR volatility.
    """

    def __init__(
        self,
        atr_window: int = 14,
        risk_per_trade: float = 0.01,
        multiplier: float = 1.0,
    ) -> None:
        """
        Initialize ATRSizer.

        Args:
            atr_window: ATR calculation window.
            risk_per_trade: Fraction of equity risked per trade.
            multiplier: ATR multiplier for stop distance.
        """
        self.atr_window = atr_window
        self.risk_per_trade = risk_per_trade
        self.multiplier = multiplier
        self._atr_values: dict[str, float] = {}

    def set_atr(self, symbol: str, atr_value: float) -> None:
        """Set the ATR value for a symbol."""
        self._atr_values[symbol] = atr_value

    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """Calculate order size based on ATR."""
        atr = self._atr_values.get(symbol, price * 0.02)
        risk_amount = cash * self.risk_per_trade
        if atr > 0:
            return float(int(risk_amount / (atr * self.multiplier)))
        return 0.0


class KellySizer(Sizer):
    """
    Kelly Criterion Sizer.

    Position sizing using the Kelly criterion.
    """

    def __init__(
        self,
        win_rate: float = 0.5,
        avg_win: float = 1.0,
        avg_loss: float = 1.0,
        fraction: float = 0.5,
    ) -> None:
        """
        Initialize KellySizer.

        Args:
            win_rate: Historical win rate (0-1).
            avg_win: Average winning trade size.
            avg_loss: Average losing trade size.
            fraction: Kelly fraction (0.5 = half-Kelly).
        """
        self.win_rate = win_rate
        self.avg_win = avg_win
        self.avg_loss = avg_loss
        self.fraction = fraction

    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """Calculate order size using Kelly criterion."""
        if self.avg_loss <= 0 or price <= 0:
            return 0.0
        kelly = (
            self.win_rate * self.avg_win
            - (1 - self.win_rate) * self.avg_loss
        ) / self.avg_win
        kelly = max(kelly, 0.0)
        allocation = cash * kelly * self.fraction
        return float(int(allocation / price))


class RiskParitySizer(Sizer):
    """
    Risk Parity Sizer.

    Equal risk contribution sizing.
    """

    def __init__(
        self,
        total_risk: float = 0.02,
        volatility: dict[str, float] | None = None,
    ) -> None:
        """
        Initialize RiskParitySizer.

        Args:
            total_risk: Total portfolio risk fraction.
            volatility: Per-symbol annualized volatility estimates.
        """
        self.total_risk = total_risk
        self.volatility: dict[str, float] = volatility or {}

    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """Calculate order size for equal risk contribution."""
        vol = self.volatility.get(symbol, 0.2)
        if vol <= 0 or price <= 0:
            return 0.0
        position_risk = cash * self.total_risk
        return float(int(position_risk / (price * vol)))


class EqualWeightSizer(Sizer):
    """
    Equal Weight Sizer.

    Equal weight across N instruments.
    """

    def __init__(self, n_instruments: int = 1) -> None:
        """
        Initialize EqualWeightSizer.

        Args:
            n_instruments: Number of instruments in the portfolio.
        """
        self.n_instruments = max(n_instruments, 1)

    def get_size(
        self, price: float, cash: float, context: "StrategyContext", symbol: str
    ) -> float:
        """Calculate equal weight order size."""
        if price <= 0:
            return 0.0
        allocation = cash / self.n_instruments
        return float(int(allocation / price))
