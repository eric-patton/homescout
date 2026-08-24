---
schema_version: 2
id: "feat-002"
slug: "source-adapters"
title: "Source adapters and the Realtor.com source"
status: done
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-001]
requires_design: null
readiness:
  research: ready
  design:   n/a
  spec:     ready
  plan:     ready
  tasks:    ready
gate:
  analyze: pass
  product_global_hash: "sha256:869c75445341"
  constitution_hash: "sha256:7ed19648690b"
converge:
  last_run: 2026-08-23
  open: 0
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Source adapters and the Realtor.com source

## Scope

The adapter interface every provider satisfies, the capability declaration that says which
filters a provider can push server-side, and the shared politeness layer: per-source rate
limiting, backoff, jitter, configurable delay, honest user agent. Ships one working adapter
against Realtor.com, including its result ceiling and the date-range chunking that works around
it. Zillow and Redfin are feat-005 and must require no core change.

Brief section 5.1. Constitution non-negotiables 9 and 10.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Later changes by other features

- **2026-08-23, command line and run orchestration (feat-003), defect.** Preview retrieval never
  returned a picture from the real source. Realtor.com gives its image addresses as plaintext
  `http://`, its image host answers every one of them with a 301 to the identical `https` address,
  and image fetches deliberately do not follow redirects, so every preview in the product was a
  167-byte redirect page. The offline tests could not catch it, because a fake transport returns
  whatever it is told to; the first live run of a command found it immediately.

  Fixed in `realtor/normalize.py`: an `http://` address is asked for over `https` instead. That is
  not following the redirect, it is declining to make the plaintext request the redirect exists to
  correct, and it costs one request rather than two. A traced regression fix against `AC-23`, with
  an offline test (`test_a_plaintext_image_address_is_asked_for_over_https`) and a live one
  (`test_a_real_preview_image_comes_back_as_a_picture`) both citing it.

- **2026-08-23, saved searches and geography (feat-004), addition.** A new area type,
  `PointRadius(latitude, longitude, miles)`, in the area vocabulary, accepted by the Realtor.com
  adapter. It is what a drawn shape becomes for a source that takes no bounding box: a circle
  around the shape that contains it, which the caller then filters exactly. Distinct from
  `AddressRadius`, which names a place the source has to look up first; a `PointRadius` resolves
  with no geography request at all, because the coordinates are what that request exists to
  produce. Additive: this feature's area vocabulary is explicitly the set of forms a source can be
  asked for, and no existing behavior changed. Offline test
  `test_a_radius_around_coordinates_is_searched_without_looking_the_place_up` cites `AC-17`.
- **2026-08-23, saved searches and geography (feat-004), defect.** The radius search had never
  worked against the real site. It carried the same sort bucket the area search uses, and the
  source answers a radius query carrying one with a server error and no rows, which is
  indistinguishable from a market with nothing for sale in it. No offline test could catch it: the
  radius path is exercised against a fake transport, which returns whatever it is told regardless
  of what the document says.

  Found by the first live run of a drawn shape, because a shape becomes a circle and a circle is a
  radius query. Fixed in `realtor/queries.py`: the radius search sorts explicitly by listing date,
  newest first, which the site accepts and which paging by offset needs anyway. Pinned offline by
  an assertion on the document shape in
  `test_a_radius_around_coordinates_is_searched_without_looking_the_place_up` (`AC-17`), and
  covered live by `test_a_drawn_shape_in_a_file_runs_against_the_real_site`.
