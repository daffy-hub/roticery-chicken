from __future__ import annotations

import argparse

import uvicorn

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="roticery")
    parser.add_argument("--config", default="config/roticery.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    uvicorn.run("roticery.cli:build_app", host=config.server.host, port=config.server.port, factory=True)


def build_app():
    # Uvicorn factory hook. Re-read config so CLI changes are reflected in the process.
    from .app import create_app_from_file
    import os
    return create_app_from_file(os.getenv("ROTI_CONFIG", "config/roticery.yaml"))
