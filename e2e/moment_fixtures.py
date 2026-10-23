"""Bilans semés pour les moments critiques (table `reviews`) : deux parties avec des moments
connus par construction, une sans bascule, et l'état `critical-moment` de deux d'entre eux.
Partagé par les suites apprendre et ux_audit (données pures, aucun état)."""
import time

import chess
import chess.pgn

START_FEN = chess.STARTING_FEN

ZERO = {k: 0 for k in ("brilliant", "great", "best", "excellent", "good", "book", "inaccuracy", "mistake", "miss", "missedWin", "blunder")}


def review_of(sans, marks):
    """Bilan valide : chaque coup est celui de Stockfish à 55 % (aucun moment), sauf `marks`
    {demi-coup: dict de champs} ; renvoie aussi la FEN avant chaque demi-coup."""
    b = chess.Board()
    moves, fens = [], []
    for i, san in enumerate(sans):
        fens.append(b.fen())
        mv = b.parse_san(san)
        m = {"san": san, "uci": mv.uci(), "class": "book" if i < 2 else "best", "evalAfterCp": 0, "mateAfter": None,
             "bestMoveUci": mv.uci(), "winPctBefore": 55.0, "winPctAfter": 55.0, "winPctSecond": 52.0}
        m.update(marks.get(i, {}))
        moves.append(m)
        b.push(mv)
    review = {"moves": moves, "startFen": START_FEN, "startTurn": "w", "accuracyWhite": 80.0, "accuracyBlack": 80.0,
              "counts": {"w": dict(ZERO), "b": dict(ZERO)}, "gameRatingWhite": 1000, "gameRatingBlack": 1000,
              "winPctSeries": [50.0] * (len(sans) + 1)}
    return review, fens


def pgn_of(sans, white, black):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    game = chess.pgn.Game.from_board(b)
    game.headers.clear()
    game.headers["White"], game.headers["Black"], game.headers["Result"] = white, black, "*"
    return str(game)


def row(key, source, sans, marks, date, color, opponent, result):
    review, fens = review_of(sans, marks)
    return {
        "key": key, "source": source, "username": "qa_user" if source == "chesscom" else None, "date": date,
        "timeClass": "blitz", "timeControl": "180", "playerColor": color, "playerRating": 1000, "opponent": opponent,
        "opponentRating": 1200, "result": result, "termination": "abandon", "lostOnTime": False,
        "pgn": pgn_of(sans, "qa_user" if color == "w" else opponent, opponent if color == "w" else "qa_user"),
        "depth": 10, "review": review,
    }, fens

NOW = int(time.time() * 1000)
# Partie de l'app (Blancs) : 4. Fxf7+ ?? fait chuter de 60 % à 20 % (Stockfish : 4. d3), un moment
# critique. Les autres coups sont ceux de Stockfish.
GAME_A, FENS_A = row("local:7", "local", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Bxf7+", "Kxf7"],
                     {6: {"uci": "c4f7", "bestMoveUci": "d2d3", "class": "blunder", "winPctBefore": 60.0, "winPctAfter": 20.0}},
                     NOW - 3 * 86400000, "w", "Iris", "loss")
# Partie chess.com (Noirs), plus récente : 2... Cc6 seul coup qui tenait, trouvé (2e coup à -30) ; 3... Fc5 ?
# (Stockfish : 3... Cf6), chute de 25 %.
GAME_B, FENS_B = row("chesscom:555", "chesscom", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6"],
                     {3: {"winPctBefore": 50.0, "winPctAfter": 50.0, "winPctSecond": 20.0},
                      5: {"uci": "f8c5", "bestMoveUci": "g8f6", "class": "mistake", "winPctBefore": 50.0, "winPctAfter": 25.0}},
                     NOW - 86400000, "b", "Rival", "win")
# Partie sans bascule : absente de la liste.
GAME_C, _ = row("local:8", "local", ["d4", "d5", "c4", "e6"], {}, NOW - 2 * 86400000, "w", "Max", "draw")
# Bilan abîmé (cache ancien ou sauvegarde) : 3. Cc3 ?? est une bascule, mais le dernier coup est
# illégal. Plus récente que les autres, la partie ne doit pas figurer dans la liste.
GAME_BROKEN, _ = row("local:9", "local", ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7"],
                     {4: {"uci": "b1c3", "bestMoveUci": "g1f3", "class": "blunder", "winPctBefore": 60.0, "winPctAfter": 20.0}},
                     NOW - 3600000, "w", "Abime", "loss")
GAME_BROKEN["review"]["moves"][7]["san"] = "Kxe1"
MOMENT_A = FENS_A[6]
FOUND_B, MISS_B = FENS_B[3], FENS_B[5]
# Le moment trouvé de B a déjà été rejoué et retrouvé (domaine critical-moment) ; celui de A est manqué.
SESSIONS = [
    {"date": NOW - 3600000, "domain": "critical-moment", "itemId": "coup:forced", "fen": FOUND_B, "success": 1, "ratingAfter": None},
    {"date": NOW - 3500000, "domain": "critical-moment", "itemId": "coup:plan", "fen": MOMENT_A, "success": 0, "ratingAfter": None},
]
