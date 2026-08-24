# Tasks — Scheduling and digests (feat-012)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

`[P]` here means what the legend says and no more: this task and the others marked `[P]` beside it
can be worked in any order. A test written against code that does not exist yet is not a peer of
that code, so the test tasks below carry no marker.

## Settings, and where a credential may come from

- [x] T1: `deliver/settings.py`: the digest path with its default beside the database, the mail
      account, and the `.env` reader that the real environment overrides (D-3, D-4, AC-9).
- [x] T2: Validation up front: an account that is half-configured is refused before anything is
      fetched, naming what is missing, and a header value containing a newline is refused there too
      (D-14, the mail-authentication edge case).
- [x] T3 [P]: `.env.example` naming every variable with no value in it, and a README line pointing
      at it (AC-9).
- [x] T4: `tests/test_deliver_settings.py`: the defaults, the override order, a half-configured
      account, a recipient with a newline in it, and that nothing accepts a credential from an
      argument or a saved search (AC-9, D-14).

## The record

- [x] T5: Schema version 4: `deliveries`, append-only, with the reason in the schema (D-7). Record
      the change in feat-001's manifest.
- [x] T6: `store.record_delivery` and `store.deliveries`, and never a credential in either (D-7,
      AC-10).

## The email

- [x] T7: `deliver/message.py`: the digest rendered as one column of table rows, inline styles,
      16px body text, at most 600px wide (D-6, AC-4, AC-5).
- [x] T8: Every interpolated value escaped, and a link rendered as a link only when its scheme is
      `http` or `https` (D-13).
- [x] T9: Images attached from the tool's own stored copies as `multipart/related` parts with
      `Content-ID` references, each with the address as alternative text (D-6, AC-6).
- [x] T10: Price changes with before, after and a direction in words; disappearances and returns in
      their own sections; newly flagged properties with the criteria that fired (AC-7).
- [x] T11: A degraded run names each failing source and its outcome in the email (AC-8).
- [x] T12: The new-property cap, with the remainder as a count and where to find it (D-8, the
      first-run edge case).
- [x] T13: A property with no stored image renders without one rather than being omitted (the
      missing-image edge case).
- [x] T14: `tests/test_deliver_message.py`: the MIME structure, every `cid:` resolving, alt text
      everywhere, the plain-text alternative, the cap, no colour-only meaning, and that no local
      path and no credential appears anywhere in the rendered message (AC-4, AC-5, AC-6, AC-7,
      AC-8, the security NFR).
- [x] T15: `tests/test_deliver_safety.py`: an address, a city and a URL from a hostile listing, each
      arriving in the message as text rather than as markup (D-13).

## Delivery

- [x] T16: `deliver/mail.py`: the SMTP conversation behind a protocol, with `starttls`, `ssl` and
      `none`, a verified default context, no fallback to plaintext, and a failure that carries the
      server's own words (D-14, AC-10).
- [x] T17: `deliver/delivery.py`: write the file, decide whether to send, send, record each
      channel's outcome. The file is written before the email is attempted (D-5, D-7, AC-2, AC-3,
      AC-10).
- [x] T18: `moved(document)`: what counts as something to say (D-5, AC-3).
- [x] T19: `tests/test_deliver_pass.py`: silence in both directions, a degraded run with nothing to
      report staying silent while its degradation still reaches the digest, a refused message
      leaving the digest and the run's results untouched, and no account configured still writing
      the file (AC-2, AC-3, AC-10, AC-11, the degraded-and-silent edge case).

## The command line

- [x] T20: `api.deliver`, so both surfaces reach one operation (invariant 5).
- [x] T21: `run --deliver`, the pre-flight check on the digest path, and the exit codes in D-9. The
      help text for code 1 widens to name delivery. Record the change in feat-003's manifest.
- [x] T22: `tests/test_deliver_command.py`: the flag, `--json`, each exit code in D-9, an unattended
      invocation that prompts for nothing, and two overlapping delivering runs where the second
      declines and mails nothing (AC-1, AC-13, AC-14).
- [x] T23: A test that a run after a missed night compares against the last completed run rather
      than against yesterday (the sleeping-machine edge case).

## Scheduling

- [x] T24: `docs/scheduling.md`: the `schtasks` command, the exact task name it creates, how to
      remove it, and why a task that works by hand fails on schedule (AC-12, the environment edge
      case).
- [x] T25: A test that feeds the documented invocation to the real argument parser, so
      documentation that stops parsing fails (D-11, AC-12).
- [x] T26: A test that no scheduler, timer, thread or event loop is imported anywhere in the
      package, that nothing in it reads from the console, and that a delivering run leaves no thread
      behind (D-10, AC-1, AC-13).

## Finishing

- [x] T27 [P]: `tests/test_deliver_live.py`: one real SMTP send, marked slow, skipped unless an
      account is configured.
- [x] T28 [P]: Document delivery in the README: the flag, the variables, and that email is optional.
- [x] T29: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T30: `/spec-flow:converge`, then the manifest stamp.
