"""HTTP met geheugen. Alleen de standaardbibliotheek, zodat de CI-runner niets
hoeft te installeren om te kunnen kijken.

Twee dingen die deze laag anders doet dan een kale download:

1. Hij kijkt eerst (`probe`) en haalt pas daarna op. Een bron die van formaat of
   locatie verandert hoort een leesbare regel op te leveren, geen stacktrace op
   regel 40 van een parser.
2. Elke download krijgt een sha256 en een cachebestand. Twee keer draaien haalt
   niets opnieuw op, en de hash gaat mee de database in als herkomst.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

UA = "terra-commons/0.1 (open onderzoek naar grondherstel; contact via de repo)"
CACHE = Path(os.environ.get("TERRA_CACHE", ".cache"))
TIMEOUT = int(os.environ.get("TERRA_HTTP_TIMEOUT", "60"))


@dataclass
class Probe:
    url: str
    ok: bool
    status: int | None = None
    content_type: str | None = None
    bytes: int | None = None
    error: str | None = None
    seconds: float | None = None

    def line(self) -> str:
        if not self.ok:
            return f"  FOUT   {self.url}\n         {self.error}"
        mb = f"{self.bytes/1e6:.1f} MB" if self.bytes else "onbekende grootte"
        return (f"  OK     {self.url}\n"
                f"         {self.status} · {self.content_type} · {mb} · {self.seconds:.1f}s")


def _request(url: str, method: str = "GET"):
    return urllib.request.Request(url, method=method,
                                  headers={"User-Agent": UA, "Accept-Encoding": "gzip"})


def probe(url: str) -> Probe:
    """Kijken zonder op te halen. HEAD, en bij weigering een GET van een paar bytes."""
    t0 = time.time()
    for method in ("HEAD", "GET"):
        try:
            with urllib.request.urlopen(_request(url, method), timeout=TIMEOUT) as r:
                length = r.headers.get("Content-Length")
                return Probe(url, True, r.status, r.headers.get("Content-Type"),
                             int(length) if length else None, None, time.time() - t0)
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue                       # sommige servers weigeren HEAD
            return Probe(url, False, e.code, None, None, f"HTTP {e.code} {e.reason}",
                         time.time() - t0)
        except Exception as e:                 # DNS, TLS, timeout
            return Probe(url, False, None, None, None, f"{type(e).__name__}: {e}",
                         time.time() - t0)
    return Probe(url, False, None, None, None, "onbereikbaar", time.time() - t0)


def download(url: str, name: str | None = None, cache: Path | None = None) -> tuple[Path, str]:
    """Haalt op naar de cache en geeft (pad, sha256) terug.

    De hash is geen decoratie: hij hoort bij de observatie in de database, zodat
    'welke versie van dit bestand zei dit' een vraag met een antwoord is.
    """
    cache = cache or CACHE
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / (name or hashlib.sha1(url.encode()).hexdigest())
    if dest.exists():
        return dest, sha256(dest)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    tmp.write_bytes(raw)
    tmp.rename(dest)
    return dest, sha256(dest)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def report(probes: list[Probe]) -> str:
    ok = sum(1 for p in probes if p.ok)
    out = [f"{ok} van {len(probes)} bronnen bereikbaar", ""]
    out += [p.line() for p in probes]
    return "\n".join(out)


def as_json(probes: list[Probe]) -> str:
    return json.dumps([asdict(p) for p in probes], indent=1)
