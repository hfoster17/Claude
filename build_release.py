#!/usr/bin/env python3
"""
build_release.py — Package the Multi-Regime Trading Stack into a release ZIP.

Creates: MultiRegime-vX.Y.Z.zip containing all source, configs, installer,
         docs, tests, and NT8 files — ready to extract and run install.bat.

Usage:
    python build_release.py                     # builds MultiRegime-v1.0.0.zip
    python build_release.py --version 2.1.0     # custom version
    python build_release.py --output-dir dist   # custom output directory
"""

import argparse
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_VERSION = "1.0.0"

# All files/directories to include (relative to project root)
INCLUDE = [
    # Engine (Python)
    "engine/main.py",
    "engine/server.py",
    "engine/hmm_inference.py",
    "engine/feature_engine.py",
    "engine/data_pull.py",
    "engine/model_manager.py",
    "engine/drift.py",
    "engine/train.py",
    "engine/scheduler.py",
    "engine/monte_carlo.py",
    "engine/walk_forward.py",
    "engine/config.yaml",
    "engine/requirements.txt",

    # Dashboard
    "dashboard/app.py",
    "dashboard/requirements.txt",

    # NinjaTrader 8
    "nt8/MultiRegimeStrategy.cs",
    "nt8/MultiRegimeWorkspace.xml",
    "nt8/MultiRegimeChartTheme.xml",

    # Contracts / schemas
    "contracts/feature_contract.md",
    "contracts/model_schema.json",
    "contracts/tcp_protocol.md",

    # Services (Windows)
    "services/start_engine.bat",
    "services/start_engine.ps1",
    "services/install_engine_service.ps1",
    "services/uninstall_engine_service.ps1",
    "services/README.md",

    # Docker
    "docker/Dockerfile",
    "docker/docker-compose.yml",
    "docker/Makefile",
    "docker/.env.example",

    # Tests
    "tests/conftest.py",
    "tests/test_drift.py",
    "tests/test_features.py",
    "tests/test_hmm.py",
    "tests/test_monte_carlo.py",
    "tests/test_schema.py",
    "tests/test_soak.py",
    "tests/test_tcp.py",
    "tests/test_walk_forward.py",

    # Sample requests
    "sample_requests/heartbeat.json",
    "sample_requests/multi_request.json",
    "sample_requests/nq_request.json",

    # Root docs and config
    "README.md",
    "DEPLOYMENT_GUIDE.md",
    ".gitignore",

    # Installer
    "install.bat",

    # Placeholders (keep directory structure)
    "data/.gitkeep",
    "models/.gitkeep",
]


def build_zip(project_root: Path, version: str, output_dir: Path) -> Path:
    """Build the release ZIP file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f"MultiRegime-v{version}.zip"
    zip_path = output_dir / zip_name
    archive_prefix = f"MultiRegime-v{version}"

    missing = []
    included = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel_path in INCLUDE:
            src = project_root / rel_path
            if not src.exists():
                missing.append(rel_path)
                continue

            arcname = f"{archive_prefix}/{rel_path}"
            zf.write(src, arcname)
            included.append(rel_path)

        # Write a VERSION file inside the ZIP
        version_content = (
            f"Multi-Regime Trading Stack v{version}\n"
            f"Built: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Files: {len(included)}\n"
        )
        zf.writestr(f"{archive_prefix}/VERSION", version_content)

    return zip_path, included, missing


def main():
    parser = argparse.ArgumentParser(description="Build Multi-Regime release ZIP")
    parser.add_argument("--version", type=str, default=DEFAULT_VERSION,
                        help=f"Version string (default: {DEFAULT_VERSION})")
    parser.add_argument("--output-dir", type=str, default="dist",
                        help="Output directory for ZIP (default: dist)")
    parser.add_argument("--project-root", type=str, default=None,
                        help="Project root (default: directory containing this script)")
    args = parser.parse_args()

    project_root = Path(args.project_root) if args.project_root else Path(__file__).parent
    output_dir = Path(args.output_dir)

    if not project_root.is_dir():
        print(f"ERROR: Project root not found: {project_root}")
        sys.exit(1)

    print(f"Building Multi-Regime v{args.version}")
    print(f"  Source: {project_root}")
    print(f"  Output: {output_dir}")
    print()

    zip_path, included, missing = build_zip(project_root, args.version, output_dir)

    print(f"Included {len(included)} files:")
    for f in included:
        print(f"  + {f}")

    if missing:
        print(f"\nWARNING: {len(missing)} files not found (skipped):")
        for f in missing:
            print(f"  - {f}")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\nZIP created: {zip_path}  ({size_mb:.2f} MB)")
    print(f"\nTo install on Windows:")
    print(f"  1. Extract {zip_path.name}")
    print(f"  2. Right-click install.bat > Run as administrator")


if __name__ == "__main__":
    main()
