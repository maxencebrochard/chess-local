"""E2E « Qu'est-ce qu'il menace ? » : alerte du coach en partie contre un bot quand le dernier coup
adverse crée une vraie menace (src/lib/threat.ts, intégrée à src/pages/Jouer).

Deux volets :
1. Détection, sans navigateur : `e2e/threat_cases.mjs` fait tourner la vraie `findThreat` sur le
   vrai Stockfish WASM (Node, voir scripts/bots-node.mjs) pour des cas écrits à la main et des
   positions de puzzles lichess. Un oracle python-chess, écrit ici sans rien partager avec le
   TypeScript, rejuge chaque cas sur les mêmes scores et la même ligne (même verdict, même type,
   mêmes cases), puis revérifie chaque menace annoncée sur l'échiquier (mat par force brute,
   prise légale d'une pièce du joueur, cases cibles occupées).
2. Navigateur (iPhone 14 Pro, PWA standalone 393x852, onglet 393x660, et 1440x900) : parties
   restaurées par l'instantané `chess-local-play-game`, donc des positions exactes ; question,
   bonne et mauvaise réponse, « Je ne sais pas », aucune alerte sur les témoins, pendule suspendue,
   bullet, réglage par défaut, prémouvement, rechargement, lignes `learnSessions`, carte de Stats.

Usage : npm run test:e2e -- --suite menace   (aussi en `npm run test:e2e:dev`, StrictMode)
"""
import json
import os
import shutil
import subprocess
import tempfile

import chess

import coach_oracle as oracle
from helpers import BASE, HOLD_BESTMOVE, Checker, desktop_context, mobile_context, overflow_x, shot, tap_move, tap_square

ck = Checker("menace")
check = ck.check

E2E = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E)

MIN_CP = 200
CP_CAP = 3000
MATE_MAX = 2
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}


def board_after(sans):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    return b


def case_from_sans(cid, sans):
    """Cas « dernier coup adverse » : position avant le dernier coup et ce coup."""
    b = board_after(sans)
    last = b.pop()
    return {"id": cid, "fenPrev": b.fen(), "lastUci": last.uci()}


