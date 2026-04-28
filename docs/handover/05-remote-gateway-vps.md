# 05 — Remote (VPS) Gateway connection

## 5.1 The user's VPS

The user has OpenClaw running on a Hostinger VPS:

- **Gateway URL:** `wss://openclaw-npt3.srv1624328.hstgr.cloud`
- **Token:** `rwOVXP2pBEo3mJ77TESWR9QCq1R3cnHN`

The VPS terminates TLS in front of the gateway (Cloudflare/nginx in
front of OpenClaw on port 18789). MC must use `wss://` and **not**
specify a port — the proxy maps to the internal port.

## 5.2 Configuring MC to use it

Three equivalent ways:

### Via env vars (deployment)

```bash
export MC_GATEWAY_URL="wss://openclaw-npt3.srv1624328.hstgr.cloud"
export MC_GATEWAY_TOKEN="rwOVXP2pBEo3mJ77TESWR9QCq1R3cnHN"
./start.sh
```

### Via Settings UI (interactive)

1. Open MC → Settings.
2. Paste URL and Token into the inputs.
3. Click "Save & Reconnect".
4. Watch the status indicator at the top.

### Via persisted file (manual)

```bash
mkdir -p ~/.mission-control
cat > ~/.mission-control/gateway.json <<EOF
{
  "gateway_url": "wss://openclaw-npt3.srv1624328.hstgr.cloud",
  "gateway_token": "rwOVXP2pBEo3mJ77TESWR9QCq1R3cnHN"
}
EOF
```

Persisted only loads if neither `MC_*` nor `OPENCLAW_*` env vars are
set, so env vars override.

## 5.3 What happened when we tested

WS handshake — succeeded. TLS, upgrade, token in query string all OK.

Device challenge / signature — succeeded. Gateway accepted our
Ed25519 public key and verified the signature.

Final auth response — **`DEVICE_PAIRING_REQUIRED`**:
```
"device pairing required: device is not approved yet"
```

In MC's diagnostics this surfaces as:
```json
{ "auth_status": "pairing_required",
  "auth_error": "device is not approved yet",
  "paired": false,
  "pairing_pending": true,
  "connected": true }
```

The WS stays open; MC keeps it alive but cannot make operator RPCs
until the device is approved.

## 5.4 How to approve the device on the VPS

The gateway holds the pending pairing request server-side. Approval
options:

1. **VPS-side MC instance** — if the VPS already runs an OpenClaw MC
   (or any operator UI), it has a "Pending devices" view that lists
   our `device_id` and offers Approve / Reject. The MC backend has
   matching endpoints we can hit *from* the VPS-side MC:
   - `GET  /api/gateway/pairing/pending`
   - `POST /api/gateway/pairing/approve/{request_id}`
   - `POST /api/gateway/pairing/reject/{request_id}`

   These already exist in `backend/routers/gateway.py` (see
   [02-session-changes.md §2.4](./02-session-changes.md)). They
   require an *already-paired* device with `operator.admin` scope to
   call them — i.e. the bootstrap admin device on the VPS.

2. **OpenClaw CLI on the VPS:**
   ```bash
   ssh user@srv1624328.hstgr.cloud
   openclaw gateway pairing list
   openclaw gateway pairing approve <request_id>
   ```

3. **Pre-trust the public key** in the VPS gateway config:
   ```json
   "gateway": {
     "auth": {
       "mode": "device",
       "trustedDevices": [
         { "deviceId": "<our-device-id>", "publicKey": "<our-pub-key-base64>" }
       ]
     }
   }
   ```
   Get the values from MC: `GET /api/gateway/device` returns the
   `device_id` and exposes the public key in `device.json`.

## 5.5 Reconnecting after approval

Once approved on the VPS, click **Reconnect** in the MC Settings UI
(or `POST /api/gateway/reconnect`). The connection loop drops the
old WS and re-handshakes; this time the gateway returns
`AUTHENTICATED` and `auth_status` flips to `authenticated`.

## 5.6 Why the VPS test was a success even with the error

The full auth flow up to the pairing decision works:
- TLS handshake to Cloudflare ✓
- WS upgrade ✓
- Token query string accepted ✓
- Device challenge issued by gateway ✓
- Ed25519 signature verified ✓
- Public key recognised as a *new* device ✓
- Pairing request created server-side ✓

So the MC code path is correct. The remaining step is purely an
operational one (someone with admin scope on the VPS approves the
device) and is **not** code-changeable from the MC side.
