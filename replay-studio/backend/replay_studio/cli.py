"""replay-studio command line: api | worker | set-password | check | fake-youtube"""
from __future__ import annotations

import argparse
import getpass
import shutil
import subprocess
import sys

from .config import load_config
from .db import DB


def cmd_set_password(args) -> None:
    from .security import hash_password
    cfg = load_config()
    cfg.ensure_dirs()
    pw = args.password or getpass.getpass("New dashboard password: ")
    if not args.password and pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    if len(pw) < 10:
        sys.exit("Use at least 10 characters.")
    DB(cfg.db_path).set_setting("password_hash", hash_password(pw))
    print("Dashboard password saved. Existing dashboard logins are signed out.")


def cmd_check(args) -> None:
    cfg = load_config()
    ok = True
    print(f"Config file : {cfg.source or '(none found, using defaults)'}")
    print(f"Data dir    : {cfg.data_dir}")
    print(f"Media folder: {cfg.media_dir} ({'exists' if cfg.media_dir.is_dir() else 'MISSING'})")
    for tool in (cfg.encoder.ffmpeg, cfg.encoder.ffprobe):
        path = shutil.which(tool)
        if not path:
            print(f"{tool:12}: NOT FOUND - install ffmpeg (sudo apt install ffmpeg)")
            ok = False
            continue
        ver = subprocess.run([path, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
        print(f"{tool:12}: {ver}")
    protos = subprocess.run([cfg.encoder.ffmpeg, "-hide_banner", "-protocols"], capture_output=True, text=True).stdout
    has_rtmps = "rtmps" in protos.split()
    print(f"RTMPS       : {'supported' if has_rtmps else 'NOT SUPPORTED by this ffmpeg build'}")
    ok &= has_rtmps
    print(f"Google OAuth: {'configured' if cfg.google.client_id and cfg.google.client_secret else 'NOT configured'}")
    db = DB(cfg.db_path)
    print(f"Password    : {'set' if db.get_setting('password_hash') else 'NOT set (run: replay-studio set-password)'}")
    sys.exit(0 if ok else 1)


def main() -> None:
    ap = argparse.ArgumentParser(prog="replay-studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("api", help="run the dashboard/API server")
    sub.add_parser("worker", help="run the background stream worker")
    sp = sub.add_parser("set-password", help="set the dashboard password")
    sp.add_argument("--password", help="non-interactive (avoid: ends up in shell history)")
    sub.add_parser("check", help="verify ffmpeg, config and password")
    sub.add_parser("fake-youtube", help="run the local fake YouTube API (testing/demo)", add_help=False)
    args, rest = ap.parse_known_args()
    if args.cmd == "api":
        from .api import main as m
        m()
    elif args.cmd == "worker":
        from .worker import main as m
        m()
    elif args.cmd == "set-password":
        cmd_set_password(args)
    elif args.cmd == "check":
        cmd_check(args)
    elif args.cmd == "fake-youtube":
        from .fake_youtube import main as m
        sys.argv = ["fake-youtube", *rest]
        m()


if __name__ == "__main__":
    main()
