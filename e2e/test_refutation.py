"""E2E « réfutation expliquée » : bouton « Pourquoi ? » sur une faute (bilan d'Analyse, Mes erreurs).

Deux parties :
1. Textes, sans navigateur : `src/lib/refutation.ts` est bundlé avec rolldown puis exercé par
   `e2e/refutation_texts.mjs` sur environ 2 000 puzzles lichess (position, coup fautif de
   l'adversaire, puis la réfutation réelle du puzzle comme ligne du moteur) et des cas à la main.
   Chaque fait de chaque demi-coup est recalculé par un oracle python-chess indépendant
   (`coach_oracle.py` + compléments ci-dessous), puis chaque phrase est confrontée à ses faits.
2. Affichage, iPhone 14 Pro standalone (393x852, 393x660) et 1440x900 : partie du berger semée
   dans IndexedDB (Noirs, 3...♞f6?? 4.♕xf7#), bilan guidé, « Pourquoi ? », lecture et contrôles,
   bon coup ; Mes erreurs (bouton après le verdict) ; prefers-reduced-motion.

Usage : npm run test:e2e -- --suite refutation   (REFUTATION_TEXTS_ONLY=1 pour la partie 1 seule)
"""
import json
import os
import re
import subprocess
import tempfile

import chess

import coach_oracle as oracle
from helpers import BASE, SHOTS, Checker, HOLD_BESTMOVE, desktop_context, mobile_context, overflow_x

ck = Checker("refutation")
check = ck.check

E2E = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
NB = " "
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
LETTER = oracle.LETTER
DEF = {"p": "le pion", "n": "le cavalier", "b": "le fou", "r": "la tour", "q": "la dame", "k": "le roi"}
SAN_EN = re.compile(r"\b[KQRBN]x?[a-h][1-8]")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
MIN_PLIES, MAX_PLIES, MAX_RECAPTURES = 4, 8, 2


# ---------------------------------------------------------------------------------------------
# Oracle python-chess des faits d'un demi-coup (indépendant de refutation.ts et motifs.ts)
# ---------------------------------------------------------------------------------------------
def material(board, color):
    return sum((1 if p.color == color else -1) * VALUES.get(p.piece_type, 0) for p in board.piece_map().values())


def has_mate_in_1(board):
    for m in board.legal_moves:
        board.push(m)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            return True
    return False


def mating_sans(board):
    out = set()
    for m in board.legal_moves:
        san = board.san(m)
        board.push(m)
        if board.is_checkmate():
            out.add(san)
        board.pop()
    return out


def chessjs_game_over(board):
    """isGameOver de chess.js sur une position sans historique : mat, pat, matériel, 50 coups."""
    return board.is_checkmate() or board.is_stalemate() or board.is_insufficient_material() or board.halfmove_clock >= 100


def facts(fen, uci, last_cap):
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        return None
    pov = board.turn
    forced = board.legal_moves.count() == 1
    before_mate1 = has_mate_in_1(board)
    victim = board.piece_type_at(move.to_square) or (chess.PAWN if board.is_en_passant(move) else None)
    board.push(move)
    mate, check_ = board.is_checkmate(), board.is_check() and not board.is_checkmate()
    capture = None
    if victim:
        net = VALUES[victim] - oracle.see(board, move.to_square)
        kind = "reprise" if last_cap == chess.square_name(move.to_square) else "gain" if net >= 2 else "echange" if net >= -1 else "sacrifice"
        clean = not any(m.to_square == move.to_square for m in board.legal_moves)
        capture = {"kind": kind, "net": net, "clean": clean, "captured": LETTER[victim], "square": chess.square_name(move.to_square)}
    threat = None
    if not mate and not check_ and not chessjs_game_over(board):
        board.push(chess.Move.null())
        sans = mating_sans(board)
        board.pop()
        if sans and not before_mate1:
            threat = sans
    f = oracle.fork(fen, uci)
    lm = oracle.line_motif(fen, uci)
    out = {
        "mate": mate, "check": check_, "stalemate": board.is_stalemate(),
        "backRank": mate and oracle.back_rank_mate(fen, uci),
        "capture": capture, "fork": sorted(f) if f else None, "line": list(lm) if lm else None,
        "passed": oracle.passed_pawn_created(fen, uci),
        "promotion": LETTER[move.promotion] if move.promotion else None,
        "threat": threat, "forced": forced, "pov": pov,
    }
    kinds = ["mate"] if mate else []
    if out["backRank"]:
        kinds.append("backRank")
    if out["promotion"]:
        kinds.append("promotion")
    if out["capture"]:
        kinds.append("capture")
    if check_:
        kinds.append("check")
    elif out["stalemate"]:
        kinds.append("stalemate")
    for k in ("fork", "line", "passed", "threat"):
        if out[k]:
            kinds.append(k)
    out["kinds"] = kinds
    return out


