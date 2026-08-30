"""Reading one property against what this household has already said it wants.

The second model pass, and the reason it is a second one rather than a wider first one is a
boundary. `extract` is handed prose, a vocabulary and the operator's notes, and deliberately not a
listing, a snapshot or a store, on the stated grounds that there is no address in scope there to
send. That blindfold is right for transcribing six enumerated fields out of a sentence, and it is
exactly why that pass can report that a description says "private well" and cannot report that the
property sits downwind of a feedlot somebody has spent a paragraph explaining they want to avoid.

Here there is an address in scope, and coordinates, and a photograph, and a picture of the fire
hazard around the point. That is the change, it was decided rather than drifted into, and feat-013's
AC-3 says so out loud so a later reader finds a decision rather than an inconsistency.

**Where this sits.** Above `rules` and below the surfaces, which is the highest position in the core
and the honest one: this is the only thing here that needs a rule verdict, an enrichment value, a
recovered field, a saved search's prose and a photograph in the same breath. It reads downward into
`store`, `enrich`, `rules`, `extract` and `search`. Nothing below it may import it, and the moment
something in `rules` wants "the assessment for this property" the direction has inverted and the
reason this module could exist at all is gone.

**What it does not do.** It does not decide. It ranks, explains and flags; keeping and passing on
remain the person's, which is non-negotiable 7. That is also this feature's whole answer to a
description written to manipulate it: a listing's text comes from somebody with an interest in the
sale, and what makes that acceptable is not the instruction telling the model to treat it as data,
which is a request rather than a guarantee. It is that nothing acts on the answer.
"""

from __future__ import annotations

from .dossier import Dossier, dossier_for
from .model import Assessment, Concern, ask, instruction, interpret

__all__ = [
    "Assessment",
    "Concern",
    "Dossier",
    "ask",
    "dossier_for",
    "instruction",
    "interpret",
]
