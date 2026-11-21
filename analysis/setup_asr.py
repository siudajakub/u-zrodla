"""Install checksum-pinned, local Vosk CPU runtime and Polish model on Linux."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

from .transcribe import ASR, MODEL, digest


def install(dest):
    lock = json.loads(Path(__file__).with_name("asr-lock.json").read_text())
    arch = platform.machine()
    if platform.system() != "Linux" or arch not in ("aarch64", "x86_64"):
        raise ValueError("Obsługiwane platformy: Linux x86_64 / aarch64.")
    dest.mkdir(parents=True, exist_ok=True)
    for key in [arch, "pl"]:
        entry = lock[key]
        package = dest / entry["url"].split("/")[-1]
        if not package.exists() or digest(package) != entry["sha256"]:
            with tempfile.NamedTemporaryFile(dir=dest, delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                with urlopen(entry["url"], timeout=60) as source, tmp_path.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if digest(tmp_path) != entry["sha256"]:
                    raise ValueError("Niezgodna suma SHA-256 pobranego pakietu.")
                tmp_path.replace(package)
            finally:
                tmp_path.unlink(missing_ok=True)
        with ZipFile(package) as archive:
            if key == "pl":
                archive.extractall(dest)
            else:
                archive.extract("vosk/libvosk.so", dest)
    print(dest / MODEL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ASR)
    install(parser.parse_args().directory)