def ref_length(fen_after, pv):
    """Règle de longueur, réécrite : mat dans les 8 premiers, sinon dernier changement de matériel
    dans les 8 premiers (au moins 4), puis reprises sur la même case (2 au plus)."""
    board = chess.Board(fen_after)
    plies = []
    for i, u in enumerate(pv[:MAX_PLIES + MAX_RECAPTURES]):
        if chessjs_game_over(board):
            break
        m = chess.Move.from_uci(u) if len(u) >= 4 and re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", u) else None
        if m is None or m not in board.legal_moves:
            break
        cap = board.is_capture(m)
        board.push(m)
        plies.append((cap, m.to_square, m.promotion))
        if board.is_checkmate() and i < MAX_PLIES:
            return i + 1
    last = max([i + 1 for i, (c, _, pr) in enumerate(plies[:MAX_PLIES]) if c or pr] or [0])
    n = min(min(MAX_PLIES, len(plies)), max(MIN_PLIES, last))
    while 0 < n < len(plies) and n < MAX_PLIES + MAX_RECAPTURES and plies[n - 1][0] and plies[n][0] and plies[n][1] == plies[n - 1][1]:
        n += 1
    return n


KEYWORDS = {
    "capture": re.compile(r"\b(?:re)?prend (?:le|la) "),
    "mate": re.compile(r"échec et mat", re.I),
    "check": re.compile(r"donne échec\.|(?:^|\s)Échec\."),
    "stalemate": re.compile(r"\bPat\b"),
    "backRank": re.compile(r"Mat du couloir"),
    "fork": re.compile(r"Fourchette"),
    "line": re.compile(r"Clouage|Enfilade"),
    "promotion": re.compile(r"Promotion en"),
    "passed": re.compile(r"devient passé"),
    "threat": re.compile(r"Nouvelle menace"),
}


def audit_step(label, step, last_cap, player, base, shown=2):
    """Faits identiques à l'oracle, puis texte ⇔ faits. Renvoie (liste d'écarts, genres affichés)."""
    errs = []
    f, o = step["facts"], facts(step["fenBefore"], step["uci"], last_cap)
    if o is None:
        return [f"{label} coup illégal pour python-chess"], []
    for k in ("mate", "check", "stalemate", "backRank", "promotion", "forced", "kinds"):
        if f[k] != o[k]:
            errs.append(f"{label} {k} : TS {f[k]} / oracle {o[k]}")
    if f["capture"] != o["capture"]:
        errs.append(f"{label} prise : TS {f['capture']} / oracle {o['capture']}")
    if sorted(f["fork"] or []) != (o["fork"] or []):
        errs.append(f"{label} fourchette : TS {f['fork']} / oracle {o['fork']}")
    if f["line"] != o["line"]:
        errs.append(f"{label} ligne : TS {f['line']} / oracle {o['line']}")
    if bool(f["passed"]) != o["passed"]:
        errs.append(f"{label} pion passé : TS {f['passed']} / oracle {o['passed']}")
    if (f["threat"] is None) != (o["threat"] is None) or (f["threat"] and f["threat"] not in o["threat"]):
        errs.append(f"{label} menace : TS {f['threat']} / oracle {o['threat']}")
    after = chess.Board(step["fenAfter"])
    if step["material"] != material(after, player) - base:
        errs.append(f"{label} bilan matériel : TS {step['material']} / oracle {material(after, player) - base}")
    text = step["text"]
    shown_kinds = o["kinds"][:shown]
    for k, rx in KEYWORDS.items():
        if bool(rx.search(text)) != (k in shown_kinds):
            errs.append(f"{label} phrase « {k} » {'absente' if k in shown_kinds else 'sans fait'} : « {text[:90]} »")
    c = o["capture"]
    if c and "capture" in shown_kinds:
        want = f"{DEF[c['captured']]} en {c['square']}"
        if want not in text:
            errs.append(f"{label} prise mal nommée (attendu « {want} ») : « {text[:90]} »")
        if ("rien ne peut reprendre" in text) != (c["clean"] and c["kind"] != "reprise"):
            errs.append(f"{label} « rien ne peut reprendre » faux : « {text[:90]} »")
        if ("reprend " in text) != (c["kind"] == "reprise"):
            errs.append(f"{label} « reprend » faux : « {text[:90]} »")
    if o["fork"] and "fork" in shown_kinds and not all(DEF[t] in text for t in o["fork"]):
        errs.append(f"{label} cibles de la fourchette absentes : « {text[:90]} »")
    if not shown_kinds and step.get("actor"):
        want = ("la suite la plus forte selon le moteur" if step["actor"] == "opponent"
                else "ton seul coup légal" if o["forced"] else "ta meilleure défense selon le moteur")
        if want not in text and not text.startswith("Tu joues") and "le moteur évalue" not in text:
            errs.append(f"{label} phrase neutre inattendue : « {text[:90]} »")
    return errs, shown_kinds


