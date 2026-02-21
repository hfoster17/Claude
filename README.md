# Multi-Futures Institutional Trading Stack

HMM-based regime detection system for futures trading across NQ, ES, CL, NG, GC, SI, ZB.

## Architecture

```
NinjaTrader 8 Strategy ←→ TCP ←→ Python Regime Engine
       ↓                              ↓
   Risk Engine                  HMM Inference
   Execution                    Model Training
   Telemetry                    Drift Detection
                                Dashboard
```

**Design priority**: Risk safety > Runtime stability > Deterministic behavior > Performance > Sophistication.

External signals are **advisory only** — the NT8 risk engine has final authority.

## Quick Start

### 1. Install Python Dependencies

```bash
cd engine
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Prepare Data

Place OHLCV CSV files in `data/` directory:
- Format: `timestamp,open,high,low,close,volume`
- One file per symbol: `NQ.csv`, `ES.csv`, etc.
- Minimum 500 bars recommended

### 3. Train Models

```bash
# Single symbol
python train.py --symbol NQ

# All symbols
python train.py --all

# Custom settings
python train.py --symbol NQ --k 3 --n-restarts 5
```

Models are saved to `models/{SYMBOL}_model.json`.

### 4. Start the Engine

```bash
python main.py --serve
# or with custom settings
python main.py --serve --port 5555 --model-dir models
```

### 5. Configure NinjaTrader 8

1. Copy `nt8/MultiRegimeStrategy.cs` to:
   `Documents\NinjaTrader 8\bin\Custom\Strategies\`
2. Open NinjaTrader → NinjaScript Editor → Compile
3. Apply strategy to chart:
   - Set `ModelConfigFolder` to your models directory
   - Set `Host` = `127.0.0.1`, `Port` = `5555`
   - Enable on simulation account first
4. Strategy auto-detects instrument and loads appropriate profile

### 6. Launch Dashboard

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

## File Structure

```
├── contracts/               System contracts and schemas
│   ├── feature_contract.md  Feature vector specification
│   ├── model_schema.json    HMM model JSON schema
│   └── tcp_protocol.md      TCP message protocol
├── nt8/
│   └── MultiRegimeStrategy.cs  NinjaTrader 8 strategy
├── engine/
│   ├── main.py              CLI entry point
│   ├── server.py            TCP inference server
│   ├── model_manager.py     Model loading + hot reload
│   ├── hmm_inference.py     Forward algorithm
│   ├── feature_engine.py    Feature computation
│   ├── train.py             Training pipeline
│   ├── data_pull.py         Data ingestion
│   ├── drift.py             Drift detection
│   ├── scheduler.py         Nightly retrain scheduler
│   ├── config.yaml          Configuration
│   └── requirements.txt     Python dependencies
├── dashboard/
│   └── app.py               Streamlit monitoring dashboard
├── services/                Windows service scripts
├── docker/                  Docker deployment
├── tests/                   Test suite
├── sample_requests/         Example TCP messages
├── models/                  Trained model files
└── data/                    Historical bar data
```

## Components

### Feature Vector (6 features)

| # | Feature | Normalization |
|---|---------|---------------|
| 0 | Log Return | Z-score (rolling 100) |
| 1 | Realized Volatility | Z-score (rolling 100) |
| 2 | RSI Deviation | Raw [-1, 1] |
| 3 | VWAP Distance | Clipped [-3, 3] |
| 4 | Bar Range Ratio | Clipped [0, 5] |
| 5 | Volume Z-Score | Clipped [-3, 3] |

### Regime Labels

- **State 0 (low_vol)**: Low volatility — no trading
- **State 1 (trending)**: Trending market — trend following
- **State 2 (high_vol)**: High volatility — mean reversion

### Risk Engine States

- **Idle** → **Armed** → **InTrade** → **Idle** (normal cycle)
- **Locked**: Daily loss limit, profit lock, or consecutive losses
- **Halted**: Max trades per day reached
- **EmergencyStop**: Kill switch activated

## Testing

```bash
# Run all tests
cd engine && python -m pytest ../tests/ -v

# Specific test files
python -m pytest ../tests/test_features.py -v
python -m pytest ../tests/test_hmm.py -v
python -m pytest ../tests/test_tcp.py -v
python -m pytest ../tests/test_soak.py -v
```

## Docker Deployment

```bash
cd docker
cp .env.example .env
make build
make run
make logs     # View logs
make stop     # Stop
```

## Windows Service

See `services/README.md` for NSSM and Task Scheduler setup.

## Go-Live Checklist

1. [ ] Train models for all target instruments
2. [ ] Run test suite — all tests pass
3. [ ] Start engine, verify heartbeat responds
4. [ ] Load strategy on NinjaTrader simulation account
5. [ ] Verify regime labels appear on chart
6. [ ] Run 1-hour soak test on replay data
7. [ ] Verify risk engine blocks trades at daily loss limit
8. [ ] Test emergency kill switch
9. [ ] Test engine disconnect → strategy falls back to internal HMM
10. [ ] Deploy engine as Windows service or Docker container
11. [ ] Monitor dashboard for one full session
12. [ ] Switch to live account with minimal size

## Rollback Plan

1. Enable `EmergencyKillSwitch` in NT8 strategy properties
2. Stop the engine service: `net stop MultiRegimeEngine`
3. Revert model files to previous version
4. Restart engine service
5. Disable kill switch after confirming stability

## Supported Instruments

| Symbol | Exchange | Tick Size | Point Value | Default Max Size |
|--------|----------|-----------|-------------|------------------|
| NQ | CME | 0.25 | $20 | 2 |
| ES | CME | 0.25 | $50 | 4 |
| CL | NYMEX | 0.01 | $1,000 | 2 |
| NG | NYMEX | 0.001 | $10,000 | 1 |
| GC | COMEX | 0.10 | $100 | 2 |
| SI | COMEX | 0.005 | $5,000 | 1 |
| ZB | CBOT | 1/32 | $1,000 | 2 |
