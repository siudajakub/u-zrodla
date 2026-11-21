"""Prepare the pinned weights for offline semantic suggestions."""

import argparse
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

LOCK = json.loads(Path(__file__).with_name("semantic-lock.json").read_text(encoding="utf-8"))
DEFAULT_DIR = Path(__file__).resolve().parents[1] / ".runtime/semantic"
MODEL_DIR_ENV = "INVESTWATCH_SEMANTIC_DIR"


class HTTPSOnly(HTTPRedirectHandler):
    def redirect_request(self, request, response, status, message, headers, url):
        if urlsplit(url).scheme != "https":
            return None
        return super().redirect_request(request, response, status, message, headers, url)


def available(path, spec):
    if not path.is_file() or path.stat().st_size != spec["bytes"]:
        return False
    with path.open("rb") as file:
        return file_digest(file, "sha256").hexdigest() == spec["sha256"]


def prepare(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = f"https://huggingface.co/{LOCK['repository']}/resolve/{LOCK['revision']}"
    opener = build_opener(HTTPSOnly)
    for name, spec in LOCK["files"].items():
        destination = directory / name
        if available(destination, spec):
            print(f"{name} · zgodny SHA-256")
            continue
        temporary = None
        try:
            request = Request(f"{source}/{spec['path']}?download=true", headers={
                "User-Agent": "InvestWatch-SemanticSetup/1.0",
            })
            deadline = monotonic() + 300
            with opener.open(request, timeout=30) as response, NamedTemporaryFile(
                dir=directory, prefix=f".{name}.", delete=False,
            ) as output:
                temporary = Path(output.name)
                total = 0
                digest = sha256()
                while chunk := response.read1(1024 * 1024):
                    if monotonic() >= deadline:
                        raise TimeoutError(f"Przekroczono limit czasu pobierania {name}.")
                    total += len(chunk)
                    if total > spec["bytes"]:
                        raise ValueError(f"Przekroczony rozmiar pliku {name}.")
                    digest.update(chunk)
                    output.write(chunk)
            if total != spec["bytes"] or digest.hexdigest() != spec["sha256"]:
                raise ValueError(f"Plik {name} różni się od przypiętej wersji.")
            os.replace(temporary, destination)
            print(f"{name} · pobrano {total:,} B i zweryfikowano SHA-256")
        except URLError as error:
            raise RuntimeError(f"Pobranie {name} nie powiodło się ({type(error).__name__}).") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(os.getenv(MODEL_DIR_ENV) or DEFAULT_DIR))
    args = parser.parse_args()
    try:
        prepare(args.directory)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
