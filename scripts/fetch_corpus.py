import argparse
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/chinese-poetry/chinese-poetry.git"
DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "corpus" / "chinese-poetry"


def run_git(args, cwd=None):
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        print(f"git {' '.join(args)} failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def clone_or_update(target: Path, shallow: bool):
    if target.exists() and (target / ".git").exists():
        print(f"Repo already exists at {target}, pulling latest changes...")
        run_git(["pull", "--ff-only"], cwd=str(target))
        return "updated"

    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["clone"]
    if shallow:
        cmd += ["--depth", "1"]
    cmd += [REPO_URL, str(target)]
    print(f"Cloning {REPO_URL} into {target}...")
    run_git(cmd)
    return "cloned"


def main():
    parser = argparse.ArgumentParser(
        description="Clone or update the chinese-poetry GitHub repo for local indexing."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"Target directory for the repo (default: {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        metavar="N",
        help="Create a shallow clone with limited history depth (e.g. --depth 1)",
    )
    args = parser.parse_args()

    target = args.output_dir.resolve()
    shallow = args.depth is not None

    action = clone_or_update(target, shallow)

    commit = run_git(["rev-parse", "--short", "HEAD"], cwd=str(target))
    file_count = run_git(["ls-files"], cwd=str(target)).count("\n") + 1

    print(f"\n{'='*50}")
    print(f"Status  : {action}")
    print(f"Path    : {target}")
    print(f"Commit  : {commit}")
    print(f"Files   : {file_count}")
    print(f"Shallow : {'yes' if shallow else 'no'}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