def hygiene(texts):
    def offenders(pred):
        return [label for label, t in texts if pred(t)]

    bad = offenders(lambda t: SAN_EN.search(t) is not None)
    check("[textes] aucun SAN anglais (figurines partout)", not bad, f"({len(bad)} : {bad[:3]})")
    bad = offenders(lambda t: "—" in t)
    check("[textes] aucun tiret cadratin", not bad, f"({bad[:3]})")
    bad = offenders(lambda t: re.search(r"undefined|NaN|\bnull\b|\[object|\{[a-z_]+\}", t) is not None)
    check("[textes] ni undefined, ni NaN, ni marqueur non rempli", not bad, f"({bad[:3]})")
    bad = offenders(lambda t: t.strip() == "")
    check("[textes] aucun texte vide", not bad, f"({bad[:3]})")
    bad = offenders(lambda t: re.search(r"[^  \s][ ]+[!?;:]", t) is not None or re.search(r" [!?;:]", t) is not None)
    check("[textes] espace insécable avant ! ? ; :", not bad, f"({len(bad)} : {bad[:3]})")
    bad = offenders(lambda t: re.search(r"\bvous\b", t, re.I) is not None)
    check("[textes] tutoiement (jamais « vous »)", not bad, f"({bad[:3]})")
    longest = max(((len(s), label, s) for label, t in texts for s in SENTENCE_SPLIT.split(t)), default=(0, "", ""))
    check("[textes] chaque phrase fait 140 caractères au plus", longest[0] <= 140, f"(max {longest[0]} : {longest[1]} « {longest[2][:60]}… »)")
    longest = max(((len(t), label) for label, t in texts), default=(0, ""))
    check("[textes] chaque commentaire fait 200 caractères au plus (bulle)", longest[0] <= 200, f"(max {longest})")


def audit_ref(r):
    """Écarts d'une réfutation complète (coup fautif + ligne) contre l'oracle, et genres affichés."""
    errs, kinds = [], []
    inp = r["input"]
    player = chess.Board(inp["fenBefore"]).turn
    base = material(chess.Board(inp["fenBefore"]), player)
    e, k = audit_step(f"{r['label']} coup joué", r["played"], None, player, base)
    errs += e
    kinds += k
    n = ref_length(r["played"]["fenAfter"], inp["pv"])
    if len(r["line"]) != n:
        errs.append(f"{r['label']} longueur {len(r['line'])}, oracle {n}")
    last_cap = r["played"]["facts"]["capture"]["square"] if r["played"]["facts"]["capture"] else None
    for i, s in enumerate(r["line"]):
        if s["uci"] != inp["pv"][i]:
            errs.append(f"{r['label']}[{i}] coup {s['uci']} au lieu de {inp['pv'][i]}")
        e, k = audit_step(f"{r['label']}[{i}]", s, last_cap, player, base)
        errs += e
        kinds += k
        last_cap = s["facts"]["capture"]["square"] if s["facts"]["capture"] else None
    end = chess.Board((r["line"][-1] if r["line"] else r["played"])["fenAfter"])
    summary = r["summary"]
    if end.is_checkmate():
        want = "ton roi est mat" if end.turn == player else "le roi adverse est mat"
        if want not in summary:
            errs.append(f"{r['label']} bilan sans le mat : « {summary} »")
    elif r["line"]:
        d = material(end, player) - material(chess.Board(inp["fenBefore"]), player)
        want = f"tu perds {-d} point" if d < 0 else f"tu gagnes {d} point" if d > 0 else "le matériel reste inchangé"
        if want not in summary or f"sur la suite de {len(r['line']) + 1} demi-coup" not in summary:
            errs.append(f"{r['label']} bilan matériel faux (attendu « {want} ») : « {summary} »")
    return errs, kinds


