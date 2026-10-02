"""Oracle python-chess des motifs du coach, indépendant de `src/lib/motifs.ts`.

Utilisé par `test_coach.py` pour vérifier, sur des positions réelles (puzzles lichess), que
chaque motif que le coach annonce existe bien sur l'échiquier. Les définitions suivent
lichess-puzzler (`tagger/util.py` et `tagger/cook.py`, github.com/ornicar/lichess-puzzler),
qui étiquette les puzzles de `public/puzzles.json` ; le code est réécrit ici avec python-chess,
sans rien partager avec le TypeScript.
"""
import chess

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
KING_VALUES = {**VALUES, chess.KING: 99}
RAY_TYPES = (chess.QUEEN, chess.ROOK, chess.BISHOP)
LETTER = {chess.PAWN: "p", chess.KNIGHT: "n", chess.BISHOP: "b", chess.ROOK: "r", chess.QUEEN: "q", chess.KING: "k"}


def is_defended(board, square):
    piece = board.piece_at(square)
    if board.attackers(piece.color, square):
        return True
    for a in board.attackers(not piece.color, square):
        if board.piece_type_at(a) in RAY_TYPES:
            bc = board.copy(stack=False)
            bc.remove_piece_at(a)
            if bc.attackers(piece.color, square):
                return True
    return False


def can_be_taken_by_lower_piece(board, square):
    piece = board.piece_at(square)
    for a in board.attackers(not piece.color, square):
        t = board.piece_type_at(a)
        if t != chess.KING and VALUES[t] < VALUES[piece.piece_type]:
            return True
    return False


def is_in_bad_spot(board, square):
    piece = board.piece_at(square)
    return bool(board.attackers(not piece.color, square)) and (
        not is_defended(board, square) or can_be_taken_by_lower_piece(board, square))


def fork(fen, uci):
    """Cibles (lettres triées par valeur décroissante) si le coup est une fourchette, sinon None."""
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    pov = board.turn
    moved = board.piece_type_at(move.from_square)
    if moved == chess.KING:
        return None
    board.push(move)
    if board.is_checkmate() or is_in_bad_spot(board, move.to_square):
        return None
    moved = board.piece_type_at(move.to_square)  # promotion comprise
    targets = []
    for sq in board.attacks(move.to_square):
        p = board.piece_at(sq)
        if not p or p.color == pov or p.piece_type == chess.PAWN:
            continue
        if KING_VALUES[p.piece_type] > KING_VALUES[moved] or (
                not is_defended(board, sq) and sq not in board.attackers(not pov, move.to_square)):
            targets.append(p.piece_type)
    if len(targets) < 2:
        return None
    return [LETTER[t] for t in sorted(targets, key=lambda t: -KING_VALUES[t])]


def back_rank_mate(fen, uci):
    board = chess.Board(fen)
    pov = board.turn
    board.push(chess.Move.from_uci(uci))
    if not board.is_checkmate():
        return False
    king = board.king(not pov)
    back = 7 if pov == chess.WHITE else 0
    if chess.square_rank(king) != back:
        return False
    front = back - 1 if pov == chess.WHITE else back + 1
    for f in (chess.square_file(king) - 1, chess.square_file(king), chess.square_file(king) + 1):
        if not 0 <= f <= 7:
            continue
        sq = chess.square(f, front)
        p = board.piece_at(sq)
        if p is None or p.color == pov or board.attackers(pov, sq):
            return False
    return any(chess.square_rank(c) == back for c in board.checkers())


def line_motif(fen, uci):
    """('clouage'|'enfilade', devant, derrière) créé par le coup, ou None. Géométrie par rayons."""
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    pov = board.turn
    board.push(move)
    if board.is_checkmate():
        return None
    to = move.to_square
    me = board.piece_type_at(to)
    if me not in RAY_TYPES or is_in_bad_spot(board, to):
        return None
    dirs = []
    if me in (chess.BISHOP, chess.QUEEN):
        dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    if me in (chess.ROOK, chess.QUEEN):
        dirs += [(1, 0), (-1, 0), (0, 1), (0, -1)]
    tf, tr = chess.square_file(to), chess.square_rank(to)
    ff, fr = chess.square_file(move.from_square), chess.square_rank(move.from_square)
    for df, dr in dirs:
        k = max(abs(ff - tf), abs(fr - tr))
        if (ff - tf, fr - tr) in ((-df * k, -dr * k), (df * k, dr * k)):
            continue  # glissade sur la même ligne (avance ou recul) : alignement déjà là avant
        hits = []
        f, r = tf + df, tr + dr
        while 0 <= f <= 7 and 0 <= r <= 7 and len(hits) < 2:
            sq = chess.square(f, r)
            if board.piece_at(sq):
                hits.append(sq)
            f, r = f + df, r + dr
        if len(hits) < 2:
            continue
        a, b = (board.piece_at(s) for s in hits)
        if a.color == pov or b.color == pov or a.piece_type == chess.PAWN:
            continue
        if hits[0] in board.attackers(not pov, to):
            continue
        va, vb, vm = KING_VALUES[a.piece_type], KING_VALUES[b.piece_type], KING_VALUES[me]
        if vb > va and (b.piece_type == chess.KING or vb > vm or not is_defended(board, hits[1])):
            return ("clouage", LETTER[a.piece_type], LETTER[b.piece_type])
        if va > vb and b.piece_type != chess.PAWN and (a.piece_type == chess.KING or va > vm or not is_defended(board, hits[0])) \
                and (vb > vm or not is_defended(board, hits[1])):
            return ("enfilade", LETTER[a.piece_type], LETTER[b.piece_type])
    return None


