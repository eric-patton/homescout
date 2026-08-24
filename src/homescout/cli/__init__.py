"""The terminal surface.

Nothing in this package decides anything about a listing. It parses arguments, calls
:mod:`homescout.api`, formats the answer, and returns an exit code. That is enforced rather than
intended: modules here may not import the store or the sources at all, so there is no object here
to make a decision about.
"""
