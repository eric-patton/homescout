# Plan — Scheduling and digests (feat-012)

The spec's WHAT, turned into a HOW. Read `spec.md` first; this file only decides how to satisfy it.

## What this feature is actually adding

Almost everything this feature reports already exists. The digest document is built by the command
line (feat-003) and has been since its first commit; its module docstring says outright that this
feature consumes it unchanged. The stored preview image the email needs exists because of decision
D2 and is already fetched by every run. One run of a saved search at a time is already enforced by
the claim (feat-003), which is AC-14 in its entirety.

So the honest scope is narrow and worth stating before designing anything, because the temptation
here is to rebuild what is already built:

| the spec asks for | where it comes from |
|---|---|
| every saved search, unattended (AC-1) | `run --all`, already built |
| the digest document (AC-2) | `homescout.digest`, already built |
| one run at a time (AC-14) | `homescout.claim`, already built |
| the preview image (AC-6) | decision D2, already stored on disk |
| price direction, gone, returned (AC-7) | already in the digest document |
| per-source outcomes (AC-8) | already in the digest document |
| **writing the digest where a schedule expects it** | new |
| **the email, and the silence rule** | new |
| **credentials, and where they may come from** | new |
| **a record that delivery happened** | new |
| **the Windows setup, documented** | new |

Everything in the second half is delivery. That word is the spec's own, and this plan uses it for
exactly that: what happens to a finished run's report, as distinct from the run.

## Design decisions

### D-1: layout

A new package, `src/homescout/deliver/`, above the store and beside `digest.py`. It reads the store
for image paths and reads the digest document; nothing in it is reachable from a source or the run
loop, which is what makes AC-10's "does not alter the run's stored results" structural rather than
observed.

| file | holds |
|---|---|
| `deliver/settings.py` | the digest path and the mail account, read from the environment or an uncommitted `.env`, plus what "configured" and "valid" mean. |
| `deliver/message.py` | one digest document turned into a phone-readable email: HTML, plain text, and the images attached. |
| `deliver/mail.py` | the SMTP conversation, behind a protocol so a test can substitute it. |
| `deliver/delivery.py` | the pass: write the file, decide whether to send, send, record what happened. |

### D-2: delivery is asked for, never inferred

The scheduled task's command line is:

```
homescout run --all --json --deliver
```

`--deliver` is explicit rather than "on whenever mail is configured", for two reasons. A person
running `homescout run north` at a terminal must never accidentally email themselves, and a
scheduler entry should say what it does: someone reading the Task Scheduler action a year from now
can see that this one sends mail without going and reading a `.env` file.

The brief writes it as `--out <path>`; the built flag is `--output`, and it stays that. `--deliver`
writes the digest to the *configured* path (D-3) rather than to a path repeated in the scheduler
entry, so moving the digest is one edit in one file rather than an edit to a task definition.
`--output` still works and still does exactly what it did; the two are independent, and giving both
writes both.

### D-3: the digest path defaults beside the database

`HOMESCOUT_DIGEST_PATH`, defaulting to `digest.json` in the database's own directory. Same reasoning
as `DEFAULT_DB_NAME`: a relative default keeps an installation self-contained and keeps one more
path out of scheduler configuration, where it would be one more thing to get wrong.

The parent directory is checked **before the run starts**, not when the file is written. This is the
existing `--output` guard's reasoning and it applies with more force here: discovering an
unwritable path after an hour of throttled requests is exactly the failure that makes a scheduled
task look like it worked. The spec's edge case asks for the exit code to reflect it, and a
pre-flight check reflects it in the code before anything has been fetched.

### D-4: credentials come from the environment, and there is nowhere else to put them

| variable | what it is | required |
|---|---|---|
| `HOMESCOUT_SMTP_HOST` | the server | yes, to send at all |
| `HOMESCOUT_SMTP_PORT` | default 587 for starttls, 465 for ssl, 25 for none | no |
| `HOMESCOUT_SMTP_SECURITY` | `starttls` (default), `ssl`, or `none` | no |
| `HOMESCOUT_SMTP_USERNAME` | | no (a relay on a home network may want none) |
| `HOMESCOUT_SMTP_PASSWORD` | | only if a username is given |
| `HOMESCOUT_MAIL_FROM` | the sender | yes, to send at all |
| `HOMESCOUT_MAIL_TO` | recipients, comma separated | yes, to send at all |
| `HOMESCOUT_DIGEST_PATH` | where the JSON goes | no (D-3) |
| `HOMESCOUT_EMAIL_MAX_NEW` | the cap on listed new properties | no (D-8) |

Read from the process environment, and from a `.env` file beside the database if one exists, with
the real environment winning. The `.env` reader is fifteen lines and is written here rather than
taken as a dependency: it needs to read `KEY=value`, strip one layer of quotes, ignore comments and
blank lines, and nothing else. `.env` is already in `.gitignore`, and an `.env.example` naming every
variable with no value in it is what gets committed.

