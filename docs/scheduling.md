# Running HomeScout on a schedule (Windows)

A monitor that has to be remembered is not a monitor. This is how to have Windows run every saved
search overnight, write a digest where a program can read it, and email you only when something
happened.

There is no service and no background process. Windows Task Scheduler starts `homescout`, it runs,
it exits. Between runs nothing of this tool is executing.

## What you will end up with

- A scheduled task named **HomeScout nightly** that runs once a day.
- A digest file rewritten by every run, whether or not anything changed.
- An email, only on the nights something was new, changed, gone, back, or newly flagged.

Everything below is undone by the two commands in [Removing it](#removing-it). Nothing is installed
anywhere else, and nothing is written outside the folder you choose.

## 1. Decide where the data lives, and say so absolutely

This is the step that decides whether the whole thing works, so do it first and do it with full
paths.

A scheduled task does not start in your project folder. Windows starts it in `C:\Windows\System32`,
so every relative path HomeScout would otherwise use (`homescout.db`, `digest.json`, `.env`) would
resolve somewhere you did not mean. Naming the database absolutely fixes all three at once, because
the digest defaults to sitting beside the database and the `.env` file is read from beside it too.

Open PowerShell and run, with your own folder:

```powershell
setx HOMESCOUT_DB "C:\repos\homescout\homescout.db"
```

`setx` writes the variable to your Windows user profile, which is what a scheduled task running as
you will see. Setting it with `$env:HOMESCOUT_DB = ...` instead would set it for that one PowerShell
window only, and the task would not see it. **This is the single most common reason a scheduled task
works when you run it by hand and does nothing at three in the morning.**

Close and reopen PowerShell afterwards. `setx` does not affect the window you typed it in.

## 2. Tell it where to send email (optional)

Skip this entire step if you do not want email. HomeScout runs without it, writes the digest, and
reports the email as skipped.

Credentials never go in a saved search, in a committed file, or on a command line, so there is
nowhere to put one except the environment or a `.env` file. Put a file called `.env` **beside your
database** (the folder from step 1). It is already in `.gitignore` and it is never committed.

```
HOMESCOUT_SMTP_HOST=smtp.example.com
HOMESCOUT_SMTP_PORT=587
HOMESCOUT_SMTP_SECURITY=starttls
HOMESCOUT_SMTP_USERNAME=you@example.com
HOMESCOUT_SMTP_PASSWORD=an-app-password-not-your-real-one
HOMESCOUT_MAIL_FROM=you@example.com
HOMESCOUT_MAIL_TO=you@example.com
```

Notes worth having before you find out the hard way:

- **Use an app password**, not your account password, on any provider that offers them.
- `HOMESCOUT_SMTP_SECURITY` is `starttls` (the default), `ssl`, or `none`. HomeScout verifies the
  server's certificate and will not quietly fall back to sending in the clear: if you ask for
  encryption and the server does not offer it, the message is not sent.
- Set all of `HOMESCOUT_SMTP_HOST`, `HOMESCOUT_MAIL_FROM` and `HOMESCOUT_MAIL_TO`, or none of them.
  Setting some is refused with a message saying which is missing, because half a mail account is
  always somebody who believes they configured email.
- `HOMESCOUT_DIGEST_PATH` moves the digest somewhere other than beside the database.
- `HOMESCOUT_EMAIL_MAX_NEW` caps how many new properties one email lists. The default is 25; the
  rest are counted in the email and listed in full in the digest file.

Check it before you schedule anything:

```powershell
homescout run --all --json --deliver
```

A configuration mistake is reported in the first second, before anything is fetched.

## 3. Create the task

One command. Substitute your own path to the installed `homescout.exe` (`(Get-Command homescout).Source`
will tell you where it is) and your own time.

```powershell
schtasks /Create /TN "HomeScout nightly" /SC DAILY /ST 03:00 /RL LIMITED /F /TR "C:\repos\homescout\.venv\Scripts\homescout.exe run --all --json --deliver"
```

What each part is doing:

| part | what it does |
|---|---|
| `/TN "HomeScout nightly"` | the task's name. This is the only name this document creates. |
| `/SC DAILY /ST 03:00` | once a day, at three in the morning. |
| `/RL LIMITED` | ordinary user rights. HomeScout needs nothing more. |
| `/F` | replace an existing task of the same name rather than failing. |
| `/TR ...` | what to run: the installed command, every saved search, machine-readable output, and delivery turned on. |

`--deliver` is what writes the digest to the configured path and sends the email. Without it, a run
prints its results and writes nothing, which is what you want when you are running one by hand.

**If the machine is asleep at three in the morning**, the run is simply missed. Nothing is lost: the
next run compares against the last run that actually completed, not against yesterday, so a
weekend's worth of changes arrives in one email on Monday. If you would rather it caught up, add
`/RU` and the wake settings in Task Scheduler's own interface; this document deliberately does not,
because waking a machine is a bigger decision than checking a property site.

## 4. Check it

Run it once, immediately, without waiting for the night:

```powershell
schtasks /Run /TN "HomeScout nightly"
```

Then look at the task's own record of what happened:

```powershell
schtasks /Query /TN "HomeScout nightly" /V /FO LIST
```

`Last Result` is HomeScout's exit code:

| code | meaning |
|---|---|
| 0 | it ran, and everything worked |
| 1 | it ran, but a source failed or the email could not be sent. The results are still recorded. |
| 2 | something in the configuration or a saved search is wrong. Nothing was run. |
| 3 | it could not start yet: usually another run was already going. |
| 4 | something unexpected, or the digest could not be written. |

A `2` here almost always means step 1 did not take. Check that the task sees the variable:

```powershell
schtasks /Run /TN "HomeScout nightly"
Get-Content "C:\repos\homescout\digest.json" | Select-Object -First 5
```

If the digest file is not where you expect it, `HOMESCOUT_DB` is not reaching the task.

## Removing it

Two commands, and everything this document created is gone:

```powershell
schtasks /Delete /TN "HomeScout nightly" /F
setx HOMESCOUT_DB ""
```

Delete the `.env` file if you made one. Your database, your images and your saved searches are
untouched by all of the above; nothing here creates or removes them.

## Two runs at once

If a scheduled run starts while you are running the same saved search by hand, the second one
declines rather than waiting, and says so with exit code 3. That is deliberate: queueing behind a
run somebody left open would mean fetching the same listings twice, and the scheduled task will try
again on its next tick anyway.
