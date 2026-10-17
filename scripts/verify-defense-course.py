#!/usr/bin/env python3
"""Vérifie le cours « Tenir sous l'attaque » (src/data/defenseCourse.json) avec Stockfish 18, puis
tamponne le fichier vérifié. Pendant défensif de verify-attack-course.py : l'élève joue le camp qui
défend, l'app joue l'attaquant.

Déroulé obligatoire à chaque modification du contenu :
    1. éditer src/data/defenseCourse.json ;
    2. python3 scripts/verify-defense-course.py  (Stockfish 18 natif : variable STOCKFISH ou
       `stockfish` du PATH ; analyses en cache hors dépôt, ~/.cache/chess-local/defense-eval.json ;
       WORKERS moteurs mono-thread en parallèle, 2 par défaut) ;
    3. committer le JSON (réécrit avec `keeps`, `close`, `eval`, `failsEval`) ET
       scripts/defense-course.verified.
Le contrôle hors ligne (scripts/check-defense-course.mjs, lancé par la suite E2E cours_defense)
échoue si le JSON ne correspond plus au tampon : un contenu non revérifié ne passe pas le gate.

Déterminisme : Stockfish mono-thread, table de hachage fixe et vidée (`ucinewgame`) avant chaque
recherche, profondeur fixe.

Valeurs du point de vue du camp concerné, en pions ; un mat vaut ±(100 - n) pour l'ordre, et les
comparaisons de proximité se font sur la valeur plafonnée à ±8 (mat = 8).

Paliers d'une ligne (`result`, point de vue de l'élève) :
- `hold` : -0,5 au moins. La défense tient : l'attaquant garde au plus un demi-pion, soit la marge
  de `claim: equal`. Palier unilatéral : une défense qui retourne la situation tient aussi.
- `edge` : +1 au moins (la défense réfute l'attaque et garde une nette avance) ;
- `win` : +2 au moins (l'attaque était fautive, la défense laisse un avantage décisif).

Ce que le script prouve :
- chaque FEN est légale (python-chess), chaque coup est jouable et en SAN canonique ;
- avant chaque coup de l'élève, tous les coups légaux sont recherchés séparément à profondeur 24 ;
  `keeps` = coups au palier, `close` = coups dans la zone grise [palier - GREY ; palier[ ;
  le coup de la leçon est au palier et à 1 pion au plus du meilleur (valeurs plafonnées) ;
  `only` <=> un seul coup au palier et tous les autres au moins 1,5 dessous ;
- réponse de l'attaquant : l'élève reste au palier après elle ; sans `weak`, elle est à
  REPLY_MARGIN au plus de la meilleure attaque (une attaque molle rendrait le « tient » trop
  facile) ; au-delà, elle doit porter `weak` (affichée « ? » : l'app montre une attaque moins forte) ;
- fin de ligne : jamais le mat de l'élève ; mat de l'attaquant accepté ; pat ou matériel
  insuffisant accepté en `hold` seulement ; sinon l'élève au palier à profondeur DEPTH.
  Pas de détection de répétition (positions isolées, sans historique) : un échec perpétuel passe par l'éval finale ;
- diagramme : `eval` (côté blanc, à profondeur DEPTH) écrite pour chaque diagramme ; `claim` w/b =
  ce camp à +2 au moins, `equal` = |éval| <= 0,5, `hold-w`/`hold-b` = ce camp à -0,5 au moins ;
  `fails` = coup jouable, après lequel son camp
  est à FAILS_MAX au plus et FAILS_GAP sous le meilleur coup, à profondeur 24 ; `failsEval`
  (point de vue du camp qui joue `fails`, à DEPTH) est écrite pour le contrôle (« perd » exige -2) ;
- menace (`threat`, diagramme ou coup de ligne) : coup de l'attaquant qui serait mat immédiat s'il
  avait le trait (position du diagramme, ou position après le coup de ligne) ; trait inversé
  refusé si le camp au trait est en échec. Vérifié sans moteur, ici et dans le contrôle hors ligne.
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
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "src", "data", "defenseCourse.json")
STAMP = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "scripts", "defense-course.verified")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "chess-local", "defense-eval.json")

DEPTH = 24
HASH_MB = 64
TIERS = {"hold": -0.5, "edge": 1.0, "win": 2.0}  # en pions, point de vue de l'élève
GREY = {"hold": 0.5, "edge": 0.7, "win": 0.7}  # zone grise sous le palier
ONLY_MARGIN = 1.5
BEST_MARGIN = 1.0  # coup de la leçon : écart toléré au meilleur
REPLY_MARGIN = 0.5  # réponse de l'attaquant : écart toléré à la meilleure attaque
CAP = 8.0
CLAIM = 2.0
EQUAL = 0.5
HOLD = -0.5
FAILS_MAX = -1.0
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


def search(fen, depth, move=None):
    """Recherche neuve (hachage vidé). Retourne [(uci, valeur, texte)] du point de vue du trait."""
    board = chess.Board(fen)
    limit = chess.engine.Limit(depth=depth)
    kw = {"game": object()}  # nouvelle « partie » : python-chess envoie ucinewgame
    if move:
        kw["root_moves"] = [chess.Move.from_uci(move)]
    infos = engine().analyse(board, limit, multipv=1, **kw)
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


def threat_mates(board, attacker, san):
    """Le coup `san` de `attacker` est-il un mat immédiat s'il avait le trait ? (sans moteur)"""
    b = board.copy(stack=False)
    if b.turn != attacker:
        if b.is_check():
            return False, "le camp au trait est en échec : trait inversé impossible"
        b.turn = attacker
        b.ep_square = None
        if not b.is_valid():
            return False, "trait inversé illégal"
    try:
        mv = b.parse_san(san)
    except ValueError:
        return False, f"menace {san} injouable"
    if b.san(mv) != san:
        return False, f"menace en SAN non canonique, attendu {b.san(mv)}"
    b.push(mv)
    return (True, "") if b.is_checkmate() else (False, f"menace {san} n'est pas mat")


