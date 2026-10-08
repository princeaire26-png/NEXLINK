# NEXLINK LAN Quick Start

## 1. Server PC

Run as Administrator:

```powershell
NEXLINK-Server.exe --auto-infra
```

Find the server LAN IPv4 address:

```powershell
ipconfig
```

The API listens on TCP `8000`.

Check from another PC:

```powershell
Invoke-WebRequest http://SERVER_IP:8000/health
```

Expected response contains:

```json
{"status":"healthy","service":"nexlink-backend","version":"0.1.0"}
```

## 2. Create the first NEXLINK account

Use the API documentation at:

```text
http://SERVER_IP:8000/docs
```

Call `POST /api/v1/auth/register` with an email, name and password. The response
contains an access token.

## 3. Create an enrollment token

Using the access token, call `POST /api/v1/enrollment/create`.

Example PowerShell:

```powershell
$token = 'ACCESS_TOKEN'
$headers = @{ Authorization = "Bearer $token" }
$body = @{ device_name = 'LAN-CLIENT-01' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://SERVER_IP:8000/api/v1/enrollment/create -Headers $headers -ContentType 'application/json' -Body $body
```

Save the returned `enrollment_token`.

## 4. Client PC

Run:

```powershell
NEXLINK-Client.exe
```

Run it as Administrator because Network Guard needs Windows Firewall and hosts
file access.

Enter the server LAN IP when prompted, for example:

```text
192.168.1.20
```

The client stores the resulting WebSocket URL in:

```text
%LOCALAPPDATA%\NEXLINK\client.json
```

## 5. Enrollment

The bundled agent accepts the enrollment token through the agent CLI during
initial setup. The Windows build keeps the agent private to the NEXLINK client
package; it is not a separate product.

After enrollment, approve the device through the NEXLINK API/dashboard.

## 6. Verify the connection

The device should progress:

```text
PENDING -> APPROVED -> ONLINE
```

The server should then receive heartbeat and metrics reports.

## 7. Verify Network Guard

From the authenticated NEXLINK API, use the Network Guard endpoint on the
approved online device:

- `block_all`
- `unblock_all`
- `block_domains`
- `status`

`block_all` uses Windows Firewall's `Internet` remote-address scope so the
NEXLINK LAN control connection can remain reachable while Internet destinations
are blocked. Microsoft documents `Internet` as a supported Windows Firewall
remote-address keyword.

A server-enforced block persists locally and has precedence over a local voucher
unlock.
