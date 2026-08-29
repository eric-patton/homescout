# Proposal — more-sources

**Status: not built.** The site will not serve the page to a client that says what it is. What
follows is the change as proposed and then what measuring it found, kept so that the next person to
have this idea, including a later version of me, does not spend the afternoon again.

**Trigger:** "Is there any way to get the pictures from Redfin listings (or maybe just these
listings are having issues?)", with six properties named, every one of them carried by this source
alone.

**Summary.** They were not having issues. This source's download has twenty-seven columns and not
one of them is a photograph, so a property no other site carries has never had a picture: not on the
results table, not in a pin's bubble, not in the morning's email. The proposal was to read the
picture off the property's own page, from the tag that exists so a pasted link shows a picture. That
tag is a web standard, read by every chat window and every search engine, and it names the size a
link preview wants rather than the original: six hundred and sixty-five pixels and fifty-four
kilobytes on the property measured, where the same photograph at full size is two thousand and
forty-eight across. Larger, in other words, than what the other two sources hand over.

## What measuring it found

It was built, and it worked, and then it was taken back out.

**The page is refused to anybody who admits to being a program.** Measured on 2026-08-29 against
three of the six properties, each request made once and spaced:

| client says it is | listing page | the CSV download |
| --- | --- | --- |
| `homescout/0.1.0 (personal listing monitor)` | **403**, every time | **200** |
| `homescout/0.1.0` | **403**, every time | - |
| nothing at all | **403** | - |
| a current build of Chrome | 200, then 202 once it had seen a few | - |

So this source hands its data to a self-identified tool and refuses that same tool the human-facing
page. The only way through is to claim to be a browser.

**That is the one thing the politeness layer exists to make impossible.** The user agent is the
single setting in `sources/politeness.py` that is deliberately not configurable, so that no adapter
can announce itself as something it is not. A change that needs that lock opened is not a change to
this adapter, it is a change to what this tool is, and it is not worth a thumbnail.

**Leaving the code in would have been worse than not having it.** Twelve properties, four attempts
each with backoff, every night, against a site that is already refusing us: that is the shape of
traffic that gets a client blocked, and being blocked is the failure that ends this project rather
than degrading it. So it came out rather than staying in to fail quietly.

## What was kept

The measurement, here and on `fetch_preview`, in place of the weaker reasoning that was there
before. The old note said fetching the page was not worth a second request, which was a judgment
about the value of a photograph. This one is a fact about the site, and it is the honest reason.

## What is still open

Nothing that does not require lying about who is asking. Constructing the picture's address from the
download was checked and is not possible: the address carries a market number and a photograph id,
and the download carries neither. Looking the property up on another site is circular, because a
property carried by another site is not one of the twelve.
