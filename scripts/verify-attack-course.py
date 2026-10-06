#!/usr/bin/env python3
"""Vérifie le cours « Démolir le roque » (src/data/attackCourse.json) avec Stockfish 18, puis
tamponne le fichier vérifié.

Déroulé obligatoire à chaque modification du contenu :
    1. éditer src/data/attackCourse.json ;
    2. python3 scripts/verify-attack-course.py  (Stockfish 18 natif : variable STOCKFISH ou
       `stockfish` du PATH ; analyses en cache hors dépôt, ~/.cache/chess-local/attack-eval.json) ;
    3. committer le JSON (réécrit avec `keeps`, `close` et `eval`) ET scripts/attack-course.verified.
Le contrôle hors ligne (scripts/check-attack-course.mjs, lancé par les E2E) échoue si le JSON ne
correspond plus au tampon : un contenu non revérifié ne passe pas le gate.

Déterminisme : Stockfish mono-thread, table de hachage fixe et vidée (`ucinewgame`) avant chaque
recherche, profondeur fixe. Plusieurs moteurs travaillent en parallèle (un par fil d'exécution).

Valeurs du point de vue du camp concerné, en pions ; un mat vaut ±(100 - n) pour l'ordre, et les
comparaisons de proximité se font sur la valeur plafonnée à ±8 (mat = 8).

Ce que le script prouve :
- chaque FEN est légale (python-chess), chaque coup est jouable et en SAN canonique ;
- ligne (`result` = `win` : avantage décisif >= +2 ; `edge` : nette avance >= +1) : avant
  chaque coup de l'élève, le meilleur coup atteint le palier ; tous les coups sont triés par une
  recherche multipv à profondeur SCAN, et tout coup à moins de 2 pions sous le palier est recherché
  seul à profondeur DEEP (même profondeur pour tous, coup de la leçon compris) ;
  `keeps` = coups au palier, `close` = coups dans la zone grise [palier - 0,7 ; palier[ ;
  le coup de la leçon est au palier et à 1 pion au plus du meilleur (valeurs plafonnées) ;
  `only` <=> un seul coup au palier et tous les autres au moins 1,5 dessous ;
  Limite assumée : un coup à plus de WINDOW sous le palier au tri garde sa valeur de tri (pas de
  recherche profonde) ; un tel coup qui atteindrait le palier plus profond serait refusé à tort.
- réponse adverse : l'élève reste au palier après elle ; sans `weak`, elle est à 1 pion au plus
  de la meilleure défense ; avec `weak`, elle est vraiment plus faible (>= 1 pion) ;
- fin de ligne : mat sur l'échiquier, ou l'élève au palier à profondeur FINAL ;
- diagramme : `claim` w/b = ce camp à +2 au moins, `equal` = |éval| <= 0,5 ; `fails` = coup
  jouable, après lequel son camp est à +0,3 au plus et 1,5 sous le meilleur coup ; `eval` (éval
  du diagramme, côté blanc, à profondeur DEEP) est écrite pour chaque diagramme.
"""
import hashlib
import json
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import chess
import chess.engine

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from course_json import dump  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "src", "data", "attackCourse.json")
STAMP = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "scripts", "attack-course.verified")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "chess-local", "attack-eval.json")

SCAN = 12  # tri multipv de tous les coups
DEEP = 18  # recherche coup par coup, réponses, diagrammes
FINAL = 20  # position finale d'une ligne
HASH_MB = 64
TIERS = {"win": 2.0, "edge": 1.0}  # en pions ; SF 18 normalise +1 à 50 % de chances de gain, +2 en donne bien davantage
WINDOW = 2.0  # coups recherchés à fond : à moins de WINDOW sous le palier au tri
GREY = 0.7  # zone grise sous le palier
ONLY_MARGIN = 1.5
BEST_MARGIN = 1.0  # coup de la leçon / réponse adverse : écart toléré au meilleur
CAP = 8.0
CLAIM = 2.0
EQUAL = 0.5
FAILS_MAX = 0.3
FAILS_GAP = 1.5

ENGINE_PATH = os.environ.get("STOCKFISH") or shutil.which("stockfish")
SETTINGS = f"Threads=1 Hash={HASH_MB}"


