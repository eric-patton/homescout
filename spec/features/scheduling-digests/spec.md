## Why

A monitor that has to be remembered is not a monitor. This feature is what makes the tool run
without being asked and report only what moved: a machine-readable digest landing where a scheduled
agent can find it, and an email worth opening on a phone. The design decision that matters most is
silence. A digest that arrives every night whether or not anything happened trains its reader to
ignore it, which costs more than sending nothing. The problem brief is in `research.md`.

## Vocabulary used in this feature

- A **scheduled run** is an unattended invocation of the command line by the operating system's
  scheduler. There is no daemon and no always-running service.
- **Delivery** is what this feature adds to a run: writing the digest to a known path, and sending
  the email. The digest's content and shape belong to the command line feature.
- A run is **silent** when it produced no changes worth reporting, and a silent run sends no email.

## User stories

- As the person running searches, I want every saved search re-run on a schedule, so that staying
  current does not depend on me remembering.
- As the person running searches away from my desk, I want an email I can read on a phone showing
  what is new with a picture, a price, and a link, so that I can decide whether anything deserves my
  evening.
- As the person running searches, I want no email at all when nothing changed, so that the ones that
  do arrive mean something.
- As a scheduled agent, I want the digest at a known path in a known shape, so that I can act on it
  without being told where to look.
- As the person running searches, I want my mail credentials outside the repository, so that sharing
  the code never shares my account.

## Behavior & scenarios

- **Scenario: an unattended run delivers both reports**
  - Given every saved search and a configured mail account
  - When the scheduler invokes the run
  - Then the digest is written to the configured path and an email is sent, with no interaction

- **Scenario: nothing changed**
  - Given a scheduled run in which no property was new, changed, gone, returned, or newly flagged
  - When it completes
  - Then no email is sent, and the digest is still written so an agent can see the run happened

- **Scenario: the email is readable on a phone**
  - Given a run with new properties
  - When the email is opened on a phone
  - Then each new property shows its stored preview image, its price, its address, its notable
    flags, and a link, in a single-column layout that requires no horizontal scrolling

- **Scenario: the image does not depend on the source**
  - Given a source that does not permit its images to be loaded from elsewhere
  - When the email is rendered
  - Then the preview image still displays, because it is the copy the tool stored rather than a
    reference to the source

- **Scenario: a degraded run is reported as such**
  - Given a scheduled run in which one source failed
  - When it completes
  - Then the digest and the email both name the source and its outcome, and the exit code reports
    the run as degraded

- **Scenario: mail delivery fails**
  - Given a run that completed and a mail server that refuses the message
  - When delivery is attempted
  - Then the failure is reported and recorded, the digest file is still written, and the run's own
    results are unaffected

- **Scenario: credentials come from outside the repository**
  - Given mail credentials in the environment or in an uncommitted local file
  - When a run sends an email
  - Then the credential is read from there, and no credential appears in any saved search, any
    committed configuration, or any command argument

- **Scenario: setting up the schedule**
  - Given a fresh installation on Windows
  - When the documented setup is followed
  - Then a scheduled task exists that runs every saved search and writes the digest, and the
    documentation states exactly what was created

## Acceptance criteria

- [ ] AC-1: A scheduled invocation runs every saved search with no interaction and no console
      prompt.
- [ ] AC-2: The digest is written to the configured path on every completed run, including runs in
      which nothing changed and runs that were degraded.
- [ ] AC-3: An email is sent only when a run produced at least one new, changed, gone, returned, or
      newly flagged property. A test asserts that an unchanged run sends nothing.
- [ ] AC-4: The email lists each new property with its stored preview image, price, address, notable
      flags, and a link to the listing.
- [ ] AC-5: The email renders in a single column and is legible on a narrow phone screen without
      horizontal scrolling.
- [ ] AC-6: Images in the email are served from the tool's own stored copies, not referenced from a
      source, so rendering does not depend on a source permitting it.
- [ ] AC-7: The email reports price changes with the previous value, the new value, and a direction,
      and reports disappearances and returns separately from new properties.
- [ ] AC-8: A degraded run names each failing source and its outcome in both the digest and the
      email.
- [ ] AC-9: Mail credentials are read from the environment or an uncommitted local file. A test
      asserts that no credential is accepted from a saved search, a committed configuration file, or
      a command-line argument.
- [ ] AC-10: A mail delivery failure is reported and recorded, does not prevent the digest from being
      written, and does not alter the run's stored results.
- [ ] AC-11: With no mail account configured, scheduled runs still execute and still write the
      digest. Email is optional.
- [ ] AC-12: Setup for the Windows scheduler is documented well enough to follow without guessing,
      and states exactly what it creates so it can be undone.
- [ ] AC-13: A scheduled run requires no always-running process. Between runs the tool is not
      executing.
- [ ] AC-14: Two scheduled runs that overlap do not interleave. The second waits or declines, per
      the behavior the command line feature defines.

## Edge cases & errors

- The machine is asleep or off at the scheduled time. The run is missed, and the next run's
  comparison covers the whole interval since the last completed run rather than only since the
  missed one.
- The first ever scheduled run, where every property is new. The email would be enormous, so the new
  property list is capped with the remainder reported as a count and available in the digest and the
  interface.
- A run produces changes but a property has no stored preview image, because the image fetch failed.
  The entry appears without an image rather than being omitted.
- The digest path is not writable. This is reported and reflected in the exit code, so the scheduler
  records a failure rather than an apparent success.
- The mail server requires a form of authentication that is not configured. Reported at validation
  time where possible rather than only at send time.
- The run is degraded and also produced no changes. No email is sent by the changed-content rule,
  but the degradation is still visible in the digest and the exit code, so a scheduled agent can act
  on it.
- The scheduled task runs under a user account with a different environment than the interactive
  one, which is the usual cause of a scheduled task working by hand and failing on schedule. Setup
  documentation must address it and the failure message must make the cause identifiable.

## Non-functional requirements

- Performance: delivery adds negligible time to a run. The run's duration is dominated by source
  pacing.
- Security: credentials only from the environment or an uncommitted local file, never in a commit,
  a saved search, or a command argument. Email content is generated from stored data and never
  includes a credential or a local file path.
- Reliability: a delivery failure never damages the run's stored results, and a missed run is
  recoverable simply by running again.
- Accessibility: the email is legible at a phone's default text size, conveys nothing by color
  alone, and every image carries descriptive alternative text so it is usable with images disabled.

## Open questions

- The cap on the number of new properties listed in a single email is a settings value, and its
  default is a plan decision rather than a requirement.
