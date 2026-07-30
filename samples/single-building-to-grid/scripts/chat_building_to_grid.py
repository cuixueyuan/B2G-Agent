from __future__ import annotations

from pathlib import Path
import argparse
import sys


def _find_repo_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "pyproject.toml").exists():
            return path
    return start


SAMPLE_ROOT = Path(__file__).resolve().parents[1]
ROOT = _find_repo_root(Path(__file__).resolve())
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from x2g_agent.chat import ChatAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat with X2G-Agent about the Building-to-Grid case.")
    parser.add_argument("--config", default="configs/building_to_grid.yaml", help="Base YAML config.")
    parser.add_argument("--session-root", default="outputs/chat_sessions", help="Directory for chat session outputs.")
    parser.add_argument("--backend", choices=["rule", "openai"], default="rule", help="Intent parser backend.")
    parser.add_argument("--debug", action="store_true", help="Print raw LLM responses and validation errors.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = config_path if config_path.exists() else SAMPLE_ROOT / config_path
    session_root = Path(args.session_root)
    if not session_root.is_absolute():
        session_root = session_root if session_root.exists() else SAMPLE_ROOT / session_root

    agent = ChatAgent(config_path, session_root=session_root, backend=args.backend, debug=args.debug)
    print(f"X2G-Agent Building-to-Grid chat ({args.backend} backend). Try: run mock Building-to-Grid")
    while True:
        try:
            user_text = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0
        response, should_exit = agent.handle(user_text)
        print(response)
        if should_exit:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
