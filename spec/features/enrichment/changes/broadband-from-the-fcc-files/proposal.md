# Proposal — enrichment

**Trigger:** The person running searches got an FCC API token, set it, and asked whether the server
needed restarting to pick it up. It did. The token then reached the provider, and the provider
answered `405 Method Not Available` on every request, because the endpoint it asks does not exist
and never has.

**Summary:** The broadband provider was written to the shape every other provider in this feature
has: one address, one point, one answer. There is no such endpoint. Measured against the live
service on 2026-08-24, the FCC's public API is a **bulk file** API: it lists per-state availability
files and hands them over as zipped CSV. The map's own per-location endpoint is blocked to anything
that is not the map, and the Fabric coordinates that would let anybody build a point query are
licensed. So the provider as specified cannot be built, and its current code reads the token, throws
it away, and asks a URL that answers 405.

What can be built, and what this change specifies, is a two-step lookup that stays inside the
feature's own rules. A point resolves to its census block through the FCC's free and keyless block
API, which is a paced request like every other. The block's service comes from a local index built
once per state from the FCC's own files. New Mexico is 47.5 MB of download, twenty-one seconds, and
a 60,287-block index; the answer for the block a Portales property sits in is 1200 down, 1000 up,
five named providers.

Three consequences the spec has to carry rather than leave to the code. The credential is two values
and not one: the FCC wants an account name alongside the token. The answer is now the *block's* best
advertised service rather than the property's, which is a weaker claim than the old wording implied
and must be said plainly wherever the value is shown. And satellite is excluded from the speed, on
purpose: it is available essentially everywhere, so folding it in would make every rural property
look served and would carry no information at all.

## Blast radius

Everything this change touches, so the ripple is explicit.

- **Requirements affected:** AC-11 (the providers that exist and are individually enableable) is
  unchanged in letter. AC-12 (national coverage, asserted by a live lookup in distant states) needs
  restating: a state with no index loaded is a different condition from a provider that is not
  configured, and the live test has to say which it is asserting. AC-13's pacing applies to the
  block lookup; the file download is one request per file and is not inside any loop. The security
  NFR's "an API token" becomes an account name and a token.
- **Design decisions affected:** the provider protocol itself. Every other provider is
  `configured()` plus `fetch(session, lat, lon)` with nothing behind it. This one has a dataset
  behind it, which is the first stateful provider in the feature and the reason this is a change
  rather than a defect fix.
- **Tasks affected (regenerate these):** the broadband tasks. New tasks for the FCC client, the
  index, the store table, the command, both surfaces, and the tests.
- **Already-built code affected:** `enrich/providers.py` (`Broadband`), `enrich/settings.py` (the
  endpoints and the credential), the store schema (a new table at version 7), `api.py`, the command
  line, and the browser's settings page.

## Status

- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