# Cas à la main : (id, cas, attendu). Attendu : None (aucune alerte), un veto ('check',
# 'recapture'), ou (types acceptés, cases qui doivent être acceptées).
HAND = [
    ("berger", case_from_sans("berger", ["e4", "e5", "Bc4", "Nc6", "Qh5"]), ({"mat"}, {"f7", "e8"})),
    ("fried-liver", case_from_sans("fried-liver", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"]), ({"fourchette", "prise"}, {"f7"})),
    ("dame-pion", case_from_sans("dame-pion", ["e4", "f5", "Qh5+", "g6"]), ({"prise"}, {"h5"})),
    # Rien à gagner, ou trop peu : un pion attaqué, un fou défendu.
    ("pion", case_from_sans("pion", ["e4", "e5", "Nf3"]), None),
    ("espagnole", case_from_sans("espagnole", ["e4", "e5", "Nf3", "Nc6", "Bb5"]), None),
    ("f5", case_from_sans("f5", ["e4", "f5"]), None),
    # Échange en cours : reprendre est le réflexe, pas une question.
    ("reprise", case_from_sans("reprise", ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6"]), "recapture"),
    # Joueur en échec : son coup est forcé.
    ("echec", case_from_sans("echec", ["e4", "f5", "Qh5+"]), "check"),
    # Découverte : le cavalier noir quitte d5, le fou b7 vise la tour f3 non défendue.
    ("decouverte", {"id": "decouverte", "fenPrev": "6k1/1b3ppp/8/3n4/8/5RP1/5P1P/6K1 b - - 0 1", "lastUci": "d5f6"}, ({"decouverte"}, {"f3"})),
    # Menace préexistante : le cavalier e5 pendait déjà, le bot a joué h3 sans le prendre.
    ("preexistante", {"id": "preexistante", "fenPrev": "rnbqkb1r/pppp1ppp/8/4n3/3P4/8/PPP2PPP/RNBQKBNR w KQkq - 0 4", "lastUci": "h2h3"}, None),
    # Le joueur a lui-même un mat (Te8#) : pas de question, même si sa dame est attaquée.
    ("joueur-mate", {"id": "joueur-mate", "fenPrev": "6k1/5ppp/8/1n6/8/8/5PPP/3QR1K1 b - - 0 1", "lastUci": "b5c3"}, None),
]


def puzzle_cases(limit_fork=50, limit_any=60):
    """Positions de puzzles lichess (`fen` avant le coup du perdant, moves[0], puis le gagnant
    joue moves[1]). Fourchettes calmes : après moves[1], le perdant est le « joueur » face à une
    vraie menace. Positions quelconques (un puzzle sur 997) : les deux coups, dans les deux sens."""
    with open(os.path.join(ROOT, "public", "puzzles.json")) as f:
        rows = json.load(f)
    forks, anyc = [], []
    for n, (pid, fen, moves, _rating, themes) in enumerate(rows):
        mv = moves.split()
        if len(mv) < 4:
            continue
        b = chess.Board(fen)
        if len(anyc) < limit_any and n % 997 == 0:
            anyc.append({"id": f"pz0-{pid}", "fenPrev": fen, "lastUci": mv[0]})
        b.push_uci(mv[0])
        m1 = chess.Move.from_uci(mv[1])
        if len(anyc) < limit_any and n % 997 == 0 and not b.gives_check(m1):
            anyc.append({"id": f"pz1-{pid}", "fenPrev": b.fen(), "lastUci": mv[1]})
        if b.gives_check(m1) or b.is_capture(m1):
            continue
        if "fork" in themes.split() and len(forks) < limit_fork:
            forks.append({"id": f"pzf-{pid}", "fenPrev": b.fen(), "lastUci": mv[1]})
        if len(forks) >= limit_fork and len(anyc) >= limit_any:
            break
    return forks, anyc


def obvious_threat(case):
    """Vérité terrain indépendante du moteur : après le coup nul, l'adversaire a un mat en 1, ou une
    prise nouvelle (pièce qui vient de jouer, ou ligne qu'elle a ouverte) d'une pièce d'au moins
    3 points, gagnante à l'échange statique (SEE >= 3)."""
    if veto(case):
        return False
    prev_board = chess.Board(case["fenPrev"])
    last = chess.Move.from_uci(case["lastUci"])
    pos = prev_board.copy()
    pos.push(last)
    nb = pos.copy()
    nb.push(chess.Move.null())
    moved = moved_to(prev_board, last)
    for m in nb.legal_moves:
        nb.push(m)
        mate = nb.is_checkmate()
        nb.pop()
        if mate:
            return True
        if not nb.is_capture(m) or nb.is_en_passant(m):
            continue
        target = m.to_square
        if VALUE[nb.piece_type_at(target)] < 3:
            continue
        new = m.from_square in moved or target not in prev_board.attacks(m.from_square)
        if new and oracle.see(nb, target) >= 3:
            return True
    return False


# ------------------------------------------------------------------ oracle python-chess

def value(score):
    cp, mate = score["cp"], score["mate"]
    if mate is not None:
        return 10000 - 10 * mate if mate > 0 else -10000 - 10 * mate
    return max(-CP_CAP, min(CP_CAP, cp or 0))


def captured_square(board, move):
    if board.is_en_passant(move):
        return move.to_square + (-8 if board.turn == chess.WHITE else 8)
    return move.to_square


def veto(case):
    b = chess.Board(case["fenPrev"])
    last = chess.Move.from_uci(case["lastUci"])
    if last not in b.legal_moves:
        return "illegal"
    was_capture = b.is_capture(last)
    b.push(last)
    if b.is_game_over():
        return "over"
    if b.is_check():
        return "check"
    if was_capture:
        for m in b.legal_moves:
            if m.to_square != last.to_square or not b.is_capture(m):
                continue
            gain = VALUE[b.piece_type_at(last.to_square)]
            b.push(m)
            rest = oracle.see(b, last.to_square)
            b.pop()
            if gain - rest >= 0:
                return "recapture"
    return None


def moved_to(prev_board, last):
    rank = chess.square_rank(last.to_square)
    if prev_board.is_kingside_castling(last):
        return {last.to_square, chess.square(5, rank)}
    if prev_board.is_queenside_castling(last):
        return {last.to_square, chess.square(3, rank)}
    return {last.to_square}


def material_gain(line):
    """Matériel gagné par l'adversaire sur la ligne (pion = 1, promotion comprise) : meilleur bilan
    après une réponse du joueur, ou après le dernier coup de la ligne."""
    bal, best = 0, None
    for i, (bd, m) in enumerate(line):
        sign = 1 if i % 2 == 0 else -1
        if bd.is_capture(m):
            bal += sign * VALUE[bd.piece_type_at(captured_square(bd, m))]
        if m.promotion:
            bal += sign * (VALUE[m.promotion] - 1)
        if i % 2 == 1 or i == len(line) - 1:
            settled = bal
            if i % 2 == 0 and (bd.is_capture(m) or m.promotion):
                after = bd.copy()
                after.push(m)
                settled -= oracle.see(after, m.to_square)
            best = settled if best is None else max(best, settled)
    return best or 0


def fork_squares(fen, uci):
    """Cases des pièces fourchetées (définition de coach_oracle.fork), ou None."""
    if not oracle.fork(fen, uci):
        return None
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    pov = board.turn
    board.push(move)
    me = board.piece_type_at(move.to_square)
    out = set()
    for sq in board.attacks(move.to_square):
        p = board.piece_at(sq)
        if p and p.color != pov and p.piece_type != chess.PAWN and (
                oracle.KING_VALUES[p.piece_type] > oracle.KING_VALUES[me]
                or (not oracle.is_defended(board, sq) and sq not in board.attackers(not pov, move.to_square))):
            out.add(sq)
    return out


def line_info(fen, uci):
    """(type, {devant, derrière}) du clouage ou de l'enfilade créés par le coup, ou None."""
    lm = oracle.line_motif(fen, uci)
    if not lm:
        return None
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    board.push(move)
    return lm[0], line_squares(board, move)


def oracle_judge(case, prev, now, nul, pv):
    """Mêmes règles que judgeThreat, réécrites avec python-chess. Renvoie None ou
    (type, uci, cases acceptées, mat en n)."""
    if veto(case):
        return None
    prev_board = chess.Board(case["fenPrev"])
    last = chess.Move.from_uci(case["lastUci"])
    pos = prev_board.copy()
    pos.push(last)
    if now["mate"] is not None:
        return None
    if nul["mate"] is not None and nul["mate"] > MATE_MAX:
        return None
    v_null = value(nul)
    nb = pos.copy()
    nb.push(chess.Move.null())
    line, lb = [], nb.copy()
    for u in pv[:5]:
        m = chess.Move.from_uci(u)
        if m not in lb.legal_moves:
            break
        line.append((lb.copy(), m))
        lb.push(m)
    if not line:
        return None
    t_board, t = line[0]
    mate_in = nul["mate"] if nul["mate"] is not None and 0 < nul["mate"] <= MATE_MAX else None
    moved = moved_to(prev_board, last)
    player = pos.turn

    def disc(board, m):
        if not board.is_capture(m) or m.from_square in moved:
            return False
        p = prev_board.piece_at(m.from_square)
        return p is not None and p.piece_type == board.piece_type_at(m.from_square) and captured_square(board, m) not in prev_board.attacks(m.from_square)

    if mate_in is not None:
        linked = t.from_square in moved or (len(line) >= 2 * mate_in - 1 and line[2 * mate_in - 2][1].from_square in moved)
    else:
        linked = t.from_square in moved or disc(t_board, t)
        if t_board.is_capture(t):
            target = captured_square(t_board, t)
            tp = prev_board.piece_at(target)
            if tp and tp.color == player and oracle.is_in_bad_spot(prev_board, target):
                linked = False
    if not linked and (prev is None or v_null - value(prev) < MIN_CP):
        return None
    names = lambda sqs: {chess.square_name(x) for x in sqs}
    squares = {t.to_square}
    if mate_in is not None:
        if len(line) < 2 * mate_in - 1:
            return None
        final_board, mating = line[2 * mate_in - 2]
        after = final_board.copy()
        after.push(mating)
        if not after.is_checkmate():
            return None
        squares |= {pos.king(player), mating.to_square}
        return ("mat", t.uci(), names(squares), mate_in)
    if material_gain(line) < 2:
        return None

    def in_p(i):
        bd, m = line[i]
        sq = captured_square(bd, m)
        for j in range(i - 1, 0, -2):
            if line[j][1].to_square == sq:
                sq = line[j][1].from_square
        return sq

    caps = []
    for i in (0, 2, 4):
        if i < len(line) and line[i][0].is_capture(line[i][1]):
            sq = in_p(i)
            pp = pos.piece_at(sq)
            if pp and pp.color == player:
                bd, m = line[i]
                caps.append((VALUE[bd.piece_type_at(captured_square(bd, m))], sq))
    best_sq = None
    if caps:
        best_val = max(v for v, _ in caps)
        best_sq = next(sq for v, sq in caps if v == best_val)
        squares.add(best_sq)
    for sq, pc in pos.piece_map().items():
        if pc.color == player and pc.piece_type not in (chess.PAWN, chess.KING) and oracle.is_in_bad_spot(pos, sq) and not oracle.is_in_bad_spot(prev_board, sq):
            squares.add(sq)
    hits = lambda sqs: any(x == t.to_square or x == best_sq for x in sqs)
    lf = fork_squares(case["fenPrev"], case["lastUci"])
    if lf and hits(lf):
        return ("fourchette", t.uci(), names(squares | lf), None)
    fk = fork_squares(nb.fen(), t.uci())
    if fk:
        return ("fourchette", t.uci(), names(squares | fk), None)
    ll = line_info(case["fenPrev"], case["lastUci"])
    if ll and hits(ll[1]):
        return (ll[0], t.uci(), names(squares | ll[1]), None)
    ps = line_info(nb.fen(), t.uci())
    if ps:
        return (ps[0], t.uci(), names(squares | ps[1]), None)
    if t_board.is_capture(t):
        return ("decouverte" if disc(t_board, t) else "prise", t.uci(), names(squares), None)
    promo = next((line[i] for i in (0, 2, 4) if i < len(line) and line[i][1].promotion), None)
    if promo and best_sq is None:
        squares.add(promo[1].to_square)
        squares.add(t.from_square if t_board.piece_type_at(t.from_square) == chess.PAWN else promo[1].from_square)
        return ("promotion", t.uci(), names(squares), None)
    if best_sq is None:
        return None
    return ("gain", t.uci(), names(squares), None)


def line_squares(after, t):
    """Pièces de devant et de derrière du premier alignement adverse sur un rayon de la pièce jouée
    (hors glissade sur la ligne d'origine), avec les conditions de coach_oracle.line_motif."""
    to = t.to_square
    me = after.piece_type_at(to)
    pov = after.piece_at(to).color
    dirs = []
    if me in (chess.BISHOP, chess.QUEEN):
        dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    if me in (chess.ROOK, chess.QUEEN):
        dirs += [(1, 0), (-1, 0), (0, 1), (0, -1)]
    tf, tr = chess.square_file(to), chess.square_rank(to)
    ff, fr = chess.square_file(t.from_square), chess.square_rank(t.from_square)
    for df, dr in dirs:
        k = max(abs(ff - tf), abs(fr - tr))
        if (ff - tf, fr - tr) in ((-df * k, -dr * k), (df * k, dr * k)):
            continue
        hits, f, r = [], tf + df, tr + dr
        while 0 <= f <= 7 and 0 <= r <= 7 and len(hits) < 2:
            sq = chess.square(f, r)
            if after.piece_at(sq):
                hits.append(sq)
            f, r = f + df, r + dr
        if len(hits) < 2:
            continue
        a, b = (after.piece_at(x) for x in hits)
        if a.color == pov or b.color == pov or a.piece_type == chess.PAWN or hits[0] in after.attackers(not pov, to):
            continue
        va, vb, vm = oracle.KING_VALUES[a.piece_type], oracle.KING_VALUES[b.piece_type], oracle.KING_VALUES[me]
        if vb > va and (b.piece_type == chess.KING or vb > vm or not oracle.is_defended(after, hits[1])):
            return set(hits)
        if va > vb and b.piece_type != chess.PAWN and (a.piece_type == chess.KING or va > vm or not oracle.is_defended(after, hits[0])) \
                and (vb > vm or not oracle.is_defended(after, hits[1])):
            return set(hits)
    return set()


def mate_in_n(board, n):
    """Le camp au trait mate en au plus n coups, par force brute (n <= 2)."""
    for m in board.legal_moves:
        board.push(m)
        try:
            if board.is_checkmate():
                return True
            if n > 1 and not board.is_game_over() and all(_replies_mate(board, r, n - 1) for r in list(board.legal_moves)):
                return True
        finally:
            board.pop()
    return False


def _replies_mate(board, reply, n):
    board.push(reply)
    try:
        return mate_in_n(board, n)
    finally:
        board.pop()


def verify_claim(case, threat):
    """Revérification indépendante d'une menace annoncée, sur l'échiquier seul. Liste des défauts."""
    bad = []
    pos = chess.Board(case["fenPrev"])
    pos.push_uci(case["lastUci"])
    player = pos.turn
    nb = pos.copy()
    nb.push(chess.Move.null())
    t = chess.Move.from_uci(threat["uci"])
    if t not in nb.legal_moves:
        return ["coup menaçant illégal après le coup nul"]
    for sq in threat["squares"]:
        s = chess.parse_square(sq)
        p = pos.piece_at(s)
        if s != t.to_square and (p is None or p.color != player):
            # Seules la case du mat, celle de la promotion et l'arrivée du coup peuvent être vides
            # ou adverses.
            if threat["kind"] not in ("mat", "promotion"):
                bad.append(f"case {sq} sans pièce du joueur")
    if threat["kind"] == "mat":
        if not mate_in_n(nb.copy(), threat["mateIn"]):
            bad.append(f"pas de mat en {threat['mateIn']} pour python-chess")
        elif threat["mateIn"] == 2 and mate_in_n(nb.copy(), 1):
            bad.append("annoncé en 2, mais mat en 1")
    elif threat["kind"] == "promotion":
        if not any(chess.square_rank(chess.parse_square(s)) in (0, 7) for s in threat["squares"]):
            bad.append("aucune case de promotion")
    else:
        targets = [chess.parse_square(s) for s in threat["squares"]]
        if not any(pos.piece_at(s) and pos.piece_at(s).color == player for s in targets):
            bad.append("aucune pièce du joueur visée")
    if threat["kind"] == "fourchette" and not (oracle.fork(nb.fen(), threat["uci"]) or oracle.fork(case["fenPrev"], case["lastUci"])):
        bad.append("fourchette inconnue de l'oracle")
    if threat["kind"] in ("prise", "decouverte") and not nb.is_capture(t):
        bad.append("prise annoncée sur un coup sans prise")
    return bad


def detection_part():
    rolldown_ok = os.path.exists(os.path.join(ROOT, "node_modules", "rolldown"))
    if not check("[détection] rolldown installé (npm ci)", rolldown_ok):
        return
    forks, anyc = puzzle_cases()
    check("[détection] corpus de puzzles : 50 fourchettes calmes et 60 positions quelconques", len(forks) == 50 and len(anyc) == 60, f"({len(forks)}, {len(anyc)})")
    cases = [c for _, c, _ in HAND] + forks + anyc
    tmp = tempfile.mkdtemp(prefix="chesslocal-menace-")
    path, out_path = os.path.join(tmp, "cases.json"), os.path.join(tmp, "out.json")
    with open(path, "w") as f:
        json.dump(cases, f)
    try:
        r = subprocess.run(["node", os.path.join(E2E, "threat_cases.mjs"), path, out_path], cwd=ROOT, capture_output=True, text=True, timeout=900)
        ok = check("[détection] harnais Node terminé", r.returncode == 0 and os.path.exists(out_path), (r.stderr or "")[-400:])
        data = json.load(open(out_path)) if ok else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not data:
        return
    check("[détection] aucune exception dans le harnais", not data["errors"], f"({data['errors'][:3]})")
    check("[détection] reprise après la coupure de la ligne : un seul pion gagné, aucune alerte", data["horizon"] == {"gain": 1, "threat": None}, str(data["horizon"]))
    res = {c["id"]: c for c in data["cases"]}
    check("[détection] un résultat par cas", len(res) == len(cases), f"({len(res)}/{len(cases)})")
    by_id = {c["id"]: c for c in cases}

    # Oracle : même verdict, même type, mêmes cases, sur les scores du harnais.
    mism, claims, bad_claims, null_bad = [], 0, [], []
    for cid, out in res.items():
        case = by_id[cid]
        v = veto(case)
        if (out["veto"] or None) != v:
            mism.append((cid, "veto", out["veto"], v))
            continue
        if v:
            if out["threat"] is not None:
                mism.append((cid, "menace malgré le veto"))
            continue
        pos = chess.Board(case["fenPrev"])
        pos.push_uci(case["lastUci"])
        nb = pos.copy()
        nb.push(chess.Move.null())
        if out["nullFen"].split()[:4] != nb.fen().split()[:4]:
            null_bad.append((cid, out["nullFen"], nb.fen()))
        s = {x["fen"]: x for x in out["searches"]}
        now, nul, prev = s.get(out["fen"]), s.get(out["nullFen"]), s.get(case["fenPrev"])
        if now is None:
            mism.append((cid, "éval de P absente"))
            continue
        if nul is None:
            # Recherche arrêtée avant N : seul un mat dans P l'autorise.
            if out["threat"] is not None or now["mate"] is None:
                mism.append((cid, "N non cherchée sans mat dans P"))
            continue
        want = oracle_judge(case, prev, now, nul, nul["pv"])
        got = out["threat"]
        got_t = (got["kind"], got["uci"], set(got["squares"]), got["mateIn"]) if got else None
        if got_t != want:
            mism.append((cid, got_t, want))
        if out["rejudged"] != got:
            mism.append((cid, "judgeThreat rejoué diffère de findThreat"))
        if got:
            claims += 1
            d = verify_claim(case, got)
            if d:
                bad_claims.append((cid, got["kind"], d))
    check("[détection] coup nul : trait inversé, prise en passant effacée (identique à python-chess)", not null_bad, f"({null_bad[:2]})")
    check(f"[détection] oracle python-chess : même verdict, type et cases sur chaque cas ({len(res)} cas)", not mism, f"({len(mism)} écarts : {mism[:3]})")
    check(f"[détection] chaque menace annoncée revérifiée sur l'échiquier ({claims} menaces)", claims > 0 and not bad_claims, f"({bad_claims[:3]})")

    # Cas à la main : verdict attendu.
    for cid, _case, want in HAND:
        out = res.get(cid)
        if out is None:
            check(f"[détection] {cid} : résultat présent", False)
            continue
        got = out["threat"]
        if want is None:
            check(f"[détection] {cid} : aucune alerte", out["veto"] is None and got is None, f"({out['veto']}, {got and got['kind']})")
        elif isinstance(want, str):
            check(f"[détection] {cid} : veto « {want} » sans moteur", out["veto"] == want and not out["searches"], f"({out['veto']}, {len(out['searches'])} recherches)")
        else:
            kinds, must = want
            ok = got is not None and got["kind"] in kinds and must <= set(got["squares"])
            check(f"[détection] {cid} : menace {'/'.join(sorted(kinds))} sur {', '.join(sorted(must))}", ok,
                  f"({got and (got['kind'], got['san'], got['squares'], got['text'])})")
    # Textes : français, figurines, sans tiret cadratin.
    texts = [o["threat"]["text"] for o in res.values() if o["threat"]]
    check("[détection] phrases en français, sans tiret cadratin ni « undefined »", texts and all(t.startswith(("Il menace", "Son coup")) and "—" not in t and "undefined" not in t for t in texts),
          f"({[t for t in texts if not t.startswith(('Il menace', 'Son coup'))][:2]})")
    # Rappel : une fourchette calme de puzzle est une menace que le perdant doit voir.
    hit = [c for c in forks if res.get(c["id"], {}).get("threat")]
    check("[détection] rappel sur les fourchettes calmes des puzzles >= 90 %", len(hit) >= 0.9 * len(forks), f"({len(hit)}/{len(forks)})")
    # Rappel contre la vérité terrain python-chess, hors mat imparable (mat annoncé dans P : la
    # question n'a plus lieu d'être, par décision).
    gt, gt_hit = [], []
    for cid, out in res.items():
        if out["veto"] or not obvious_threat(by_id[cid]):
            continue
        s_ = {x["fen"]: x for x in out["searches"]}
        now = s_.get(out["fen"])
        if not now or now["mate"] is not None:
            continue
        gt.append(cid)
        if out["threat"]:
            gt_hit.append(cid)
    check("[détection] rappel sur les menaces évidentes (python-chess) >= 90 %", len(gt) >= 10 and len(gt_hit) >= 0.9 * len(gt),
          f"({len(gt_hit)}/{len(gt)}, ratées : {[c for c in gt if c not in gt_hit][:5]})")
    kinds = {o["threat"]["kind"] for o in res.values() if o["threat"]}
    check("[détection] types exercés : mat, fourchette, prise, découverte", {"mat", "fourchette", "prise", "decouverte"} <= kinds, f"({sorted(kinds)})")


# ------------------------------------------------------------------ navigateur

PREFS_KEY = "chess-local-threat-check"


def seed_game(page, mode, color, sans, tc="10 min", prefs=None, threat_ply=None):
    """Instantané de partie en cours (format StoredGame de Play.tsx), relu à l'ouverture de Jouer.
    Jouer est d'abord quitté : son démontage (et `pagehide`) réécrit l'instantané de la partie en
    cours, qui écraserait celui-ci."""
    page.goto(f"{BASE}/#/stats")
    page.wait_for_selector("[data-testid=threat-stats]", timeout=20000)
    page.evaluate("""([g, prefs, key]) => {
      localStorage.setItem('chess-local-play-game', JSON.stringify({ ...g, savedAt: Date.now() }))
      if (prefs) localStorage.setItem(key, JSON.stringify(prefs)); else localStorage.removeItem(key)
    }""", [{"mode": mode, "botId": "noa", "playerColor": color, "tcLabel": tc, "sans": sans,
            "clocks": {"w": 600000, "b": 600000} if tc == "10 min" else {"w": 60000, "b": 60000},
            "unrated": False, "lastWhiteCp": 0, **({"threatPly": threat_ply} if threat_ply is not None else {})}, prefs, PREFS_KEY])
    page.goto(f"{BASE}/#/jouer")


def threat_state(page):
    return page.evaluate("""() => { const e = document.querySelector('[data-threat]');
      return e ? { s: e.dataset.threat, ply: +e.dataset.threatPly, squares: e.dataset.threatSquares ?? null } : null }""")


def wait_state(page, states, ply=None, timeout=30000):
    waited = 0
    while waited < timeout:
        st = threat_state(page)
        if st and st["s"] in states and (ply is None or st["ply"] == ply):
            return st
        page.wait_for_timeout(200)
        waited += 200
    return threat_state(page)


def threat_rows(page):
    return page.evaluate("""() => new Promise((res, rej) => {
      const r = indexedDB.open('chess-local')
      r.onsuccess = () => {
        const db = r.result
        const q = db.transaction('learnSessions').objectStore('learnSessions').getAll()
        q.onsuccess = () => { db.close(); res(q.result.filter((x) => x.domain === 'threat-check')) }
        q.onerror = () => { db.close(); rej(q.error) }
      }
      r.onerror = () => rej(r.error)
    })""")


def wait_rows(page, n, timeout=5000):
    waited = 0
    while waited < timeout:
        rows = threat_rows(page)
        if len(rows) >= n:
            return rows
        page.wait_for_timeout(200)
        waited += 200
    return threat_rows(page)


def bubble_text(page):
    loc = page.locator("[data-testid=threat-bubble]")
    return loc.inner_text() if loc.count() else ""


def answer_tap(page, square):
    """Réponse par toucher : l'app ignore un toucher dans les 400 ms qui suivent l'apparition."""
    page.wait_for_timeout(450)
    tap_square(page, square)


def board_rect(page):
    return page.evaluate("() => { const r = document.querySelector('[data-board]').getBoundingClientRect(); return [r.x, r.y, r.width, r.height] }")


def open_play(page):
    page.goto(f"{BASE}/#/jouer")
    ck.appears("[jouer] écran de configuration", page, "text=Adversaire", timeout=20000)


def coach_part(p, browser):
    # ---------- Entraîneur (activé par défaut), Berger : mauvaise réponse, révélation ----------
    ctx = mobile_context(p, browser, ck, standalone=True, threat_prefs=None)
    page = ctx.new_page()
    open_play(page)
    seed_game(page, "coach", "b", ["e4", "e5", "Bc4", "Nc6", "Qh5"])
    if not ck.appears("[entraîneur] question posée après le coup du bot (Berger)", page, "[data-threat='ask']", timeout=40000):
        shot(page, "menace_berger_echec")
        ctx.close()
        return
    rect_ask = board_rect(page)
    txt = bubble_text(page)
    check("[entraîneur] bandeau « Qu'est-ce qu'il menace ? » et consigne", "Qu'est-ce qu'il menace ?" in txt and "Touche la pièce menacée" in txt, f"({txt!r})")
    check("[entraîneur] aucune case acceptée publiée pendant la question", threat_state(page)["squares"] is None)
    check("[entraîneur] Indication désactivée pendant la question", page.locator("main button", has_text="Indication").is_disabled())
    shot(page, "menace_coach_question_852")
    lines_ask = page.locator("[data-board] svg marker").count()
    # Pendant la question, un toucher ne joue pas de coup : a7-a6 ne doit rien déplacer.
    answer_tap(page, "a7")
    st = wait_state(page, {"wrong", "right"}, timeout=5000)
    check("[entraîneur] toucher faux (a7) : réponse fausse", st["s"] == "wrong", f"({st})")
    check("[entraîneur] la pièce touchée n'a pas bougé", page.locator("[data-square='a7'] [data-piece]").count() == 1)
    txt = bubble_text(page)
    check("[entraîneur] menace révélée : phrase du mat", "Voici sa menace" in txt and "mat" in txt and "f7" in txt, f"({txt!r})")
    check("[entraîneur] cases révélées : f7 et e8", {"f7", "e8"} <= set((st["squares"] or "").split()), f"({st['squares']})")
    check("[entraîneur] flèche de la menace dessinée", page.locator("[data-board] svg marker").count() > lines_ask, f"({lines_ask} -> {page.locator('[data-board] svg marker').count()})")
    check("[entraîneur] l'échiquier n'a pas bougé pendant la question", board_rect(page) == rect_ask, f"({board_rect(page)} vs {rect_ask})")
    check("[entraîneur] menace révélée : partie non classée", page.locator("text=non classée").count() >= 1)
    rows = wait_rows(page, 1)
    check("[entraîneur] une ligne threat-check ratée, hors Elo", len(rows) == 1 and rows[0]["success"] == 0 and rows[0]["ratingAfter"] is None
          and rows[0]["itemId"].startswith("mat:") and rows[0]["fen"] == board_after(["e4", "e5", "Bc4", "Nc6", "Qh5"]).fen(), f"({rows})")
    shot(page, "menace_coach_revelee_852")
    # Rechargement : la question répondue n'est pas reposée.
    page.reload()
    st = wait_state(page, {"idle", "ask", "thinking"}, timeout=15000)
    page.wait_for_timeout(4000)
    st = threat_state(page)
    check("[entraîneur] rechargement : question répondue jamais reposée", st and st["s"] == "idle" and st["ply"] == 5, f"({st})")
    # Le joueur joue ensuite normalement (g6 pare le mat) : la bulle disparaît.
    tap_move(page, "g7", "g6")
    ok = False
    for _ in range(25):
        if page.locator("[data-testid=threat-bubble]").count() == 0 and page.locator("[data-square='g6'] [data-piece]").count() == 1:
            ok = True
            break
        page.wait_for_timeout(200)
    check("[entraîneur] l'échiquier rejoue après la réponse (g6), bulle retirée", ok)
    ctx.close()

    # ---------- Entraîneur, fourchette f7 : bonne réponse, partie toujours classée ----------
    ctx = mobile_context(p, browser, ck, threat_prefs=None)  # onglet Safari 393x660
    page = ctx.new_page()
    open_play(page)
    seed_game(page, "coach", "b", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"])
    if ck.appears("[entraîneur 660] question posée (Cg5)", page, "[data-threat='ask']", timeout=40000):
        shot(page, "menace_coach_question_660")
        b = page.locator("[data-board]").bounding_box()
        bubble = page.locator("[data-testid=threat-bubble]").bounding_box()
        check("[entraîneur 660] échiquier et bulle entièrement visibles", b and bubble and b["y"] + b["height"] <= 660 and bubble["y"] >= 0, f"({b}, {bubble})")
        check("[entraîneur 660] aucun débordement horizontal", not overflow_x(page))
        visible = page.locator("[data-board]").evaluate("""el => {
          const r = el.getBoundingClientRect();
          return [4, r.width - 4].every(x => [4, r.height - 4].every(y =>
            el.contains(document.elementFromPoint(r.x + x, r.y + y))));
        }""")
        check("[entraîneur 660] les quatre coins sont accessibles, sans barre superposée", visible)
        answer_tap(page, "f7")
        st = wait_state(page, {"right", "wrong"}, timeout=5000)
        check("[entraîneur 660] f7 touché : bonne réponse", st["s"] == "right", f"({st})")
        txt = bubble_text(page)
        check("[entraîneur 660] félicitation et phrase", "Bien vu" in txt and "f7" in txt, f"({txt!r})")
        check("[entraîneur 660] menace trouvée : partie toujours classée", page.locator("text=non classée").count() == 0)
        rows = wait_rows(page, 1)
        check("[entraîneur 660] ligne threat-check vue", len(rows) == 1 and rows[0]["success"] == 1, f"({rows})")
        shot(page, "menace_coach_bien_vu_660")
        tap_move(page, "d7", "d5")
        ok = False
        for _ in range(25):
            if page.locator("[data-square='d5'] [data-piece]").count() == 1:
                ok = True
                break
            page.wait_for_timeout(200)
        check("[entraîneur 660] coup joué après la bonne réponse (d5)", ok)
    ctx.close()

    # ---------- Témoins sans alerte : pion attaqué, reprise ; « Je ne sais pas » ----------
    ctx = desktop_context(browser, ck, threat_prefs=None)
    page = ctx.new_page()
    open_play(page)
    for label, sans in (("pion attaqué (Cf3)", ["e4", "e5", "Nf3"]), ("reprise (Fxc6)", ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6"])):
        seed_game(page, "coach", "b", sans)
        st = wait_state(page, {"idle", "ask"}, ply=len(sans), timeout=40000)
        check(f"[témoin] {label} : analyse terminée sans question", st and st["s"] == "idle" and st["ply"] == len(sans), f"({st})")
        check(f"[témoin] {label} : pas de bandeau", page.locator("[data-testid=threat-bubble]").count() == 0, f"({bubble_text(page)!r})")
    seed_game(page, "coach", "b", ["e4", "e5", "Bc4", "Nc6", "Qh5"])
    if ck.appears("[1440] question posée", page, "[data-threat='ask']", timeout=40000):
        shot(page, "menace_coach_question_1440")
        page.locator("[data-testid=threat-unknown]").click()
        st = wait_state(page, {"wrong", "right"}, timeout=5000)
        check("[1440] « Je ne sais pas » : menace révélée", st["s"] == "wrong" and "Voici sa menace" in bubble_text(page), f"({st})")
        rows = wait_rows(page, 1)
        check("[1440] « Je ne sais pas » compte comme ratée", len(rows) == 1 and rows[0]["success"] == 0, f"({rows})")
        check("[1440] aucun débordement horizontal", not overflow_x(page))
        shot(page, "menace_coach_revelee_1440")
    ctx.close()


def clock_texts(page):
    return page.evaluate("() => [...document.querySelectorAll('main .font-mono')].map((e) => e.textContent)")


def bot_part(p, browser):
    # ---------- Mode bot, réglage par défaut : désactivé ----------
    ctx = mobile_context(p, browser, ck, standalone=True, threat_prefs=None)
    page = ctx.new_page()
    open_play(page)
    check("[bot] interrupteur présent, désactivé par défaut", page.locator("[data-testid=toggle-threat]").get_attribute("aria-checked") == "false")
    seed_game(page, "bot", "b", ["e4", "e5", "Bc4", "Nc6", "Qh5"])
    page.wait_for_timeout(5000)
    st = threat_state(page)
    check("[bot] réglage par défaut : alerte coupée, aucune question", st and st["s"] == "off" and page.locator("[data-testid=threat-bubble]").count() == 0, f"({st})")
    ctx.close()

    # ---------- Mode bot 10 min, activé : coup forcé du bot (g6), pendule suspendue ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(HOLD_BESTMOVE)
    page = ctx.new_page()
    open_play(page)
    seed_game(page, "bot", "w", ["e4", "f5"], prefs={"bot": True, "coach": True})
    st = wait_state(page, {"idle", "ask"}, ply=2, timeout=40000)
    check("[bot] 1...f5 : pas de question (un pion attaqué)", st and st["s"] == "idle", f"({st})")
    tap_move(page, "d1", "h5")
    # Après Dh5+, le seul coup légal des Noirs est g6, qui attaque la dame.
    if ck.appears("[bot] question après le coup forcé g6", page, "[data-threat='ask']", timeout=40000):
        before = clock_texts(page)
        page.wait_for_timeout(2600)
        during = clock_texts(page)
        check("[bot] pendule suspendue pendant la question", before == during and len(before) == 2, f"({before} -> {during})")
        shot(page, "menace_bot_question_852")
        answer_tap(page, "h5")
        st = wait_state(page, {"right", "wrong"}, timeout=5000)
        check("[bot] dame h5 touchée : bonne réponse", st["s"] == "right", f"({st})")
        page.wait_for_timeout(2600)
        after = clock_texts(page)
        check("[bot] pendule repartie après la réponse", after != during, f"({during} -> {after})")
        stored = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-play-game'))")
        check("[bot] alerte affichée en mode bot : partie non classée", stored and stored["unrated"] is True, f"({stored and stored.get('unrated')})")
        shot(page, "menace_bot_bien_vu_852")
    ctx.close()

    # ---------- Prémouvement en file au moment du coup du bot : pas de question ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(HOLD_BESTMOVE)
    ctx.add_init_script("""(() => { window.__asked = false; new MutationObserver(() => {
      if (document.querySelector("[data-threat='ask']")) window.__asked = true
    }).observe(document, { subtree: true, attributes: true, childList: true }) })()""")
    page = ctx.new_page()
    open_play(page)
    seed_game(page, "bot", "w", ["e4", "f5"], prefs={"bot": True, "coach": True})
    wait_state(page, {"idle"}, ply=2, timeout=40000)
    page.evaluate("() => { window.__heldUci = [] }")
    tap_move(page, "d1", "h5")
    page.wait_for_timeout(1500)
    tap_move(page, "h5", "h4")  # prémouvement : Dh4 après la réponse forcée
    released = page.evaluate("() => window.__releaseUci()")
    ok = False
    for _ in range(50):
        if page.locator("[data-square='h4'] [data-piece]").count() == 1:
            ok = True
            break
        page.wait_for_timeout(200)
    check("[prémouvement] Dh4 exécuté juste après g6", ok and released >= 1, f"({released} réponses retenues)")
    page.wait_for_timeout(3000)
    check("[prémouvement] aucune question posée", page.evaluate("() => window.__asked") is False)
    ctx.close()

    # ---------- Bullet : indisponible ----------
    ctx = mobile_context(p, browser, ck, standalone=True, settings={"playTcLabel": "1 min"})
    page = ctx.new_page()
    page.goto(f"{BASE}/#/jouer")
    page.evaluate(f"() => localStorage.setItem('{PREFS_KEY}', JSON.stringify({{ bot: true, coach: true }}))")
    page.reload()
    ck.appears("[bullet] écran de configuration", page, "text=Adversaire", timeout=20000)
    note = page.locator("[data-testid=threat-setting]").inner_text()
    check("[bullet] note « indisponible en bullet », pas d'interrupteur", "Indisponible en bullet" in note and page.locator("[data-testid=toggle-threat]").count() == 0, f"({note!r})")
    shot(page, "menace_config_bullet")
    seed_game(page, "bot", "b", ["e4", "e5", "Bc4", "Nc6", "Qh5"], tc="1 min", prefs={"bot": True, "coach": True})
    page.wait_for_timeout(4000)
    st = threat_state(page)
    check("[bullet] aucune question en partie bullet", st and st["s"] == "off", f"({st})")
    ctx.close()

    # ---------- Configuration : interrupteur mémorisé par mode ----------
    ctx = mobile_context(p, browser, ck, standalone=True, threat_prefs=None)
    page = ctx.new_page()
    open_play(page)
    page.locator("main button", has_text="Entraîneur").first.click()
    sw = page.locator("[data-testid=toggle-threat]")
    check("[config] entraîneur : activé par défaut", sw.get_attribute("aria-checked") == "true")
    sw.click()
    page.locator("main button", has_text="Contre un bot").first.click()
    page.locator("[data-testid=toggle-threat]").click()
    prefs = page.evaluate(f"() => JSON.parse(localStorage.getItem('{PREFS_KEY}'))")
    check("[config] choix mémorisés hors réglages (bot activé, entraîneur coupé)", prefs == {"bot": True, "coach": False}, f"({prefs})")
    settings = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-settings')).state")
    check("[config] forme des réglages persistés inchangée", not any("threat" in k.lower() for k in settings), f"({sorted(settings)})")
    shot(page, "menace_config_bot")
    ctx.close()


def lifecycle_part(p, browser):
    # L'utilisateur consulte un ancien coup pendant la recherche : la question doit revenir
    # au direct, sinon le toucher d'une case ne peut pas répondre.
    ctx = desktop_context(browser, ck, threat_prefs=None)
    ctx.add_init_script(HOLD_BESTMOVE)
    page = ctx.new_page()
    open_play(page)
    page.evaluate("() => { window.__heldUci = [] }")
    seed_game(page, "bot", "b", ["e4", "e5", "Bc4", "Nc6", "Qh5"], prefs={"bot": True, "coach": True})
    if ck.appears("[historique] analyse de menace en cours", page, "[data-threat=thinking]"):
        page.locator("main button[data-current]").first.click()
        check("[historique] ancien coup consulté pendant l'analyse", page.locator("main button[data-current=true]").inner_text() == "e4")
        for _ in range(100):
            if page.evaluate("() => window.__heldUci?.length > 0"):
                break
            page.wait_for_timeout(100)
        page.evaluate("() => window.__releaseUci()")
        if ck.appears("[historique] question après l'analyse", page, "[data-threat=ask]", timeout=40000):
            check("[historique] question sur la position actuelle", "h5" in page.locator("main button[data-current=true]").inner_text())
            page.wait_for_timeout(450)
            page.locator("[data-board] [data-square=f7]").click()
            st = wait_state(page, {"right", "wrong"}, timeout=2000)
            check("[historique] réponse possible après retour automatique au direct", st and st["s"] == "right", str(st))
    ctx.close()

    # Une question non répondue survit à la reprise ; Annuler l'abandonne sans statistique.
    ctx = mobile_context(p, browser, ck, standalone=True, threat_prefs=None)
    page = ctx.new_page()
    open_play(page)
    seed_game(page, "coach", "b", ["e4", "e5", "Bc4", "Nc6", "Qh5"])
    if ck.appears("[reprise] question initiale", page, "[data-threat=ask]", timeout=40000):
        page.reload()
        if ck.appears("[reprise] question en attente reposée", page, "[data-threat=ask]", timeout=40000):
            page.get_by_role("button", name="Annuler", exact=False).click()
            st = wait_state(page, {"idle"}, ply=3)
            check("[annulation] question abandonnée et deux demi-coups retirés", st and st["s"] == "idle" and st["ply"] == 3, str(st))
            check("[annulation] aucune réponse enregistrée", threat_rows(page) == [])
    ctx.close()


def stats_part(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    ck.appears("[stats] carte des menaces (vide)", page, "[data-testid=threat-stats]", timeout=20000)
    ck.appears("[stats] sans question : invitation à activer l'alerte", page, "[data-testid=threat-stats] :text('Aucune question encore')")
    page.evaluate("""() => new Promise((res, rej) => {
      const r = indexedDB.open('chess-local')
      r.onsuccess = () => {
        const db = r.result
        const tx = db.transaction('learnSessions', 'readwrite')
        const st = tx.objectStore('learnSessions')
        const rows = [['mat:d1h5', 1], ['mat:h5f7', 0], ['fourchette:g5f7', 1], ['prise:g6h5', 1], ['zzz:a1a2', 1]]
        rows.forEach(([itemId, success], i) => st.add({ date: 1758000000000 + i, domain: 'threat-check', itemId, success, ratingAfter: null }))
        st.add({ date: 1758000000100, domain: 'tactic', itemId: 'x', success: 1, ratingAfter: 900 })
        tx.oncomplete = () => { db.close(); res(true) }
        tx.onerror = () => { db.close(); rej(tx.error) }
      }
      r.onerror = () => rej(r.error)
    })""")
    page.reload()
    ok = ck.appears("[stats] résumé des menaces", page, "[data-testid=threat-summary]", timeout=10000)
    if ok:
        txt = page.locator("[data-testid=threat-summary]").inner_text()
        check("[stats] « 3 menaces repérées sur 4 (75 %) » (type inconnu et autres domaines ignorés)", txt.strip() == "3 menaces repérées sur 4 (75 %)", f"({txt!r})")
        kinds = page.locator("[data-threat-kind]").all_inner_texts()
        check("[stats] détail par type", kinds == ["Mats 1/2", "Fourchettes 1/1", "Pièces en prise 1/1"], f"({kinds})")
        page.locator("[data-testid=threat-stats]").scroll_into_view_if_needed()
        shot(page, "menace_stats_852")
    ctx.close()


def suite(p):
    detection_part()
    browser = p.chromium.launch(headless=True)
    try:
        coach_part(p, browser)
        bot_part(p, browser)
        stats_part(p, browser)
        lifecycle_part(p, browser)
    finally:
        browser.close()


if __name__ == "__main__":
    ck.run(suite)
