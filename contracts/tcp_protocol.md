# TCP Communication Protocol v2

## Transport Layer

- **Protocol**: TCP over localhost (127.0.0.1)
- **Default Port**: 5555
- **Framing**: 4-byte big-endian length prefix + UTF-8 JSON payload
- **Max message size**: 65536 bytes

### Frame Format
```
[4 bytes: uint32 big-endian payload length][N bytes: UTF-8 JSON payload]
```

## Message Types

### 1. Inference Request (Client → Server)
```json
{
  "type": "infer",
  "symbol": "NQ",
  "timestamp": "2026-02-21T14:30:00Z",
  "features": [0.12, -0.45, 0.33, 0.21, 1.15, -0.28]
}
```

| Field      | Type     | Required | Description                          |
|------------|----------|----------|--------------------------------------|
| type       | string   | yes      | Must be "infer"                      |
| symbol     | string   | yes      | Instrument symbol                    |
| timestamp  | string   | yes      | ISO 8601 UTC timestamp               |
| features   | float[]  | yes      | Feature vector (length must match model n_features) |

### 2. Inference Response (Server → Client)
```json
{
  "type": "result",
  "symbol": "NQ",
  "state_probs": [0.10, 0.72, 0.18],
  "state": 1,
  "confidence": 0.72,
  "version": 2,
  "model_timestamp": "2026-02-20T22:00:00Z"
}
```

| Field           | Type     | Description                            |
|-----------------|----------|----------------------------------------|
| type            | string   | "result"                               |
| symbol          | string   | Echo of request symbol                 |
| state_probs     | float[]  | Posterior probability per state [k]    |
| state           | int      | Most probable state index              |
| confidence      | float    | Probability of dominant state          |
| version         | int      | Model schema version                   |
| model_timestamp | string   | When the active model was trained      |

### 3. Heartbeat (Client → Server)
```json
{"type": "heartbeat"}
```

### 4. Heartbeat Ack (Server → Client)
```json
{
  "type": "heartbeat_ack",
  "uptime_s": 3600,
  "models_loaded": ["NQ", "ES", "CL", "NG", "GC", "SI", "ZB"],
  "request_count": 12345
}
```

### 5. Error Response (Server → Client)
```json
{
  "type": "error",
  "symbol": "NQ",
  "message": "Model not loaded for symbol NQ",
  "code": "MODEL_NOT_FOUND"
}
```

Error codes: `MODEL_NOT_FOUND`, `INVALID_FEATURES`, `INVALID_REQUEST`, `INTERNAL_ERROR`

### 6. Status Request (Client → Server)
```json
{"type": "status"}
```

### 7. Status Response (Server → Client)
```json
{
  "type": "status_response",
  "uptime_s": 3600,
  "models": {
    "NQ": {"version": 2, "trained_at": "2026-02-20T22:00:00Z", "request_count": 500},
    "ES": {"version": 2, "trained_at": "2026-02-20T22:00:00Z", "request_count": 480}
  },
  "total_requests": 12345,
  "avg_latency_ms": 1.2
}
```

## Timing Rules

| Rule                    | Value  | Description                                    |
|-------------------------|--------|------------------------------------------------|
| Heartbeat interval      | 30s    | Client sends heartbeat every 30 seconds        |
| Heartbeat timeout       | 60s    | No ack in 60s → mark connection stale          |
| Inference timeout       | 2000ms | No response in 2s → use internal HMM fallback  |
| Stale bar threshold     | 5      | Response older than 5 bars → stale             |
| Reconnect base delay    | 1s     | Exponential backoff: 1, 2, 4, 8, 16, 30s max  |
| Max reconnect attempts  | 10     | After 10 fails, stop until next bar cycle      |

## Connection Lifecycle

1. Client connects on strategy startup (State.DataLoaded)
2. Client sends heartbeat immediately after connect
3. On each bar: client sends infer request, waits up to TimeoutMs
4. If timeout: use internal HMM, increment stale counter
5. On disconnect: begin reconnect with exponential backoff
6. On strategy termination: close connection gracefully