def absolute_pin(fen, uci):
    """Pièce adverse (hors pion) clouée sur son roi par la pièce jouée, d'après `Board.pin`."""
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    pov = board.turn
    board.push(move)
    for sq in chess.SquareSet(board.occupied_co[not pov]):
        if board.piece_type_at(sq) in (chess.PAWN, chess.KING):
            continue
        if board.is_pinned(not pov, sq) and move.to_square in board.pin(not pov, sq):
            return LETTER[board.piece_type_at(sq)]
    return None


def see(board, square):
    """Échange statique par coups légaux : gain du camp au trait s'il prend sur `square`."""
    caps = [m for m in board.legal_moves if m.to_square == square and board.piece_at(square)]
    if not caps:
        return 0
    m = min(caps, key=lambda m: KING_VALUES[board.piece_type_at(m.from_square)])
    gain = KING_VALUES[board.piece_type_at(square)]
    board.push(m)
    rest = see(board, square)
    board.pop()
    return max(0, gain - rest)


def _passed(board, sq, color):
    f, r = chess.square_file(sq), chess.square_rank(sq)
    for e in board.pieces(chess.PAWN, not color):
        ef, er = chess.square_file(e), chess.square_rank(e)
        if abs(ef - f) <= 1 and ((er > r) if color == chess.WHITE else (er < r)):
            return False
    return True


def passed_pawn_created(fen, uci):
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    color = board.turn
    if board.piece_type_at(move.from_square) != chess.PAWN or move.promotion:
        return False
    if _passed(board, move.from_square, color):
        return False
    board.push(move)
    return _passed(board, move.to_square, color) and see(board, move.to_square) == 0


def mates(fen, uci):
    board = chess.Board(fen)
    board.push(chess.Move.from_uci(uci))
    return board.is_checkmate()


def forced_mate_in_1(fen):
    """Le camp qui n'a pas le trait mate au coup suivant quelle que soit la réponse (mat en 1 forcé)."""
    board = chess.Board(fen)
    replies = list(board.legal_moves)
    if not replies:
        return False
    for r in replies:
        board.push(r)
        ok = False
        for m in board.legal_moves:
            board.push(m)
            ok = board.is_checkmate()
            board.pop()
            if ok:
                break
        board.pop()
        if not ok:
            return False
    return True


def is_castling(fen, uci):
    board = chess.Board(fen)
    return board.is_castling(chess.Move.from_uci(uci))


def free_capture(fen, uci):
    """Prise d'une pièce adverse (≥ 2 points) qu'aucune pièce ne peut reprendre ensuite."""
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    victim = board.piece_at(move.to_square)
    if not victim or VALUES.get(victim.piece_type, 0) < 2:
        return False
    board.push(move)
    return not any(m.to_square == move.to_square for m in board.legal_moves)


def hanging(fen_after, square_name, color_letter):
    """La pièce du joueur sur `square` est attaquée ; renvoie (attaquée, défendue directement)."""
    board = chess.Board(fen_after)
    sq = chess.parse_square(square_name)
    color = chess.WHITE if color_letter == "w" else chess.BLACK
    p = board.piece_at(sq)
    if not p or p.color != color:
        return None
    return bool(board.attackers(not color, sq)), bool(board.attackers(color, sq))


# ---------------------------------------------------------------------------------------------
# Revérification d'une phrase du coach : chaque motif nommé doit exister sur l'échiquier.
# ---------------------------------------------------------------------------------------------
import re  # noqa: E402

WORD_PIECE = {"roi": "k", "dame": "q", "tour": "r", "fou": "b", "cavalier": "n"}
FIGS = "♔♕♖♗♘♚♛♜♝♞"


def _named(body):
    """Pièces nommées en toutes lettres (hors pions), figurines retirées."""
    text = re.sub(rf"[{FIGS}]", " ", body.lower())
    return {WORD_PIECE[w] for w in re.findall(r"\b(roi|dame|tour|fou|cavalier)\b", text)}


def _rights(fen, color):
    field = fen.split(" ")[2]
    return {c for c in field if (c.isupper() if color == "w" else c.islower())}


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:  # coup illégal ou absent : pas de motif
        return None


