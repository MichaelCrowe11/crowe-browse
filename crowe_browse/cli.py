"""CLI for crowe-browse: headless browser interaction."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from crowe_browse.config import BrowseSettings
from crowe_browse.search import parse_results
from crowe_browse.session import BrowseSession


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2))


async def _cmd_navigate(args) -> None:
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        text = await session.engine.navigate(args.url)
        _print_json({"url": args.url, "text": text[:2000]})


async def _cmd_get_text(args) -> None:
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        text = await session.engine.get_page_text()
        _print_json({"text": text[:2000]})


async def _cmd_get_interactive(args) -> None:
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        elements = await session.engine.get_interactive_elements()
        _print_json([{"ref": e.ref, "role": e.role, "name": e.name, "tag": e.tag} for e in elements])


async def _cmd_screenshot(args) -> None:
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        path = args.path or "screenshot.png"
        await session.engine.screenshot(path)
        print(f"Screenshot saved to {path}")


async def _cmd_click(args) -> None:
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        await session.engine.click(args.ref)
        text = await session.engine.get_page_text()
        _print_json({"clicked": args.ref, "text": text[:2000]})


async def _cmd_fill(args) -> None:
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        await session.engine.fill(args.ref, args.text)
        print(f"Filled element {args.ref} with: {args.text}")


async def _cmd_search(args) -> None:
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        from crowe_browse.search import SEARCH_URL

        url = SEARCH_URL.format(q=args.query)
        await session.engine.navigate(url)
        html = await session.engine.get_page_text()
        results = parse_results(html)
        _print_json(results[: args.limit])


async def _cmd_repl(args) -> None:  # noqa: ARG001
    """Interactive browse REPL."""
    settings = BrowseSettings()
    async with BrowseSession(settings) as session:
        print("crowe-browse REPL. Commands: navigate <url>, text, interactive, screenshot [path], click <ref>, fill <ref> <text>, search <query>, quit")
        while True:
            try:
                line = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            try:
                if cmd == "quit" or cmd == "exit":
                    break
                elif cmd == "navigate" and arg:
                    text = await session.engine.navigate(arg)
                    print(text[:2000])
                elif cmd == "text":
                    text = await session.engine.get_page_text()
                    print(text[:2000])
                elif cmd == "interactive":
                    elements = await session.engine.get_interactive_elements()
                    for e in elements:
                        print(f"  [{e.ref}] {e.role}: {e.name}")
                elif cmd == "screenshot":
                    path = arg or "screenshot.png"
                    await session.engine.screenshot(path)
                    print(f"Saved to {path}")
                elif cmd == "click" and arg:
                    await session.engine.click(int(arg))
                    text = await session.engine.get_page_text()
                    print(text[:2000])
                elif cmd == "fill":
                    fill_parts = arg.split(maxsplit=1)
                    if len(fill_parts) == 2:
                        await session.engine.fill(int(fill_parts[0]), fill_parts[1])
                        print(f"Filled element {fill_parts[0]}")
                    else:
                        print("Usage: fill <ref> <text>")
                elif cmd == "search" and arg:
                    from crowe_browse.search import SEARCH_URL

                    url = SEARCH_URL.format(q=arg)
                    await session.engine.navigate(url)
                    html = await session.engine.get_page_text()
                    results = parse_results(html)
                    for r in results[:10]:
                        print(f"  {r['title']}")
                        print(f"    {r['url']}")
                else:
                    print(f"Unknown command: {cmd}")
            except Exception as exc:
                print(f"Error: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="crowe-browse", description="Headless browser CLI")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("navigate", help="Navigate to a URL and get page text")
    p.add_argument("url", help="URL to navigate to")

    sub.add_parser("get-text", help="Get readable text of the current page")

    sub.add_parser("get-interactive", help="List interactive elements on the page")

    p = sub.add_parser("screenshot", help="Take a screenshot")
    p.add_argument("path", nargs="?", default="screenshot.png", help="Output file path")

    p = sub.add_parser("click", help="Click an element by ref number")
    p.add_argument("ref", type=int, help="Element ref from get-interactive")

    p = sub.add_parser("fill", help="Fill a text input")
    p.add_argument("ref", type=int, help="Element ref from get-interactive")
    p.add_argument("text", help="Text to fill")

    p = sub.add_parser("search", help="Search the web")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=10, help="Max results")

    sub.add_parser("repl", help="Start interactive browse REPL")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "navigate": _cmd_navigate,
        "get-text": _cmd_get_text,
        "get-interactive": _cmd_get_interactive,
        "screenshot": _cmd_screenshot,
        "click": _cmd_click,
        "fill": _cmd_fill,
        "search": _cmd_search,
        "repl": _cmd_repl,
    }

    asyncio.run(cmds[args.command](args))


if __name__ == "__main__":
    main()
