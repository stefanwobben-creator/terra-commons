"""Sonde. Draai dit eerst, waar netwerk is.

    python -m terra.fetch.probe            # leesbaar
    python -m terra.fetch.probe --peek     # plus de eerste regels van de inhoud
    python -m terra.fetch.probe --json     # voor een workflow-artefact

Wat eruit komt is de lijst met welke bronadressen kloppen. Daarna pas bouwen we
de ophalers voor de adressen die werken, in plaats van voor de adressen die we
hoopten.
"""
from __future__ import annotations

import sys

from .base import as_json, probe, report
from .sources import ALL


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    results, per_source = [], {}
    for s in ALL:
        got = [probe(c.url, with_peek="--peek" in argv) for c in s.candidates]
        results += got
        per_source[s.id] = any(p.ok for p in got)
    if "--json" in argv:
        print(as_json(results))
    else:
        print(report(results))
        print("\nper bron:")
        for sid, ok in per_source.items():
            print(f"  {'bereikbaar    ' if ok else 'geen enkele URL'}  {sid}")
    # Exit-code 1 als geen enkele bron te bereiken is: dan is er iets mis met het
    # netwerk en niet met de adressen, en dat verschil wil je zien.
    return 0 if any(per_source.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