def texts_part():
    bundle_dir = tempfile.mkdtemp(prefix="chesslocal-refutation-")
    bundle = os.path.join(bundle_dir, "bundle.mjs")
    r = subprocess.run([ROLLDOWN, os.path.join(E2E, "refutation_texts_entry.ts"), "--format", "esm", "--file", bundle],
                       cwd=ROOT, capture_output=True, text=True)
    if not check("[textes] bundle rolldown", r.returncode == 0, (r.stderr or r.stdout)[-300:]):
        return
    r = subprocess.run(["node", os.path.join(E2E, "refutation_texts.mjs"), bundle, os.path.join(ROOT, "public", "puzzles.json")],
                       cwd=ROOT, capture_output=True, text=True)
    if not check("[textes] harnais Node", r.returncode == 0, r.stderr[-400:]):
        return
    data = json.loads(r.stdout)
    check("[textes] aucune exception dans le harnais", not data["errors"], f"({data['errors'][:2]})")
    check("[textes] bornes de longueur 4 à 8 demi-coups", (data["minPlies"], data["maxPlies"]) == (MIN_PLIES, MAX_PLIES), f"({data['minPlies']}, {data['maxPlies']})")

    puzzles = [p for p in data["puzzles"] if p["ok"]]
    check("[puzzles] réfutations construites sur des puzzles lichess", len(puzzles) >= 1900, f"({len(puzzles)}/{len(data['puzzles'])})")
    errors, counts = [], {}
    for p in puzzles:
        e, kinds = audit_ref(p)
        errors += e
        for k in kinds:
            counts[k] = counts.get(k, 0) + 1
    check(f"[puzzles] faits, phrases et bilans identiques à l'oracle python-chess ({sum(counts.values())} faits affichés)",
          not errors, f"({len(errors)} : {errors[:3]})")
    mins = {"capture": 1000, "mate": 500, "check": 500, "backRank": 25, "fork": 100, "line": 50, "promotion": 20, "passed": 30, "threat": 100}
    for k, n in mins.items():
        check(f"[puzzles] fait « {k} » branché (≥ {n} affichés)", counts.get(k, 0) >= n, f"({counts.get(k, 0)})")
    lengths = [len(p["line"]) for p in puzzles]
    check("[puzzles] lignes de 1 à 10 demi-coups, jamais plus", lengths and min(lengths) >= 1 and max(lengths) <= MAX_PLIES + MAX_RECAPTURES,
          f"(min {min(lengths)}, max {max(lengths)})")

    hand = {h["label"]: h for h in data["hand"]}
    for h in data["hand"]:
        if h["ok"]:
            e, _ = audit_ref(h)
            check(f"[main] {h['label']} : faits et phrases conformes à l'oracle", not e, f"({e[:2]})")
    b = hand["berger"]
    check("[berger] réfutation en un demi-coup : ♕xf7#", [s["uci"] for s in b["line"]] == ["h5f7"] and "♕xf7#" in b["line"][0]["text"], f"({[s['text'] for s in b['line']]})")
    check("[berger] le commentaire dit le mat", "échec et mat" in b["line"][0]["text"].lower(), f"({b['line'][0]['text']})")
    check("[berger] bilan : ton roi est mat", "ton roi est mat" in b["summary"], f"({b['summary']})")
    check("[berger] coup joué : éval « mat en 1 contre toi »", f"mat{NB}en{NB}1 contre toi" in b["played"]["text"], f"({b['played']['text']})")
    check("[berger] bon coup g6 : il empêche ♕xf7#", b["best"] and b["best"]["prevention"] == "illegal" and "Il empêche ♕xf7#" in b["best"]["text"], f"({b['best']})")
    e7 = hand["berger_e7"]
    check("[berger] bon coup ♛e7 : ♕xf7 ne serait plus mat", e7["best"] and e7["best"]["prevention"] == "no_mate" and "ne serait plus mat" in e7["best"]["text"], f"({e7['best']})")
    for h in (b, e7):
        bd = chess.Board(h["best"]["fenAfter"])
        m = chess.Move.from_uci("h5f7")
        legal = m in bd.legal_moves and bd.piece_type_at(chess.F7) is not None
        mate = False
        if legal:
            bd.push(m)
            mate = bd.is_checkmate()
        want = "illegal" if not (m in chess.Board(h["best"]["fenAfter"]).legal_moves) else "no_mate" if not mate else None
        check(f"[{h['label']}] prévention recalculée par python-chess ({want})", h["best"]["prevention"] == want, f"({h['best']['prevention']})")
    fk = hand["fourchette"]
    check("[fourchette] ♘e7+ annoncé comme fourchette du roi et de la dame",
          "Fourchette" in fk["line"][0]["text"] and "le roi" in fk["line"][0]["text"] and "la dame" in fk["line"][0]["text"], f"({fk['line'][0]['text']})")
    check("[fourchette] bilan : tu perds 9 points", "tu perds 9 points" in fk["summary"], f"({fk['summary']})")
    check("[fourchette] badge matériel -9 après ♘xc6", fk["line"][2]["material"] == -9, f"({[s['material'] for s in fk['line']]})")
    check("[fourchette] le bon coup mate : pas d'éval comparée", f"Moteur{NB}:" not in fk["best"]["text"] and "échec et mat" in fk["best"]["text"], f"({fk['best']['text']})")
    pat = hand["pat"]
    check("[pat] coup fautif qui pate : aucune ligne, bilan « pat »", pat["line"] == [] and "pat" in pat["summary"].lower(), f"({pat['summary']})")
    check("[pv vide] bilan honnête sans ligne", "n'a pas donné de suite" in hand["pv_vide"]["summary"], f"({hand['pv_vide']['summary']})")
    check("[pv illégale] la ligne s'arrête au premier coup illégal", hand["pv_illegale"]["line"] == [], f"({len(hand['pv_illegale']['line'])})")
    pr = hand["proche"]
    check("[proche] le moteur juge le coup joué aussi bon : pas de « bon coup » affirmé",
          pr["best"]["close"] and "presque aussi bon" in pr["best"]["text"], f"({pr['best']['text']})")
    check("[échange] arrêt au dernier changement de matériel, 4 demi-coups au moins", len(hand["echange"]["line"]) == 4, f"({len(hand['echange']['line'])})")
    check("[échange coupé] la reprise du 9e demi-coup est montrée", len(hand["echange_coupe"]["line"]) == 9, f"({len(hand['echange_coupe']['line'])})")
    check("[illégal] coup joué illégal : pas de réfutation", hand["illegal"]["ok"] is False)
    sc = {s["k"]: s for s in data["scores"]}
    check("[éval] score du trait adverse retourné pour le joueur (cp)", sc["cp"]["s"] == {"cp": -120, "mate": None} and sc["cp"]["text"] == "-1,2", f"({sc['cp']})")
    check("[éval] mat adverse = « mat en 2 contre toi »", sc["mate_contre"]["text"] == f"mat{NB}en{NB}2 contre toi", f"({sc['mate_contre']})")
    check("[éval] mat du joueur = « mat en 3 pour toi »", sc["mate_pour"]["text"] == f"mat{NB}en{NB}3 pour toi", f"({sc['mate_pour']})")

    check("[matériel] variation nulle : aucune égalité absolue annoncée",
          "le matériel reste égal" not in hand["echange"]["summary"], hand["echange"]["summary"])
    unequal = hand["materiel_inegal"]
    check("[matériel] avantage initial conservé et variation nulle",
          material(chess.Board(unequal["input"]["fenBefore"]), chess.WHITE) == 5
          and unequal["line"][-1]["material"] == 0 and "reste inchangé" in unequal["summary"])
    for label, expected in (("reprise_possible", "no_take"), ("prise_inchangee", None), ("fourchette_evitee", "no_fork"), ("fourchette_conservee", None)):
        h = hand[label]
        check(f"[prévention] {label} : position légale", chess.Board(h["input"]["fenBefore"]).is_valid())
        before = facts(h["line"][0]["fenBefore"], h["line"][0]["uci"], None)
        after = facts(h["best"]["fenAfter"], h["line"][0]["uci"], None)
        actual = "no_take" if before["capture"] and before["capture"]["clean"] and not (after["capture"] and after["capture"]["clean"]) else "no_fork" if before["fork"] and not after["fork"] else None
        check(f"[prévention] {label} : oracle indépendant", actual == expected and h["best"]["prevention"] == expected, str(h["best"]))
        if expected == "no_take":
            check("[prévention] prise : commentaire limité à la reprise possible", "sans reprise possible" in h["best"]["text"])
        elif expected == "no_fork":
            check("[prévention] fourchette : commentaire conforme", "ne serait plus une fourchette" in h["best"]["text"])
        if label == "reprise_possible":
            check("[prévention] reprise légale malgré un gain matériel positif", after["capture"]["net"] > 0 and not after["capture"]["clean"])
    texts = []
    for r_ in data["puzzles"] + data["hand"]:
        if not r_["ok"]:
            continue
        texts += [(f"{r_['label']} intro", r_["intro"]), (f"{r_['label']} coup", r_["played"]["text"]), (f"{r_['label']} bilan", r_["summary"])]
        texts += [(f"{r_['label']}[{i}]", s["text"]) for i, s in enumerate(r_["line"])]
        if r_.get("best"):
            texts.append((f"{r_['label']} bon coup", r_["best"]["text"]))
    hygiene(texts)