def audit(row):
    """Renvoie (motifs annoncés, erreurs). `row` : body, cls, fenBefore, fenAfter, uci, bestUci, replyUci, mover."""
    body = row["body"] or ""
    low = body.lower()
    fb, fa, uci, best, reply = row["fenBefore"], row["fenAfter"], row["uci"], row.get("bestUci"), row.get("replyUci")
    mine = [(fb, uci)] + ([(fb, best)] if best and best != uci else [])
    theirs = [(fa, reply)] if reply else []
    if row.get("any"):
        # Bilan lu dans l'UI : meilleur coup et réponse inconnus, tout coup légal est candidat.
        mine = [(fb, uci)] + [(fb, m.uci()) for m in chess.Board(fb).legal_moves if m.uci() != uci]
        theirs = [(fa, m.uci()) for m in chess.Board(fa).legal_moves]
    cands = mine + theirs
    # Rôle du motif : « ton roi », « ta dame » = tes pièces, visées par la réponse adverse ;
    # sinon les pièces adverses, visées par ton coup ou par le meilleur coup.
    own = re.search(r"\b(ton|ta) (roi|dame|tour|fou|cavalier)\b", body.lower()) is not None
    motif_cands = theirs if own else mine
    if row.get("byPlayer") is False:
        motif_cands = mine  # coup du bot (live) : le motif est fait par le coup joué, contre tes pièces
    named = _named(body)
    claims, errors = [], []

    if re.search(r"fourchette|double attaque", low):
        claims.append("fourchette")
        ok = any((t := _safe(fork, f, u)) and named <= set(t) for f, u in motif_cands)
        if not ok:
            errors.append(f"fourchette introuvable (pièces {sorted(named)})")
    if re.search(r"\bclou", low.replace("clouage inversé", "")):
        claims.append("clouage")
        ok = any((m := _safe(line_motif, f, u)) and m[0] == "clouage" and named <= {m[1], m[2]} for f, u in motif_cands)
        if not ok:
            errors.append(f"clouage introuvable (pièces {sorted(named)})")
    if "enfilade" in low:
        claims.append("enfilade")
        ok = any((m := _safe(line_motif, f, u)) and m[0] == "enfilade" and named <= {m[1], m[2]} for f, u in motif_cands)
        if not ok:
            errors.append("enfilade introuvable")
    if re.search(r"couloir|dernière rangée", low):
        claims.append("couloir")
        if not any(_safe(back_rank_mate, f, u) for f, u in cands):
            errors.append("mat du couloir introuvable")
    if re.search(r"pion passé|est passé", low):
        claims.append("pion_passe")
        if not _safe(passed_pawn_created, fb, uci):
            errors.append("pion passé non créé par le coup")
    if re.search(r"roqu", low) and row.get("cls") != "book":
        if re.search(r"plus roquer|droit de roquer|droit au roque|prive du roque", low):
            claims.append("droit_roque")
            if _rights(fb, row["mover"]) == _rights(fa, row["mover"]) or not _rights(fb, row["mover"]):
                errors.append("aucun droit au roque perdu")
        else:
            claims.append("roque")
            if not any(_safe(is_castling, f, u) for f, u in cands[:2]):
                errors.append("aucun roque joué ni proposé")
    if re.search(r"mat en 1\b", low):
        claims.append("mat_en_1")
        # Mat forcé en 1 pour le joueur (« chemin du mat ») : vrai quelle que soit la réponse.
        forced = re.search(r"chemin du mat|gagnée de force|mat forcé|le mat est forcé", low) and _safe(forced_mate_in_1, fa)
        if not any(_safe(mates, f, u) for f, u in cands[1:]) and not forced:
            errors.append("aucun mat en 1 (meilleur coup ou réponse)")
    if re.search(r"sans contrepartie|gratuitement|sans rien donner", low):
        claims.append("prise_gratuite")
        if not any(_safe(free_capture, f, u) for f, u in cands):
            errors.append("aucune prise gratuite")
    squares = re.findall(r"\ben ([a-h][1-8])\b", body)
    if re.search(r"n'est (pas|plus) défendue?|sans défenseur|sans protection|personne pour l", low):
        claims.append("non_defendue")
        if not squares:
            errors.append("pièce non défendue sans case")
        for sq in squares[:1]:
            h = _safe(hanging, fa, sq, row["mover"])
            if not h or not h[0] or h[1]:
                errors.append(f"{sq} : pas une pièce attaquée et non défendue ({h})")
    if "qui vaut moins" in low:
        claims.append("attaquant_moins_cher")
        for sq in squares[:1]:
            board = chess.Board(fa)
            s = chess.parse_square(sq)
            p = board.piece_at(s)
            if not p or not any(VALUES.get(board.piece_type_at(a), 99) < VALUES[p.piece_type] for a in board.attackers(not p.color, s)):
                errors.append(f"{sq} : aucun attaquant moins cher")
    return claims, errors
