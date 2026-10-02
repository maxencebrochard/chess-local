#!/usr/bin/env python3
"""Vérifie le cours de finales (src/data/endgameCourse.json) contre les tables de finales Syzygy
de lichess (tablebase.lichess.ovh, 7 pièces au plus), puis tamponne le fichier vérifié.

Déroulé obligatoire à chaque modification du contenu :
    1. éditer src/data/endgameCourse.json ;
    2. python3 scripts/verify-endgame-course.py  (réseau requis, réponses en cache hors dépôt) ;
    3. committer le JSON (réécrit avec les `keeps`) ET scripts/endgame-course.verified.
Le contrôle hors ligne (scripts/check-endgame-course.mjs, lancé par les E2E) échoue si le JSON
ne correspond plus au tampon : un contenu non revérifié ne passe pas le gate.

Ce que le script prouve, position par position :
- chaque FEN est légale (python-chess) et compte 7 pièces au plus ;
- diagramme avec `claim` : le verdict des tables est bien celui annoncé ;
- ligne : l'élève a le trait au départ ; à chacun de ses coups, la position a le verdict `result`
  (win/draw de son point de vue) et son coup le conserve ; `keeps` = tous ses coups qui le
  conservent (réécrit dans le JSON) ; `only` <=> un seul coup le conserve ;
- chaque réponse adverse est la meilleure catégorie possible (elle ne lâche rien) ; une réponse
  qui n'est pas la plus tenace (DTM) est signalée en note, pour relecture ;
- une ligne gagnante finit par un mat ou une promotion ; une ligne nulle finit sur une nulle ;
  « pat » dans le texte de fin impose un pat sur l'échiquier ;
- les verdicts « cursed-win »/« blessed-loss » (règle des 50 coups) sont refusés.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import chess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "src", "data", "endgameCourse.json")
STAMP = os.path.join(ROOT, "scripts", "endgame-course.verified")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "chess-local", "tablebase.json")
API = "https://tablebase.lichess.ovh/standard?fen="

_cache = {}
if os.path.exists(CACHE):
    with open(CACHE) as f:
        _cache = json.load(f)


def _save_cache():
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_cache, f)
    os.replace(tmp, CACHE)


def probe(board):
    key = " ".join(board.fen().split()[:4])
    if key not in _cache:
        url = API + urllib.parse.quote(key.replace(" ", "_"))
        for attempt in range(8):
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    _cache[key] = json.load(r)
                break
            except Exception as e:  # 429 ou réseau : on attend et on réessaie
                if attempt == 7:
                    raise RuntimeError(f"tables injoignables pour {key} : {e}")
                time.sleep(2 + 3 * attempt)
        _save_cache()
        time.sleep(0.2)
    return _cache[key]


errors = []
notes = []


def fail(label, msg):
    errors.append(f"[KO] {label} : {msg}")


# Catégorie du point de vue du camp au trait -> verdict simple. Tout le reste est refusé.
VERDICT = {"win": "win", "draw": "draw", "loss": "loss"}
OPPOSITE = {"win": "loss", "loss": "win", "draw": "draw"}


def verdict(board, label):
    cat = probe(board)["category"]
    if cat not in VERDICT:
        fail(label, f"verdict « {cat} » refusé ({board.fen()})")
        return None
    return cat


def legal_board(fen, label):
    try:
        b = chess.Board(fen)
    except ValueError as e:
        fail(label, f"FEN illisible {fen} ({e})")
        return None
    if not b.is_valid():
        fail(label, f"position illégale {fen} ({b.status()!r})")
        return None
    if len(b.piece_map()) > 7:
        fail(label, f"plus de 7 pièces, invérifiable par les tables : {fen}")
        return None
    if b.halfmove_clock != 0:
        fail(label, f"compteur des 50 coups non nul : {fen}")
    return b


def check_diagram(step, label):
    b = legal_board(step["fen"], label)
    if b is None or "claim" not in step:
        return
    v = verdict(b, label)
    if v is None:
        return
    mover = "w" if b.turn == chess.WHITE else "b"
    other = "b" if mover == "w" else "w"
    actual = "draw" if v == "draw" else (mover if v == "win" else other)
    if actual != step["claim"]:
        fail(label, f"claim {step['claim']} mais les tables disent {actual} ({step['fen']})")


def check_line(step, label):
    b = legal_board(step["fen"], label)
    if b is None:
        return
    result = step["result"]
    player = b.turn
    moves = step["moves"]
    if not moves:
        fail(label, "ligne vide")
    for i, m in enumerate(moves):
        ml = f"{label} coup {i + 1} ({m['san']})"
        try:
            mv = b.parse_san(m["san"])
        except ValueError:
            fail(ml, f"coup injouable dans {b.fen()}")
            return
        if b.san(mv) != m["san"]:
            fail(ml, f"SAN non canonique, attendu {b.san(mv)}")
        d = probe(b)
        v = verdict(b, ml)
        if v is None:
            return
        by_uci = {x["uci"]: x for x in d["moves"]}
        if b.turn == player:
            if v != result:
                fail(ml, f"la position avant le coup est {v}, la ligne annonce {result} ({b.fen()})")
            keeps = sorted(u for u, x in by_uci.items() if OPPOSITE.get(x["category"]) == result)
            if mv.uci() not in keeps:
                fail(ml, f"le coup lâche le résultat {result} ({b.fen()})")
            if m.get("only") and len(keeps) != 1:
                fail(ml, f"« only » faux : {len(keeps)} coups gardent le résultat ({', '.join(keeps)})")
            if not m.get("only") and len(keeps) == 1:
                notes.append(f"{ml} : seul coup qui garde le résultat, « only » possible")
            m["keeps"] = keeps
        else:
            if m.get("only") or "keeps" in m:
                fail(ml, "« only »/« keeps » réservés aux coups de l'élève")
            cats = [OPPOSITE[x["category"]] for x in d["moves"] if x["category"] in OPPOSITE]
            if not cats:
                fail(ml, "aucune réponse adverse au verdict simple (win/draw/loss)")
                return
            best = max(cats, key=lambda c: {"loss": 0, "draw": 1, "win": 2}[c])
            got = OPPOSITE.get(by_uci[mv.uci()]["category"])
            if got != best:
                fail(ml, f"la réponse adverse n'est pas la meilleure catégorie ({got} au lieu de {best})")
            dtms = [abs(x["dtm"]) for x in d["moves"] if x.get("dtm") is not None and OPPOSITE.get(x["category"]) == best]
            mine = by_uci[mv.uci()].get("dtm")
            if best == "loss" and dtms and mine is not None and abs(mine) < max(dtms):
                notes.append(f"{ml} : défense moins tenace que possible (mat en {abs(mine)} demi-coups au lieu de {max(dtms)})")
        b.push(mv)
    end = step.get("end", "")
    # Une ligne gagnante peut finir sur un coup adverse : seul compte le verdict de la position finale.
    if result == "win":
        promoted = any(mv.promotion for mv in b.move_stack)
        # Conversion : l'élève vient de prendre la dernière pièce ou le dernier pion adverse.
        last = b.pop()
        last_capture = b.turn == player and b.is_capture(last)
        b.push(last)
        lone = len(b.pieces(chess.PAWN, not player) | b.pieces(chess.KNIGHT, not player) | b.pieces(chess.BISHOP, not player) | b.pieces(chess.ROOK, not player) | b.pieces(chess.QUEEN, not player)) == 0
        if not b.is_checkmate() and not promoted and not (last_capture and lone):
            fail(label, "une ligne gagnante finit par un mat, une promotion, ou la prise du dernier pion ou pièce adverse")
        if not b.is_checkmate():
            v = verdict(b, label)
            expected = "loss" if b.turn != player else "win"
            if v is not None and v != expected:
                fail(label, f"position finale {v} pour le camp au trait, la ligne annonce le gain ({b.fen()})")
    else:
        if b.is_checkmate():
            fail(label, "une ligne nulle ne peut pas finir par un mat")
        elif not b.is_stalemate():
            v = verdict(b, label)
            if v is not None and v != "draw":
                fail(label, f"position finale {v}, la ligne annonce la nulle ({b.fen()})")
    if re.search(r"\bpat\b", end, re.IGNORECASE) and not b.is_stalemate():
        fail(label, "le texte de fin parle de pat, la position finale n'est pas pat")


# Écriture déterministe : un coup par ligne, le reste indenté de 2 espaces.
def dump(obj, indent=0):
    pad = "  " * indent
    if isinstance(obj, dict):
        if indent >= 4 and all(not isinstance(v, (dict,)) for v in obj.values()) and "san" in obj:
            return json.dumps(obj, ensure_ascii=False)
        items = [f'{pad}  {json.dumps(k, ensure_ascii=False)}: {dump(v, indent + 1)}' for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(obj, list):
        if all(isinstance(x, str) for x in obj) and sum(len(x) for x in obj) < 60:
            return json.dumps(obj, ensure_ascii=False)
        if all(isinstance(x, list) for x in obj):
            return json.dumps(obj, ensure_ascii=False)
        items = [f"{pad}  {dump(x, indent + 1)}" for x in obj]
        return "[\n" + ",\n".join(items) + f"\n{pad}]"
    return json.dumps(obj, ensure_ascii=False)


def main():
    with open(DATA) as f:
        data = json.load(f)
    for lid, lesson in data["lessons"].items():
        for si, step in enumerate(lesson["steps"]):
            label = f"{lid} étape {si + 1}"
            if step["kind"] == "diagram":
                check_diagram(step, label)
            elif step["kind"] == "line":
                check_line(step, label)
            else:
                fail(label, f"type d'étape inconnu {step['kind']}")
    for n in notes:
        print(f"[note] {n}")
    for e in errors:
        print(e)
    if errors:
        print(f"{len(errors)} manquement(s) : JSON et tampon non modifiés.")
        sys.exit(1)
    text = dump(data) + "\n"
    with open(DATA, "w") as f:
        f.write(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    with open(STAMP, "w") as f:
        f.write(digest + "\n")
    lines = sum(1 for l in data["lessons"].values() for s in l["steps"] if s["kind"] == "line")
    print(f"OK : {len(data['lessons'])} leçons, {lines} lignes vérifiées par les tables. Tampon {digest[:12]}.")


if __name__ == "__main__":
    main()
