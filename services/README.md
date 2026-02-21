# Windows Service Setup

## Option 1: NSSM (Recommended)

### Prerequisites
1. Download NSSM from https://nssm.cc
2. Extract to `C:\Program Files\nssm\`
3. Ensure `nssm.exe` is in PATH or update script paths

### Install
```powershell
# Run as Administrator
.\install_engine_service.ps1
```

### Manage
```powershell
net start MultiRegimeEngine
net stop MultiRegimeEngine
```

### Uninstall
```powershell
.\uninstall_engine_service.ps1
```

## Option 2: Task Scheduler

### Setup
1. Open Task Scheduler (`taskschd.msc`)
2. Create New Task:
   - **General**: Run whether user is logged on or not
   - **Trigger**: At startup (or at logon)
   - **Action**: Start a program
     - Program: `powershell.exe`
     - Arguments: `-ExecutionPolicy Bypass -File "C:\MultiRegime\services\start_engine.ps1"`
     - Start in: `C:\MultiRegime\engine`
   - **Settings**: Restart on failure every 1 minute, up to 10 times

### Or use the batch file
- Action Program: `C:\MultiRegime\services\start_engine.bat`

## Environment Variables (Optional)

Set these to override default paths:
- `MULTIREGIME_VENV` — Virtual environment path (default: `C:\MultiRegime\venv`)
- `MULTIREGIME_ENGINE` — Engine code path (default: `C:\MultiRegime\engine`)
- `MULTIREGIME_LOGS` — Log directory (default: `C:\MultiRegime\logs`)

## Log Files

- NSSM: `C:\MultiRegime\logs\engine_stdout.log` and `engine_stderr.log`
- Engine: `C:\MultiRegime\logs\engine.log` (rotating, 10MB max, 5 backups)
