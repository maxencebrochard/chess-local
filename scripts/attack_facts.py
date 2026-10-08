"""Faits d'attaque d'une position (python-chess, sans moteur) : catégorie de roques, abords du
roi adverse, colonnes, bouclier de pions, tempête de pions, puis UN levier principal dont
dérivent le thème, la consigne et la première phrase du plan. Partagé par
`scripts/prepare-attacks.py` (génération de `src/data/attacks.json`) et `e2e/test_attaque.py`
(qui recalcule tout, et vérifie en plus des invariants indépendants sur l'échiquier).

L'attaquant est le camp au trait.
"""
import chess

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
FILES = "abcdefgh"
CATEGORIES = ("opposes", "meme", "centre")
CATEGORY_SHORT = {"opposes": "Roques opposés", "meme": "Même aile", "centre": "Roi au centre"}
COLOR_FR = {chess.WHITE: "blanc", chess.BLACK: "noir"}
WING_FILES = {0, 1, 2, 5, 6, 7}  # colonnes a-c et f-h : celles d'une tempête de pions


def relative_rank(sq, color):
    """Rangée vue du camp `color` (0 = sa première rangée)."""
    r = chess.square_rank(sq)
    return r if color == chess.WHITE else 7 - r


def castled_wing(sq, color):
    """'q' (roi en a-c) ou 'k' (roi en g-h) sur ses deux premières rangées, sinon None."""
    if relative_rank(sq, color) > 1:
        return None
    f = chess.square_file(sq)
    return "q" if f <= 2 else "k" if f >= 6 else None


def material(board, color):
    return sum(VALUES[p.piece_type] for p in board.piece_map().values() if p.color == color)


def category(board):
    """Catégorie du point de vue de l'attaquant (camp au trait), ou None :
    - centre : roi adverse en colonne d ou e sur ses deux premières rangées, roi de
      l'attaquant sur ses deux premières rangées ;
    - opposes / meme : les deux rois roqués (a-c ou g-h, deux premières rangées), sur des ailes
      différentes ou sur la même.
    Un roi en colonne f, ou sorti de ses deux premières rangées, n'entre dans aucune catégorie."""
    att = board.turn
    dk, ak = board.king(not att), board.king(att)
    if relative_rank(dk, not att) <= 1 and chess.square_file(dk) in (3, 4):
        return "centre" if relative_rank(ak, att) <= 1 else None
    dw, aw = castled_wing(dk, not att), castled_wing(ak, att)
    if not dw or not aw:
        return None
    return "meme" if aw == dw else "opposes"


def facts(board):
    """Faits mesurés autour du roi adverse ; cases et colonnes nommées pour être citées."""
    att, dfn = board.turn, not board.turn
    dk = board.king(dfn)
    kf, kr = chess.square_file(dk), chess.square_rank(dk)
    k_rel = relative_rank(dk, dfn)
    fwd = 1 if dfn == chess.WHITE else -1  # direction « vers l'attaquant » vue du roi adverse
    near_files = [f for f in (kf - 1, kf, kf + 1) if 0 <= f <= 7]

    # Abords du roi : sa case, ses voisines, et les cases deux rangées devant lui.
    zone = set(chess.SquareSet(chess.BB_KING_ATTACKS[dk])) | {dk}
    r2 = kr + 2 * fwd
    if 0 <= r2 <= 7:
        zone |= {chess.square(f, r2) for f in near_files}
    attackers = set()
    for sq in zone:
        for a in board.attackers(att, sq):
            p = board.piece_at(a)
            if p and p.piece_type not in (chess.PAWN, chess.KING):
                attackers.add(a)

    def pawns_on(color, f):
        return [s for s in board.pieces(chess.PAWN, color) if chess.square_file(s) == f]

    open_files, semi_open = [], []
    for f in near_files:
        if not pawns_on(att, f):
            (open_files if not pawns_on(dfn, f) else semi_open).append(FILES[f])

    # Pièces lourdes de l'attaquant déjà sur une de ces colonnes.
    heavy_on = sorted(
        chess.square_name(s)
        for t in (chess.ROOK, chess.QUEEN)
        for s in board.pieces(t, att)
        if FILES[chess.square_file(s)] in open_files + semi_open
    )

    # Bouclier (roi sur ses deux premières rangées) : colonnes a-c / f-h seulement, un pion d ou e
    # parti n'entame pas un roque. Pion avancé de deux rangées ou plus devant le roi : affaibli,
    # sauf fianchetto (fou du défenseur juste derrière lui).
    missing, advanced = [], []
    if k_rel <= 1:
        for f in near_files:
            if f not in WING_FILES:
                continue
            front = sorted((relative_rank(s, dfn), s) for s in pawns_on(dfn, f) if relative_rank(s, dfn) > k_rel)
            if not front:
                missing.append(FILES[f])
                continue
            rank, sq = front[0]
            if rank - k_rel >= 2:
                behind = board.piece_at(chess.square(f, chess.square_rank(sq) - fwd))
                if not (behind and behind.color == dfn and behind.piece_type == chess.BISHOP):
                    advanced.append(chess.square_name(sq))

    # Tempête : pions de l'attaquant sur les colonnes a-c / f-h voisines du roi adverse, au moins
    # sur leur 4e rangée.
    storm = sorted(
        chess.square_name(s)
        for f in near_files
        if f in WING_FILES
        for s in pawns_on(att, f)
        if relative_rank(s, att) >= 3
    )

    return {
        "attackers": sorted(chess.square_name(s) for s in attackers),
        "open": open_files,
        "semiOpen": semi_open,
        "heavyOn": heavy_on,
        "shieldMissing": missing,
        "shieldAdvanced": sorted(advanced),
        "storm": storm,
        "canCastle": board.has_castling_rights(dfn),
    }


