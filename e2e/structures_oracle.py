"""Oracle python-chess du détecteur de structures de pions (src/lib/structures.ts).

Réécrit indépendamment, aux mêmes définitions (rangs relatifs : 2 = rangée de départ du camp) :
e2e/test_structures.py compare ses verdicts à ceux du bundle Node de structures.ts, position par
position, et le repérage dans une partie (milieu de partie, série de positions stables).
"""
import chess
import chess.pgn
import io

IDS = ["iqp", "pendants", "carlsbad", "maroczy", "herisson", "francaise", "est-indienne", "stonewall", "caro-slave", "majorite"]
MIN_PLY = 10
MIN_PIECES = 3
STABLE = 4
FILES = {f: i for i, f in enumerate("abcdefgh")}


def pawns(board, color):
    """{colonne: [rangs relatifs]} des pions de `color`."""
    out = {i: [] for i in range(8)}
    for sq in board.pieces(chess.PAWN, color):
        rank = chess.square_rank(sq) + 1
        out[chess.square_file(sq)].append(rank if color == chess.WHITE else 9 - rank)
    return out


def has(p, sq):
    return int(sq[1]) in p[FILES[sq[0]]]


def empty(p, files):
    return all(not p[FILES[f]] for f in files)


def n(p, files):
    return sum(len(p[FILES[f]]) for f in files)


def rule(sid, us, them):
    if sid == "iqp":
        return len(us[3]) == 1 and has(us, "d4") and empty(us, "ce") and empty(them, "d")
    if sid == "pendants":
        return has(us, "c4") and has(us, "d4") and len(us[2]) == 1 and len(us[3]) == 1 and empty(us, "be") and empty(them, "cd")
    if sid == "carlsbad":
        return (has(us, "d4") and empty(us, "c") and n(us, "b") > 0 and (has(us, "e2") or has(us, "e3"))
                and has(them, "d4") and (has(them, "c2") or has(them, "c3")) and empty(them, "e"))
    if sid == "maroczy":
        return has(us, "c4") and has(us, "e4") and empty(us, "d") and (has(them, "d2") or has(them, "d3")) and empty(them, "c")
    if sid == "herisson":
        return all(has(us, s) for s in ("a3", "b3", "d3", "e3")) and empty(us, "c") and has(them, "c4") and has(them, "e4") and empty(them, "d")
    if sid == "francaise":
        return has(us, "d4") and has(us, "e5") and has(them, "d4") and has(them, "e3")
    if sid == "est-indienne":
        return has(us, "d5") and has(us, "e4") and has(them, "d3") and has(them, "e4")
    if sid == "stonewall":
        return has(us, "d4") and has(us, "e3") and has(us, "f4")
    if sid == "caro-slave":
        return has(us, "c3") and has(us, "e3") and empty(us, "d") and has(them, "d4") and ((n(them, "c") > 0) != (n(them, "e") > 0))
    if sid == "majorite":
        return n(us, "abc") > n(them, "abc") and n(us, "abc") >= 2 and n(them, "defgh") > n(us, "defgh")
    raise ValueError(sid)


def detect(board):
    """[(id, 'w'|'b')] dans l'ordre de IDS, Blancs avant Noirs, avec les exclusions du détecteur."""
    p = {"w": pawns(board, chess.WHITE), "b": pawns(board, chess.BLACK)}
    other = {"w": "b", "b": "w"}
    found = [(sid, side) for sid in IDS if sid != "majorite" for side in ("w", "b") if rule(sid, p[side], p[other[side]])]
    found = [(sid, side) for sid, side in found if not (sid == "maroczy" and ("herisson", other[side]) in found)]
    if not found:
        found = [("majorite", side) for side in ("w", "b") if rule("majorite", p[side], p[other[side]])]
    return found


def pieces(board, color):
    return sum(len(board.pieces(t, color)) for t in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))


def over(fen):
    """Fin de partie lisible sur la seule FEN (comme `new Chess(fen).isGameOver()`, sans historique)."""
    b = chess.Board(fen)
    return b.is_checkmate() or b.is_stalemate() or b.is_insufficient_material() or b.halfmove_clock >= 100


def scan(pgn, player):
    """Premières apparitions [(id, camp, demi-coup, fen)] : mêmes règles que structuresInGame."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return []
    board = game.board()
    boards = [board.copy()]
    for mv in game.mainline_moves():
        board.push(mv)
        boards.append(board.copy())
    if len(boards) == 1:
        return []
    color = chess.WHITE if player == "w" else chess.BLACK
    runs, seen, out = {}, set(), []
    for ply, b in enumerate(boards):
        middle = ply >= MIN_PLY and pieces(b, chess.WHITE) >= MIN_PIECES and pieces(b, chess.BLACK) >= MIN_PIECES
        keys = set()
        for sid, side in (detect(b) if ply >= MIN_PLY else []):
            if sid != "majorite" and not middle:
                continue
            k = (sid, side)
            keys.add(k)
            runs[k] = runs.get(k, 0) + 1
            if runs[k] == STABLE and sid not in seen:
                for j in range(ply - STABLE + 1, ply + 1):
                    if boards[j].turn == color and not over(boards[j].fen()):
                        seen.add(sid)
                        out.append((sid, side, j, boards[j].fen()))
                        break
        runs = {k: v for k, v in runs.items() if k in keys}
    return out