# ---------- Moteurs (un par fil d'exécution) ----------
_local = threading.local()
_engines = []
_engines_lock = threading.Lock()


def engine():
    if not hasattr(_local, "engine"):
        eng = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        eng.configure({"Threads": 1, "Hash": HASH_MB})
        _local.engine = eng
        with _engines_lock:
            _engines.append(eng)
    return _local.engine


def engine_name():
    eng = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
    name = eng.id.get("name", "?")
    eng.quit()
    return name


def to_val(score):
    """PovScore -> (valeur en pions, texte)."""
    if score.is_mate():
        m = score.mate()
        return (100 - m if m > 0 else -100 - m), f"#{m}"
    cp = score.score()
    return cp / 100, f"{cp / 100:+.2f}"


def cap(v):
    return max(-CAP, min(CAP, v))


def search(fen, depth, move=None, multipv=1):
    """Recherche neuve (hachage vidé). Retourne [(uci, valeur, texte)] du point de vue du trait."""
    board = chess.Board(fen)
    limit = chess.engine.Limit(depth=depth)
    kw = {"game": object()}  # nouvelle « partie » : python-chess envoie ucinewgame
    if move:
        kw["root_moves"] = [chess.Move.from_uci(move)]
    infos = engine().analyse(board, limit, multipv=multipv, **kw)
    if isinstance(infos, dict):
        infos = [infos]
    out = []
    for info in infos:
        v, t = to_val(info["score"].pov(board.turn))
        out.append((info["pv"][0].uci(), v, t))
    return out


# Tâches (une recherche chacune) : job -> résultat sérialisable.
def task(job):
    kind, fen, arg, depth = job
    if kind == "scan":
        n = chess.Board(fen).legal_moves.count()
        return job, search(fen, depth, multipv=n)
    if kind == "move":
        return job, search(fen, depth, move=arg)[0]
    if kind == "best":
        return job, search(fen, depth)[0]
    raise ValueError(kind)


class Evaluator:
    def __init__(self, workers):
        self.workers = workers
        self.engine = engine_name()
        if not self.engine.startswith("Stockfish 18"):
            sys.exit(f"Moteur {self.engine!r} : Stockfish 18 requis (même version que le WASM de l'app).")
        self.cache = {}
        if os.path.exists(CACHE):
            with open(CACHE) as f:
                self.cache = json.load(f)

    def key(self, job):
        kind, fen, arg, depth = job
        return f"{self.engine}|{SETTINGS}|{kind}|{fen}|{arg or '-'}|{depth}"

    def run(self, jobs):
        todo = list(dict.fromkeys(j for j in jobs if self.key(j) not in self.cache))
        if todo:
            print(f"  {len(todo)} recherche(s) moteur…", flush=True)
            try:
                with ThreadPoolExecutor(max_workers=self.workers) as ex:
                    for i, (job, res) in enumerate(ex.map(task, todo), 1):
                        self.cache[self.key(job)] = res
                        if i % 20 == 0:
                            print(f"    {i}/{len(todo)}", flush=True)
                            self.save()
            finally:
                self.save()
                with _engines_lock:
                    while _engines:
                        _engines.pop().quit()
        return {j: self.cache[self.key(j)] for j in jobs}

    def save(self):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.cache, f)
        os.replace(tmp, CACHE)


errors = []


def fail(label, msg):
    errors.append(f"[KO] {label} : {msg}")


def legal_board(fen, label):
    try:
        b = chess.Board(fen)
    except ValueError as e:
        fail(label, f"FEN illisible {fen} ({e})")
        return None
    if not b.is_valid():
        fail(label, f"position illégale {fen} ({b.status()!r})")
        return None
    return b


