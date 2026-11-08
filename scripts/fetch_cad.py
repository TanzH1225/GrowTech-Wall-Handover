"""Download the pinned CAD Release asset, verify it and optionally extract it."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import shutil
import stat
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true", help="Extract into CAD library after verification")
    parser.add_argument("--archive", type=Path, help="Verify/use an already downloaded archive")
    args = parser.parse_args()
    meta = json.loads((ROOT / "documentation/reference/CAD-download.json").read_text())
    archive = args.archive.resolve() if args.archive else ROOT / "release-assets/GrowTech-Wall-CAD-Library.zip"
    if not archive.exists():
        if args.archive:
            parser.error("The supplied archive does not exist")
        archive.parent.mkdir(parents=True, exist_ok=True)
        pending = archive.with_suffix(".download")
        print("Downloading CAD archive from the project Release...")
        request = urllib.request.Request(meta["url"], headers={"User-Agent": "GrowTech-Wall-Handover"})
        with urllib.request.urlopen(request, timeout=60) as response, pending.open("wb") as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        if pending.stat().st_size != meta["bytes"] or digest(pending) != meta["sha256"]:
            raise SystemExit("Downloaded file failed size/SHA-256 verification; no extraction performed")
        pending.replace(archive)
    if archive.stat().st_size != meta["bytes"] or digest(archive) != meta["sha256"]:
        raise SystemExit("Archive failed size/SHA-256 verification; no extraction performed")
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len([m for m in members if not m.is_dir()]) != meta["files"]:
            raise SystemExit("Archive file count differs from the published manifest")
        for member in members:
            path = PurePosixPath(member.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in member.filename
                    or ":" in member.filename or not path.parts or path.parts[0] != "CAD library"
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise SystemExit(f"Unsafe archive member: {member.filename}")
            target = ROOT.joinpath(*path.parts).resolve()
            if not target.is_relative_to(ROOT / "CAD library"):
                raise SystemExit("Archive extraction target escapes CAD library")
        if z.testzip() is not None:
            raise SystemExit("Archive failed CRC verification")
        print(f"Verified SHA-256 and CRC: {len(members)} archive entries.")
        if args.extract:
            # Ask before replacing any locally edited CAD; repeated identical
            # extraction is safe and silently skips those existing files.
            conflicts = []
            for member in members:
                target = ROOT / member.filename
                if target.is_file() and not member.is_dir():
                    with z.open(member) as stream:
                        expected = hashlib.file_digest(stream, "sha256").hexdigest()
                    if digest(target) != expected:
                        conflicts.append(member.filename)
            if conflicts:
                raise SystemExit("Existing CAD differs; move it aside before extracting:\n" + "\n".join(conflicts))
            z.extractall(ROOT)
            print(f"Extracted into {ROOT / 'CAD library'}")
        else:
            print(f"Archive ready: {archive}\nUse --extract to restore native CAD links.")


if __name__ == "__main__":
    main()