There is no `--smtp-password` and there will not be one. Arguments are visible to every other
process on the machine through the process list, and Windows Task Scheduler stores a task's
arguments in plain text in its own XML. The command line's own docstring already says this about
options in general; this feature is the one that makes it matter. A saved search cannot carry a
credential either, and the reason is stronger than convention: the saved-search validator rejects
keys it does not know, so `smtp_password:` in a definition is a validation problem naming the file
and the line, not an ignored key.

**The password is never written anywhere.** Not to the delivery record (D-7), not to a progress
line, not to an error message. An SMTP failure's own text is reported, and `smtplib`'s exceptions
carry the server's response rather than what was sent to it.

### D-5: silence is computed from the digest, not from the run

```python
def moved(document) -> int:
    """How many properties this digest has something to say about."""
```

Summed across every saved search in the document: new, price changes, status changes, other changes,
gone, returned, and newly flagged. Zero means no email (AC-3). Newly flagged is in the list because
the spec's own wording puts it there, and it is the interesting one: a property that has not
changed at all can still become worth looking at because a criterion started matching it, which
happens the night after enrichment fills in a flood zone.

Deliberately **not** part of the count: a degraded source. AC-3 lists what counts and a failing
source is not in it, and the spec's own edge case settles the collision: a degraded run with no
changes sends no email, and its degradation is visible in the digest and the exit code, which is
where an automated agent is looking anyway. A person does not need to be woken up because
`realtor` timed out.

The digest file is written either way (AC-2), including for a run that changed nothing and a run
that was degraded, because "the run happened and found nothing" and "the run did not happen" are
completely different facts to a scheduled agent and the file is how it tells them apart.

### D-6: the email is a table, in one column, and every image is attached

Two decisions that look dated and are not:

**Layout is `<table>`, not `<div>`.** Mail clients are not browsers. Flexbox and grid still fail in
Outlook's rendering engine, and a single-column table with `max-width: 600px` renders correctly in
everything from a phone's default client to a webmail preview pane. AC-5 is about a phone screen
with no horizontal scrolling, and a table with `width: 100%` on the outer element and inline styles
is how that is actually achieved. All CSS is inline on the elements, because several clients strip
a `<style>` block entirely.

**Images are attached, not linked.** `multipart/related`, each stored preview attached with a
`Content-ID`, referenced as `cid:...` from the HTML. That is AC-6 in its literal form: the picture
in the email is this tool's own copy from its own disk, so it renders whether or not the source
permits its images to be loaded from elsewhere, and it still renders for a listing that has since
disappeared and taken its images with it. It also means the email contains no outbound reference at
all, so opening it tells nobody anything.

Every image carries alternative text that is the property's address, so an email read with images
disabled still says which property each row is (the accessibility NFR). Direction is words and an
arrow character, never colour alone: `down $12,000` reads the same to everyone.

The message is `multipart/alternative` inside `multipart/related`: a plain-text part that is a
readable summary in its own right, and the HTML part. A phone at default text size gets 16px body
text and nothing smaller than 14px.

### D-7: a delivery is recorded, and the record is append-only

Schema version 4, one table:

```sql
CREATE TABLE deliveries (
    id           TEXT PRIMARY KEY,
    attempted_at TEXT NOT NULL,
    channel      TEXT NOT NULL,   -- 'digest' or 'email'
    target       TEXT,            -- the path, or the recipients. Never a credential.
    outcome      TEXT NOT NULL,   -- 'written' | 'sent' | 'suppressed' | 'skipped' | 'failed'
    detail       TEXT,
    run_ids      TEXT             -- the runs this delivery reported on
);
```

Append-only like every other history table, and for the same reason: "the email went out on the
fourteenth" is an observation, and this database does not rewrite observations. It is also the
answer to a question a person actually asks, which is why it is a table rather than a log line: *did
last night's run mail me and I missed it, or did it decide there was nothing to say?* `suppressed`
and `sent` are different rows with different meanings, and `skipped` (no account configured) is a
third.

AC-10's "recorded" is this. AC-10's "does not prevent the digest from being written" is ordering:
the file is written first, then the email is attempted, and the attempt cannot reach back.

### D-8: the first run is capped, and says so

`HOMESCOUT_EMAIL_MAX_NEW`, default **25**. The spec leaves the default to this plan; 25 is chosen
because it is more than a normal night ever produces and few enough to scroll on a phone. Above the
cap the email lists the first 25 by price and then says how many more there are and where they are:
the digest file has all of them, and so does the results table. Nothing is silently dropped, which
is the failure the cap could easily become.

The cap applies to the new-property list only. Price changes, disappearances and returns are the
part a person is actually reading for and are never large on a night that is not the first one; if
one of them is enormous, that is news in itself and truncating it would hide it.

### D-9: what an unattended invocation returns

| situation | code |
|---|---|
| ran, delivered, nothing to report | 0 |
| ran, delivered, email sent | 0 |
| a source failed (AC-8) | 1, as it already does |
| the mail server refused the message (AC-10) | 1 |
| no mail account configured (AC-11) | 0, and the digest is still written |
| the digest path's directory does not exist | 2, before anything is fetched |
| the digest could not be written | 4 |

