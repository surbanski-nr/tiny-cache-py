import re
import sys
from pathlib import Path


_CACHE_PB2_IMPORT_RE = re.compile(
    r"^import cache_pb2(\s+as\s+(?P<alias>\w+))?$",
    re.MULTILINE,
)


def _fix_grpc_imports(path: Path) -> None:
    content = path.read_text(encoding="utf-8")

    def _replace(match: re.Match[str]) -> str:
        alias = match.group("alias")
        if alias:
            return f"from . import cache_pb2 as {alias}"
        return "from . import cache_pb2"

    updated = _CACHE_PB2_IMPORT_RE.sub(_replace, content)
    if updated != content:
        path.write_text(updated, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: fix_protoc_imports.py <file> [<file>...]", file=sys.stderr)
        return 2

    for filename in argv[1:]:
        _fix_grpc_imports(Path(filename))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