# ---------- Collecte des positions ----------
def walk(data):
    """Positions à analyser, avec ce qu'il faut vérifier. Erreurs de légalité relevées au passage."""
    diagrams, students, replies, finals = [], [], [], []
    for lid, lesson in data["lessons"].items():
        for si, step in enumerate(lesson["steps"]):
            label = f"{lid} étape {si + 1}"
            if step["kind"] == "diagram":
                b = legal_board(step["fen"], label)
                if b is None:
                    continue
                fails = None
                if "fails" in step:
                    try:
                        fails = b.parse_san(step["fails"]).uci()
                    except ValueError:
                        fail(label, f"fails {step['fails']} injouable")
                        continue
                diagrams.append((label, step, b.fen(), fails))
            elif step["kind"] == "line":
                b = legal_board(step["fen"], label)
                if b is None:
                    continue
                if step["result"] not in TIERS:
                    fail(label, f"result {step['result']} inconnu (win ou edge)")
                    continue
                player = b.turn
                for i, m in enumerate(step["moves"]):
                    ml = f"{label} coup {i + 1} ({m['san']})"
                    try:
                        mv = b.parse_san(m["san"])
                    except ValueError:
                        fail(ml, f"coup injouable dans {b.fen()}")
                        break
                    if b.san(mv) != m["san"]:
                        fail(ml, f"SAN non canonique, attendu {b.san(mv)}")
                    if b.turn == player:
                        if mv.promotion and mv.promotion != chess.QUEEN:
                            fail(ml, "sous-promotion de l'élève : le glisser promeut en dame")
                        students.append((ml, step, m, b.fen(), mv.uci()))
                    else:
                        replies.append((ml, step, m, b.fen(), mv.uci()))
                    b.push(mv)
                else:
                    finals.append((label, step, b.copy(), player))
            else:
                fail(label, f"type d'étape inconnu {step['kind']}")
    return diagrams, students, replies, finals


