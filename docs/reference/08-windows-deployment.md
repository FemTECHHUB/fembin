# 08 — Windows Server deployment & port whitelisting

How to expose BUSY's port 981 safely and where the connector runs, on a cloud Windows Server
(AWS / other) with TSplus RDP.

## Topology (chosen model)

```
[ Connector server ]  ──HTTP/HTTPS──►  [ BUSY Windows Server ]
  (our infra, fixed IP)   port 981        (TSplus RDP, BUSY always logged in)
```

The connector runs on a **separate server** and polls BUSY at `http://<busy-server-ip>:981`.
We're fine provisioning that separate server.

## The security rule (do not skip)

Port 981 is **plaintext HTTP** and carries `UserName`/`Pwd` in headers. **Never** open it to the
whole internet. Two layers:

1. **Whitelist the connector's IP only** (network layer).
2. **Optionally wrap in TLS** so the hop is encrypted even along the whitelisted path.

Give the connector server a **static/Elastic IP** first — the whitelist points at it.

## Step 1 — Cloud firewall / security group (do this at the cloud layer)

**AWS (Security Group on the BUSY instance):**
- Inbound rule → Type: Custom TCP → Port: `981` → Source: `<connector-elastic-ip>/32`
- Do **not** use `0.0.0.0/0`.

(Azure NSG / GCP firewall: same idea — allow TCP 981 only from the connector's IP.)

RDP/TSplus stays on its own rule (typically 3389 or the TSplus HTTPS gateway port) — unchanged.

## Step 2 — Windows Firewall on the BUSY server (host layer)

Run in an elevated PowerShell on the BUSY server:

```powershell
New-NetFirewallRule -DisplayName "BUSY Web Service 981" `
  -Direction Inbound -Protocol TCP -LocalPort 981 `
  -RemoteAddress <CONNECTOR_IP>/32 -Action Allow
```

`-RemoteAddress` restricts the rule to the connector's IP, mirroring the cloud rule (defense in depth).

## Step 3 — Confirm BUSY is listening

On the BUSY server:
```powershell
netstat -ano | findstr :981
```
You should see it listening. If not, enable "BUSY as Web Service" inside BUSY and confirm the port
(the VB sample used 985 — verify the actual port and use it consistently).

## Step 4 (recommended) — Encrypt the hop with a TLS proxy

Because 981 is cleartext, put a TLS terminator in front of it on the BUSY server so the connector
talks HTTPS:

- **stunnel** or **nginx (Windows)** listens on e.g. `8443` with a TLS cert, forwards to
  `localhost:981`.
- Whitelist `8443` to the connector IP (Steps 1–2) instead of exposing 981 off-box at all.
- Connector calls `https://<busy-server-ip>:8443` → proxy → `localhost:981`.

Even better: skip public exposure entirely with a **VPN / VPC peering / private link** between the
two servers, so 981 is only reachable on the private network.

## Step 5 — Verify from the connector server

```powershell
Test-NetConnection <busy-server-ip> -Port 981     # TcpTestSucceeded : True
```
Then a real call (any HTTP client) with the `SC`/`UserName`/`Pwd` headers from
[04-examples.md](04-examples.md), starting with a harmless `SC=1` query.

## Deployment checklist

- ☐ Provision connector server; assign it a static/Elastic IP.
- ☐ Cloud security group: allow TCP 981 (or 8443 if TLS) from connector IP only.
- ☐ Windows Firewall inbound rule scoped to connector IP.
- ☐ Confirm BUSY web service is enabled and listening on the expected port.
- ☐ (Recommended) TLS proxy or VPN between the servers.
- ☐ `Test-NetConnection` succeeds from the connector server.
- ☐ First live `SC=1` read returns `Result: T`.
- ☐ BUSY company auto-login/keep-alive verified (session stays logged in across restarts).
