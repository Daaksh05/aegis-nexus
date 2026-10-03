import json
import sys
from pathlib import Path

api_dir = Path(__file__).resolve().parents[1]
repo_dir = api_dir.parents[1]
sys.path.insert(0, str(api_dir))

from app.main import app  # noqa: E402


def main() -> None:
    output_path = repo_dir / "packages" / "contracts" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()