def main():
    workers = int(os.environ.get("WORKERS", max(1, (os.cpu_count() or 2) - 1)))
    ev = Evaluator(workers)
    with open(DATA) as f:
        data = json.load(f)
    diagrams, students, replies, finals = walk(data)

    # 1. Diagrammes, réponses, fins de ligne, tri multipv des positions de l'élève.
    jobs = []
    for _, step, fen, fails in diagrams:
        jobs.append(("best", fen, None, DEEP))
        if fails:
            jobs.append(("move", fen, fails, DEEP))
    for _, _, _, fen, uci in replies:
        jobs += [("best", fen, None, DEEP), ("move", fen, uci, DEEP)]
    for _, _, b, _ in finals:
        if not b.is_checkmate() and not b.is_game_over():
            jobs.append(("best", b.fen(), None, FINAL))
    for _, _, _, fen, _ in students:
        jobs.append(("scan", fen, None, SCAN))
    res = ev.run(jobs)

    # 2. Recherche coup par coup des candidats de chaque position de l'élève.
    jobs2 = []
    for _, step, m, fen, uci in students:
        tier = TIERS[step["result"]]
        scan = res[("scan", fen, None, SCAN)]
        cands = {u for u, v, _ in scan if v >= tier - WINDOW} | {uci}
        jobs2 += [("move", fen, u, DEEP) for u in sorted(cands)]
    res.update(ev.run(jobs2))

    # ---------- Verdicts ----------
    for label, step, fen, fails in diagrams:
        u, v, t = res[("best", fen, None, DEEP)]
        white = v if chess.Board(fen).turn == chess.WHITE else -v
        wtxt = t if chess.Board(fen).turn == chess.WHITE else (f"#{-int(t[1:])}" if t.startswith("#") else f"{-v:+.2f}")
        step["eval"] = wtxt
        claim = step.get("claim")
        if claim == "w" and white < CLAIM:
            fail(label, f"claim w mais éval {wtxt}")
        elif claim == "b" and white > -CLAIM:
            fail(label, f"claim b mais éval {wtxt}")
        elif claim == "equal" and abs(white) > EQUAL:
            fail(label, f"claim equal mais éval {wtxt}")
        elif claim is not None and claim not in ("w", "b", "equal"):
            fail(label, f"claim {claim} inconnu (w, b ou equal)")
        if fails:
            _, fv, ft = res[("move", fen, fails, DEEP)]
            if fv > FAILS_MAX or v - fv < FAILS_GAP:
                fail(label, f"fails {step['fails']} : {ft} pour son camp, meilleur coup {t} : l'échec n'est pas établi")

    for ml, step, m, fen, uci in students:
        tier = TIERS[step["result"]]
        scan = res[("scan", fen, None, SCAN)]
        vals = {u: v for u, v, _ in scan}
        txt = {u: t for u, _, t in scan}
        for u in list(vals):
            key = ("move", fen, u, DEEP)
            if key in res:
                _, vals[u], txt[u] = res[key]
        if uci not in vals:
            _, vals[uci], txt[uci] = res[("move", fen, uci, DEEP)]
        best_u = max(vals, key=lambda u: vals[u])
        keeps = sorted(u for u, v in vals.items() if v >= tier)
        close = sorted(u for u, v in vals.items() if tier - GREY <= v < tier)
        if vals[best_u] < tier:
            fail(ml, f"la position n'atteint pas le palier {step['result']} (meilleur {txt[best_u]}, {fen})")
        if uci not in keeps:
            fail(ml, f"le coup vaut {txt[uci]}, sous le palier {step['result']} ({fen})")
        elif cap(vals[uci]) < cap(vals[best_u]) - BEST_MARGIN:
            fail(ml, f"le coup vaut {txt[uci]}, nettement moins que {chess.Board(fen).san(chess.Move.from_uci(best_u))} ({txt[best_u]})")
        others = [v for u, v in vals.items() if u != uci]
        is_only = len(keeps) == 1 and all(v <= tier - ONLY_MARGIN for v in others)
        if m.get("only") and not is_only:
            fail(ml, f"« only » faux : {len(keeps)} coup(s) au palier, second meilleur {max(others, default=-999):+.2f}")
        m["keeps"] = keeps
        m["close"] = close
        if not m.get("close"):
            del m["close"]

    for ml, step, m, fen, uci in replies:
        tier = TIERS[step["result"]]
        _, bv, bt = res[("best", fen, None, DEEP)]
        _, rv, rt = res[("move", fen, uci, DEEP)]
        # Du point de vue de l'élève (l'attaquant).
        att_best, att_reply = -bv, -rv
        if att_best < tier:
            fail(ml, f"la meilleure défense ({bt} pour la défense) fait sortir l'élève du palier : le coup précédent ne le gardait pas")
        if att_reply < tier:
            fail(ml, f"après cette réponse ({rt} pour la défense), l'élève n'est plus au palier")
        gap = cap(att_reply) - cap(att_best)
        if m.get("weak"):
            if gap < BEST_MARGIN:
                fail(ml, f"marquée weak mais à {gap:.2f} seulement de la meilleure défense ({bt})")
        elif gap > BEST_MARGIN:
            best_san = chess.Board(fen).san(chess.Move.from_uci(res[("best", fen, None, DEEP)][0]))
            fail(ml, f"réponse à {gap:.2f} de la meilleure défense {best_san} ({bt}) : marquer weak et le dire, ou suivre la meilleure défense")

    for label, step, b, player in finals:
        if b.is_checkmate():
            if b.turn == player:
                fail(label, "la ligne finit par le mat de l'élève")
            continue
        if b.is_game_over():
            fail(label, "la ligne finit par une nulle")
            continue
        _, v, t = res[("best", b.fen(), None, FINAL)]
        att = v if b.turn == player else -v
        if att < TIERS[step["result"]]:
            fail(label, f"position finale {t} (trait {'blanc' if b.turn else 'noir'}) : sous le palier {step['result']}")

    for e in errors:
        print(e)
    if errors:
        print(f"{len(errors)} manquement(s) : JSON et tampon non modifiés.")
        sys.exit(1)
    text = dump(data) + "\n"
    with open(DATA, "w") as f:
        f.write(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    # Second mot : sha du vérificateur lui-même (paliers, profondeurs), contrôlé par check-attack-course.mjs.
    with open(os.path.abspath(__file__), "rb") as f:
        verifier = hashlib.sha256(f.read()).hexdigest()
    with open(STAMP, "w") as f:
        f.write(f"{digest} {verifier}\n")
    lines = sum(1 for l in data["lessons"].values() for s in l["steps"] if s["kind"] == "line")
    print(
        f"OK : {len(data['lessons'])} leçons, {lines} lignes, {len(students)} coups de l'élève, {len(replies)} réponses, "
        f"{len(diagrams)} diagrammes vérifiés par {ev.engine} ({SETTINGS}, profondeurs {SCAN}/{DEEP}/{FINAL}). Tampon {digest[:12]}."
    )


if __name__ == "__main__":
    main()