def lever(cat, f):
    """Levier principal, par ordre de priorité, ou None si la position n'en a aucun."""
    if cat == "centre":
        return "centre"
    if cat == "opposes" and f["storm"]:
        return "storm"
    if f["heavyOn"] or f["open"] or f["semiOpen"]:
        return "file"
    if f["shieldMissing"] or f["shieldAdvanced"]:
        return "shield"
    if f["storm"]:
        return "storm"
    return None


THEMES = {
    "storm": "Tempête de pions",
    "file": "Colonne ouverte",
    "shield": "Roque affaibli",
}


def theme(cat, f):
    if cat == "centre":
        return "Roi pas encore roqué" if f["canCastle"] else "Roi privé de roque"
    return THEMES[lever(cat, f)]


def _list(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def _storm_files(f):
    return sorted({sq[0] for sq in f["storm"]})


def goal(cat, f):
    """Consigne courte (une ligne sur iPhone) : catégorie + l'action du levier."""
    lv = lever(cat, f)
    cols = f["open"] + f["semiOpen"]
    if lv == "centre":
        action = "frappe avant qu'il roque" if f["canCastle"] else "il ne peut plus roquer, ouvre le jeu"
    elif lv == "storm":
        action = f"pousse ton pion {f['storm'][0][0]}" if len(f["storm"]) == 1 else f"pousse tes pions {_list(_storm_files(f))}"
    elif lv == "file":
        action = f"exploite la colonne {f['heavyOn'][0][0]}" if f["heavyOn"] else f"ouvre le feu sur la colonne {cols[0]}"
    else:
        action = "frappe le roque affaibli"
    return f"{CATEGORY_SHORT[cat]} : {action}."


NUMBER_FR = {2: "Deux", 3: "Trois", 4: "Quatre", 5: "Cinq", 6: "Six", 7: "Sept"}


def plan(board, cat, f):
    """Trois ou quatre phrases, chacune tirée d'un fait mesuré, le levier d'abord."""
    att = board.turn
    dk, ak = chess.square_name(board.king(not att)), chess.square_name(board.king(att))
    lv = lever(cat, f)
    if cat == "opposes":
        out = [f"Ton roi est en {ak}, le sien en {dk} : les roques sont opposés, c'est une course, chaque tempo compte."]
    elif cat == "meme":
        out = [f"Les deux rois sont sur la même aile ({ak} et {dk}) : n'expose pas le tien en poussant tes pions."]
    else:
        out = [
            f"Le roi {COLOR_FR[not att]} est resté au centre en {dk}"
            + (" et peut encore roquer : ouvre le jeu avant qu'il s'abrite." if f["canCastle"] else " et ne peut plus roquer : ouvre les colonnes vers lui.")
        ]
    if len(f["storm"]) == 1:
        storm = f"Ton pion {f['storm'][0]} est déjà lancé vers son roi : pousse-le pour ouvrir une colonne."
    elif f["storm"]:
        storm = f"Tes pions {_list(f['storm'])} sont déjà lancés vers son roi : pousse-les pour ouvrir une colonne."
    else:
        storm = None
    if len(f["heavyOn"]) == 1:
        file_ = f"Ta pièce lourde en {f['heavyOn'][0]} est déjà sur une colonne sans pion à toi, devant son roi."
    elif f["heavyOn"]:
        file_ = f"Tes pièces lourdes en {_list(f['heavyOn'])} sont déjà sur des colonnes sans pion à toi, devant son roi."
    elif f["open"]:
        file_ = (f"La colonne {f['open'][0]} est ouverte" if len(f["open"]) == 1 else f"Les colonnes {_list(f['open'])} sont ouvertes") + " près de son roi : places-y une tour ou ta dame."
    elif f["semiOpen"]:
        file_ = (f"La colonne {f['semiOpen'][0]} est semi-ouverte" if len(f["semiOpen"]) == 1 else f"Les colonnes {_list(f['semiOpen'])} sont semi-ouvertes") + " pour toi : une tour ou ta dame y serait bien placée."
    else:
        file_ = None
    if f["shieldMissing"]:
        cols = f"la colonne {f['shieldMissing'][0]}" if len(f["shieldMissing"]) == 1 else f"les colonnes {_list(f['shieldMissing'])}"
        shield = f"Son roi n'a plus de pion devant lui sur {cols}."
    elif len(f["shieldAdvanced"]) == 1:
        shield = f"Le pion {f['shieldAdvanced'][0]} devant son roi a avancé : les cases derrière sont faibles."
    elif f["shieldAdvanced"]:
        shield = f"Les pions {_list(f['shieldAdvanced'])} devant son roi ont avancé : les cases derrière sont faibles."
    else:
        shield = None
    order = {"storm": [storm, file_, shield], "file": [file_, shield, storm], "shield": [shield, file_, storm], "centre": [file_, shield, storm]}[lv]
    out += [s for s in order if s]
    n = len(f["attackers"])
    out.append(f"{NUMBER_FR.get(n, str(n))} de tes pièces visent déjà les abords de son roi ({_list(f['attackers'])}) : amène les autres.")
    return " ".join(out)