def suite(p):
    texts_part()
    if os.environ.get("REFUTATION_TEXTS_ONLY"):
        return
    browser = p.chromium.launch(headless=True)
    browser_part(p, browser)
    browser.close()


# ---------------------------------------------------------------------------------------------
# Partie 2 : affichage
# ---------------------------------------------------------------------------------------------
# Mat du berger, côté Noirs : 3...♞f6?? 4.♕xf7#. La faute est celle du joueur (playerColor 'b').
BERGER = "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7#"
NF6 = 5  # index du demi-coup 3...♞f6

STATE_JS = """() => {
  const root = document.querySelector('[data-refutation]')
  if (!root) return null
  const body = root.querySelector('[data-refutation-text] [data-coach-body]')
  const board = root.querySelector('[id^=chessboard-]')
  const nav = root.querySelector('.border-t')
  const b = board ? board.getBoundingClientRect() : null
  return {
    kind: root.dataset.refutation,
    text: body ? body.innerText.trim() : '',
    fits: body ? body.scrollHeight <= body.clientHeight + 1 : false,
    step: (root.querySelector('[data-refutation-step]') || {}).innerText || '',
    material: (root.querySelector('[data-refutation-material]') || {}).innerText || '',
    arrows: root.querySelectorAll('svg line, svg path[marker-end], svg polygon').length,
    boardBottom: b ? b.bottom : null, boardW: b ? b.width : null,
    navTop: nav ? nav.getBoundingClientRect().top : null,
  }
}"""


