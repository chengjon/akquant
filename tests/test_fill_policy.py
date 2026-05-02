from __future__ import annotations

import pytest

from akquant import Engine


class TestFillPolicyPriceBasis:
    """Fill policy PriceBasis extension tests."""

    def _make_engine(self) -> Engine:
        """Create a minimal engine for fill policy testing."""
        engine = Engine()
        engine.use_simple_market(0.0001)
        return engine

    def test_mid_quote_basis(self) -> None:
        """mid_quote price basis can be set and retrieved."""
        engine = self._make_engine()
        engine.set_fill_policy("mid_quote", 1, "same_cycle")
        basis, offset, temporal = engine.get_fill_policy()
        assert basis == "mid_quote"
        assert offset == 1

    def test_typical_basis(self) -> None:
        """typical price basis can be set and retrieved."""
        engine = self._make_engine()
        engine.set_fill_policy("typical", 1, "same_cycle")
        basis, offset, temporal = engine.get_fill_policy()
        assert basis == "typical"

    def test_vwap_bar_basis(self) -> None:
        """vwap_bar price basis can be set and retrieved."""
        engine = self._make_engine()
        engine.set_fill_policy("vwap_bar", 1, "same_cycle")
        basis, offset, temporal = engine.get_fill_policy()
        assert basis == "vwap_bar"

    def test_new_basis_requires_bar_offset_1(self) -> None:
        """New price basis variants require bar_offset=1."""
        engine = self._make_engine()
        for basis in ["mid_quote", "typical", "vwap_bar"]:
            with pytest.raises(ValueError, match="bar_offset"):
                engine.set_fill_policy(basis, 0, "same_cycle")

    def test_unknown_basis_rejected(self) -> None:
        """Unknown price basis is rejected."""
        engine = self._make_engine()
        with pytest.raises(ValueError, match="Unknown"):
            engine.set_fill_policy("twap", 1, "same_cycle")

    def test_existing_basis_still_works(self) -> None:
        """Existing price basis options still work."""
        engine = self._make_engine()
        for basis in ["open", "close", "ohlc4", "hl2"]:
            offset = 0 if basis == "close" else 1
            engine.set_fill_policy(basis, offset, "same_cycle")
            b, _, _ = engine.get_fill_policy()
            assert b == basis
