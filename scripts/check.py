"""Offline desk verification. Never start the real GUI or hardware providers."""
from pathlib import Path
import ast
import hashlib
from html.parser import HTMLParser
import importlib.abc
import json
import os
import re
import sys
import unittest
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "source code/Raspberry Pi/GUI/refactored"
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs
                         if key in {"href", "src", "poster"} and value)


def check_assets():
    assets = json.loads((ROOT / "documentation/reference/Software-assets.json").read_text())
    for name, expected in assets.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"Source differs from the handover snapshot: {name}")
    for path in (ROOT / "source code").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    print(f"Verified {len(assets)} source/model/action assets; Python syntax passed.")


def check_links():
    checked, failures = 0, []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(p in {".git", "release-assets", "__pycache__"}
                                     for p in path.relative_to(ROOT).parts):
            continue
        urls = []
        if path.suffix.lower() in {".html", ".htm"}:
            parser = Links()
            parser.feed(path.read_text(encoding="utf-8-sig"))
            urls = parser.urls
        elif path.suffix.lower() == ".md":
            content = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8-sig"), flags=re.S)
            urls = re.findall(r"!?\[[^\]]*\]\(([^\n)]+)\)", content)
        elif path.suffix.lower() == ".docx":
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if name.endswith(".rels"):
                        for rel in ET.fromstring(z.read(name)):
                            if rel.get("TargetMode") == "External":
                                urls.append(rel.get("Target", ""))
        for url in urls:
            url = url.strip().strip("<>")
            if not url or "${" in url:
                continue
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            checked += 1
            if not target.is_relative_to(ROOT) or not target.exists():
                failures.append(f"{path.relative_to(ROOT)} -> {url}")
    if failures:
        raise AssertionError("Broken or outside-package local links:\n" + "\n".join(failures))
    print(f"Verified {checked} static local links (including Word hyperlinks).")
    return checked


def run_mock_tests():
    # Fail before a hardware provider can even be imported. Tk widgets are faked
    # by the UI tests; importing Tcl/Tk is allowed, constructing a real root isn't.
    blocked = {"serial", "cv2", "ultralytics", "RPi", "gpiozero", "smbus",
               "smbus2", "spidev", "gpiod", "ServoControl", "GTW_GUIv2"}

    class NoHardware(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".", 1)[0] in blocked:
                raise AssertionError(f"Hardware import blocked in desk checks: {fullname}")

    sys.meta_path.insert(0, NoHardware())
    import tkinter

    def deny_tk(*args, **kwargs):
        raise AssertionError("A real Tk window is forbidden in headless desk checks")

    tkinter.Tk = deny_tk
    os.chdir(GUI)
    sys.path.insert(0, str(GUI))
    suite = unittest.defaultTestLoader.discover(str(GUI / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    return result.testsRun


if __name__ == "__main__":
    check_assets()
    links = check_links()
    tests = run_mock_tests()
    print(f"PASS: {tests} mock tests; {links} static links. No hardware operated.")
