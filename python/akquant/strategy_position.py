from .akquant import StrategyContext


class Position:
    """
    持仓信息辅助类 (Position Helper).

    允许通过属性访问特定标的的持仓信息.
    """

    def __init__(self, ctx: StrategyContext, symbol: str) -> None:
        """
        初始化持仓辅助对象.

        :param ctx: 策略上下文
        :param symbol: 标的代码
        """
        self._ctx = ctx
        self._symbol = symbol

    @property
    def size(self) -> float:
        """持仓数量."""
        return self._ctx.get_position(self._symbol)

    @property
    def available(self) -> float:
        """可用持仓数量."""
        return self._ctx.get_available_position(self._symbol)

    def __repr__(self) -> str:
        """返回持仓信息的字符串表示."""
        return f"Position(symbol={self._symbol}, size={self.size})"
