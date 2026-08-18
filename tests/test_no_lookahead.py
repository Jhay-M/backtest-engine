"""The no-lookahead guarantee — the single most important correctness test.

The invariant, stated precisely:

* A signal computed on bar ``t`` may read only bars ``<= t``.
* The order it raises fills at the **open of bar ``t+1``**, never at the close
  of bar ``t``.

This file is the home of that proof. It is written property-based (hypothesis):
over randomly generated OHLCV series, no fill price may ever equal information
that was unavailable at signal time. The assertions are marked ``skip`` until
the concrete ``DataHandler``/``ExecutionHandler`` land — the scaffold ships the
contract so the test is impossible to forget, not an afterthought.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="pending concrete DataHandler/ExecutionHandler (v1)")


def test_signal_reads_only_past_bars() -> None:
    """A strategy must never observe a bar dated after the current timestamp."""
    raise NotImplementedError


def test_fill_prices_at_next_bar_open() -> None:
    """Every fill is priced at the open of the bar after its signal."""
    raise NotImplementedError
