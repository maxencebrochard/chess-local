"""Contrat du lanceur : parallélisme borné, résultats fidèles et arrêt au délai."""
import json
import os
from pathlib import Path
import signal
import tempfile
import time

from helpers import Checker
from run import run_suites

ck = Checker("runner")


def suite(_p):
    with tempfile.TemporaryDirectory(prefix="runner-contrat-") as work:
        paths = {}
        for name, seconds, code in (("a", 1, 0), ("b", 1, 7), ("c", 1, 0), ("lent", 30, 0)):
            path = Path(work) / f"{name}.py"
            trace = str(Path(work) / f"{name}.json")
            path.write_text(f"""import json, os, subprocess, sys, time
from pathlib import Path
p = Path({trace!r})
d = {{'start': time.monotonic(), 'tmp': os.environ['TMPDIR'], 'pid': os.getpid()}}
if {name!r} == 'lent':
    child = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"
    d['children'] = [subprocess.Popen([sys.executable, '-c', child, os.environ['TMPDIR']],
                                     start_new_session=detached).pid for detached in (False, True)]
p.write_text(json.dumps(d))
time.sleep({seconds})
d['end'] = time.monotonic()
p.write_text(json.dumps(d))
raise SystemExit({code})
""")
            paths[name] = str(path)
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        results, durations = {}, {}
        try:
            run_suites(list(paths), paths, "http://unused", None, 3, {}, 2, results, durations)
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        traces = {n: json.loads((Path(work) / f"{n}.json").read_text()) for n in paths}
        ck.check("succès conservés", results['a'] is None and results['c'] is None)
        ck.check("échec conservé malgré un succès ultérieur", results['b'] == "code de sortie 7")
        ck.check("suite lente arrêtée au délai", results['lent'] == "délai de 3 s dépassé" and 'end' not in traces['lent'])
        ck.check("durée mesurée pour chaque résultat", set(durations) == set(paths) and all(d > 0 for d in durations.values()))
        a, b, c = (traces[n] for n in ('a', 'b', 'c'))
        ck.check("deux suites se chevauchent", max(a['start'], b['start']) < min(a['end'], b['end']))
        ck.check("la troisième attend une place", c['start'] >= min(a['end'], b['end']))
        ck.check("dossiers temporaires isolés et supprimés", len({t['tmp'] for t in traces.values()}) == 4 and all(not os.path.exists(t['tmp']) for t in traces.values()))
        alive = [pid for t in traces.values() for pid in [t['pid'], *t.get('children', [])]]
        deadline = time.monotonic() + 3
        while alive and time.monotonic() < deadline:
            for pid in alive[:]:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    alive.remove(pid)
            if alive:
                time.sleep(0.05)
        ck.check("aucun processus survivant, enfants résistants et détachés compris", not alive, str(alive))


ck.run(suite)
