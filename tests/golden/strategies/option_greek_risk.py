"""Option Greek risk strategy - tests Delta limit enforcement."""

from akquant import Bar, Strategy


class OptionGreekRiskStrategy(Strategy):
    """Buy call options until Greek limit is breached."""

    def __init__(self) -> None:
        self.count = 0

    def on_bar(self, bar: Bar) -> None:
        self.count += 1

        if bar.symbol != "CALL_OPT":
            return

        pos = self.get_position("CALL_OPT")

        # Day 1: Buy 5 contracts (should fill)
        if self.count == 1 and pos == 0:
            self.buy("CALL_OPT", 5)

        # Day 3: Buy 5 more (should fill, still under limit)
        if self.count == 3 and pos > 0:
            self.buy("CALL_OPT", 5)

        # Day 5: Buy 10 more (should trigger Greek limit breach)
        if self.count == 5 and pos > 0:
            self.buy("CALL_OPT", 10)