def white_text(v, t, turn):
    if turn == chess.WHITE:
        return t
    return f"#{-int(t[1:])}" if t.startswith("#") else f"{-v:+.2f}"


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
                if "threat" in step:
                    ok, why = threat_mates(b, not b.turn, step["threat"])
                    if not ok:
                        fail(label, why)
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
                    fail(label, f"result {step['result']} inconnu (hold, edge ou win)")
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
                    if "threat" in m:
                        ok, why = threat_mates(b, not player, m["threat"])
                        if not ok:
                            fail(ml, why)
                else:
                    finals.append((label, step, b.copy(), player))
            else:
                fail(label, f"type d'étape inconnu {step['kind']}")
    return diagrams, students, replies, finals


def main():
    workers = int(os.environ.get("WORKERS", 2))
    ev = Evaluator(workers)
    with open(DATA) as f:
        data = json.load(f)
    diagrams, students, replies, finals = walk(data)

    jobs = []
    for _, step, fen, fails in diagrams:
        jobs.append(("best", fen, None, DEPTH))
        if fails:
            jobs.append(("move", fen, fails, DEPTH))
    for _, _, _, fen, uci in replies:
        jobs += [("best", fen, None, DEPTH), ("move", fen, uci, DEPTH)]
    for _, step, b, _ in finals:
        if not b.is_game_over():
            jobs.append(("best", b.fen(), None, DEPTH))
    for _, _, _, fen, _ in students:
        jobs += [("move", fen, m.uci(), DEPTH) for m in chess.Board(fen).legal_moves]
    res = ev.run(jobs)

    # ---------- Verdicts ----------
    for label, step, fen, fails in diagrams:
        turn = chess.Board(fen).turn
        u, v, t = res[("best", fen, None, DEPTH)]
        white = v if turn == chess.WHITE else -v
        wtxt = white_text(v, t, turn)
        step["eval"] = wtxt
        claim = step.get("claim")
        if claim == "w" and white < CLAIM:
            fail(label, f"claim w mais éval {wtxt}")
        elif claim == "b" and white > -CLAIM:
            fail(label, f"claim b mais éval {wtxt}")
        elif claim == "equal" and abs(white) > EQUAL:
            fail(label, f"claim equal mais éval {wtxt}")
        elif claim == "hold-w" and white < HOLD:
            fail(label, f"claim hold-w mais éval {wtxt}")
        elif claim == "hold-b" and -white < HOLD:
            fail(label, f"claim hold-b mais éval {wtxt}")
        elif claim is not None and claim not in ("w", "b", "equal", "hold-w", "hold-b"):
            fail(label, f"claim {claim} inconnu (w, b, equal, hold-w ou hold-b)")
        if fails:
            _, fv, ft = res[("move", fen, fails, DEPTH)]
            if fv > FAILS_MAX or v - fv < FAILS_GAP:
                fail(label, f"fails {step['fails']} : {ft} pour son camp, meilleur coup {t} : l'échec n'est pas établi")
            step["failsEval"] = ft
        else:
            step.pop("failsEval", None)

    for ml, step, m, fen, uci in students:
        r = step["result"]
        tier = TIERS[r]
        moves = [res[("move", fen, mv.uci(), DEPTH)] for mv in chess.Board(fen).legal_moves]
        vals = {u: v for u, v, _ in moves}
        txt = {u: t for u, _, t in moves}
        best_u = max(vals, key=lambda u: vals[u])
        keeps = sorted(u for u, v in vals.items() if v >= tier)
        close = sorted(u for u, v in vals.items() if tier - GREY[r] <= v < tier)
        if vals[best_u] < tier:
            fail(ml, f"la position n'atteint pas le palier {r} (meilleur {txt[best_u]}, {fen})")
        if uci not in keeps:
            fail(ml, f"le coup vaut {txt[uci]}, sous le palier {r} ({fen})")
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
        best_uci, bv, bt = res[("best", fen, None, DEPTH)]
        _, rv, rt = res[("move", fen, uci, DEPTH)]
        # Du point de vue de l'élève (le défenseur).
        def_best, def_reply = -bv, -rv
        if def_best < tier:
            fail(ml, f"la meilleure attaque ({bt} pour l'attaquant) fait sortir l'élève du palier : le coup précédent ne tenait pas")
        if def_reply < tier:
            fail(ml, f"après cette réponse ({rt} pour l'attaquant), l'élève n'est plus au palier")
        # Une recherche limitée à un coup peut donner une autre évaluation que la recherche
        # libre à profondeur identique. Si celle-ci choisit déjà la réponse, son écart
        # à la meilleure attaque est nul ; les deux contrôles de palier restent requis.
        gap = 0.0 if uci == best_uci else cap(def_reply) - cap(def_best)
        if m.get("weak"):
            if gap <= REPLY_MARGIN:
                fail(ml, f"marquée weak mais à {gap:.2f} seulement de la meilleure attaque ({bt})")
        elif gap > REPLY_MARGIN:
            best_san = chess.Board(fen).san(chess.Move.from_uci(res[("best", fen, None, DEPTH)][0]))
            fail(ml, f"réponse à {gap:.2f} de la meilleure attaque {best_san} ({bt}) : marquer weak et le dire, ou suivre la meilleure attaque")

    for label, step, b, player in finals:
        if b.is_checkmate():
            if b.turn == player:
                fail(label, "la ligne finit par le mat de l'élève")
            continue
        if b.is_game_over():
            if step["result"] != "hold":
                fail(label, "la ligne finit par une nulle sur l'échiquier")
            continue
        _, v, t = res[("best", b.fen(), None, DEPTH)]
        mine = v if b.turn == player else -v
        if mine < TIERS[step["result"]]:
            fail(label, f"position finale {t} (trait {'blanc' if b.turn else 'noir'}, profondeur {DEPTH}) : sous le palier {step['result']}")

    for e in errors:
        print(e)
    if errors:
        print(f"{len(errors)} manquement(s) : JSON et tampon non modifiés.")
        sys.exit(1)
    text = dump(data) + "\n"
    with open(DATA, "w") as f:
        f.write(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    # Second mot : sha du vérificateur lui-même (paliers, profondeurs), contrôlé par check-defense-course.mjs.
    with open(os.path.abspath(__file__), "rb") as f:
        verifier = hashlib.sha256(f.read()).hexdigest()
    with open(STAMP, "w") as f:
        f.write(f"{digest} {verifier}\n")
    lines = sum(1 for l in data["lessons"].values() for s in l["steps"] if s["kind"] == "line")
    print(
        f"OK : {len(data['lessons'])} leçons, {lines} lignes, {len(students)} coups de l'élève, {len(replies)} réponses, "
        f"{len(diagrams)} diagrammes vérifiés par {ev.engine} ({SETTINGS}, profondeur {DEPTH}). Tampon {digest[:12]}."
    )


if __name__ == "__main__":
    main()
