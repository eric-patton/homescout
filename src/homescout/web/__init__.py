"""The local browser interface: six surfaces over the same core the command line calls.

Nothing in this package decides anything. Every endpoint is a call to `homescout.api` and a
serialization of the answer, which is non-negotiable 8 made structural rather than promised, and a
test scans this package to prove it: nothing here imports the store, the runner, the rule engine or
the export.

Two rules the rest of it is built around, both of them things a localhost tool usually gets wrong:

**No authentication is not the same as no access control.** Binding to the loopback address settles
which machines can reach this. It settles nothing about which *pages* can, and every page the person
has open can send a request here. `app.py`'s guard is what closes that.

**Nothing from a listing site or a person's notes ever becomes markup.** There is exactly one way to
build an element in `static/common.js` and it puts text in with `textContent`. There is no
`innerHTML` in this package at all, which a test also asserts, so a description containing a script
tag is a description containing the characters of one.
"""

from __future__ import annotations

# Deliberately empty of names. `web.app` and `web.serve` are modules, and a convenience function
# called `serve` here would shadow the module called `serve`, which is the kind of ambiguity that
# resolves differently depending on what has been imported first.
