# Multi-Regime Trading Stack — Deployment Guide

Step-by-step instructions for installing, configuring, deploying, loading data, and testing the complete system.

---

## Table of Contents

1. [File Inventory](#1-file-inventory)
2. [Prerequisites](#2-prerequisites)
3. [Download & Install Files](#3-download--install-files)
4. [Set Up Python Environment](#4-set-up-python-environment)
5. [Configure the Engine](#5-configure-the-engine)
6. [Prepare Historical Data](#6-prepare-historical-data)
7. [Train HMM Models](#7-train-hmm-models)
8. [Run Tests](#8-run-tests)
9. [Start the Python Engine](#9-start-the-python-engine)
10. [Install NinjaTrader 8 Strategy](#10-install-ninjatrader-8-strategy)
11. [Configure Strategy on Chart](#11-configure-strategy-on-chart)
12. [Deploy as Windows Service](#12-deploy-as-windows-service)
13. [Deploy with Docker (Alternative)](#13-deploy-with-docker-alternative)
14. [Launch the Dashboard](#14-launch-the-dashboard)
15. [Verification Checklist](#15-verification-checklist)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. File Inventory

Below is every file in the project. Download all of them, preserving the directory structure.

### Root
| File | Purpose |
|------|---------|
| `README.md` | Project overview and quick start |
| `DEPLOYMENT_GUIDE.md` | This document |
| `.gitignore` | Git ignore rules |

### `contracts/` — System Contracts & Schemas
| File | Purpose |
|------|---------|
| `contracts/feature_contract.md` | Feature vector specification (6 features + order flow) |
| `contracts/model_schema.json` | JSON schema for HMM model files |
| `contracts/tcp_protocol.md` | TCP message protocol specification |

### `nt8/` — NinjaTrader 8 Strategy
| File | Purpose |
|------|---------|
| `nt8/MultiRegimeStrategy.cs` | Complete NT8 strategy (all modules in one file) |

### `engine/` — Python Regime Engine
| File | Purpose |
|------|---------|
| `engine/main.py` | CLI entry point (`--serve`, `--train`, `--status`) |
| `engine/server.py` | Async TCP inference server |
| `engine/model_manager.py` | Model loading, validation, hot-reload |
| `engine/hmm_inference.py` | HMM forward algorithm + Viterbi decoding |
| `engine/feature_engine.py` | Feature computation (mirrors NT8 exactly) |
| `engine/train.py` | HMM training pipeline |
| `engine/data_pull.py` | CSV data ingestion + NT8 export watcher |
| `engine/drift.py` | Drift detection (occupancy, KL, likelihood, KS) |
| `engine/scheduler.py` | Nightly retrain + drift-triggered retrain |
| `engine/config.yaml` | Engine configuration |
| `engine/requirements.txt` | Python dependencies |

### `dashboard/` — Streamlit Monitoring UI
| File | Purpose |
|------|---------|
| `dashboard/app.py` | Dashboard application |
| `dashboard/requirements.txt` | Dashboard dependencies |

### `services/` — Windows Service Scripts
| File | Purpose |
|------|---------|
| `services/install_engine_service.ps1` | NSSM service installer |
| `services/uninstall_engine_service.ps1` | NSSM service uninstaller |
| `services/start_engine.ps1` | PowerShell startup script |
| `services/start_engine.bat` | Batch file startup script |
| `services/README.md` | Windows service setup guide |

### `docker/` — Docker Deployment
| File | Purpose |
|------|---------|
| `docker/Dockerfile` | Docker image definition |
| `docker/docker-compose.yml` | Compose configuration |
| `docker/.env.example` | Environment variable template |
| `docker/Makefile` | Build/run/stop shortcuts |

### `tests/` — Test Suite (66 tests)
| File | Purpose |
|------|---------|
| `tests/conftest.py` | Shared test fixtures |
| `tests/test_features.py` | Feature engine tests |
| `tests/test_hmm.py` | HMM filter + Viterbi tests |
| `tests/test_schema.py` | Model schema validation tests |
| `tests/test_tcp.py` | TCP server protocol tests |
| `tests/test_drift.py` | Drift detection tests |
| `tests/test_soak.py` | 1000-message soak tests |

### `sample_requests/` — Example TCP Messages
| File | Purpose |
|------|---------|
| `sample_requests/heartbeat.json` | Heartbeat message example |
| `sample_requests/nq_request.json` | Single NQ inference request |
| `sample_requests/multi_request.json` | Multi-instrument batch request |

### `models/` and `data/`
Empty directories — you will populate these during setup.

---

## 2. Prerequisites

### Windows Machine (for NinjaTrader + Engine)
- **Windows 10/11** 64-bit
- **NinjaTrader 8** installed and licensed (sim or live)
- **Python 3.10+** (3.11 recommended) — download from https://www.python.org
- **Git** (optional, for cloning) — https://git-scm.com
- **NSSM** (for Windows service) — https://nssm.cc

### Alternative: Docker Host (for Engine only)
- **Docker** 20.10+ with Docker Compose
- NinjaTrader still runs on Windows, engine runs in Docker on any host

---

## 3. Download & Install Files

### Option A: Clone from Git
```bash
git clone <your-repo-url> C:\MultiRegime
cd C:\MultiRegime
```

### Option B: Manual Download
1. Create the directory structure:
```
C:\MultiRegime\
├── contracts\
├── nt8\
├── engine\
├── dashboard\
├── services\
├── docker\
├── tests\
├── sample_requests\
├── models\
├── data\
└── logs\
```

2. Copy each file into its corresponding directory as listed in Section 1.

3. Create the empty directories:
```powershell
mkdir C:\MultiRegime\models
mkdir C:\MultiRegime\data
mkdir C:\MultiRegime\logs
```

---

## 4. Set Up Python Environment

Open PowerShell and run:

```powershell
cd C:\MultiRegime

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# Install engine dependencies
pip install -r engine\requirements.txt

# Install dashboard dependencies
pip install -r dashboard\requirements.txt

# Install test dependencies
pip install pytest
```

### Verify installation:
```powershell
python -c "import hmmlearn; import numpy; import pandas; print('All packages OK')"
```

Expected output: `All packages OK`

---

## 5. Configure the Engine

Edit `engine/config.yaml` to match your environment:

```yaml
server:
  host: "127.0.0.1"       # Keep as localhost
  port: 5555               # Must match NT8 strategy Port setting
  status_file: "engine_status.json"
  status_interval_s: 5

models:
  directory: "models"      # Relative to engine/ or use absolute path
  hot_reload_poll_s: 5.0

data:
  directory: "data"        # Where your CSV files live
  nt8_export_dir: ""       # Optional: path to NT8 export folder

training:
  k: 3                     # 3 states: low_vol, trending, high_vol
  n_restarts: 5            # Random restarts for training
  max_iter: 200
  tol: 0.0001
  min_training_bars: 500   # Minimum bars required to train
  warmup_bars: 100

symbols:                   # Instruments to support
  - NQ
  - ES
  - CL
  - NG
  - GC
  - SI
  - ZB
  - UB
```

**Key settings to verify:**
- `server.port` = 5555 (or your chosen port)
- `models.directory` points to where model files will be saved
- `data.directory` points to where your CSV data lives
- `symbols` list matches the instruments you want to trade

---

## 6. Prepare Historical Data

### Data Format

Each instrument needs a CSV file in `C:\MultiRegime\data\` named `{SYMBOL}.csv`.

**Required columns** (lowercase, comma-separated):
```
timestamp,open,high,low,close,volume
2024-01-02 18:00:00,16500.25,16525.50,16490.00,16510.75,1250
2024-01-02 18:05:00,16510.75,16530.00,16505.25,16528.50,980
...
```

### Minimum Data Requirements
- **500 bars minimum** per instrument (more is better)
- **Recommended**: 5000+ bars (several months of 5-minute data)
- Bar size should match what you'll run on the NT8 chart (e.g., 5-minute)

### Exporting from NinjaTrader 8

1. Open a chart for the instrument (e.g., NQ 03-26, 5-min)
2. Right-click chart → **Export** → **Export bars to CSV...**
3. Save as `C:\MultiRegime\data\NQ.csv`
4. Repeat for each instrument: ES, CL, NG, GC, SI, ZB, UB

### File naming convention:
```
C:\MultiRegime\data\NQ.csv
C:\MultiRegime\data\ES.csv
C:\MultiRegime\data\CL.csv
C:\MultiRegime\data\NG.csv
C:\MultiRegime\data\GC.csv
C:\MultiRegime\data\SI.csv
C:\MultiRegime\data\ZB.csv
C:\MultiRegime\data\UB.csv
```

**Note**: You only need CSV files for instruments you intend to trade. You don't need all 8.

---

## 7. Train HMM Models

Activate your virtual environment first:
```powershell
.\venv\Scripts\Activate.ps1
cd C:\MultiRegime\engine
```

### Train a single instrument:
```powershell
python train.py --symbol NQ --data-dir ..\data --model-dir ..\models
```

### Train all instruments at once:
```powershell
python train.py --all --data-dir ..\data --model-dir ..\models
```

### Train with custom settings:
```powershell
python train.py --symbol NQ --k 3 --n-restarts 10 --data-dir ..\data --model-dir ..\models
```

### Expected output:
```
2026-02-21 10:00:00 [INFO] ============================================================
2026-02-21 10:00:00 [INFO] Training model for NQ (k=3, restarts=5)
2026-02-21 10:00:00 [INFO] ============================================================
2026-02-21 10:00:00 [INFO] Loaded 5000 bars for NQ
2026-02-21 10:00:00 [INFO] Training on 4900 bars (after warmup)
2026-02-21 10:00:01 [INFO]   Restart 1/5: log-likelihood=-12345.67 (new best)
...
2026-02-21 10:00:05 [INFO] Saved model for NQ to ..\models\NQ_model.json
2026-02-21 10:00:05 [INFO] Training complete for NQ in 5.2s

=== Training Results ===
  NQ: OK
```

### Verify model files exist:
```powershell
dir C:\MultiRegime\models\*.json
```

You should see files like `NQ_model.json`, `ES_model.json`, etc.

---

## 8. Run Tests

```powershell
cd C:\MultiRegime\engine
python -m pytest ..\tests\ -v
```

### Expected output:
```
============================= test session starts ==============================
collected 66 items

../tests/test_drift.py::TestDriftMonitor::test_not_ready_initially PASSED
../tests/test_drift.py::TestDriftMonitor::test_ready_after_updates PASSED
...
../tests/test_soak.py::TestSoakInference::test_1000_server_messages PASSED
../tests/test_tcp.py::TestInferenceServer::test_infer_valid PASSED
...

============================== 66 passed in ~1s ================================
```

**All 66 tests must pass before proceeding.** If any fail, check:
- Python dependencies installed correctly
- You're running from the `engine/` directory
- Virtual environment is activated

---

## 9. Start the Python Engine

### Manual start (for testing):
```powershell
cd C:\MultiRegime\engine
python main.py --serve
```

### With custom port:
```powershell
python main.py --serve --port 5555 --model-dir ..\models
```

### Expected output:
```
2026-02-21 10:05:00 [INFO] Loading models from ..\models
2026-02-21 10:05:00 [INFO] Loaded 8 models
2026-02-21 10:05:00 [INFO] Model watcher started (poll interval: 5.0s)
2026-02-21 10:05:00 [INFO] TCP server listening on 127.0.0.1:5555
```

### Verify the engine is running:

Open a second PowerShell window and test with a sample request:
```powershell
cd C:\MultiRegime\engine
python -c "
import socket, struct, json
s = socket.socket()
s.connect(('127.0.0.1', 5555))
msg = json.dumps({'type': 'heartbeat'}).encode()
s.send(struct.pack('>I', len(msg)) + msg)
header = s.recv(4)
length = struct.unpack('>I', header)[0]
resp = json.loads(s.recv(length))
print(json.dumps(resp, indent=2))
s.close()
"
```

Expected response:
```json
{
  "type": "heartbeat_ack",
  "uptime_s": 5.1,
  "models_loaded": ["NQ", "ES", ...],
  "request_count": 0
}
```

**Leave the engine running** for the next step.

---

## 10. Install NinjaTrader 8 Strategy

1. **Copy the strategy file:**
   ```
   From: C:\MultiRegime\nt8\MultiRegimeStrategy.cs
   To:   C:\Users\<YOU>\Documents\NinjaTrader 8\bin\Custom\Strategies\MultiRegimeStrategy.cs
   ```

2. **Open NinjaTrader 8**

3. **Compile the strategy:**
   - Go to **New** → **NinjaScript Editor**
   - Press **F5** (or click the compile button)
   - Verify: "0 errors" in the output panel
   - If errors appear, ensure you're running NinjaTrader 8.1+ and the file is in the correct directory

---

## 11. Configure Strategy on Chart

### Step 1: Open a chart
- Open a chart for one of the supported instruments (NQ, ES, CL, NG, GC, SI, ZB, or UB)
- Set bar type to match your training data (e.g., 5-minute bars)

### Step 2: Apply the strategy
- Right-click chart → **Strategies** → **MultiRegimeStrategy** → **Add**

### Step 3: Configure properties

**Tab: 1. Auto Profile**
| Setting | Value | Notes |
|---------|-------|-------|
| Use Auto Profile | `True` | Auto-detects instrument from chart |
| Profile Symbol Override | *(leave blank)* | Only use if auto-detect fails |
| Model Config Folder | `C:\MultiRegime\models` | Where your trained models live |

**Tab: 2. External Engine**
| Setting | Value | Notes |
|---------|-------|-------|
| Enable External Engine | `True` | Connect to Python engine |
| Host | `127.0.0.1` | Localhost |
| Port | `5555` | Must match engine port |
| Timeout (ms) | `2000` | Falls back to internal HMM if exceeded |

**Tab: 3. Regime**
| Setting | Value | Notes |
|---------|-------|-------|
| Confidence Threshold | `0.55` | Minimum probability to act on regime |
| Dwell Bars | `3` | Bars required to confirm regime change |
| Max Flips | `6` | Maximum regime changes per session |

**Tab: 4. Order Flow**
| Setting | Value | Notes |
|---------|-------|-------|
| Enable Order Flow Filter | `True` | Enables trade confirmation via order flow |
| OF Lookback Bars | `10` | Bars for delta z-score calculation |
| Delta Confirmation Threshold | `1.5` | Z-score threshold for delta |
| Imbalance Threshold | `0.15` | Volume imbalance ratio threshold |
| Large Order Multiplier | `3.0` | Multiplier of avg trade size |

**Tab: 5. Risk**
| Setting | Value | Notes |
|---------|-------|-------|
| Daily Max Loss | `2000` | Locks trading after this loss |
| Daily Profit Lock | `5000` | Locks trading after this profit |
| Max Trades Per Day | `10` | Max trades before halting |
| Consecutive Loss Lock Count | `3` | Lock after 3 consecutive losses |
| Flatten Minutes Before Close | `5` | Flatten positions before session end |
| Enable Longs | `True` | Allow long entries |
| Enable Shorts | `True` | Allow short entries |

**Tab: 6. System**
| Setting | Value | Notes |
|---------|-------|-------|
| Debug Enabled | `True` | Enable for initial testing, disable later |
| Emergency Kill Switch | `False` | Set `True` to halt all trading |

### Step 4: Select account
- **IMPORTANT**: Start on a **Sim (Simulation) account** first!
- Select your simulation account from the Account dropdown

### Step 5: Enable the strategy
- Click **OK** to apply
- The strategy will initialize and display telemetry in the top-right corner:
  ```
  R:trending C:0.72 | Risk:Idle PnL:0 T:0 | Ext:ON OF:Neutral
  ```

### Step 6: Repeat for each instrument
- Open a separate chart for each instrument you want to trade
- Apply the strategy to each chart — it auto-detects the instrument

---

## 12. Deploy as Windows Service

For production use, run the engine as an auto-start Windows service.

### Prerequisites
1. Download NSSM from https://nssm.cc/download
2. Extract to `C:\Program Files\nssm\`

### Install the service
```powershell
# Run PowerShell as Administrator
cd C:\MultiRegime\services
.\install_engine_service.ps1
```

### Manage the service
```powershell
# Start
net start MultiRegimeEngine

# Stop
net stop MultiRegimeEngine

# Check status
sc query MultiRegimeEngine

# View logs
Get-Content C:\MultiRegime\logs\engine_stdout.log -Tail 50
```

### Uninstall (if needed)
```powershell
.\uninstall_engine_service.ps1
```

The service will:
- Auto-start at Windows boot
- Auto-restart on failure (5-second delay)
- Rotate log files at 10MB

---

## 13. Deploy with Docker (Alternative)

If you prefer Docker instead of a Windows service:

```powershell
cd C:\MultiRegime\docker

# Copy and edit environment file
copy .env.example .env

# Build the image
docker-compose build

# Start the engine
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

**Note**: The Docker engine listens on `127.0.0.1:5555` by default. NinjaTrader connects to this same address, so both can run on the same Windows machine.

---

## 14. Launch the Dashboard

```powershell
cd C:\MultiRegime

# Set environment variables (point to your status file and models)
$env:ENGINE_STATUS_FILE = "C:\MultiRegime\engine\engine_status.json"
$env:MODEL_DIR = "C:\MultiRegime\models"

# Launch
streamlit run dashboard\app.py
```

The dashboard opens at `http://localhost:8501` and shows:
- Regime overview per instrument
- Transition matrices
- Model metadata (training date, bars, convergence)
- Request statistics
- Engine health (uptime, latency, error count)

---

## 15. Verification Checklist

Run through this checklist **in order** before going live:

| # | Check | How to Verify | Status |
|---|-------|---------------|--------|
| 1 | Python packages installed | `pip list \| findstr hmmlearn` shows version | [ ] |
| 2 | Models trained for all target instruments | `dir C:\MultiRegime\models\*.json` shows files | [ ] |
| 3 | All 66 tests pass | `python -m pytest ..\tests\ -v` → 66 passed | [ ] |
| 4 | Engine starts and listens | Engine log shows "TCP server listening on 127.0.0.1:5555" | [ ] |
| 5 | Heartbeat responds | Python test script above returns heartbeat_ack | [ ] |
| 6 | NT8 strategy compiles | NinjaScript Editor → F5 → 0 errors | [ ] |
| 7 | Strategy loads on sim account | Telemetry label appears on chart top-right | [ ] |
| 8 | External engine connected | Telemetry shows `Ext:ON` | [ ] |
| 9 | Regime labels change | Watch for regime transitions during market hours | [ ] |
| 10 | Order flow active | Telemetry shows `OF:Confirm` / `OF:Neutral` / `OF:Deny` | [ ] |
| 11 | Risk engine blocks at limits | Set DailyMaxLoss very low, verify `Risk:Locked` | [ ] |
| 12 | Emergency kill switch works | Enable KillSwitch → all positions flatten | [ ] |
| 13 | Engine disconnect → fallback | Stop engine → strategy continues with internal HMM | [ ] |
| 14 | Model hot-reload works | Retrain a model → engine logs "Hot-reloaded model" | [ ] |
| 15 | Run 1-hour soak on replay | Replay historical data, confirm stability | [ ] |
| 16 | Dashboard shows live data | Open http://localhost:8501, verify metrics update | [ ] |
| 17 | Windows service auto-starts | Restart PC, verify engine starts automatically | [ ] |

**Only after all checks pass**, switch from sim to live with minimal position size.

---

## 16. Troubleshooting

### Engine won't start
```
Error: Address already in use
```
Another process is using port 5555. Either stop it or change the port in `config.yaml`.

### NT8 can't connect to engine
- Verify engine is running: `netstat -an | findstr 5555`
- Check firewall isn't blocking localhost connections
- Ensure Host/Port in strategy properties match engine settings

### Strategy shows "SAFE MODE"
- Model file not found — check `ModelConfigFolder` path
- Ensure model files are named `{SYMBOL}_model.json` (e.g., `NQ_model.json`)

### Training fails with "Insufficient data"
- You need at least 500 bars per instrument
- Check CSV format: columns must be `timestamp,open,high,low,close,volume` (lowercase)

### Order flow always shows "Neutral"
- Order flow needs `OrderFlowLookbackBars` (default 10) bars of tick data before it can confirm
- Only works with real-time or replay data (not historical backtest without tick data)
- Ensure `EnableOrderFlowFilter` is `True` in strategy properties

### Models seem stale
- The engine watches for file changes every 5 seconds
- Retrain: `python train.py --symbol NQ` → engine auto-reloads
- Check drift detection in dashboard for alerts

### Emergency: Flatten all positions immediately
1. In NT8: Set `Emergency Kill Switch = True` on each strategy
2. Or: Stop the engine service → strategy enters safe mode
3. Manually flatten in NT8: **Ctrl+F** → Flatten Everything

---

*Generated for Multi-Regime Trading Stack v1.1 (with UB + Order Flow)*
