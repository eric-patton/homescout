"""Where the model is, and where its credential comes from.

Three variables and one rule: **the credential comes from the environment or from the uncommitted
`.env` file beside the database, and from nowhere else.** Not from a saved search, not from a
committed file, and not from a command-line argument, for the reason the digest feature already
wrote down: arguments are visible to every other process on the machine, and Windows Task Scheduler
keeps a task's arguments as plain text in its own XML.

The same `.env` file the digest reads, using the same loader, because a person who put their mail
password there will put their model key there too and being told it is missing while it sits in the
file the tool already reads would be a defect in a feature about honesty.

The one branch between a hosted service and a local server lives here and nowhere else: a hosted
address needs a credential and a loopback address does not. Everything downstream of this module
sees one client with one configuration, which is what AC-9 means by two backends being one code
path.
"""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..errors import InvalidInput
from ..sources.politeness import PolitenessConfig, SourcePolicy

BASE_URL = "HOMESCOUT_EXTRACT_BASE_URL"
MODEL = "HOMESCOUT_EXTRACT_MODEL"
API_KEY = "HOMESCOUT_EXTRACT_API_KEY"
#: The name the constitution and the decisions log both use. Read second, so an installation that
#: already has one for something else does not have to duplicate it, and one that wants a different
#: key for this can say so.
FALLBACK_API_KEY = "OPENAI_API_KEY"

#: Every variable this feature reads, named once so the example file, the documentation and the
#: tests cannot drift apart from the code.
VARIABLES: tuple[str, ...] = (BASE_URL, MODEL, API_KEY, FALLBACK_API_KEY)

DEFAULT_BASE_URL = "https://api.openai.com/v1"

#: Pacing for the model, keyed like a source. Two seconds is slower than a paid service needs and
#: about right for a local one on the same machine as the run: non-negotiable 10 says default to
#: slow, and nothing here is in a hurry.
MODEL_DELAY_SECONDS = 2.0
MODEL_TIMEOUT_SECONDS = 60.0

#: What the paced session calls this, in its own rate limiting and in any failure it reports.
PACING_KEY = "extract"


class ExtractionMisconfigured(InvalidInput):
    """The model pass is on and something it needs is missing or unusable.

    Invalid input rather than a precondition, because the fix is always in what the operator wrote.
    Raised while the settings are read, which is before a run starts: the spec asks for a missing
    credential to be reported at validation time rather than as a failure per property.
    """


@dataclass(frozen=True, slots=True)
class ModelAccount:
    """Where to ask, what to ask, and what to prove.

    `__repr__` is overridden so the credential cannot reach a traceback, a log line or a test
    failure. The digest feature learned that one the expensive way.
    """

    base_url: str
    model: str
    api_key: str | None = None

    def __repr__(self) -> str:
        held = "a key" if self.api_key else "no key"
        return f"ModelAccount(base_url={self.base_url!r}, model={self.model!r}, {held})"

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def headers(self) -> dict[str, str]:
        """What the request carries. No `Authorization` at all when there is no credential."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _loopback(url: str) -> bool:
    """Is this address on this machine?

    The only thing that decides whether a credential is required. A local server does not need one
    and a hosted one does, and asking somebody to invent a key for LM Studio would be the kind of
    friction that makes a person disable the feature.
    """
    host = (urlparse(url).hostname or "").strip("[]")
    if host.casefold() in ("localhost", "host.docker.internal"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def environment(root: Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The `.env` file beside the database, with the real environment on top.

    The digest feature's loader, not a second one. One file, one syntax, one place to look.
    """
    from ..deliver.settings import environment as shared

    return shared(root, environ)


def account(root: Path, environ: Mapping[str, str] | None = None) -> ModelAccount:
    """Where the model is, or a refusal naming what is missing.

    Only ever called when a saved search has turned the model pass on. With it off, nothing here
    runs, no credential is read, and no address is resolved, which is product invariant 9 and AC-7.
    """
    values = environment(root, environ)
    base_url = (values.get(BASE_URL) or DEFAULT_BASE_URL).strip()
    model = (values.get(MODEL) or "").strip()
    key = (values.get(API_KEY) or values.get(FALLBACK_API_KEY) or "").strip() or None

    scheme = urlparse(base_url).scheme.casefold()
    if scheme not in ("http", "https"):
        # A request target is configuration and configuration is checked. `file:` and `data:` are
        # not requests, and finding that out inside a loop over five thousand properties is not
        # where anybody wants to find it out.
        raise ExtractionMisconfigured(
            f"{BASE_URL} has to be an http or https address, and this one is {base_url!r}."
        )
    if not urlparse(base_url).hostname:
        raise ExtractionMisconfigured(f"{BASE_URL} has no host in it: {base_url!r}.")
    if not model:
        raise ExtractionMisconfigured(
            f"The model pass is on for this search, so {MODEL} has to name a model. "
            "For a hosted service that is something like 'gpt-4o-mini'; for a local server it is "
            "whatever that server calls the model it has loaded."
        )
    if key is None and not _loopback(base_url):
        raise ExtractionMisconfigured(
            f"The model pass is on and {base_url} is not on this machine, so it needs a "
            f"credential. Put one in {API_KEY} or {FALLBACK_API_KEY}, in the environment or in the "
            "uncommitted .env file beside the database. It never goes in a saved search."
        )
    return ModelAccount(base_url=base_url, model=model, api_key=key)


def configured(root: Path, environ: Mapping[str, str] | None = None) -> bool:
    """Could the model pass run at all? Asked without raising, for reporting."""
    try:
        account(root, environ)
    except ExtractionMisconfigured:
        return False
    return True


def pacing() -> PolitenessConfig:
    """The same politeness everything else in this product gets, keyed to the model."""
    policy = SourcePolicy(delay=MODEL_DELAY_SECONDS, timeout=MODEL_TIMEOUT_SECONDS)
    return PolitenessConfig(default=policy, per_source={PACING_KEY: policy})


#: An address with a query string, for removing the second one. Some OpenAI-compatible proxies take
#: a key as a query parameter, so a failure detail carrying a URL can carry a credential.
_QUERY = re.compile(r"(https?://[^\s?]*)\?\S*")


def without_credential(detail: str, account: ModelAccount | None) -> str:
    """A failure message with nothing secret in it.

    Two things are removed, and the second is the one that is easy to forget. The credential itself,
    wherever it appears; and the whole query string of any address in the message, because some
    OpenAI-compatible proxies take a key as a query parameter and a failure carrying the URL then
    carries the key into whatever records it.
    """
    cleaned = detail
    if account is not None and account.api_key:
        cleaned = cleaned.replace(account.api_key, "[redacted]")
    return _QUERY.sub(r"\1[query removed]", cleaned)


def default_environ() -> Mapping[str, str]:
    return os.environ
