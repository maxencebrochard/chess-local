"""Faits de conversion d'une position (python-chess, sans moteur) : matériel par type, pions
passés, roi à activer, tour en 7e, paire de fous, pions isolés, majorités, puis UN levier
principal dont dérivent le thème, la consigne et la première phrase utile du plan. Partagé par
`scripts/prepare-conversions.py` (génération de `src/data/conversions.json`) et
`e2e/test_convertir.py` (qui recalcule tout, et vérifie en plus des invariants indépendants sur
l'échiquier).

Le joueur (celui qui doit convertir) est le camp au trait.
"""
import chess

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
PIECES = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
FILES = "abcdefgh"
CATEGORIES = ("finale", "materiel", "positionnel")
ENDGAME_MAX_PIECES = 4  # dames, tours, fous et cavaliers des deux camps réunis
WORDS = {
    chess.PAWN: ("un pion", "pions"),
    chess.KNIGHT: ("un cavalier", "cavaliers"),
    chess.BISHOP: ("un fou", "fous"),
    chess.ROOK: ("une tour", "tours"),
    chess.QUEEN: ("une dame", "dames"),
}
NUMBER_FR = {2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit"}


def relative_rank(sq, color):
    """Rangée vue du camp `color` (0 = sa première rangée)."""
    r = chess.square_rank(sq)
    return r if color == chess.WHITE else 7 - r


def material(board, color):
    return sum(VALUES[p.piece_type] for p in board.piece_map().values() if p.color == color)


def piece_count(board, color=None):
    """Dames, tours, fous et cavaliers (d'un camp, ou des deux)."""
    return sum(1 for p in board.piece_map().values() if p.piece_type in PIECES and (color is None or p.color == color))


def is_endgame(board):
    return piece_count(board) <= ENDGAME_MAX_PIECES


def category(board):
    """Finale (au plus 4 pièces hors rois et pions), sinon avantage matériel (au moins un point de
    plus pour le joueur), sinon avantage positionnel."""
    if is_endgame(board):
        return "finale"
    pl = board.turn
    return "materiel" if material(board, pl) - material(board, not pl) >= 1 else "positionnel"


def passed_pawns(board, color):
    """Pions passés de `color` : aucun pion adverse devant eux, sur leur colonne ni les voisines.
    Du plus avancé au moins avancé."""
    out = []
    for sq in board.pieces(chess.PAWN, color):
        f, r = chess.square_file(sq), relative_rank(sq, color)
        blocked = any(
            abs(chess.square_file(o) - f) <= 1 and relative_rank(o, color) > r
            for o in board.pieces(chess.PAWN, not color)
        )
        if not blocked:
            out.append(sq)
    return [chess.square_name(s) for s in sorted(out, key=lambda s: (-relative_rank(s, color), chess.square_file(s)))]


def isolated_pawns(board, color):
    files = {chess.square_file(s) for s in board.pieces(chess.PAWN, color)}
    return sorted(chess.square_name(s) for s in board.pieces(chess.PAWN, color) if not ({chess.square_file(s) - 1, chess.square_file(s) + 1} & files))


def opposite_bishops(board):
    """Un seul fou de chaque côté, sur des cases de couleurs différentes, et aucun cavalier (tours
    et dames permises : la banque écarte toutes ces positions, au conseil d'échange incertain)."""
    wb, bb = list(board.pieces(chess.BISHOP, chess.WHITE)), list(board.pieces(chess.BISHOP, chess.BLACK))
    if len(wb) != 1 or len(bb) != 1 or board.pieces(chess.KNIGHT, chess.WHITE) or board.pieces(chess.KNIGHT, chess.BLACK):
        return False
    shade = lambda s: (chess.square_file(s) + chess.square_rank(s)) % 2  # noqa: E731
    return shade(wb[0]) != shade(bb[0])


def facts(board):
    pl, op = board.turn, not board.turn
    counts = {t: (len(board.pieces(t, pl)), len(board.pieces(t, op))) for t in (chess.PAWN,) + PIECES}
    shade = lambda s: (chess.square_file(s) + chess.square_rank(s)) % 2  # noqa: E731

    def has_pair(color):
        return len({shade(s) for s in board.pieces(chess.BISHOP, color)}) == 2

    # Tour en 7e : sur la 7e rangée du joueur, avec le roi adverse sur sa dernière rangée ou des
    # pions adverses encore sur leur rangée de départ (la tour a des cibles).
    op_king = board.king(op)
    targets = relative_rank(op_king, pl) == 7 or any(relative_rank(s, pl) == 6 for s in board.pieces(chess.PAWN, op))
    rook7 = sorted(chess.square_name(s) for s in board.pieces(chess.ROOK, pl) if relative_rank(s, pl) == 6) if targets else []

    # Majorités : ailes dame (a-d) et roi (e-h), le joueur plus nombreux face à au moins un pion.
    # Comptées en colonnes : des pions doublés ne créent pas de pion passé.
    majority = []
    for wing, files in (("dame", range(0, 4)), ("roi", range(4, 8))):
        a = len({chess.square_file(s) for s in board.pieces(chess.PAWN, pl) if chess.square_file(s) in files})
        b = len({chess.square_file(s) for s in board.pieces(chess.PAWN, op) if chess.square_file(s) in files})
        if a > b >= 1:
            majority.append({"wing": wing, "mine": a, "his": b})

    king = board.king(pl)
    return {
        "counts": {chess.piece_symbol(t): list(c) for t, c in counts.items()},
        "diff": material(board, pl) - material(board, op),
        "endgame": is_endgame(board),
        "opPieces": piece_count(board, op),
        "myPieces": piece_count(board, pl),
        "passed": passed_pawns(board, pl),
        "opPassed": passed_pawns(board, op),
        "king": chess.square_name(king),
        # Roi à activer : finale sans dame (avec les dames, sortir le roi l'expose).
        "kingBack": is_endgame(board) and not board.pieces(chess.QUEEN, pl) and not board.pieces(chess.QUEEN, op) and relative_rank(king, pl) <= 1,
        "rook7": rook7,
        "bishopPair": has_pair(pl) and not has_pair(op),
        "opIsolated": isolated_pawns(board, op),
        "majority": majority,
        "oppositeBishops": opposite_bishops(board),
    }


# ---------- Matériel en mots ----------

def _count_words(t, n):
    one, plural = WORDS[t]
    return one if n == 1 else f"{NUMBER_FR.get(n, str(n))} {plural}"


def _list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def _extras(f):
    """(ce que le joueur a en plus, ce que l'adversaire a en plus), par type, dames d'abord."""
    mine, his = [], []
    for sym in ("q", "r", "b", "n", "p"):
        a, b = f["counts"][sym]
        t = chess.PIECE_SYMBOLS.index(sym)
        if a > b:
            mine.append(_count_words(t, a - b))
        elif b > a:
            his.append(_count_words(t, b - a))
    return mine, his


def material_label(f):
    """Thème matériel : pions seuls, qualité, pièce, tour ou dame de plus, sinon générique."""
    d = {sym: f["counts"][sym][0] - f["counts"][sym][1] for sym in ("q", "r", "b", "n", "p")}
    pieces = {k: v for k, v in d.items() if k != "p" and v}
    if not pieces:
        n = d["p"]
        return "Pion de plus" if n == 1 else f"{NUMBER_FR.get(n, str(n)).capitalize()} pions de plus"
    if pieces in ({"r": 1, "b": -1}, {"r": 1, "n": -1}):
        return "Qualité de plus"
    if pieces in ({"b": 1}, {"n": 1}):
        return "Pièce de plus"
    if pieces == {"r": 1}:
        return "Tour de plus"
    if pieces == {"q": 1}:
        return "Dame de plus"
    return "Plus de matériel"


def material_sentence(f):
    mine, his = _extras(f)
    n = abs(f["diff"])
    pts = f"{n} point{'s' if n > 1 else ''}"
    if not mine and not his:
        return "Le matériel est égal : ton avantage vient de la position."
    if not his:
        return f"Tu as {_list(mine)} de plus."
    if not mine:
        return f"Il a {_list(his)} de plus, mais ton avantage vient de la position."
    if f["diff"] > 0:
        return f"Tu as {_list(mine)} contre {_list(his)} : {pts} de plus."
    if f["diff"] == 0:
        return f"Tu as {_list(mine)} contre {_list(his)} : autant de points de chaque côté, ton avantage vient de la position."
    return f"Tu as {_list(mine)} contre {_list(his)} : {pts} de moins, mais ton avantage vient de la position."


# ---------- Levier, thème, consigne, plan ----------

def lever(cat, f):
    """Levier principal, par ordre de priorité selon la catégorie, ou None si la position n'en a aucun."""
    if f["oppositeBishops"]:
        return None  # fous de couleurs opposées : souvent nulle, conseils trop incertains
    if cat == "finale":
        order = ["passed", "king", "material", "majority"]
    elif cat == "materiel":
        order = ["material"]
    else:
        order = ["passed", "rook7", "bishops", "isolated", "majority"]
    have = {
        "passed": bool(f["passed"]),
        "king": f["kingBack"],
        "material": f["diff"] >= 1,
        "majority": bool(f["majority"]),
        "rook7": bool(f["rook7"]),
        "bishops": f["bishopPair"],
        "isolated": bool(f["opIsolated"]),
    }
    return next((lv for lv in order if have[lv]), None)


THEMES = {
    "passed": "Pion passé",
    "king": "Roi à activer",
    "majority": "Majorité de pions",
    "rook7": "Tour en 7e",
    "bishops": "Paire de fous",
    "isolated": "Pion isolé à cibler",
}


def theme(cat, f):
    lv = lever(cat, f)
    return material_label(f) if lv == "material" else THEMES[lv]


def _action(lv, f):
    if lv == "passed":
        return f"pousse ton pion passé {f['passed'][0]}"
    if lv == "king":
        return "active ton roi"
    if lv == "material":
        return "échange les pièces, pas les pions" if f["opPieces"] else "avance tes pions, escortés par ton roi"
    if lv == "majority":
        return f"crée un pion passé à l'aile {f['majority'][0]['wing']}"
    if lv == "rook7":
        return f"exploite ta tour en {f['rook7'][0]}"
    if lv == "bishops":
        return "ouvre le jeu pour ta paire de fous"
    return f"attaque son pion isolé {f['opIsolated'][0]}"


def goal(cat, f):
    """Consigne courte (une ligne sur iPhone) : thème + l'action du levier."""
    return f"{theme(cat, f)} : {_action(lever(cat, f), f)}."


def plan(board, cat, f):
    """Deux à cinq phrases, chacune tirée d'un fait mesuré : matériel, puis le levier, puis les
    autres faits."""
    lv = lever(cat, f)
    s = {}
    if f["diff"] >= 1 and f["opPieces"]:
        s["material"] = "Avec ce matériel en plus, chaque échange de pièces te rapproche du gain : échange les pièces, garde tes pions."
    elif f["diff"] >= 1:
        s["material"] = "Ne rends pas ce matériel : ne lâche aucun pion sans contrepartie."
    escort = "tes pièces" if f["myPieces"] else "ton roi"
    if len(f["passed"]) == 1:
        s["passed"] = f"Ton pion {f['passed'][0]} est passé (aucun pion adverse devant lui ni sur les colonnes voisines) : pousse-le, escorté par {escort}."
    elif f["passed"]:
        s["passed"] = f"Tes pions {_list(f['passed'])} sont passés (aucun pion adverse devant eux ni sur les colonnes voisines) : pousse-les, escortés par {escort}."
    if f["kingBack"]:
        s["king"] = f"En finale, le roi est une pièce forte : sors ton roi de {f['king']} vers le centre."
    if f["majority"]:
        m = f["majority"][0]
        cols = {1: "une", 2: "deux", 3: "trois", 4: "quatre"}
        s["majority"] = f"À l'aile {m['wing']}, tes pions occupent {cols[m['mine']]} colonnes contre {cols[m['his']]} pour les siens : avance-les pour créer un pion passé."
    if f["rook7"]:
        s["rook7"] = f"Ta tour en {f['rook7'][0]} est sur ta 7e rangée, où sont ses cibles : garde-la active."
    if f["bishopPair"]:
        s["bishops"] = "Tu as la paire de fous, pas lui : ouvre le jeu, elle y gagne en force."
    if len(f["opIsolated"]) == 1:
        s["isolated"] = f"Son pion {f['opIsolated'][0]} est isolé : aucun pion ne peut le défendre, attaque-le."
    elif f["opIsolated"]:
        s["isolated"] = f"Ses pions {_list(f['opIsolated'])} sont isolés : aucun pion ne peut les défendre, attaque-les."
    order = [lv] + [k for k in ("material", "passed", "king", "rook7", "bishops", "majority", "isolated") if k != lv]
    out = [material_sentence(f)] + [s[k] for k in order if k in s][:3]
    if len(f["opPassed"]) == 1:
        out.append(f"Attention à son pion passé en {f['opPassed'][0]} : bloque-le avant de foncer.")
    elif f["opPassed"]:
        out.append(f"Attention à ses pions passés {_list(f['opPassed'])} : bloque-les avant de foncer.")
    return " ".join(out)
