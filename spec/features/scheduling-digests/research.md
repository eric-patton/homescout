# Research — scheduling-digests

## Discovery input

From `homescout-brief.md` sections 7 and 10, and decision D2 in `homescout-decisions.md`:

- The whole premise of a monitor is that it runs without being asked. The primary target is Windows
  Task Scheduler invoking the command line, because the development machine is Windows with no
  Linux subsystem.
- Scheduled runs report two ways, and the brief chose both: a JSON digest file that lands in a known
  location for an automated agent to read, and an email digest for a person.
- The email has to be readable on a phone: new properties with a thumbnail, price, address, key
  flags, and a link. It is suppressed entirely when nothing changed, because a monitor that mails
  you every night trains you to ignore it.
- Credentials come from the environment or a local file that is never committed. This is a
  constitution requirement, not a preference.
- The thumbnail the email needs exists because of decision D2, which stores one preview image per
  property precisely so the digest renders without depending on a source permitting hotlinking.

## Problem brief

### Problem statement

Someone monitoring a market struggles to stay current because doing so means remembering to run a
search and then reading a table to find the handful of rows that moved, which results in checking
too rarely and missing the price cut that mattered. A solution should run unattended, deliver only
what changed, in a form readable on a phone and in a form readable by an automated agent, and stay
silent when nothing changed, without any credential ever living in the repository.

### Target users

- **The person running searches, away from their desk** (primary): reads the email on a phone and
  decides whether to open anything.
- **A scheduled automated agent** (primary): reads the JSON digest from a known path and acts on it.

### Jobs to be done

- Run every saved search on a schedule with no interaction.
- Land a machine-readable summary where an agent can find it.
- Send a human-readable summary that is worth opening.
- Say nothing at all when there is nothing to say.

### Success signals

- The email is opened rather than filtered, because it only arrives when something happened.
- The digest file is picked up and acted on without any parsing of prose.
- No credential ever appears in a commit.

### Constraints

- Windows Task Scheduler is the target. No daemon, no service, no always-on process.
- Credentials from the environment or an uncommitted local file only.
- The email must render on a phone, including the image, without depending on a source allowing
  its images to be loaded from elsewhere.

### Explicitly out of scope

- The digest's content and shape, which the command line owns (feat-003). This feature delivers and
  schedules it.
- Any notification channel other than email.
- Hosting, or any always-running server beyond the local browser interface.

### Open questions

None blocking.
