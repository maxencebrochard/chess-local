#!/usr/bin/env python3
"""Vérifie le cours « Structures de pions » (src/data/structuresCourse.json) avec Stockfish 18, puis
tamponne le fichier vérifié.

Déroulé obligatoire à chaque modification du contenu :
    1. éditer src/data/structuresCourse.json ;
    2. python3 scripts/verify-structures-course.py  (Stockfish 18 natif : variable STOCKFISH ou
       `stockfish` du PATH ; analyses en cache hors dépôt, ~/.cache/chess-local/structures-eval.json ;
       WORKERS=2 pour limiter les moteurs en parallèle) ;
    3. committer le JSON (réécrit avec `keeps`, `close` et `eval`) ET scripts/structures-course.verified.
Le contrôle hors ligne (scripts/check-structures-course.mjs, lancé par les E2E) échoue si le JSON ne
correspond plus au tampon : un contenu non revérifié ne passe pas le gate.

La plomberie moteur (moteurs par fil, recherches déterministes, cache, légalité, parcours des
leçons) est celle de scripts/verify-attack-course.py, importé par chemin : le tampon lie donc aussi
ce fichier-là. Seuls les verdicts diffèrent : une structure ne promet pas un gain, elle donne un
plan. Valeurs du point de vue du camp concerné, en pions, plafonnées à ±8 (mat = 8).

Ce que le script prouve, pour les lignes (`result` = `plan`, seul résultat de ce cours) :
- avant chaque coup de l'élève, la position reste jouable : meilleur coup >= FLOOR (-1, un pion de retard au plus : la est-indienne vaut -0,7 pour les Noirs selon Stockfish) ;
  tous les coups sont triés par une recherche multipv à profondeur SCAN, et tout coup à moins de
  WINDOW (1,4) du meilleur au tri est recherché seul à profondeur DEEP (coup de la leçon compris) ;
  `keeps` = coups à moins de GAP (0,5) du meilleur et >= FLOOR ; `close` = coups dans
  [meilleur - BAD ; meilleur - GAP[ ; le coup de la leçon est dans `keeps` ;
  l'exercice discrimine : `keeps` couvre au plus deux tiers des coups légaux (3 au moins permis ;
  un milieu de partie calme en compte souvent un tiers, l'élève lit alors « se défend aussi »), et
  au moins un coup légal est à plus de BAD (0,9) sous le meilleur ;
  `only` <=> un seul coup dans `keeps` et tous les autres au moins ONLY_MARGIN (1,5) dessous ;
- réponse adverse : l'élève reste >= FLOOR après elle ; sans `weak`, elle est à 1 pion au plus de
  la meilleure défense ; avec `weak`, elle est vraiment plus faible (>= 1 pion) ;
- fin de ligne : l'élève >= FLOOR à profondeur FINAL ;
- diagramme : `claim` w/b = ce camp à +2 au moins, `equal` = |éval| <= 0,5 ; `fails` = coup
  jouable, après lequel son camp est à +0,3 au plus et 1,5 sous le meilleur coup ; `eval` (éval du
  diagramme, côté blanc, à profondeur DEEP) est écrite pour chaque diagramme.
"""
import hashlib
import importlib.util
import json
import os
import sys

import chess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from course_json import dump  # noqa: E402

ATTACK_VERIFIER = os.path.join(HERE, "verify-attack-course.py")
_spec = importlib.util.spec_from_file_location("verify_attack_course", ATTACK_VERIFIER)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

ROOT = os.path.dirname(HERE)
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "src", "data", "structuresCourse.json")
STAMP = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "scripts", "structures-course.verified")
# Cache propre au cours (mêmes clés que le cours d'attaque : moteur, réglages, tâche, profondeur).
base.CACHE = os.path.join(os.path.expanduser("~"), ".cache", "chess-local", "structures-eval.json")
# Le parcours des leçons de base.walk n'accepte que les résultats connus de TIERS.
base.TIERS = {"plan": None}

