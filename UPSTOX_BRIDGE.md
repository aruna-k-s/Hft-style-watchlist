# Upstox Bridge Runbook

This repository now supports two ingest modes:

1. Simulator ingest (existing): `docker/docker-compose.yml`
2. Upstox live ingest (new): `docker/docker-compose.upstox.yml`

## Required Environment (Always)

- `UPSTOX_INSTRUMENTS` (comma-separated instrument keys)

## Token Source Options (Choose One Flow)

### Flow A: Direct Access Token (existing behavior)

- `UPSTOX_ACCESS_TOKEN` **or**
- `UPSTOX_TOKEN_FILE` (raw token string or JSON with `access_token`) **or**
- `UPSTOX_TOKEN_REFRESH_CMD` (stdout raw token or JSON with `access_token`)

### Flow B: OAuth Auth-Code Exchange (new)

Required env:

- `UPSTOX_CLIENT_ID`
- `UPSTOX_CLIENT_SECRET`
- `UPSTOX_REDIRECT_URI`
- `UPSTOX_AUTH_CODE` **or** `UPSTOX_AUTH_CODE_FILE`
- Optional `UPSTOX_AUTH_STATE` (validated if set)

How to obtain auth code:

1. Open authorize URL:

   `https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=<client_id>&redirect_uri=<redirect_uri>&state=<optional_state>`

2. Complete login on Upstox page.
3. Capture callback URL or `code` value.
4. Put callback URL/code into `UPSTOX_AUTH_CODE` or `UPSTOX_AUTH_CODE_FILE`.
5. Bridge exchanges it at:
   `POST https://api.upstox.com/v2/login/authorization/token`

### Flow C: Individual Token Request + Notifier Webhook (new)

Required env:

- `UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL=true`
- `UPSTOX_CLIENT_ID`
- `UPSTOX_CLIENT_SECRET`
- `UPSTOX_NOTIFIER_TOKEN_FILE` (path where your webhook writer stores notifier JSON payload)
- Optional `UPSTOX_TOKEN_REQUEST_WAIT_SECONDS` (default `180`)

Bridge flow:

1. Initiates token request:
   `POST https://api.upstox.com/v3/login/auth/token/request/{client_id}`
2. Waits for notifier payload file update.
3. Validates payload structure (`message_type=access_token`, matching `client_id`, non-empty `access_token`).
4. Uses received access token.

Optional:

- `UPSTOX_MODE` (`ltpc`, `option_greeks`, `full`, `full_d30`; default `full`)
- `UPSTOX_SUBSCRIPTION_BATCH_SIZE` (default `100`)
- `UPSTOX_BRIDGE_LOG_LEVEL` (default `INFO`)
- `UPSTOX_LOGIN_TIMEOUT_SECONDS` (default `10`)

## Start Live Upstox Pipeline

```bash
docker compose -f docker/docker-compose.upstox.yml up --build -d
```

## Validate

```bash
docker ps
docker logs -f hft-upstox-bridge
docker logs -f hft-signal-engine
```

Expected bridge lifecycle:

1. `get_token`
2. authorize URL (`/v3/feed/market-data-feed/authorize`)
3. connect websocket
4. subscribe
5. decode protobuf feed
6. publish binary ticks to ZeroMQ (`tcp://*:5555`)
7. reconnect and re-subscribe on disconnect

## Expected Logs

```text
INFO bridge.start endpoint=tcp://*:5555 instruments=12 mode=full batch_size=100
INFO bridge.connect.start
INFO bridge.connect.ok
INFO bridge.subscribe.ok instruments=12
DEBUG bridge.decode.ok symbol=NSE_EQ|INE002A01018
WARNING bridge.token.refreshed
ERROR bridge.token.refresh_failed type=TokenRefreshError message=...
```

## Stop

```bash
docker compose -f docker/docker-compose.upstox.yml down
```
