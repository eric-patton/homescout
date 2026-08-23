"""HomeScout: a local-first property search monitor.

A monitor, not a scraper. Every run records what it observed of every matching listing, so that
the exact state at any past run stays recoverable and nothing already recorded is ever rewritten.
New, changed and gone are computed here by comparing those records, because no free listing source
exposes trustworthy history.
"""

__version__ = "0.1.0"