def state(page):
    return page.evaluate(STATE_JS)


def seed_game(page, pgn=BERGER, color="b", result="1-0"):
    page.goto(f"{BASE}/#/archive")
    page.wait_for_timeout(800)
    return page.evaluate("""([pgn, color, result]) => new Promise((resolve, reject) => {
      const req = indexedDB.open('chess-local')
      req.onerror = () => reject(req.error)
      req.onsuccess = () => {
        const db = req.result
        const tx = db.transaction('games', 'readwrite')
        const add = tx.objectStore('games').add({
          date: Date.now(), mode: 'bot', botId: 'noa', playerColor: color, timeControl: 'illimité',
          timeClass: 'unlimited', pgn, result, termination: 'mat',
        })
        add.onsuccess = () => resolve(add.result)
        add.onerror = () => reject(add.error)
      }
    })""", [pgn, color, result])


def wait_kind(page, kind, timeout=30000):
    waited = 0
    while waited < timeout:
        st = state(page)
        if st and st["kind"] == kind:
            return st
        page.wait_for_timeout(200)
        waited += 200
    return state(page)


def open_guided_at_nf6(page, tag):
    gid = seed_game(page)
    page.goto(f"{BASE}/#/analyse?game={gid}&review=1")
    if not ck.appears(f"[{tag}] bilan calculé", page, "text=Démarrer le bilan", timeout=240000):
        return False
    page.click("text=Démarrer le bilan")
    page.wait_for_timeout(500)
    why = page.locator(".fixed button", has_text="Pourquoi")
    for i in range(NF6):
        if i == 4:
            check(f"[{tag}] « Pourquoi ? » grisé sur un coup adverse (3.♕h5)", why.count() == 1 and not why.is_enabled(), f"({why.count()})")
        page.locator(".fixed button", has_text="Suivant").click()
        page.wait_for_timeout(250)
    return True