SCAN, DEEP, FINAL = base.SCAN, base.DEEP, base.FINAL
FLOOR = -1.0
GAP = 0.5
BAD = 0.9
WINDOW = 1.4
ONLY_MARGIN = 1.5
REPLY_MARGIN = 1.0
cap = base.cap


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    workers = int(os.environ.get("WORKERS", "2"))
    ev = base.Evaluator(workers)
    with open(DATA) as f:
        data = json.load(f)
    diagrams, students, replies, finals = base.walk(data)
    fail = base.fail

    jobs = []
    for _, step, fen, fails in diagrams:
        jobs.append(("best", fen, None, DEEP))
        if fails:
            jobs.append(("move", fen, fails, DEEP))
    for _, _, _, fen, uci in replies:
        jobs += [("best", fen, None, DEEP), ("move", fen, uci, DEEP)]
    for _, _, b, _ in finals:
        if not b.is_game_over():
            jobs.append(("best", b.fen(), None, FINAL))
    for _, _, _, fen, _ in students:
        jobs.append(("scan", fen, None, SCAN))
    res = ev.run(jobs)

    jobs2 = []
    for _, _, _, fen, uci in students:
        scan = res[("scan", fen, None, SCAN)]
        top = max(cap(v) for _, v, _ in scan)
        cands = {u for u, v, _ in scan if cap(v) >= top - WINDOW} | {uci}
        jobs2 += [("move", fen, u, DEEP) for u in sorted(cands)]
    res.update(ev.run(jobs2))

    for label, step, fen, fails in diagrams:
        u, v, t = res[("best", fen, None, DEEP)]
        white_turn = chess.Board(fen).turn == chess.WHITE
        white = v if white_turn else -v
        wtxt = t if white_turn else (f"#{-int(t[1:])}" if t.startswith("#") else f"{-v:+.2f}")
        step["eval"] = wtxt
        claim = step.get("claim")
        if claim == "w" and white < base.CLAIM:
            fail(label, f"claim w mais éval {wtxt}")
        elif claim == "b" and white > -base.CLAIM:
            fail(label, f"claim b mais éval {wtxt}")
        elif claim == "equal" and abs(white) > base.EQUAL:
            fail(label, f"claim equal mais éval {wtxt}")
        elif claim is not None and claim not in ("w", "b", "equal"):
            fail(label, f"claim {claim} inconnu (w, b ou equal)")
        if fails:
            _, fv, ft = res[("move", fen, fails, DEEP)]
            if fv > base.FAILS_MAX or v - fv < base.FAILS_GAP:
                fail(label, f"fails {step['fails']} : {ft} pour son camp, meilleur coup {t} : l'échec n'est pas établi")

    for ml, step, m, fen, uci in students:
        board = chess.Board(fen)
        scan = res[("scan", fen, None, SCAN)]
        vals = {u: v for u, v, _ in scan}
        txt = {u: t for u, _, t in scan}
        for u in list(vals) + [uci]:
            key = ("move", fen, u, DEEP)
            if key in res:
                _, vals[u], txt[u] = res[key]
        best_u = max(vals, key=lambda u: vals[u])
        best = cap(vals[best_u])
        keeps = sorted(u for u, v in vals.items() if cap(v) >= best - GAP and v >= FLOOR)
        close = sorted(u for u, v in vals.items() if best - BAD <= cap(v) < best - GAP and v >= FLOOR)
        legal = board.legal_moves.count()
        san = lambda u: board.san(chess.Move.from_uci(u))  # noqa: E731
        if vals[best_u] < FLOOR:
            fail(ml, f"position injouable pour l'élève (meilleur {san(best_u)} {txt[best_u]}, {fen})")
        if uci not in keeps:
            fail(ml, f"le coup vaut {txt[uci]}, le meilleur est {san(best_u)} ({txt[best_u]}) : hors plan ({fen})")
        if len(keeps) > max(3, 2 * legal // 3):
            fail(ml, f"{len(keeps)} coups sur {legal} gardent le plan : l'exercice ne discrimine pas ({fen})")
        if not any(cap(v) < best - BAD for v in vals.values()):
            fail(ml, f"aucun coup à plus de {BAD} sous le meilleur : aucun refus possible ({fen})")
        others = [cap(v) for u, v in vals.items() if u != uci]
        is_only = keeps == [uci] and all(v <= best - ONLY_MARGIN for v in others)
        if m.get("only") and not is_only:
            fail(ml, f"« only » faux : {len(keeps)} coup(s) gardent le plan, second meilleur {max(others, default=-999):+.2f}")
        m["keeps"] = keeps
        m["close"] = close
        if not m.get("close"):
            del m["close"]

    for ml, step, m, fen, uci in replies:
        _, bv, bt = res[("best", fen, None, DEEP)]
        _, rv, rt = res[("move", fen, uci, DEEP)]
        stu_best, stu_reply = -bv, -rv
        if stu_reply < FLOOR:
            fail(ml, f"après cette réponse ({rt} pour la défense), la position de l'élève n'est plus jouable")
        gap = cap(stu_reply) - cap(stu_best)
        if m.get("weak"):
            if gap < REPLY_MARGIN:
                fail(ml, f"marquée weak mais à {gap:.2f} seulement de la meilleure défense ({bt})")
        elif gap > REPLY_MARGIN:
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
        stu = v if b.turn == player else -v
        if stu < FLOOR:
            fail(label, f"position finale {t} (trait {'blanc' if b.turn else 'noir'}) : injouable pour l'élève")

    for e in base.errors:
        print(e)
    if base.errors:
        print(f"{len(base.errors)} manquement(s) : JSON et tampon non modifiés.")
        sys.exit(1)
    text = dump(data) + "\n"
    with open(DATA, "w") as f:
        f.write(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    # Deuxième et troisième mots : ce vérificateur et celui dont il réutilise la plomberie.
    with open(STAMP, "w") as f:
        f.write(f"{digest} {sha(os.path.abspath(__file__))} {sha(ATTACK_VERIFIER)}\n")
    lines = sum(1 for l in data["lessons"].values() for s in l["steps"] if s["kind"] == "line")
    print(
        f"OK : {len(data['lessons'])} leçons, {lines} lignes, {len(students)} coups de l'élève, {len(replies)} réponses, "
        f"{len(diagrams)} diagrammes vérifiés par {ev.engine} ({base.SETTINGS}, profondeurs {SCAN}/{DEEP}/{FINAL}). Tampon {digest[:12]}."
    )


if __name__ == "__main__":
    main()