A mail failure is degraded rather than an error, and this widens what code 1 means: it has been "at
least one source failed or was unavailable" and it becomes "at least one source or delivery
failed". The run's own results are complete and stored and the exit code should not claim otherwise;
what failed is a report about them. The help text that documents the codes is edited to match, which
is a change to the command line feature's surface and is recorded in its manifest.

A digest that could not be written is an internal error, matching what `--output` already returns
for the same failure. It is deliberately not 1: a scheduled agent that reads the file needs to know
the file is not there, and 1 would tell it the file is fine and a source was down.

### D-10: no process runs between runs

AC-13 is a structural property, so it is asserted structurally rather than observed. There is no
loop, no thread, no timer and no service anywhere in this feature: the console entry point calls
`main()`, `main()` returns an integer, and the operating system's scheduler is the only thing that
knows what time it is. A test asserts that a full delivering run leaves the thread it started with
and no other, and a second test asserts that nothing in the package imports `sched`, `asyncio`,
`threading.Timer`, or any third-party scheduler, which is the drift this criterion is really about:
somebody adding a `--watch` flag in two years.

### D-11: the setup documentation is checked by a test

AC-12 asks for documentation good enough to follow without guessing, that says exactly what it
creates so it can be undone. `docs/scheduling.md` gets the `schtasks` command that creates the task,
the exact task name it creates, the command to delete it, and the environment problem that the
spec's last edge case names: a scheduled task runs with the account's environment, not the
interactive shell's, which is why a task works by hand and fails on schedule.

The documented invocation is extracted by a test and fed to the real argument parser. Documentation
that stops parsing is then a failing test rather than a discovery made at midnight.

### D-12: what this feature does not own

- **The digest's content and shape.** Owned by the command line (feat-003). This feature writes it
  and renders it, and adds nothing to it.
- **Any channel other than email.** Named out of scope by the spec's own research.
- **A notification when a run does not happen at all.** A machine that was asleep produces no run
  and therefore no digest; noticing that is the scheduled agent's job, and the digest's timestamp is
  what it reads. The spec's edge case only requires that the next run's comparison covers the whole
  interval, which it already does: a comparison's baseline is the previous *completed* run, not
  yesterday.

## Verification approach

- **The silence rule is tested in both directions.** An unchanged run sends nothing and writes the
  file; a run with one price change sends. AC-3 asks for the first explicitly.
- **The mail server is a fake that records the message**, and the assertions are made against the
  parsed MIME: that there is a plain-text alternative, that every `cid:` reference resolves to an
  attached part, that every `<img>` has alt text, and that the bytes of the attached image are the
  bytes on disk rather than a URL.
- **The credential rules are tested as refusals**, not as absences: the parser rejects
  `--smtp-password`, a saved search containing `smtp_password` is a validation problem, and a
  delivery record and every rendered message are searched for the password string.
- **The live test is one real SMTP conversation**, marked slow and skipped unless an account is
  configured in the environment, because there is no public mail server to be polite to.

## Added after the pre-build check

Two decisions the first draft of this plan did not make. Both came out of the security pass, which
is what that pass is for: they are cheap now and would have been a rewrite of the message builder
after it existed. The findings they answer are S-1 and S-2 in `analyze.md`.

### D-13: everything a listing site wrote is untrusted text

An address, a city, a property type and a listing URL all arrive from a listing site, and they end
up inside an HTML document that a mail client renders. The first draft of this plan said nothing
about that, which would have produced a message builder that interpolated them directly.

- **Every interpolated value is escaped**, with `html.escape(value, quote=True)`, including inside
  attributes. There is one function that turns a value into HTML text and one that turns it into an
  attribute value, and nothing in the message builder writes an interpolation any other way.
- **A link is only a link if it is `http` or `https`.** A `listing_url` with any other scheme
  (`javascript:`, `data:`, `file:`) renders as escaped text rather than as an `href`. Checked by
  parsing the URL, not by looking for a substring.
- **The plain-text part is not exempt.** It carries no markup, but it must not carry a value that
  contains a newline into a position where the reader would take the next line as a field, so
  values are collapsed to a single line there.

This is not a hypothetical about a hostile listing site. A house whose address contains an
ampersand is a Tuesday, and an unescaped one is a broken email; the same rule handles both.

### D-14: the transport is verified, and never silently plaintext

- `ssl.create_default_context()`, so certificates are actually verified. Both `ssl` and `starttls`
  use it.
- **No fallback.** A server that does not offer STARTTLS when STARTTLS was asked for is a failure,
  not a reason to continue in the clear. `smtplib` raises there and that exception is allowed to be
  a failed delivery.
- `security: none` exists because a relay on a home network is a real configuration, and it is
  reachable only by setting it explicitly. It is never a default and never a fallback.
- **A header value containing a newline is refused at validation time**, before anything is sent,
  naming the variable it came from. `EmailMessage` would refuse it at send time anyway; refusing it
  up front is the spec's own edge case about reporting configuration problems at validation time.
- **The message is searched for the credential in a test.** Not because a code path writes it, but
  because that is the assertion that stays true after somebody adds a debugging header.
