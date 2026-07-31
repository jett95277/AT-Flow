from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from at_flow.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
