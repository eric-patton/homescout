"""Taking secrets out of text that is about to be written down.

This exists because of what recording a pass does to a failure message. A progress line and the
exception that ends an operation used to live in the memory of one process and go away with it.
Recorded, they are bytes in the database file, and this product's own advice is to keep a backup of
that file beside it. The exposure changed; the text did not.

`extract/settings.py` already had half of this and says why: some OpenAI-compatible proxies take a
key as a query parameter, so a failure detail carrying an address carries the key into whatever
records it. That half was applied at one call site, to extraction's own per-description failures,
and not to the exception that ends a pass, which is the string this now makes durable.

So it lives here, at the root, where the store can reach it. Layer order runs sources, merge, store,
enrich, rules, then the surfaces, and every one of them is above `store`: a scrubber the store must
call cannot live in any of them.

Four things are removed, and only the first is obvious.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

REDACTED = "[redacted]"

#: An address with a query string, for removing the second part. Taken from the version in
#: `extract/settings.py`, which is now written in terms of this one.
_QUERY = re.compile(r"(https?://[^\s?]*)\?\S*")

#: `Authorization: Bearer ...` and the same thing said in prose. The token runs to whitespace.
_BEARER = re.compile(r"(?i)\b(bearer|token|api[-_ ]?key)\b([\s:=]+)(\S{8,})")

#: The shape most providers issue: a short prefix, a separator, then a long opaque run. Deliberately
#: not anchored to one vendor, and deliberately requiring length, so that `sk-` in a sentence is
#: left alone and a real credential is not.
_KEYLIKE = re.compile(r"\b([A-Za-z][A-Za-z0-9]{1,7}[-_])([A-Za-z0-9_-]{20,})")

#: A name that means the value under it must never be written down. Matched on the name because the
#: value is opaque by construction: there is nothing about a credential's own text that identifies
#: it, which is why scanning for shapes alone is not enough.
_SECRETISH = re.compile(r"(?i)(key|token|password|secret|credential)")

#: Below this, a value is too short to be a credential and too likely to be a word that appears in
#: ordinary text. Redacting "1" everywhere it occurs would destroy every message it touched.
_SHORTEST_SECRET = 8


def scrub(text: str, environ: Mapping[str, str] | None = None) -> str:
    """The same text with anything that looks like a credential taken out of it.

    Not a guarantee, and nothing here should be read as one: this reduces what a leaked message
    discloses, and the thing that actually keeps a key out of a database is not putting it in a
    message. It is applied at the point of writing rather than at each call site because a caller
    who forgets is the failure it exists to remove, and there will be callers.
    """
    if not text:
        return text

    # Values first, because a literal key is the one thing here that is certain rather than
    # inferred, and removing it before the shape rules run means the shape rules cannot half-match
    # what is left and leave a recognisable stub.
    for name, value in (environ if environ is not None else os.environ).items():
        if value and len(value) >= _SHORTEST_SECRET and _SECRETISH.search(name):
            text = text.replace(value, REDACTED)

    text = _QUERY.sub(r"\1?" + REDACTED, text)
    text = _BEARER.sub(r"\1\2" + REDACTED, text)
    return _KEYLIKE.sub(r"\1" + REDACTED, text)