def guided_flow(p, browser, tag, standalone, shots):
    ctx = mobile_context(p, browser, ck, standalone=standalone)
    page = ctx.new_page()
    if not open_guided_at_nf6(page, tag):
        ctx.close()
        return
    why = page.locator(".fixed button", has_text="Pourquoi")
    check(f"[{tag}] « Pourquoi ? » actif sur la gaffe 3...♞f6", why.count() == 1 and why.is_enabled(), f"({why.count()})")
    check(f"[{tag}] barre du bilan guidé sans débordement", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    page.screenshot(path=f"{SHOTS}/refutation_guided_{shots}.png")
    why.click()
    if not ck.appears(f"[{tag}] calque de réfutation ouvert", page, "[data-refutation]", timeout=5000):
        ctx.close()
        return
    st = state(page)
    check(f"[{tag}] départ : position avant la faute, flèche du coup joué", st["kind"] == "intro" and st["arrows"] > 0 and "♞f6" in st["text"], f"({st})")
    # Lecture automatique (pas de réduction de mouvement) : la suite défile jusqu'au bilan.
    st = wait_kind(page, "summary", timeout=60000)
    check(f"[{tag}] lecture automatique jusqu'au bilan", st and st["kind"] == "summary", f"({st and st['kind']})")
    check(f"[{tag}] bilan : ton roi est mat", st and "ton roi est mat" in st["text"], f"({st and st['text']})")
    page.wait_for_timeout(2500)
    check(f"[{tag}] la lecture s'arrête au bilan (pas de saut vers le bon coup)", state(page)["kind"] == "summary", f"({state(page)['kind']})")
    # Contrôles : début, puis coup par coup.
    page.get_by_role("button", name="Début").click()
    page.wait_for_timeout(300)
    check(f"[{tag}] ⏮ revient au départ", state(page)["kind"] == "intro")
    page.get_by_role("button", name="Coup suivant").click()
    page.wait_for_timeout(300)
    st = state(page)
    check(f"[{tag}] variation matérielle nulle correctement nommée", st["material"] == "Matériel inchangé", st["material"])
    check(f"[{tag}] ▶ : le coup fautif, éval « mat en 1 contre toi »", st["kind"] == "played" and "mat en 1 contre toi" in st["text"].replace(NB, " "), f"({st['text']})")
    page.get_by_role("button", name="Coup suivant").click()
    page.wait_for_timeout(300)
    st = state(page)
    check(f"[{tag}] la réfutation : ♕xf7#, échec et mat", st["kind"] == "line" and "♕xf7#" in st["text"] and "échec et mat" in st["text"], f"({st})")
    check(f"[{tag}] flèche de la réfutation sur l'échiquier", st["arrows"] > 0, f"({st['arrows']})")
    check(f"[{tag}] badge matériel du joueur (-1, le pion f7)", "-1" in st["material"], f"({st['material']})")
    check(f"[{tag}] compteur de demi-coups 1/1", "1/1" in st["step"], f"({st['step']})")
    check(f"[{tag}] commentaire lisible sans défiler", st["fits"], f"({st['text']})")
    check(f"[{tag}] échiquier entier au-dessus de la barre de contrôle", st["boardBottom"] is not None and st["navTop"] is not None and st["boardBottom"] <= st["navTop"] + 0.5,
          f"({st['boardBottom']} / {st['navTop']})")
    page.screenshot(path=f"{SHOTS}/refutation_line_{shots}.png")
    page.get_by_role("button", name="Coup précédent").click()
    page.wait_for_timeout(300)
    check(f"[{tag}] ◀ revient au coup fautif", state(page)["kind"] == "played")
    page.locator("[data-refutation] button", has_text="Le bon coup").click()
    page.wait_for_timeout(300)
    st = state(page)
    check(f"[{tag}] bon coup : justification vérifiée (empêche ♕xf7# ou ♕xf7 n'est plus mat)",
          st["kind"] == "best" and re.search(r"Il empêche ♕xf7#|♕xf7 ne serait plus mat", st["text"]) is not None, f"({st['text']})")
    check(f"[{tag}] position du bon coup correctement nommée", st["step"] == "Après le bon coup", st["step"])
    check(f"[{tag}] bon coup : flèche verte", st["arrows"] > 0)
    check(f"[{tag}] bon coup : commentaire lisible sans défiler", st["fits"], f"({st['text']})")
    check(f"[{tag}] calque sans débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    page.screenshot(path=f"{SHOTS}/refutation_best_{shots}.png")
    page.locator("[data-refutation] button", has_text="Compris").click()
    page.wait_for_timeout(300)
    check(f"[{tag}] « Compris » ferme le calque, retour au bilan guidé", page.locator("[data-refutation]").count() == 0 and why.is_visible())
    ctx.close()


def reduced_motion(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True, reduced_motion="reduce")
    ctx.add_init_script(HOLD_BESTMOVE)
    ctx.add_init_script("""(() => {
      const Native = window.Worker
      window.__uciCommands = []
      window.__terminatedWorkers = 0
      window.Worker = class extends Native {
        postMessage(message, ...args) {
          window.__uciCommands.push(message)
          return super.postMessage(message, ...args)
        }
        terminate() { window.__terminatedWorkers++; return super.terminate() }
      }
    })()""")
    page = ctx.new_page()
    if not open_guided_at_nf6(page, "réduit"):
        ctx.close()
        return
    page.evaluate("window.__heldUci = []")
    page.locator(".fixed button", has_text="Pourquoi").click()
    ck.appears("[cycle] calcul ouvert", page, "[data-refutation]", timeout=5000)
    page.wait_for_timeout(300)
    stopped = page.evaluate("window.__terminatedWorkers")
    page.keyboard.press("Escape")
    check("[cycle] fermer pendant le calcul détruit le worker", page.evaluate("window.__terminatedWorkers") == stopped + 1)
    page.evaluate("window.__heldUci = null")
    page.locator(".fixed button", has_text="Pourquoi").click()
    ck.appears("[réduit] calque ouvert", page, "[data-refutation]", timeout=5000)
    if not ck.appears("[réduit] calcul terminé", page, '[data-refutation] button[aria-label="Lecture"]:enabled', timeout=60000):
        ctx.close()
        return
    page.wait_for_timeout(5000)
    check("[réduit] prefers-reduced-motion : aucune lecture automatique", state(page)["kind"] == "intro", f"({state(page)['kind']})")
    check("[réduit] profondeur effective 12 avec le réglage rapide", page.evaluate("window.__uciCommands.includes('go depth 12')"))
    check("[réduit] bouton Lecture proposé", page.get_by_role("button", name="Lecture").is_enabled())
    page.evaluate("""() => {
      window.__stepTimes = [performance.now()]
      const root = document.querySelector('[data-refutation]')
      const observer = new MutationObserver(() => {
        window.__stepTimes.push(performance.now())
        if (root.dataset.refutation === 'summary') observer.disconnect()
      })
      observer.observe(root, {attributes: true, attributeFilter: ['data-refutation']})
    }""")
    page.get_by_role("button", name="Lecture").click()
    st = wait_kind(page, "summary", timeout=20000)
    gaps = page.evaluate("window.__stepTimes.slice(1).map((t, i) => t - window.__stepTimes[i])")
    check("[réduit] cadence de lecture 1,8 s (tolérance de charge)", len(gaps) == 3 and all(1700 <= g <= 5000 for g in gaps), str(gaps))
    check("[réduit] Lecture lance le déroulé à la demande", st and st["kind"] == "summary", f"({st and st['kind']})")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    check("[réduit] Échap ferme le calque", page.locator("[data-refutation]").count() == 0)
    ctx.close()


def mes_erreurs(p, browser):
    """Le bilan du berger a rangé 3...♞f6 dans Mes erreurs : « Pourquoi ? » après le verdict seulement."""
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    gid = seed_game(page)
    page.goto(f"{BASE}/#/analyse?game={gid}&review=1")
    if not ck.appears("[erreurs] bilan calculé", page, "text=Démarrer le bilan", timeout=240000):
        ctx.close()
        return
    page.wait_for_timeout(800)
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1200)
    page.locator("button", has_text="Mes erreurs").click()
    page.wait_for_timeout(1000)
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(600)
    check("[erreurs] exercice de la faute 3...♞f6 affiché", page.locator("text=Trouve mieux").is_visible())
    check("[erreurs] pas de « Pourquoi ? » avant le verdict (pas de solution soufflée)", page.locator("button", has_text="Pourquoi").count() == 0)
    # Un coup qui ne pare pas le mat : 3...a6.
    page.locator("[data-square='a7']").click()
    page.wait_for_timeout(150)
    page.locator("[data-square='a6']").click()
    ck.appears("[erreurs] verdict rendu", page, "text=Raté", timeout=60000)
    btn = page.locator("button", has_text="Pourquoi")
    check("[erreurs] « Pourquoi ? » après le verdict", btn.count() == 1 and btn.is_visible())
    verdict = page.locator("text=Raté").bounding_box()
    check("[erreurs] barre du verdict visible sans défiler (852)", verdict is not None and verdict["y"] + verdict["height"] <= 852, f"({verdict})")
    page.screenshot(path=f"{SHOTS}/refutation_mistake_852.png")
    btn.click()
    ck.appears("[erreurs] calque ouvert", page, "[data-refutation]", timeout=5000)
    st = wait_kind(page, "summary", timeout=60000)
    check("[erreurs] la réfutation du berger se déroule jusqu'au mat", st and "ton roi est mat" in st["text"], f"({st and st['text']})")
    page.locator("[data-refutation] button", has_text="Le bon coup").click()
    page.wait_for_timeout(300)
    st = state(page)
    check("[erreurs] bon coup enregistré justifié", st["kind"] == "best" and re.search(r"Il empêche ♕xf7#|♕xf7 ne serait plus mat", st["text"]) is not None, f"({st['text']})")
    page.locator("[data-refutation] header button").click()
    page.wait_for_timeout(300)
    check("[erreurs] « ← Retour » rend l'exercice, verdict intact", page.locator("[data-refutation]").count() == 0 and page.locator("text=Raté").is_visible())
    ctx.close()


def desktop(p, browser):
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    gid = seed_game(page)
    page.goto(f"{BASE}/#/analyse?game={gid}&review=1")
    if not ck.appears("[1440] bilan calculé", page, "text=Démarrer le bilan", timeout=240000):
        ctx.close()
        return
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(500)
    page.locator("button:visible", has_text="♞f6").first.click()
    page.wait_for_timeout(400)
    btn = page.locator("button", has_text="Pourquoi")
    check("[1440] carte du coach : « Pourquoi ? » sur la gaffe", btn.count() == 1 and btn.is_visible(), f"({btn.count()})")
    btn.click()
    ck.appears("[1440] calque ouvert", page, "[data-refutation]", timeout=5000)
    check("[1440] dialogue modal natif ouvert", page.locator("dialog[data-refutation]").evaluate("el => el.matches(':modal')"))
    page.locator("[data-refutation] header button").focus()
    page.keyboard.press("Shift+Tab")
    check("[1440] le focus reste dans le dialogue", page.evaluate("!!document.activeElement.closest('[data-refutation]')"))
    page.keyboard.press("Tab")
    check("[1440] Tab revient au premier contrôle", page.locator("[data-refutation] header button").evaluate("el => el === document.activeElement"))
    st = wait_kind(page, "summary", timeout=60000)
    check("[1440] réfutation jusqu'au mat", st and "ton roi est mat" in st["text"], f"({st and st['text']})")
    check("[1440] échiquier entier au-dessus de la barre de contrôle", st and st["boardBottom"] <= st["navTop"] + 0.5 and st["boardW"] >= 400, f"({st})")
    check("[1440] aucun débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    page.screenshot(path=f"{SHOTS}/refutation_1440.png")
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(300)
    check("[1440] flèche gauche du clavier : demi-coup précédent", state(page)["kind"] == "line", f"({state(page)['kind']})")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    check("[1440] Échap ferme le calque", page.locator("[data-refutation]").count() == 0)
    check("[1440] focus rendu au bouton Pourquoi", btn.evaluate("el => el === document.activeElement"))
    ctx.close()


def browser_part(p, browser):
    guided_flow(p, browser, "852", standalone=True, shots="852")
    guided_flow(p, browser, "660", standalone=False, shots="660")
    reduced_motion(p, browser)
    mes_erreurs(p, browser)
    desktop(p, browser)


ck.run(suite)
