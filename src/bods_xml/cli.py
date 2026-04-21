"""Command-line interface for bods-xml.

Usage:
    bods-xml input.json                        # canonical XML to stdout
    bods-xml input.json -o output.xml          # canonical XML to file
    bods-xml input.json -p mras -o output.xml  # MRAS preBODS profile
    bods-xml input.jsonl -p mras               # JSONL input, MRAS output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bods_xml import canonical
from bods_xml.profiles import mras


PROFILES = {
    "canonical": None,
    "mras": mras,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="bods-xml",
        description="Convert BODS 0.4 JSON/JSONL to XML.",
    )
    parser.add_argument(
        "input",
        help="Path to BODS 0.4 JSON or JSONL file",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)",
        default=None,
    )
    parser.add_argument(
        "-p", "--profile",
        choices=list(PROFILES.keys()),
        default="canonical",
        help="Output profile (default: canonical)",
    )
    parser.add_argument(
        "--timestamp",
        help="Record timestamp for MRAS preBODS output (ISO format). "
             "Default: current UTC time.",
        default=None,
    )
    parser.add_argument(
        "--no-pretty-print",
        action="store_true",
        help="Disable pretty-printing of XML output",
    )

    args = parser.parse_args(argv)
    pretty = not args.no_pretty_print

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    profile = PROFILES[args.profile]

    if profile is None:
        # Canonical output
        root = canonical.convert_file(input_path)
        xml_str = canonical.to_string(root, pretty_print=pretty)
    else:
        # Profile output
        root = profile.convert_file(input_path, record_timestamp=args.timestamp)
        xml_str = profile.to_string(root, pretty_print=pretty)

    if args.output:
        Path(args.output).write_text(xml_str, encoding="utf-8")
    else:
        sys.stdout.write(xml_str)


if __name__ == "__main__":
    main()
