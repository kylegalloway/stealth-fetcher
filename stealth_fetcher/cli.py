from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from stealth_fetcher.engines import ENGINES


def _cmd_fetch(args: argparse.Namespace) -> None:
    session_cls = ENGINES[args.engine]
    with session_cls(headless=not args.headed) as session:
        html = session.goto(args.url, wait_selector=args.wait_for)

    if args.output:
        Path(args.output).write_text(html)
        print(f"wrote {args.output} ({len(html)} bytes)")
    else:
        sys.stdout.write(html)


def _load_script(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path} as a Python module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cmd_run(args: argparse.Namespace) -> None:
    """Runs a `run(session, argv)` function from a script owned by whatever
    project needs this fetch — that's where the site-specific knowledge
    (which URLs, which selectors, how to parse and save the result) belongs.
    stealth-fetcher only supplies the browser session that can pass the
    challenge."""
    script_path = Path(args.script).resolve()
    module = _load_script(script_path)
    if not hasattr(module, "run"):
        raise RuntimeError(f"{script_path} must define a `run(session, argv)` function")

    session_cls = ENGINES[args.engine]
    with session_cls(headless=not args.headed) as session:
        module.run(session, args.script_args)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stealth-fetcher",
        description="Fetch Cloudflare-protected pages with a real (or real-ish) browser.",
    )
    parser.add_argument(
        "--engine",
        choices=sorted(ENGINES),
        default="camoufox",
        help="browser engine to use (default: camoufox)",
    )
    parser.add_argument("--headed", action="store_true", help="show the browser window instead of running headless")

    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="fetch one URL, print (or save) the rendered HTML")
    p_fetch.add_argument("url")
    p_fetch.add_argument("-o", "--output", help="file to write HTML to (default: stdout)")
    p_fetch.add_argument("--wait-for", help="CSS selector to wait for instead of network-idle")
    p_fetch.set_defaults(func=_cmd_fetch)

    p_run = sub.add_parser(
        "run",
        help="run a project-owned fetch script — see README for the `run(session, argv)` contract",
    )
    p_run.add_argument("script", help="path to a Python file defining run(session, argv)")
    p_run.add_argument("script_args", nargs=argparse.REMAINDER, help="extra args passed through to the script")
    p_run.set_defaults(func=_cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
