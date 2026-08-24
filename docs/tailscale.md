# Reaching the interface from your phone, over Tailscale

The interface listens on `127.0.0.1` and nothing else. That does not change, and there is no setting
that changes it: `homescout serve` refuses a routable bind address outright, because there is no
authentication in this tool by design and an address anybody can reach would turn that from a design
into a hole.

What this document sets up is the other shape. **Tailscale runs on the same machine, takes the
connection, and forwards it to the loopback port.** Nothing is listening on a network at any point.

```
your phone  ──── WireGuard ────►  tailscaled on this machine  ──► 127.0.0.1:47823
             (encrypted, and                                       (the only thing
              only your tailnet)                                    listening at all)
```

## What is set up

| | |
|---|---|
| the interface listens on | `127.0.0.1:47823` |
| Tailscale presents it at | `https://ursine-blue.tail9a8857.ts.net:10000/` |
| the workspace | `%USERPROFILE%\HomeScout` |
| starts at log on via | a shortcut in the Startup folder running `start-homescout.vbs` |

`47823` is deliberately uncommon so it collides with nothing. `10000` is one of only three ports
Tailscale Serve will terminate HTTPS on (`443`, `8443`, `10000`), and `443` was already taken by
another service at `/`.

## The one setting that had to change

The guard in front of the interface refuses any request whose `Host` header is a name this server
does not answer to. That is not decoration: it is what stops **DNS rebinding**, where a page on
`evil.invalid` whose DNS points at `127.0.0.1` becomes same-origin with anything listening there and
can read the answers.

Through a proxy, the request still arrives on loopback but carries the name the browser asked for.
So the guard needs to be told that name:

```
HOMESCOUT_ALLOWED_HOSTS=ursine-blue.tail9a8857.ts.net,ursine-blue.tail9a8857.ts.net:10000
```

**A list, not a switch.** Every name that is not in it is still refused, so rebinding is still
refused. Empty is the default, which is loopback and nothing else.

The other two checks are untouched: a request from another site's page is refused, and anything that
changes something has to carry a header a form cannot set.

## What this does not add

**Authentication.** There is none, and this does not create any. Anything that can reach the proxy
can use the interface: read every property, every note you have written, and write more.

That is worth a moment because **your tailnet is shared**. It currently holds:

| device | belongs to |
|---|---|
| `ursine-blue` | `eric-patton@github` (this machine) |
| `mac` | `eric-patton@github` |
| `1955kjvcctv` | `becky.deckard44@gmail.com` |

The third one is somebody else's account. If you would rather it could not open this, restrict it in
the Tailscale admin console under **Access controls**, with a rule naming who may reach this port:

```jsonc
// tailscale.com/admin/acls
{
  "acls": [
    // ... whatever you already have ...
    {
      "action": "accept",
      "src":    ["eric-patton@github"],
      "dst":    ["ursine-blue:10000"]
    }
  ]
}
```

Read the rest of that file before saving it. A default tailnet policy is usually a single
allow-everything rule, and adding a narrow rule beside it changes nothing; tightening it means
editing the broad one, which will also affect the two services you already run.

**Funnel is not set up and I would not set it up without you asking.** Funnel puts a service on the
public internet. `tailscale funnel status` currently shows tailnet-only, which is what you want for
something with no password on it.

## Running it

Nothing to do: it starts when you log in, with no window.

```
# see whether it is up
Get-NetTCPConnection -State Listen -LocalPort 47823

# start it by hand, with output, if something looks wrong
cd $env:USERPROFILE\HomeScout
C:\repos\homescout\.venv\Scripts\homescout.exe serve

# stop whatever is running
Get-NetTCPConnection -State Listen -LocalPort 47823 |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### If you want it up when you are not logged in

The Startup folder runs things at log on, so the interface is down between a reboot and your first
log in. To have it up from boot instead, make it a scheduled task. This needs an **administrator**
terminal and it will prompt you for your Windows password, which Task Scheduler stores so it can run
as you without you being there:

```
schtasks /Create /TN "HomeScout interface" /SC ONSTART /RL LIMITED /RU %USERNAME% /RP * /F ^
  /TR "\"C:\repos\homescout\.venv\Scripts\homescout.exe\" serve"
```

Then remove the Startup shortcut so it does not also start a second copy:

```
Remove-Item "$([Environment]::GetFolderPath('Startup'))\HomeScout.lnk"
```

### Turning the Tailscale side off

```
tailscale serve --https=10000 off
```

The interface keeps running on `127.0.0.1:47823` and only this machine can reach it, which is where
it started.

## The nightly run is separate

This document is about the interface. The scheduled run that fetches listings and emails the digest
is `docs/scheduling.md`, and the two are independent: the run writes to the database, the interface
reads it, and either can be running without the other.

They do share one thing worth knowing: a run started from the interface and a run started from a
terminal are the same operation, and the store's own claim stops two happening at once. Whichever is
second is refused with the reason.
