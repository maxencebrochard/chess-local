"""E2E « Insights » (lot F13) : le coach qui analyse mes parties.

Trois volets :
- banc Node (src/lib/insights.ts bundlé par rolldown, comme test_mats) : jeu connu de 13 parties
  (11 blitz de la fixture, 2 parties ChessLocal longues générées) à bilans synthétiques ; phases,
  pendule, résultats, conversion, défense et opportunisme recalculés par un oracle python-chess,
  motifs ancrés sur des positions vérifiées, forces et faiblesses confrontées aux seuils du SPEC,
  résumé du coach, lecture des horloges %clk d'un PGN chess.com ;
- UI avec cache semé (IndexedDB natif, table `reviews`) : le rapport se reconstruit hors réseau et
  sans moteur, affiche les chiffres du banc, 3 forces / 3 faiblesses au plus, exemples ouverts dans
  l'Analyse avec retour, plan d'entraînement vers Apprendre, Mats éclair, finales, ouvertures ;
- série réelle : pseudo `insights_qa` de la fixture (horloges, défaite au temps, gaffe sous
  pression), aucune requête avant le tap, progression, pause quand la page est masquée,
  annulation (bestmove retenu), reprise, cache en base, relance sans moteur ni réseau.

Fondée sur la fixture e2e/fixtures/chesscom.json : ignorée en --live.
Usage : npm run test:e2e -- --suite insights
INSIGHTS_CASE=trainers cible le parcours des entraîneurs et le bilan depuis un exemple.
INSIGHTS_CASE=f19 ajoute les seuils et exclusions dans le navigateur et le banc Node.
"""
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import chess
import chess.pgn

from helpers import BASE, HOLD_BESTMOVE, LIVE, SHOTS, Checker, click_square, desktop_context, mobile_context, overflow_x

if LIVE:
    print("[insights] suite fondée sur la fixture chess.com : ignorée en --live")
    sys.exit(0)

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
ck = Checker("insights")
check = ck.check

USER = "insights_qa"
INSIGHTS_KEY = "chess-local-insights-v1"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
STORES = 7  # games, ratings, puzzleAttempts, rushScores, mistakes, learnSessions, reviews

with open(os.path.join(E2E_DIR, "fixtures", "chesscom.json"), encoding="utf-8") as f:
    FIXTURE = json.load(f)["routes"]


def fixture_game(game_id):
    for url, entry in FIXTURE.items():
        if USER not in url:
            continue
        for g in entry.get("body", {}).get("games", []):
            if g["url"].endswith(f"/{game_id}"):
                return g
    raise KeyError(game_id)


# Précision d'un coup depuis sa chute de win% (formule lichess, celle de review.ts).
def acc(drop):
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * drop) - 3.1669))


def fr(n, digits=1):
    return f"{n:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------- jeu connu (banc)
# 13 parties : les 11 blitz de la fixture (insights_qa) et 2 parties longues ChessLocal générées
# (python-chess, graine fixe, sans pendule), avec des bilans synthétiques posés à la main : classes,
# chutes de win%, évaluations et meilleurs coups. Les attentes de phases, de pendule, de résultats,
# de conversion, de défense et d'opportunisme sont recalculées par l'oracle Python ci-dessous à
# partir des mêmes données ; les motifs (pièces en prise, mats autorisés...) sont des ancres
# littérales vérifiées sur l'échiquier.
#
# `book` : index du dernier coup théorique (les coups 0..book sont `book`).
# `moves` : {index: (classe, chute, éval côté blanc, mat côté blanc ou None, meilleur coup UCI ou None)}.
FIXTURE_SPECS = {
    # Mat du berger gagné (4 coups des Blancs : hors de la précision moyenne).
    201: {"acc": 92.0, "book": 3, "moves": {4: ("good", 5, -20, None, None), 6: ("best", 0, 10000, 0, None)}},
    # 3... Qh4?? sous pression (14 s à la pendule) : dame en prise (Nxh4).
    202: {"acc": 40.0, "book": 4, "evals_from": (5, 900), "moves": {5: ("blunder", 43, 900, None, "g8f6")}},
    # Défaite au temps ; 10. Qe2 erreur, 11. Rfd1 joué à 20 s (pression).
    203: {"acc": 75.0, "book": 13, "moves": {18: ("mistake", 12, -40, None, "d1c2")}},
    # Sicilienne Najdorf, empoisonné : 12. Ne4?? adverse puni par 12... Qxa2 (position gagnante).
    204: {"acc": 88.0, "book": 17, "moves": {22: ("blunder", 20, -400, None, None), 23: ("best", 0, -400, None, None)}},
    # Mat de Légal : 5... Bxd1?? adverse puni par 6. Bxf7+.
    205: {"acc": 96.0, "book": 7, "moves": {8: ("best", 0, 300, None, None), 9: ("blunder", 60, 10000, 2, None), 10: ("best", 0, 10000, 1, None), 12: ("best", 0, 10000, 0, None)}},
    # 3... Nf6?? autorise Qxf7# (g6 l'empêchait).
    206: {"acc": 30.0, "book": 4, "moves": {5: ("blunder", 50, 10000, 1, "g7g6"), 6: ("best", 0, 10000, 0, None)}},
    # Espagnole fermée, 22 demi-coups théoriques : nulle finie en ouverture.
    207: {"acc": 95.0, "book": 21, "moves": {}},
    # Gambit dame accepté raté : 6... Nc6? laisse le cavalier en prise (Qxc6+, fourchette roi-tour).
    208: {"acc": 35.0, "book": 4, "moves": {5: ("mistake", 12, 60, None, "g8f6"), 6: ("best", 0, 60, None, None), 7: ("blunder", 30, 250, None, "b8c6"), 8: ("best", 0, 250, None, None),
                                             9: ("blunder", 25, 500, None, "g8f6"), 10: ("best", 0, 500, None, None), 11: ("mistake", 12, 900, None, "b8d7"),
                                             12: ("best", 0, 900, None, None), 13: ("best", 0, 900, None, None), 14: ("best", 0, 900, None, None)}},
    # Partie italienne gagnée : 8. O-O imprécis, deux gaffes adverses punies.
    211: {"acc": 84.0, "book": 9, "evals_from": (24, 500), "moves": {14: ("inaccuracy", 8, 30, None, None), 21: ("blunder", 25, 200, None, None), 22: ("good", 4, 200, None, None),
                                                                      33: ("blunder", 30, 900, None, None), 34: ("best", 0, 900, None, None)}},
    # Mat du lion : 2. g4?? adverse puni par 2... Qh4#.
    212: {"acc": 100.0, "book": 1, "moves": {2: ("blunder", 50, -10000, -1, None), 3: ("best", 0, -10000, 0, None)}},
    # Blackburne-Shilling : +3,5 après 4. Nxe5, puis 5. Nxf7? (gain manqué), 7. Be2?? autorise Nf3#.
    213: {"acc": 38.0, "book": 5, "moves": {6: ("best", 0, 350, None, None), 7: ("best", 0, 350, None, None), 8: ("missedWin", 40, -600, None, "c4f7"),
                                             9: ("best", 0, -800, None, None), 10: ("best", 0, -800, None, None), 11: ("best", 0, -800, None, None),
                                             12: ("blunder", 30, -10000, -1, "d1e2"), 13: ("best", 0, -10000, 0, None)}},
}
# Parties ChessLocal générées : (graine, couleur du joueur, résultat, bot, Elo du bot, Elo du joueur, date ms).
LOCAL_SPECS = {
    1: (11, "w", "win", "Léa", 1000, 1010, 1792300000000),
    2: (23, "b", "loss", "Nina", 1300, 1005, 1792400000000),
}


def mm_count(board):
    return sum(1 for p in board.piece_map().values() if p.piece_type not in (chess.PAWN, chess.KING))


def generate_game(seed):
    """Partie légale et longue qui atteint la finale (≤ 6 pièces hors pions et rois) et y dure,
    sans fin de partie avant son dernier coup. Captures privilégiées pour y arriver."""
    import random
    for attempt in range(200):
        rng = random.Random(seed * 1000 + attempt)
        b = chess.Board()
        endgame_at = None
        ok = True
        while True:
            if endgame_at is not None and len(b.move_stack) - endgame_at >= 36 and len(b.move_stack) >= 80:
                break
            moves = sorted(b.legal_moves, key=lambda m: m.uci())
            caps = [m for m in moves if b.is_capture(m)]
            pref = 0.75 if endgame_at is None else 0.1
            pool = caps if caps and rng.random() < pref else moves
            rng.shuffle(pool)
            chosen = None
            for m in pool + moves:
                b.push(m)
                ended = b.is_game_over(claim_draw=True) or b.is_repetition(2)
                b.pop()
                if not ended:
                    chosen = m
                    break
            if chosen is None or len(b.move_stack) > 160:
                ok = False
                break
            b.push(chosen)
            if endgame_at is None and mm_count(b) <= 6:
                if len(b.move_stack) < 40:
                    ok = False
                    break
                endgame_at = len(b.move_stack)
        if ok:
            return b
    raise RuntimeError("partie générée introuvable")


def phases_oracle(board_moves, classes):
    """detectPhases (coach.ts) puis ouverture étendue à 20 demi-coups (insights.ts), en python-chess."""
    total = len(board_moves)
    opening_end = max((i for i, c in enumerate(classes) if c == "book"), default=-1)
    if opening_end == -1:
        opening_end = min(15, total - 1)
    b = chess.Board()
    e_start = total
    for i, m in enumerate(board_moves):
        b.push(m)
        if mm_count(b) <= 6:
            e_start = i + 1
            break
    e_start = max(e_start, opening_end + 1)
    if total - e_start < 8:
        e_start = total
    o_end = min(max(opening_end, 19), e_start - 1)
    return o_end, e_start


def review_of(board_moves, color, acc_player, entries):
    """Bilan synthétique (forme de GameReview) : entries[i] = (classe, chute, éval, mat, meilleur)."""
    b = chess.Board()
    moves = []
    counts = {"w": {}, "b": {}}
    for i, m in enumerate(board_moves):
        cls, drop, ev, mate, best = entries[i]
        san = b.san(m)
        b.push(m)
        mover = "w" if i % 2 == 0 else "b"
        counts[mover][cls] = counts[mover].get(cls, 0) + 1
        moves.append({"san": san, "uci": m.uci(), "class": cls, "evalAfterCp": ev, "mateAfter": mate, "bestMoveUci": best or m.uci(),
                      "winPctBefore": 50.0, "winPctAfter": 50.0 - drop})
    return {"moves": moves, "startFen": START_FEN, "startTurn": "w",
            "accuracyWhite": acc_player if color == "w" else 100.0, "accuracyBlack": acc_player if color == "b" else 100.0,
            "counts": counts, "gameRatingWhite": 1000, "gameRatingBlack": 1000, "winPctSeries": [50.0] * (len(moves) + 1)}


def pgn_moves(pgn):
    game = chess.pgn.read_game(io.StringIO(pgn))
    return list(game.mainline_moves())


def build_rows():
    """Lignes `reviews` du jeu connu, la plus récente d'abord (ordre de la page)."""
    rows = []
    for gid, spec in FIXTURE_SPECS.items():
        g = fixture_game(gid)
        color = "w" if g["white"]["username"] == USER else "b"
        me, opp = (g["white"], g["black"]) if color == "w" else (g["black"], g["white"])
        mv = pgn_moves(g["pgn"])
        entries = []
        ev_from = spec.get("evals_from")
        for i in range(len(mv)):
            if i in spec["moves"]:
                entries.append(spec["moves"][i])
            else:
                ev = ev_from[1] if ev_from and i >= ev_from[0] else 0
                entries.append(("book" if i <= spec["book"] else "best", 0, ev, None, None))
        result = "win" if me["result"] == "win" else "draw" if me["result"] in ("agreed", "repetition", "stalemate", "insufficient") else "loss"
        rows.append({"key": f"chesscom:{gid}", "source": "chesscom", "username": USER, "date": g["end_time"] * 1000, "timeClass": "blitz",
                     "timeControl": g["time_control"], "playerColor": color, "playerRating": me["rating"], "opponent": opp["username"],
                     "opponentRating": opp["rating"], "result": result, "termination": "au temps" if me["result"] == "timeout" else "test",
                     "lostOnTime": me["result"] == "timeout", "pgn": g["pgn"], "depth": 12,
                     "review": review_of(mv, color, spec["acc"], entries)})
    for lid, (seed, color, result, bot, bot_elo, my_elo, date) in LOCAL_SPECS.items():
        board = generate_game(seed)
        mv = list(board.move_stack)
        classes0 = ["book" if i <= 3 else "best" for i in range(len(mv))]
        o_end, e_start = phases_oracle(mv, classes0)
        replay = chess.Board()
        captures = []
        for m in mv:
            captures.append(replay.is_capture(m))
            replay.push(m)
        entries = []
        k = {"opening": 0, "middlegame": 0, "endgame": 0}
        for i in range(len(mv)):
            ev = (350 if color == "w" else 400) if i >= e_start else (50 if color == "w" else 0)
            mover = "w" if i % 2 == 0 else "b"
            if i <= 3:
                entries.append(("book", 0, ev, None, None))
                continue
            if mover != color:
                entries.append(("best", 0, ev, None, None))
                continue
            phase = "opening" if i <= o_end else "middlegame" if i < e_start else "endgame"
            n = k[phase]
            k[phase] += 1
            # Une faute dont la réponse est une prise serait étiquetée « en prise » : pas de faute là.
            safe = i + 1 >= len(mv) or not captures[i + 1]
            if phase == "opening":
                cls, drop = ("excellent", 2) if n % 3 == 1 else ("best", 0)
            elif phase == "middlegame":
                cls, drop = ("inaccuracy", 8) if n % 4 == 1 else ("good", 4) if n % 4 == 3 else ("best", 0)
            else:
                cls, drop = ("blunder", 22) if n % 5 == 0 and safe else ("mistake", 12) if n % 5 == 2 and safe else ("good", 5)
            entries.append((cls, drop, ev, None, None))
        game = chess.pgn.Game.from_board(board)
        game.headers["Event"] = f"Partie contre {bot}"
        game.headers["Site"] = "chess-local"
        game.headers["Result"] = {"win": "1-0" if color == "w" else "0-1", "loss": "0-1" if color == "w" else "1-0", "draw": "1/2-1/2"}[result]
        rows.append({"key": f"local:{lid}", "source": "local", "username": None, "date": date, "timeClass": "blitz", "timeControl": "5+0",
                     "playerColor": color, "playerRating": my_elo, "opponent": bot, "opponentRating": bot_elo, "result": result,
                     "termination": "abandon", "lostOnTime": False, "pgn": str(game), "depth": 12,
                     "review": review_of(mv, color, 70.0 if color == "w" else 55.0, entries)})
    rows.sort(key=lambda r: -r["date"])
    return rows


def oracle(rows):
    """Recalcul indépendant (python-chess) de ce que computeInsights doit rendre, hors motifs."""
    out = {"phase": {p: {"moves": 0, "accs": [], "mistakes": 0, "blunders": 0, "ended": 0, "drop": 0.0} for p in ("opening", "middlegame", "endgame")}}
    games = sorted(rows, key=lambda r: r["date"])
    res = [r["result"] for r in games]
    score = lambda rs: (sum(1 if x == "win" else 0.5 if x == "draw" else 0 for x in rs) / len(rs) * 100) if rs else 0  # noqa: E731
    out["n"], out["wins"], out["draws"], out["losses"] = len(res), res.count("win"), res.count("draw"), res.count("loss")
    out["score"] = score(res)
    counted = []
    by_color = {}
    t = {"games": 0, "pm": 0, "pb": 0, "nm": 0, "nb": 0, "secs": {"opening": [], "middlegame": [], "endgame": []}}
    conv = [0, 0]
    defe = [0, 0]
    opp = [0, 0]
    for r in games:
        rv, color = r["review"], r["playerColor"]
        ms = rv["moves"]
        board_moves = [chess.Move.from_uci(m["uci"]) for m in ms]
        o_end, e_start = phases_oracle(board_moves, [m["class"] for m in ms])
        phase_of = lambda i: "opening" if i <= o_end else "middlegame" if i < e_start else "endgame"  # noqa: E731
        own = [i for i in range(len(ms)) if (i % 2 == 0) == (color == "w")]
        acc_g = rv["accuracyWhite"] if color == "w" else rv["accuracyBlack"]
        if len(own) >= 5:
            counted.append(acc_g)
        by_color.setdefault(color, []).append((r["result"], acc_g if len(own) >= 5 else None))
        for i in own:
            m = ms[i]
            if m["class"] == "book":
                continue
            ph = out["phase"][phase_of(i)]
            drop = max(0.0, m["winPctBefore"] - m["winPctAfter"])
            ph["moves"] += 1
            ph["accs"].append(acc(drop))
            ph["drop"] += drop
            ph["mistakes"] += m["class"] in ("mistake", "miss", "missedWin")
            ph["blunders"] += m["class"] == "blunder"
        out["phase"][phase_of(len(ms) - 1)]["ended"] += 1
        # Pendule
        clocks = [int(h) * 3600 + int(mi) * 60 + float(se) for h, mi, se in re.findall(r"\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]", r["pgn"])]
        tc = re.search(r'\[TimeControl "(\d+)(?:\+(\d+))?"\]', r["pgn"])
        if clocks and tc and len(clocks) == len(ms):
            base, inc = int(tc.group(1)), int(tc.group(2) or 0)
            t["games"] += 1
            for i in own:
                before = clocks[i - 2] if i >= 2 else base
                t["secs"][phase_of(i)].append(max(0, before - clocks[i] + inc))
                if ms[i]["class"] == "book":
                    continue
                if before < 0.1 * base:
                    t["pm"] += 1
                    t["pb"] += ms[i]["class"] == "blunder"
                else:
                    t["nm"] += 1
                    t["nb"] += ms[i]["class"] == "blunder"
        evs = [(m["evalAfterCp"] if color == "w" else -m["evalAfterCp"]) for m in ms if m["evalAfterCp"] is not None]
        if any(e >= 300 for e in evs):
            conv[0] += 1
            conv[1] += r["result"] == "win"
        if any(e <= -300 for e in evs):
            defe[0] += 1
            defe[1] += r["result"] != "loss"
        for i, m in enumerate(ms):
            if (i % 2 == 0) == (color == "w") or m["class"] not in ("blunder", "missedWin") or i + 1 >= len(ms):
                continue
            opp[0] += 1
            opp[1] += ms[i + 1]["class"] not in ("miss", "missedWin")
    out["acc_mean"] = sum(counted) / len(counted) if counted else None
    out["acc_series"] = counted
    out["by_color"] = {c: {"n": len(v), "wins": sum(1 for x in v if x[0] == "win"), "draws": sum(1 for x in v if x[0] == "draw"), "losses": sum(1 for x in v if x[0] == "loss"),
                           "score": score([x[0] for x in v]), "acc": (lambda a: sum(a) / len(a) if a else None)([x[1] for x in v if x[1] is not None])} for c, v in by_color.items()}
    out["lost_on_time"] = sum(1 for r in games if r["lostOnTime"] and r["result"] == "loss")
    out["time"] = t
    out["conversion"], out["defense"], out["opportunism"] = conv, defe, opp
    after_loss = [games[j]["result"] for j in range(1, len(games)) if games[j - 1]["result"] == "loss"]
    out["tilt"] = (len(after_loss), score(after_loss)) if len(after_loss) >= 3 else None
    out["total_drop"] = sum(p["drop"] for p in out["phase"].values())
    return out


# ---------------------------------------------------------------- cas positifs isolés
# Une position par détecteur de motif : (FEN, coup joué fautif, réponse adverse, meilleur coup).
# Chaque ligne est calculée SEULE : le détecteur visé doit être le seul à se déclencher.
MOTIF_CASES = {
    "missedFork": ("r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "e1d2", "a8a1", "b5c7"),  # Nc7+ prend roi et tour en fourchette
    "missedPin": ("4k3/3r4/8/8/8/8/8/4KB2 w - - 0 1", "e1e2", "d7d1", "f1b5"),  # Bb5 cloue la tour au roi
    "missedFreePiece": ("4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1", "e1e2", "e8e7", "d1d5"),  # Rxd5 : dame gratuite
    "missedMate": ("7k/Q7/6K1/8/8/8/8/8 w - - 0 1", "a7a6", "h8g8", "a7g7"),  # Qg7#
    "missedBackRank": ("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", "g1f1", "g8f8", "a1a8"),  # Ra8# du couloir
    "ignoredThreat": ("4k3/8/1b6/8/3R4/8/8/4K3 w - - 0 1", "e1e2", "b6d4", "d4h4"),  # tour déjà attaquée, laissée
    "allowedPin": ("4kb2/8/8/8/8/5N2/8/4K3 w - - 0 1", "f3d2", "f8b4", "f3g5"),  # Nd2 se met sous le clouage Bb4
    "missedKingAttack": ("rnbq1rk1/ppp2ppp/4p3/8/8/3B1N2/PPP2PPP/RNBQ1RK1 w - - 0 1", "a2a3", "b7b6", "f3g5"),  # Ng5 vise h7 avec le Bd3
}


def motif_row(name, copy=0):
    fen, played, reply, best = MOTIF_CASES[name]
    b = chess.Board(fen)
    color = "w" if b.turn else "b"
    moves = []
    for i, u in enumerate((played, reply)):
        m = chess.Move.from_uci(u)
        san = b.san(m)
        b.push(m)
        moves.append({"san": san, "uci": u, "class": "mistake" if i == 0 else "best", "evalAfterCp": 0, "mateAfter": None,
                      "bestMoveUci": best if i == 0 else reply, "winPctBefore": 50.0, "winPctAfter": 38.0 if i == 0 else 50.0})
    return {"key": f"cas:{name}:{copy}", "source": "local", "username": None, "date": 1792000000000 + copy, "timeClass": "blitz", "timeControl": "5+0",
            "playerColor": color, "playerRating": None, "opponent": "Noa", "opponentRating": None, "result": "loss", "termination": "abandon",
            "lostOnTime": False, "pgn": "", "depth": 12,
            "review": {"moves": moves, "startFen": fen, "startTurn": color, "accuracyWhite": 60.0, "accuracyBlack": 60.0, "counts": {"w": {}, "b": {}},
                       "gameRatingWhite": 1000, "gameRatingBlack": 1000, "winPctSeries": [50.0, 50.0, 50.0]}}


# Trois pièces blanches visent le roi noir, contre deux défenseurs.
DEFENSE_FEN = "r1bq1rk1/pp3pp1/2n1p2p/3pP1NQ/3P4/2NB4/PP3PPP/R3K2R b KQ - 0 1"


def defense_row(copy=0, mirror=False, cls="blunder", opponent=False, best=None, fen=None):
    board = chess.Board(fen or DEFENSE_FEN)
    played, solution = "c6b4", "d8g5"
    if mirror:
        board = board.mirror()
        played, solution = "c3b5", "d1g4"
    if fen:
        legal = list(board.legal_moves)
        played, solution = legal[0].uci(), legal[-1].uci()
    row = motif_row("missedFork", copy)
    color = "w" if board.turn else "b"
    start = board.fen()
    san = board.san(chess.Move.from_uci(played))
    row.update(key=f"defense:{copy}", playerColor=("b" if color == "w" else "w") if opponent else color)
    row["review"].update(startFen=start, startTurn=color, moves=[{
        "san": san, "uci": played, "class": cls, "evalAfterCp": 0, "mateAfter": None,
        "bestMoveUci": best or solution, "winPctBefore": 50, "winPctAfter": 20,
    }])
    return row


def defense_cases():
    positive = [defense_row(i, mirror=i % 2 == 1) for i in range(5)]
    quiet = [motif_row("missedFork", i) for i in range(5)]
    repeated = defense_row()
    board = chess.Board(DEFENSE_FEN)
    moves = []
    for i, uci in enumerate(("c6b4", "a2a3", "b4c6", "a3a4", "c6b4")):
        move = dict(repeated["review"]["moves"][0], uci=uci, san=board.san(chess.Move.from_uci(uci)),
                    **({"class": "best", "bestMoveUci": uci, "winPctAfter": 50} if i % 2 else {}))
        board.push_uci(uci)
        moves.append(move)
    repeated["review"]["moves"] = moves
    ordered = [defense_row(i) for i in range(5)]
    for i, row in enumerate(ordered):
        row["review"]["moves"][0]["winPctAfter"] = 20 - i
    return {
        "defense:positive": positive,
        "defense:ordered": ordered,
        "defense:single-game": [repeated] + quiet[:4],
        "defense:four": positive[:4],
        "defense:one": positive[:1] + quiet[:4],
        "defense:two": positive[:2] + quiet[:3],
        "defense:opponent": [defense_row(i, opponent=True) for i in range(5)],
        **{f"defense:{cls}": [defense_row(i, cls=cls) for i in range(5)] for cls in ("book", "best", "miss", "missedWin", "inaccuracy", "mistake")},
        "defense:illegal": [defense_row(i, best="a1a8") for i in range(5)],
        "defense:quiet": quiet,
        "defense:one-attacker": [defense_row(i, fen="r1bq1rk1/pp3pp1/2n1p2p/3pP3/3P4/2NB4/PP3PPP/R3K2R b KQ - 0 1") for i in range(5)],
        "defense:centre": [defense_row(i, fen="r2qk3/pp3ppp/8/1B5Q/8/8/PPP2PPP/4R1K1 b q - 0 1") for i in range(5)],
        "defense:ending": [defense_row(i, fen="6k1/8/8/8/8/8/5rr1/6K1 w - - 0 1") for i in range(5)],
    }


def clocked_pgn(moves, white, black, result, clock_of):
    """PGN chess.com avec une pendule par demi-coup (clock_of(i) en secondes), cadence 180."""
    game = chess.pgn.Game()
    game.headers.update({"Event": "Live Chess", "Site": "Chess.com", "White": white, "Black": black, "Result": result, "TimeControl": "180"})
    node = game
    for i, m in enumerate(moves):
        node = node.add_variation(m)
        sec = int(clock_of(i))
        node.comment = f"[%clk 0:{sec // 60:02d}:{sec % 60:02d}]"
    return str(game)


def verdict_rows():
    """24 parties qui déclenchent chaque verdict de résultats et de pendule. 12 Siciliennes avec les
    Noirs d'abord (toutes perdues, 3 au temps, +4 pour moi en cours de partie, gaffes de l'adversaire
    jamais punies), puis 12 Italiennes avec les Blancs (toutes gagnées) ; gaffes du joueur jouées
    avec moins de 18 s (10 % de 3 min), précision qui baisse de 85 à 70."""
    rows = []
    for j in range(24):
        black = j < 12
        g = fixture_game(204 if black else 211)
        mv = pgn_moves(g["pgn"])
        color = "b" if black else "w"
        own = [i for i in range(len(mv)) if (i % 2 == 0) == (color == "w")]
        entries = []
        for i in range(len(mv)):
            mine = i in own
            if i <= 3:
                entries.append(("book", 0, 0, None, None))
            elif mine and i == own[-2]:
                entries.append(("blunder", 25, 400 if black else 0, None, None))
            elif not mine and black and i == own[-4] + 1:
                # Gaffe adverse que je ne punis pas : mon coup suivant est une occasion manquée.
                entries.append(("blunder", 30, -400, None, None))
            elif mine and black and i == own[-2] - 2:
                entries.append(("miss", 10, -400, None, None))
            else:
                entries.append(("best", 0, -400 if black and i >= 10 else 0, None, None))
        result = "loss" if black else "win"
        timeout = black and j in (1, 3, 5)
        pgn = clocked_pgn(mv, "QaW" if black else USER, USER if black else "QaB", "1-0" if black else "1-0", lambda i: 170 - 2 * i if i < 12 else 12)
        rows.append({"key": f"verdict:{j}", "source": "chesscom", "username": USER, "date": 1791000000000 + j * 86400000, "timeClass": "blitz",
                     "timeControl": "180", "playerColor": color, "playerRating": 1000, "opponent": "Qa", "opponentRating": 1000, "result": result,
                     "termination": "au temps" if timeout else "abandon", "lostOnTime": timeout, "pgn": pgn, "depth": 12,
                     "review": review_of(mv, color, 85.0 if black else 70.0, entries)})
    return rows


BENCH_JS = r"""
// computeInsights sur les lignes du jeu connu, et parseClocks sur un PGN chess.com avec « 1... ».
// engine.ts (tiré par review.ts via coach.ts) lit `location` au chargement : posé avant l'import.
globalThis.location ??= { href: '' }
const fs = await import('node:fs')
const mod = await import(process.argv[2])
const { rows, clockPgn, cases } = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'))
const brief = (ins) => ({
  errors: Object.fromEntries(ins.errors.filter((e) => e.count).map((e) => [e.kind, e.count])),
  weak: ins.findings.candidates.weaknesses.map((f) => f.id), strong: ins.findings.candidates.strengths.map((f) => f.id),
  kingDefense: ins.kingDefense, findings: ins.findings.candidates.weaknesses, skipped: ins.games.skipped, n: ins.games.n, plans: Object.fromEntries(ins.findings.candidates.weaknesses.map((f) => [f.id, f.plan])),
})
const out = { insights: mod.computeInsights(rows), clocks: mod.parseClocks(clockPgn), cases: {} }
for (const [name, rs] of Object.entries(cases)) out.cases[name] = brief(mod.computeInsights(rs))
console.log(JSON.stringify(out))
"""


def bench_cases():
    cases = {f"motif:{k}": [motif_row(k)] for k in MOTIF_CASES}
    # Cinq parties portant le même motif : les verdicts de motifs passent leur seuil.
    for k in ("ignoredThreat", "missedFork", "missedMate", "missedKingAttack"):
        cases[f"x5:{k}"] = [motif_row(k, c) for c in range(5)]
    cases.update(defense_cases())
    cases["verdicts"] = verdict_rows()
    # Ligne abîmée (sauvegarde trafiquée) : ignorée et comptée, jamais d'exception.
    broken = dict(motif_row("missedFork"), key="cas:abimee")
    broken["review"] = dict(broken["review"], accuracyWhite="NaN")
    cases["abimee"] = [motif_row("missedPin"), broken, dict(motif_row("missedPin", 1), review={"moves": "x"})]
    return cases


def node_bench(rows):
    """Bundle rolldown de src/lib/insights.ts exécuté sous Node. (insights, clocks, cas) ou (None, None, None)."""
    src = os.path.join(ROOT, "src", "lib", "insights.ts")
    if not os.path.exists(src):
        ck.fail("[banc] src/lib/insights.ts existe", "(fichier absent)")
        return None, None, None
    with tempfile.TemporaryDirectory() as d:
        bundle = os.path.join(d, "insights.mjs")
        r = subprocess.run([ROLLDOWN, src, "--format", "esm", "--file", bundle], cwd=ROOT, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            ck.fail("[banc] bundle rolldown de insights.ts", (r.stderr or r.stdout)[-300:])
            return None, None, None
        script = os.path.join(d, "bench.mjs")
        data = os.path.join(d, "rows.json")
        with open(script, "w", encoding="utf-8") as f:
            f.write(BENCH_JS)
        with open(data, "w", encoding="utf-8") as f:
            json.dump({"rows": rows, "clockPgn": fixture_game(202)["pgn"], "cases": bench_cases()}, f)
        r = subprocess.run(["node", script, "file://" + bundle, data], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        ck.fail("[banc] computeInsights sous Node", r.stderr.strip()[-400:])
        return None, None, None
    out = json.loads(r.stdout.strip().splitlines()[-1])
    return out["insights"], out["clocks"], out["cases"]


def close(a, b, tol=0.05):
    return a is not None and b is not None and abs(a - b) < tol


def case_checks(cases):
    tag = "[banc cas]"
    for k in MOTIF_CASES:
        got = cases[f"motif:{k}"]["errors"]
        check(f"{tag} {k} : seul détecteur déclenché sur sa position", got == {k: 1}, f"({got})")
    x5 = {k: cases[f"x5:{k}"]["weak"] for k in ("ignoredThreat", "missedFork", "missedMate", "missedKingAttack")}
    check(f"{tag} 5 menaces ignorées : faiblesses « pièces en prise » et « menaces ignorées »", {"pieces-en-prise", "menaces-ignorees"} <= set(x5["ignoredThreat"]), f"({x5['ignoredThreat']})")
    check(f"{tag} 5 fourchettes manquées : faiblesse « tactiques manquées » avec une séance Fourchette",
          "tactiques-manquees" in x5["missedFork"] and any(p.get("state", {}).get("tactic") == "fork" for p in cases["x5:missedFork"]["plans"].get("tactiques-manquees", [])), f"({x5['missedFork']})")
    check(f"{tag} 5 mats manqués : faiblesse « mats manqués » vers Mats éclair mat en 1",
          "mats-manques" in x5["missedMate"] and any(p.get("to") == "/mats?d=mate-1" for p in cases["x5:missedMate"]["plans"].get("mats-manques", [])), f"({x5['missedMate']})")
    check(f"{tag} 5 attaques manquées : faiblesse « attaque » avec une séance Attaque à l'aile roi",
          "attaque" in x5["missedKingAttack"] and any(p.get("state", {}).get("tactic") == "kingsideAttack" for p in cases["x5:missedKingAttack"]["plans"].get("attaque", [])), f"({x5['missedKingAttack']})")
    check(f"{tag} attaque reliée aux deux entraîneurs", {"/attaque", "/attaques-manquees"} <= {p.get("to") for p in cases["x5:missedKingAttack"]["plans"].get("attaque", [])})
    for name, case in cases.items():
        check(f"{tag} {name} : chaque faiblesse possède une destination", all(any(p.get("to") for p in plan) for plan in case["plans"].values()))
    for name, case in cases.items():
        if not name.startswith("defense:"):
            continue
        positive = name in ("defense:positive", "defense:two", "defense:mistake", "defense:centre", "defense:ordered")
        check(f"{tag} {name} : seuil et exclusions", ("roi-attaque" in case["weak"]) == positive)
        if name not in ("defense:positive", "defense:four", "defense:one", "defense:two", "defense:mistake", "defense:centre", "defense:ordered", "defense:single-game"):
            check(f"{tag} {name} : aucun faux positif compté", case.get("kingDefense", {}).get("faults") == 0)
    single = cases["defense:single-game"].get("kingDefense", {})
    check(f"{tag} trois fautes dans une partie ne suffisent pas", (single.get("faults"), single.get("games"), single.get("drop")) == (3, 1, 90))
    ordered = cases["defense:ordered"].get("kingDefense", {})
    check(f"{tag} exemples les plus coûteux, cumul avant troncature", ordered.get("drop") == 160 and [e["drop"] for e in ordered.get("examples", [])] == [34, 33, 32])
    check(f"{tag} le diagnostic attaque Insights ne confond pas les mats avec ses coups offensifs", "attaque" not in cases["x5:missedMate"]["weak"])
    d = cases["defense:positive"].get("kingDefense", {})
    check(f"{tag} défense blancs/noirs : 5 fautes, 5 parties, 150 points perdus", (d.get("faults"), d.get("games"), d.get("drop")) == (5, 5, 150))
    check(f"{tag} défense : trois exemples corrects", len(d.get("examples", [])) == 3 and all(e["index"] == 0 and e["drop"] == 30 and e["bestSan"] for e in d.get("examples", [])))
    f = next((f for f in cases["defense:positive"]["findings"] if f["id"] == "roi-attaque"), {})
    check(f"{tag} défense : détail chiffré et sévérité exacte", f.get("severity") == 1 and "5 fautes" in f.get("detail", "") and "5 parties" in f.get("detail", ""))
    check(f"{tag} défense : entraîneur et liste personnelle", {p.get("to") for p in f.get("plan", [])} >= {"/defense", "/defenses-ratees"})
    v = cases["verdicts"]
    want = {"gaffes", "temps-pression", "defaites-au-temps", "conversion", "opportunisme", "couleur", "tendance", "tilt", "ouverture-Sicilian Defense-b"}
    check(f"{tag} 24 parties : chaque verdict de résultats et de pendule se déclenche", v["n"] == 24 and want <= set(v["weak"]), f"(manquants : {sorted(want - set(v['weak']))})")
    check(f"{tag} 24 parties : l'Italienne gagnée 12 fois est une force, la Sicilienne coûteuse n'en est pas une",
          "ouverture-Italian Game-w" in v["strong"] and "ouverture-Sicilian Defense-b" not in v["strong"], f"({v['strong']})")
    check(f"{tag} 24 parties : plan de l'ouverture coûteuse vers l'entraîneur (famille et camp)",
          any(p.get("to") == "/ouvertures?famille=Sicilian%20Defense&camp=b" for p in v["plans"].get("ouverture-Sicilian Defense-b", [])), f"({v['plans'].get('ouverture-Sicilian Defense-b')})")
    a = cases["abimee"]
    check(f"{tag} lignes abîmées (précision non numérique, coups illisibles) ignorées et comptées", a["n"] == 1 and a["skipped"] == 2, f"({a['n']}, {a['skipped']})")


def bench_checks(ins, clocks, rows):
    tag = "[banc]"
    o = oracle(rows)
    check(f"{tag} parseClocks : une pendule par demi-coup (partie 202, « 1... » compris)",
          clocks == [180, 92, 179, 14, 178, 13, 178, 13, 176, 13, 175, 13, 174], f"({clocks})")

    g = ins["games"]
    check(f"{tag} 13 parties : {o['wins']} V, {o['draws']} N, {o['losses']} D", (g["n"], g["wins"], g["draws"], g["losses"]) == (13, o["wins"], o["draws"], o["losses"]) and (o["wins"], o["draws"], o["losses"]) == (6, 1, 6), f"({g['n']}, {g['wins']}, {g['draws']}, {g['losses']})")
    check(f"{tag} 1 défaite au temps (203), aucune en position gagnante", g["lostOnTime"] == o["lost_on_time"] == 1 and g["lostOnTimeWinning"] == 0, f"({g['lostOnTime']}, {g['lostOnTimeWinning']})")
    for c in ("w", "b"):
        want, got = o["by_color"][c], g["byColor"][c]
        check(f"{tag} {('Blancs', 'Noirs')[c == 'b']} : {want['n']} parties, score et précision de l'oracle",
              (got["n"], got["wins"], got["draws"], got["losses"]) == (want["n"], want["wins"], want["draws"], want["losses"]) and close(got["score"], want["score"]) and close(got["accuracy"], round(want["acc"], 1)), f"({got} / {want})")
    check(f"{tag} précision moyenne sur les {len(o['acc_series'])} parties d'au moins 5 coups (201, 206, 212 exclues)",
          len(o["acc_series"]) == 10 and close(ins["accuracy"]["mean"], round(o["acc_mean"], 1)), f"({ins['accuracy']['mean']} / {o['acc_mean']})")
    check(f"{tag} série chronologique des précisions", [x["acc"] for x in ins["accuracy"]["perGame"]] == o["acc_series"], f"({[x['acc'] for x in ins['accuracy']['perGame']]})")

    ph = ins["phases"]
    for p, want in o["phase"].items():
        n = want["moves"]
        got = ph[p]
        wacc = round(sum(want["accs"]) / n, 1) if n else None
        ok = got["moves"] == n and (got["accuracy"] == wacc if wacc is None else close(got["accuracy"], wacc)) \
            and close(got["mistakesPer100"], round(want["mistakes"] / n * 100, 1) if n else 0) and close(got["blundersPer100"], round(want["blunders"] / n * 100, 1) if n else 0) \
            and got["gamesEnded"] == want["ended"]
        check(f"{tag} phase {p} : {n} coups hors théorie, précision {wacc}, {want['mistakes']} erreurs, {want['blunders']} gaffes, {want['ended']} fins", ok, f"({got})")
    check(f"{tag} les trois phases ont assez de coups (≥ 15) pour un verdict", all(o["phase"][p]["moves"] >= 15 for p in o["phase"]), f"({[o['phase'][p]['moves'] for p in o['phase']]})")
    check(f"{tag} théorie exclue : l'ouverture ne compte aucun coup `book`", ph["opening"]["moves"] < sum(1 for r in rows for i, m in enumerate(r["review"]["moves"]) if ((i % 2 == 0) == (r["playerColor"] == "w")) and i <= 19), f"({ph['opening']['moves']})")

    t = ins["time"]
    ot = o["time"]
    check(f"{tag} pendule : {ot['games']} parties avec horloges (parties ChessLocal exclues)", t is not None and t["gamesWithClocks"] == ot["games"] == 11, f"({t and t['gamesWithClocks']})")
    check(f"{tag} pendule : {ot['pm']} coups sous pression dont {ot['pb']} gaffe, {ot['nm']} hors pression dont {ot['nb']}",
          t is not None and (t["pressureMoves"], t["pressureBlunders"], t["normalMoves"], t["normalBlunders"]) == (ot["pm"], ot["pb"], ot["nm"], ot["nb"]) and ot["pm"] >= 5 and ot["pb"] == 1, f"({t})")
    for p, xs in ot["secs"].items():
        want = round(sum(xs) / len(xs), 1) if xs else None
        check(f"{tag} pendule : secondes par coup en {p} = {want}", t is not None and (t["avgSecPerMove"][p] == want if want is None else close(t["avgSecPerMove"][p], want)), f"({t and t['avgSecPerMove'][p]})")

    err = {e["kind"]: e for e in ins["errors"]}
    counts = {k: v["count"] for k, v in err.items() if v["count"]}
    check(f"{tag} erreurs typiques : 2 pièces en prise (202 Qh4, 208 Nc6), 2 mats en 1 autorisés (206 Nf6, 213 Be2), 1 fourchette autorisée (208 Qxc6+)",
          counts == {"hanging": 2, "allowedMate": 2, "allowedFork": 1}, f"({counts})")
    ex = err["hanging"]["examples"]
    check(f"{tag} exemple : 3... Qh4 au demi-coup 6 de la partie 202, meilleur ♞f6, le plus coûteux d'abord",
          len(ex) == 2 and ex[0]["key"] == "chesscom:202" and ex[0]["ply"] == 6 and ex[0]["san"] == "Qh4" and ex[0]["bestSan"] == "♞f6" and ex[0]["moveNo"] == "3...", f"({ex[:1]})")
    check(f"{tag} exemple : position AVANT la faute", ex and ex[0]["fen"] == "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3", f"({ex and ex[0]['fen']})")

    check(f"{tag} conversion {o['conversion'][1]}/{o['conversion'][0]}, défense {o['defense'][1]}/{o['defense'][0]}",
          (ins["conversion"]["winning"], ins["conversion"]["converted"], ins["defense"]["losing"], ins["defense"]["saved"]) == (*o["conversion"], *o["defense"]) and tuple(o["conversion"]) == (7, 6) and tuple(o["defense"]) == (5, 0),
          f"({ins['conversion']}, {ins['defense']})")
    check(f"{tag} opportunisme : {o['opportunism'][1]} gaffes adverses punies sur {o['opportunism'][0]}", (ins["opportunism"]["chances"], ins["opportunism"]["punished"]) == tuple(o["opportunism"]), f"({ins['opportunism']})")
    tl = ins["tilt"]
    check(f"{tag} après une défaite : {o['tilt']}", (tl is None and o["tilt"] is None) or (tl is not None and o["tilt"] is not None and tl["n"] == o["tilt"][0] and close(tl["score"], o["tilt"][1])), f"({tl})")

    ops = {(x["name"], x["color"]): x for x in ins["openings"]}
    check(f"{tag} ouvertures par famille et couleur (accepté et refusé regroupés sous Gambit dame)",
          all(k in ops for k in (("Partie espagnole", "b"), ("Partie espagnole", "w"), ("Gambit dame", "w"), ("Gambit dame", "b"), ("Défense sicilienne", "b"), ("Partie italienne", "w"))), f"({sorted(ops)})")
    check(f"{tag} Partie espagnole : une défaite en Noirs, une nulle en Blancs", ops.get(("Partie espagnole", "b"), {}).get("losses") == 1 and ops.get(("Partie espagnole", "w"), {}).get("draws") == 1, f"({ops.get(('Partie espagnole', 'b'))})")
    check(f"{tag} aucune ouverture coûteuse (moins de 3 parties par ligne)", ins["costlyOpenings"] == [], f"({ins['costlyOpenings']})")

    # Forces et faiblesses : chaque verdict vérifié contre les seuils du SPEC sur les chiffres de l'oracle.
    weak = {f_["id"]: f_ for f_ in ins["findings"]["weaknesses"]}
    strong = {f_["id"]: f_ for f_ in ins["findings"]["strengths"]}
    best_acc = max(round(sum(v["accs"]) / v["moves"], 1) for v in o["phase"].values())
    phase_weak = {f"phase-{p}" for p, v in o["phase"].items() if v["moves"] >= 15 and (sum(v["accs"]) / v["moves"] <= 65 or best_acc - round(sum(v["accs"]) / v["moves"], 1) >= 8)}
    phase_strong = {f"phase-{p}" for p, v in o["phase"].items() if v["moves"] >= 15 and f"phase-{p}" not in phase_weak and sum(v["accs"]) / v["moves"] >= 80}
    check(f"{tag} faiblesses : 3 au plus, dont la défense (0 sur 5) et la finale", len(weak) <= 3 and "defense" in weak and "phase-endgame" in weak, f"({list(weak)})")
    # La conversion (6/7) passe le seuil de 85 % de peu : sévérité plancher, elle reste derrière trois forces plus nettes.
    check(f"{tag} forces : les 3 plus nettes (milieu de partie, œil tactique, opportunisme 5/5), la conversion juste au seuil en retrait",
          list(strong) == ["tactiques-manquees", "opportunisme", "phase-middlegame"] and o["conversion"][1] / o["conversion"][0] >= 0.85, f"({list(strong)})")
    allowed_weak = phase_weak | {"defense", "pieces-en-prise", "menaces-ignorees", "temps-pression", "gaffes"}
    allowed_strong = phase_strong | {"conversion", "tactiques-manquees", "opportunisme"}
    check(f"{tag} verdicts justifiés par les seuils (faiblesses ⊂ {sorted(allowed_weak)})", set(weak) <= allowed_weak and set(strong) <= allowed_strong, f"({list(weak)} / {list(strong)})")
    for f_ in ins["findings"]["weaknesses"] + ins["findings"]["strengths"]:
        check(f"{tag} {f_['kind']} {f_['id']} : titre, détail chiffré, sévérité dans [0, 1], plan", bool(f_["title"]) and re.search(r"\d", f_["detail"]) is not None and 0 <= f_["severity"] <= 1 and (f_["kind"] == "force" or len(f_["plan"]) > 0), f"({f_['title']!r} / {f_['detail']!r})")
    sev = [f_["severity"] for f_ in ins["findings"]["weaknesses"]]
    check(f"{tag} faiblesses triées par sévérité", sev == sorted(sev, reverse=True), f"({sev})")
    d = weak.get("defense")
    check(f"{tag} plan de la défense : séance Tactiques « defensiveMove » avec retour vers Insights",
          d is not None and any(p.get("to") == "/apprendre" and p.get("state", {}).get("tactic") == "defensiveMove" and p["state"].get("returnTo") == "/insights" for p in d["plan"]), f"({d and d['plan']})")
    e = weak.get("phase-endgame")
    check(f"{tag} plan de la finale : /finales et /apprendre/finales", e is not None and {"/finales", "/apprendre/finales"} <= {p.get("to") for p in e["plan"]}, f"({e and e['plan']})")

    text = " ".join(ins["narrative"])
    check(f"{tag} résumé : 13 parties de blitz, 6 victoires, 1 nulle, 6 défaites, précision {fr(round(o['acc_mean'], 1))} %",
          all(s_ in text for s_ in ("13 parties de blitz", "6 victoires", "1 nulle", "6 défaites", f"{fr(round(o['acc_mean'], 1))} %")), f"({text[:300]!r})")
    worst = min(o["phase"], key=lambda p: sum(o["phase"][p]["accs"]) / o["phase"][p]["moves"])
    check(f"{tag} résumé : la phase la plus fragile ({worst}) nommée avec sa précision",
          {"opening": "l'ouverture", "middlegame": "le milieu de partie", "endgame": "la finale"}[worst] in text and fr(round(sum(o["phase"][worst]["accs"]) / o["phase"][worst]["moves"], 1)) in text, f"({text!r})")
    check(f"{tag} résumé : défaite au temps, conversion et défense chiffrées", "1 défaite au temps" in text and "des 7 positions gagnantes" in text and "des 5 positions perdantes" in text, f"({text!r})")
    check(f"{tag} résumé : conclusion sur la première faiblesse", ins["findings"]["weaknesses"][0]["title"][1:] in ins["narrative"][-1], f"({ins['narrative'][-1]!r})")
    check(f"{tag} résumé : pas de cadratin, pas d'anglais", "\u2014" not in text and re.search(r"\b(Defense|Opening|Game|Gambit\b(?! dame))\b", text) is None, f"({text!r})")


# ---------------------------------------------------------------- IndexedDB natif
OPEN_DB = f"""
() => new Promise((res, rej) => {{
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {{
    const db = r.result
    if (db.objectStoreNames.length !== {STORES}) {{ db.close(); rej(new Error('schéma inattendu : ' + db.objectStoreNames.length + ' stores')); return }}
    res(db)
  }}
  r.onerror = () => rej(r.error)
}})
"""


def wait_schema(page, tries=40):
    for _ in range(tries):
        n = page.evaluate(
            """() => new Promise((res) => {
              indexedDB.databases().then((list) => {
                if (!list.some((d) => d.name === 'chess-local')) return res(0)
                const r = indexedDB.open('chess-local')
                r.onsuccess = () => { const n = r.result.objectStoreNames.length; r.result.close(); res(n) }
                r.onerror = () => res(-1)
              })
            })"""
        )
        if n == STORES:
            return True
        page.wait_for_timeout(250)
    return False


def seed_db(page, data):
    page.evaluate(
        "async (data) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const tx = db.transaction(Object.keys(data), 'readwrite')
          for (const [t, rows] of Object.entries(data)) for (const r of rows) tx.objectStore(t).put(r)
          await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); tx.onabort = () => rej(tx.error) })
          db.close()
        }""",
        data,
    )


def rows_of(page, store):
    return page.evaluate(
        "async (store) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const rows = await new Promise((res, rej) => { const q = db.transaction(store).objectStore(store).getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
          db.close()
          return rows
        }""",
        store,
    )


def count_api_calls(ctx):
    """Compte les requêtes vers api.chess.com (la fixture les sert ensuite)."""
    box = {"n": 0}
    ctx.on("request", lambda req: box.__setitem__("n", box["n"] + 1) if "api.chess.com" in req.url else None)
    return box


def shoot_scrolled(page, name, max_shots=8):
    """`main` est le seul conteneur qui défile : une capture par écran, de haut en bas."""
    h = page.evaluate("() => document.querySelector('main').clientHeight")
    total = page.evaluate("() => document.querySelector('main').scrollHeight")
    for k in range(min(max_shots, max(1, -(-total // h)))):
        page.evaluate(f"() => document.querySelector('main').scrollTo(0, {k * (h - 60)})")
        page.wait_for_timeout(150)
        page.screenshot(path=f"{SHOTS}/{name}_{k}.png")
    page.evaluate("() => document.querySelector('main').scrollTo(0, 0)")


def main_text(page):
    # Espaces insécables de la typographie française ramenées à des espaces.
    return page.locator("main").inner_text().replace("\xa0", " ")


def data_attr(page, selector, name):
    el = page.locator(selector)
    return el.first.get_attribute(f"data-{name}") if el.count() else None


def tap(name, page, selector, timeout=10000):
    """Clic précédé d'un check : un élément absent fait échouer un check, pas toute la suite."""
    if ck.appears(name, page, selector, timeout=timeout):
        page.click(selector)
        return True
    return False


def delete_row(page, store, key):
    page.evaluate(
        "async ([store, key]) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const tx = db.transaction(store, 'readwrite')
          tx.objectStore(store).delete(key)
          await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error) })
          db.close()
        }""",
        [store, key],
    )


# Verrou d'écran simulé : compte les demandes et les verrous encore tenus. Comme le vrai, un
# verrou tombe quand la page est masquée.
WAKE_LOCK_STUB = """(() => {
  const w = { requests: 0, held: new Set() }
  window.__wake = w
  document.addEventListener('visibilitychange', () => { if (document.hidden) w.held.clear() })
  Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
    request: async () => {
      w.requests++
      const s = { release: async () => { w.held.delete(s) } }
      w.held.add(s)
      return s
    },
  } })
})()"""


def wake(page):
    return page.evaluate("() => window.__wake ? { requests: window.__wake.requests, held: window.__wake.held.size } : null")


# ---------------------------------------------------------------- UI : cache semé
# Un mat en 1 portant les thèmes du plan : quelle que soit la séance Tactiques demandée, elle sert
# ce puzzle (patron de test_learn), sans charger les 16 Mo de puzzles.json.
MATE_IN_1 = ["L10", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8"]
THEMES = "fork pin skewer mateIn1 backRankMate hangingPiece defensiveMove kingsideAttack mateIn2 sacrifice"


def seeded_report(p, browser, rows, ins):
    """Le rapport se reconstruit depuis la table `reviews` et la configuration mémorisée : sans
    réseau, sans moteur."""
    tag = "[cache]"
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": USER}, standalone=True, service_workers="block")
    body = json.dumps([[MATE_IN_1[0], MATE_IN_1[1], MATE_IN_1[2], 1000, THEMES]])
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    calls = count_api_calls(ctx)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    ck.appears(f"{tag} Stats chargée", page, "main :text('Statistiques')", timeout=15000)
    if not check(f"{tag} base Dexie en version 3 ({STORES} stores)", wait_schema(page)):
        ctx.close()
        return
    # Une ligne abîmée en plus (sauvegarde trafiquée) : ignorée, signalée, chiffres inchangés.
    broken = dict(rows[0], key="chesscom:999", review={"moves": "illisible"})
    seed_db(page, {"reviews": rows + [broken]})
    page.evaluate(
        "([key, keys]) => localStorage.setItem(key, JSON.stringify({ config: { timeClass: 'blitz', count: 25, sources: ['chesscom', 'local'] }, lastRun: { keys, at: Date.now() } }))",
        [INSIGHTS_KEY, [r["key"] for r in rows] + [broken["key"]]],
    )

    # Entrée depuis Stats.
    page.reload()
    ck.appears(f"{tag} Stats : carte Insights", page, "main a[href='#/insights']", timeout=15000)
    page.locator("main a[href='#/insights']").first.click()
    if not ck.appears(f"{tag} rapport affiché depuis le cache", page, "[data-testid=insights-report]", timeout=15000):
        ctx.close()
        return
    check(f"{tag} aucune requête chess.com (rapport reconstruit depuis le cache)", calls["n"] == 0, f"({calls['n']})")
    check(f"{tag} pas de barre de progression (aucun moteur lancé)", page.locator("[role=progressbar]").count() == 0)
    text = main_text(page)
    g = ins["games"]
    check(f"{tag} en-tête : 13 parties de blitz", "13 parties de blitz" in text, f"({text[:200]!r})")
    check(f"{tag} bilan : 6 victoires, 1 nulle, 6 défaites", all(s_ in text for s_ in ("6 victoires", "1 nulle", "6 défaites")) and (g["wins"], g["draws"], g["losses"]) == (6, 1, 6), f"({text[:400]!r})")
    check(f"{tag} précision moyenne du banc ({fr(ins['accuracy']['mean'])})", fr(ins["accuracy"]["mean"]) in text, f"({text[:400]!r})")
    check(f"{tag} résumé du coach affiché (avatar + phrases du banc)", page.locator("[data-testid=insights-coach] [data-coach-avatar]").count() == 1 and ins["narrative"][0][:40] in text, f"({ins['narrative'][0][:60]!r})")

    more = page.locator("[data-testid=coach-more]")
    if check(f"{tag} bulle du coach repliée : bilan et conclusion visibles, le reste sur demande", more.count() == 1 and ins["narrative"][-1] in text and ins["narrative"][2] not in text, f"({ins['narrative'][-1]!r})"):
        more.click()
        full = main_text(page)
        check(f"{tag} bilan complet déplié : toutes les phrases du banc", all(s_ in full for s_ in ins["narrative"]), f"({[s_ for s_ in ins['narrative'] if s_ not in full]})")
        more.click()
    weak = page.locator("[data-testid=insights-weaknesses] > li")
    strong = page.locator("[data-testid=insights-strengths] > li")
    check(f"{tag} 3 faiblesses et 3 forces listées", weak.count() == 3 and strong.count() == 3, f"({weak.count()} / {strong.count()})")
    check(f"{tag} faiblesses dans l'ordre du banc", [weak.nth(i).get_attribute("data-id") for i in range(weak.count())] == [f_["id"] for f_ in ins["findings"]["weaknesses"]], f"({[weak.nth(i).get_attribute('data-id') for i in range(weak.count())]})")

    # Phases : attributs lisibles par la suite, libellés français.
    for phase in ("opening", "middlegame", "endgame"):
        want = ins["phases"][phase]
        row = f"[data-testid=insights-phases] [data-phase={phase}]"
        got = (data_attr(page, row, "moves"), data_attr(page, row, "accuracy"), data_attr(page, row, "mistakes"), data_attr(page, row, "blunders"))
        check(f"{tag} phase {phase} : coups, précision, erreurs et gaffes pour 100 coups", got == (str(want["moves"]), fr(want["accuracy"]), fr(want["mistakesPer100"]), fr(want["blundersPer100"])), f"({got} attendu {want})")
    check(f"{tag} libellés : Ouverture, Milieu de partie, Finale", all(s in page.locator("[data-testid=insights-phases]").inner_text() for s in ("Ouverture", "Milieu de partie", "Finale")))

    ops = page.locator("[data-testid=insights-openings] [data-opening]")
    check(f"{tag} {len(ins['openings'])} lignes d'ouverture, Partie espagnole en Blancs et en Noirs", ops.count() == min(12, len(ins["openings"])) and page.locator("[data-testid=insights-openings] [data-opening='Partie espagnole'][data-color=b]").count() == 1 and page.locator("[data-testid=insights-openings] [data-opening='Partie espagnole'][data-color=w]").count() == 1, f"({ops.count()})")

    tm = "[data-testid=insights-time]"
    check(f"{tag} pendule : 5 coups sous pression, 1 gaffe, 1 défaite au temps, 11 parties avec horloges", (data_attr(page, tm, "pressure-moves"), data_attr(page, tm, "pressure-blunders"), data_attr(page, tm, "timeouts"), data_attr(page, tm, "games-with-clocks")) == ("5", "1", "1", "11"), f"({data_attr(page, tm, 'pressure-moves')}, {data_attr(page, tm, 'pressure-blunders')}, {data_attr(page, tm, 'timeouts')})")
    sec = fr(ins["time"]["avgSecPerMove"]["opening"]) + " s"
    check(f"{tag} pendule : secondes par coup affichées ({sec} en ouverture), parties sans pendule mentionnées", sec in page.locator(tm).inner_text() and "2 parties sans pendule" in page.locator(tm).inner_text(), f"({page.locator(tm).inner_text()[:300]!r})")

    errs = page.locator("[data-testid=insights-errors] [data-kind]")
    kinds = {errs.nth(i).get_attribute("data-kind"): errs.nth(i).get_attribute("data-count") for i in range(errs.count())}
    check(f"{tag} erreurs typiques : pièces en prise 2, mats en 1 autorisés 2, fourchette autorisée 1", kinds == {"hanging": "2", "allowedMate": "2", "allowedFork": "1"}, f"({kinds})")
    check(f"{tag} erreurs : libellés français", "Pièce laissée en prise" in page.locator("[data-testid=insights-errors]").inner_text(), f"({page.locator('[data-testid=insights-errors]').inner_text()[:200]!r})")

    conv = "[data-testid=insights-conversion]"
    check(f"{tag} conversion 6/7 et défense 0/5", (data_attr(page, conv, "winning"), data_attr(page, conv, "converted"), data_attr(page, "[data-testid=insights-defense]", "losing"), data_attr(page, "[data-testid=insights-defense]", "saved")) == ("7", "6", "5", "0"))
    check(f"{tag} pas de débordement horizontal (393 px)", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    shoot_scrolled(page, "insights_report_852")

    # Exemple -> Analyse à la position de la faute, puis retour sur le rapport restauré.
    ex = page.locator("[data-testid=insights-errors] [data-kind=hanging] button[data-testid=example]")
    if check(f"{tag} exemples cliquables de la catégorie pièces en prise", ex.count() == 2, f"({ex.count()})"):
        first = ex.first
        key, ply = first.get_attribute("data-key"), first.get_attribute("data-ply")
        first.click()
        if ck.appears(f"{tag} l'Analyse s'ouvre", page, "main [data-square]", timeout=20000):
            page.wait_for_timeout(800)
            fens = page.evaluate("() => [...document.querySelectorAll('[data-square] [data-piece]')].length")
            # Le libellé de partie n'est affiché qu'à partir de md (comportement de l'Analyse) : lu dans le DOM.
            label = page.evaluate("() => document.querySelector('main').textContent")
            check(f"{tag} Analyse : libellé de la partie chess.com et bouton « Retour aux Insights »", "chess.com · contre QaBravo (1040)" in label and page.locator("main button", has_text="Retour aux Insights").count() == 1, f"({label[:200]!r})")
            check(f"{tag} Analyse : position affichée (pièces présentes)", fens > 20, f"({fens})")
            # L'exemple le plus coûteux d'abord : 3... Qh4 de la partie 202. Avant lui, la dame noire est en d8.
            check(f"{tag} Analyse : exemple le plus coûteux (202, demi-coup 6) à la position AVANT la faute (dame noire en d8)",
                  (key, ply) == ("chesscom:202", "6") and page.evaluate("() => document.querySelector(\"[data-square='d8'] [data-piece]\")?.getAttribute('data-piece')") == "bQ", f"({key}, {ply})")
            page.locator("main button", has_text="Retour").first.click()
            ck.appears(f"{tag} retour : rapport restauré sans recalcul", page, "[data-testid=insights-report]", timeout=15000)
            check(f"{tag} retour : toujours aucune requête chess.com", calls["n"] == 0, f"({calls['n']})")

    # Plan d'entraînement : séance Tactiques ciblée dans Apprendre, avec retour vers Insights.
    plan = page.locator("[data-testid=insights-weaknesses] [data-id=defense] [data-testid=plan-link][data-tactic=defensiveMove]")
    if check(f"{tag} plan de la faiblesse défense : lien vers une séance Tactiques « Coup défensif »", plan.count() == 1, f"({plan.count()})"):
        plan.first.click()
        if ck.appears(f"{tag} Apprendre : leçon de la séance ciblée", page, "button:has-text(\"C'est parti\")", timeout=30000):
            check(f"{tag} Apprendre : la séance porte le thème demandé", "Coup défensif" in page.locator("body").inner_text(), f"({page.locator('body').inner_text()[:200]!r})")
            # Le puzzle servi (mat en 1, tous thèmes) se résout : ...Nc3 joué, puis Ra8#.
            page.get_by_role("button", name="C'est parti").click()
            page.wait_for_timeout(1500)
            click_square(page, "a1")
            page.wait_for_timeout(200)
            click_square(page, "a8")
            if ck.appears(f"{tag} Apprendre : puzzle résolu", page, "text=Suivant", timeout=8000):
                page.locator("button", has_text="Suivant").first.click()
                if ck.appears(f"{tag} Apprendre : écran de fin avec « Retour aux Insights »", page, "button:has-text('Retour aux Insights')", timeout=8000):
                    check(f"{tag} Apprendre : « Encore une séance » proposé", page.locator("button", has_text="Encore une séance").count() == 1)
                    page.screenshot(path=f"{SHOTS}/insights_learn_end_852.png")
                    page.locator("button", has_text="Encore une séance").click()
                    if ck.appears(f"{tag} Apprendre : nouvelle séance", page, "button:has-text(\"C'est parti\")", timeout=20000):
                        check(f"{tag} Apprendre : « Encore une séance » rejoue le même thème", "Coup défensif" in page.locator("body").inner_text())
            # Quitter la séance par ✕ : le retour mène à Insights, rapport restauré.
            quit_btn = page.locator("header button:has-text('✕')")
            if check(f"{tag} Apprendre : bouton ✕ de la séance", quit_btn.count() == 1, f"({quit_btn.count()})"):
                quit_btn.first.click()
                ck.appears(f"{tag} Apprendre : la sortie renvoie au rapport Insights", page, "[data-testid=insights-report]", timeout=15000)
                check(f"{tag} Apprendre : URL /insights", page.evaluate("() => location.hash").startswith("#/insights"), f"({page.evaluate('() => location.hash')})")
    page.goto(f"{BASE}/#/insights")
    ck.appears(f"{tag} retour direct : rapport depuis le cache", page, "[data-testid=insights-report]", timeout=15000)
    hrefs = page.evaluate("() => [...document.querySelectorAll('[data-testid=insights-report] a[href]')].map((a) => a.getAttribute('href'))")
    check(f"{tag} liens du rapport vers les modules existants (finales, mats, ouvertures)", any(h.startswith("#/finales") for h in hrefs) and any(h.startswith("#/mats") for h in hrefs) and any(h.startswith("#/ouvertures") for h in hrefs), f"({hrefs})")
    check(f"{tag} ligne abîmée du cache ignorée et signalée", "1 partie illisible ignorée" in main_text(page), f"({main_text(page)[-300:]!r})")

    # chess.com injoignable : les parties de ce pseudo déjà analysées servent, sans moteur.
    ctx.route("https://api.chess.com/**", lambda route: route.abort())
    tap(f"{tag} hors ligne : bouton Modifier", page, "[data-testid=insights-edit]")
    tap(f"{tag} hors ligne : choix 10 parties", page, "[data-testid=count-10]")
    tap(f"{tag} hors ligne : bouton Analyser", page, "[data-testid=insights-run]")
    if ck.appears(f"{tag} hors ligne : avis affiché", page, "text=Hors ligne", timeout=15000):
        ck.appears(f"{tag} hors ligne : rapport", page, "[data-testid=insights-report]", timeout=15000)
        text = main_text(page)
        check(f"{tag} hors ligne : les 10 parties chess.com en cache les plus récentes, sans barre de progression", "10 parties de blitz" in text and page.locator("[role=progressbar]").count() == 0, f"({text[:300]!r})")
    ctx.close()

    # Hauteur Safari (393x660) et bureau (1440x900) : captures et débordement.
    for name, factory in (("660", lambda: mobile_context(p, browser, ck, settings={"chesscomUsername": USER}, service_workers="block")),
                          ("1440", lambda: desktop_context(browser, ck, settings={"chesscomUsername": USER}, service_workers="block"))):
        ctx = factory()
        page = ctx.new_page()
        page.goto(f"{BASE}/#/stats")
        ck.appears(f"[{name}] Stats chargée", page, "main :text('Statistiques')", timeout=15000)
        if wait_schema(page):
            seed_db(page, {"reviews": rows})
            page.evaluate(
                "([key, keys]) => localStorage.setItem(key, JSON.stringify({ config: { timeClass: 'blitz', count: 10, sources: ['chesscom', 'local'] }, lastRun: { keys, at: Date.now() } }))",
                [INSIGHTS_KEY, [r["key"] for r in rows]],
            )
        page.goto(f"{BASE}/#/insights")
        if ck.appears(f"[{name}] rapport affiché", page, "[data-testid=insights-report]", timeout=15000):
            page.wait_for_timeout(500)
            check(f"[{name}] pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
            shoot_scrolled(page, f"insights_report_{name}", max_shots=3 if name == "1440" else 8)
        page.goto(f"{BASE}/#/")
        if ck.appears(f"[{name}] accueil", page, "main a[href='#/insights']", timeout=15000):
            page.wait_for_timeout(300)
            box = page.locator("main a[href='#/insights']").bounding_box()
            check(f"[{name}] accueil : tuile Insights visible sans défiler", box is not None and box["y"] + box["height"] <= page.viewport_size["height"], f"({box})")
            play = page.locator("main button", has_text="Jouer").last.bounding_box()
            check(f"[{name}] accueil : bouton Jouer entièrement au-dessus de la nav basse", play is not None and play["y"] + play["height"] <= page.evaluate("() => document.querySelector('main').getBoundingClientRect().bottom") + 0.5, f"({play})")
            page.screenshot(path=f"{SHOTS}/insights_home_{name}.png")
        ctx.close()


# ---------------------------------------------------------------- UI : série réelle
def defense_guards(p, browser):
    """Le rapport réel applique les seuils et exclusions aux bilans en cache."""
    positives = {"positive", "ordered", "two", "mistake", "centre"}
    for name, rows in defense_cases().items():
        ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
        try:
            page = ctx.new_page()
            page.goto(f"{BASE}/#/stats")
            if not check(f"[F19 seuils] {name} : base prête", wait_schema(page)):
                continue
            seed_db(page, {"reviews": rows})
            page.evaluate("([key, keys]) => localStorage.setItem(key, JSON.stringify({config: {timeClass: 'blitz', count: 10, sources: ['local']}, lastRun: {keys, at: Date.now()}}))", [INSIGHTS_KEY, [r["key"] for r in rows]])
            before = page.evaluate("() => Object.keys(localStorage).sort()")
            page.goto(f"{BASE}/#/insights")
            if ck.appears(f"[F19 seuils] {name} : rapport", page, "[data-testid=insights-report]"):
                card = page.locator("[data-testid=insights-weaknesses] [data-id=roi-attaque]")
                check(f"[F19 seuils] {name} : diagnostic attendu", (card.count() == 1) == (name.split(":")[1] in positives))
                check(f"[F19 seuils] {name} : cache inchangé", rows_of(page, "reviews") == sorted(rows, key=lambda r: r["key"]))
                check(f"[F19 seuils] {name} : aucune nouvelle persistance", rows_of(page, "mistakes") == [] and page.evaluate("() => Object.keys(localStorage).sort()") == before)
                if name in ("defense:two", "defense:four", "defense:single-game"):
                    if card.count():
                        card.scroll_into_view_if_needed()
                    page.screenshot(path=f"{SHOTS}/insights_f19_{name.replace(':', '_')}.png")
        finally:
            ctx.close()


def trainer_links(p, browser):
    for kind, rows, finding, routes in (
        ("defense", defense_cases()["defense:positive"], "roi-attaque", ("/defense", "/defenses-ratees")),
        ("defense-blancs", [defense_row(i, mirror=True) for i in range(5)], "roi-attaque", ("/defense", "/defenses-ratees")),
        ("attaque", [motif_row("missedKingAttack", i) for i in range(5)], "attaque", ("/attaque", "/attaques-manquees")),
        ("positions-perdues", build_rows(), "defense", ("/defense",)),
    ):
        ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
        page = ctx.new_page()
        page.goto(f"{BASE}/#/stats")
        if not check(f"[F19] {kind} : base prête", wait_schema(page)):
            ctx.close()
            continue
        seed_db(page, {"reviews": rows})
        page.evaluate("([key, keys]) => localStorage.setItem(key, JSON.stringify({config: {timeClass: 'blitz', count: 10, sources: ['local']}, lastRun: {keys, at: Date.now()}}))", [INSIGHTS_KEY, [r["key"] for r in rows]])
        page.goto(f"{BASE}/#/insights")
        card = f"[data-testid=insights-weaknesses] [data-id={finding}]"
        if ck.appears(f"[F19] {kind} : faiblesse depuis les reviews", page, card):
            if finding != "defense":
                check(f"[F19] {kind} : aide pour les listes personnelles", "bilan dans Analyse" in page.locator(card).inner_text())
            for width, height in ((393, 852), (393, 660), (1440, 900)):
                page.set_viewport_size({"width": width, "height": height})
                page.locator(card).scroll_into_view_if_needed()
                check(f"[F19] {kind} {width}x{height} : aucun débordement", not overflow_x(page))
                page.screenshot(path=f"{SHOTS}/insights_f19_{kind}_{width}x{height}.png")
            for route in routes:
                page.locator(f"{card} a[href='#{route}']").click()
                ck.appears(f"[F19] destination {route}", page, "main h1")
                check(f"[F19] route {route} ouverte", page.url.endswith(f"#{route}"))
                check(f"[F19] {route} : contenu chargé", bool(page.locator("main h1").inner_text()))
                page.goto(f"{BASE}/#/insights")
                ck.appears(f"[F19] retour {kind}", page, card)
            check(f"[F19] {kind} : aucune écriture dans mistakes", rows_of(page, "mistakes") == [])
            if finding == "roi-attaque":
                page.locator(f"{card} summary").click()
                page.locator(f"{card} [data-testid=example]").first.click()
                if ck.appears("[F19] exemple ouvert dans Analyse", page, "button:text('Bilan de partie')"):
                    page.locator("button:text('Bilan de partie')").click()
                    if ck.appears("[F19] bilan de l’exemple terminé", page, "h1:text('Bilan de la partie')", timeout=90000):
                        faults = []
                        for _ in range(40):
                            faults = rows_of(page, "mistakes")
                            if faults:
                                break
                            page.wait_for_timeout(100)
                        color = "w" if kind == "defense-blancs" else "b"
                        check(f"[F19] bilan conserve le camp {color} du joueur", bool(faults) and all(r.get("color") == color for r in faults), str(faults)[:300])
                        page.screenshot(path=f"{SHOTS}/insights_f19_bilan_{color}.png")
                        page.goto(f"{BASE}/#/defenses-ratees")
                        ck.appears("[F19] défense de l’exemple disponible personnellement", page, "[data-testid=missed-defense-item]")
        ctx.close()


def set_hidden(page, hidden):
    """Page masquée ou visible, comme quand l'utilisateur quitte la PWA puis y revient."""
    page.evaluate(
        """(h) => {
          Object.defineProperty(document, 'hidden', { configurable: true, get: () => h })
          Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (h ? 'hidden' : 'visible') })
          document.dispatchEvent(new Event('visibilitychange'))
        }""",
        hidden,
    )


def held_count(page):
    return page.evaluate("() => (Array.isArray(window.__heldUci) ? window.__heldUci.length : -1)")


def wait_held(page, timeout=30000):
    try:
        page.wait_for_function("() => Array.isArray(window.__heldUci) && window.__heldUci.length >= 1", timeout=timeout)
        return True
    except Exception:
        return False


def real_run(p, browser):
    """Fixture `insights_qa` : 10 parties de blitz (11 disponibles), aucune requête avant le tap,
    progression, pause quand la page est masquée, annulation pendant une recherche retenue,
    reprise, cache, relance sans moteur, rechargement sans réseau."""
    tag = "[série]"
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": USER}, standalone=True, service_workers="block")
    ctx.add_init_script(HOLD_BESTMOVE)
    ctx.add_init_script(WAKE_LOCK_STUB)
    calls = count_api_calls(ctx)
    page = ctx.new_page()
    page.set_default_timeout(15000)

    # Entrée depuis l'accueil.
    page.goto(f"{BASE}/#/")
    ck.appears(f"{tag} accueil chargé", page, "text=Résolvez !", timeout=15000)
    home_link = page.locator("main a[href='#/insights']")
    if check(f"{tag} accueil : tuile Insights", home_link.count() == 1, f"({home_link.count()})"):
        page.screenshot(path=f"{SHOTS}/insights_home_852.png")
        home_link.first.click()
    else:
        page.goto(f"{BASE}/#/insights")
    if not ck.appears(f"{tag} panneau de configuration", page, "[data-testid=insights-config]", timeout=15000):
        ctx.close()
        return
    page.wait_for_timeout(500)
    check(f"{tag} aucune requête chess.com au chargement", calls["n"] == 0, f"({calls['n']})")
    check(f"{tag} aucun rapport sans série", page.locator("[data-testid=insights-report]").count() == 0)
    current = page.locator("nav a[aria-current]").locator("visible=true").all_inner_texts()
    check(f"{tag} onglet Plus allumé sur /insights", current == ["Plus"], f"({current})")
    page.screenshot(path=f"{SHOTS}/insights_config_852.png", full_page=True)

    tap(f"{tag} cadence Blitz", page, "[data-testid=tc-blitz]")
    tap(f"{tag} choix 10 parties", page, "[data-testid=count-10]")
    est = page.locator("[data-testid=insights-estimate]")
    check(f"{tag} estimation affichée avant le lancement (profondeur 12 et durée)", est.count() == 1 and "Profondeur 12" in est.inner_text() and re.search(r"\d+ min|minute", est.inner_text()) is not None, f"({est.inner_text() if est.count() else ''!r})")
    check(f"{tag} « Sans limite » proposé (parties de l'app seulement)", page.locator("[data-testid=tc-unlimited]").count() == 1)
    check(f"{tag} aucune requête après les réglages", calls["n"] == 0, f"({calls['n']})")

    # Lancement avec bestmove retenu : la série démarre et reste sur la première recherche.
    page.evaluate("() => { window.__heldUci = [] }")
    tap(f"{tag} bouton Analyser", page, "[data-testid=insights-run]")
    if not ck.appears(f"{tag} barre de progression", page, "[role=progressbar]", timeout=20000):
        ctx.close()
        return
    check(f"{tag} requêtes chess.com après le tap seulement : archives + 2 mois (2026/07 jamais lue)", calls["n"] == 3, f"({calls['n']})")
    check(f"{tag} le moteur cherche (bestmove retenu)", wait_held(page))
    w = wake(page)
    check(f"{tag} écran gardé allumé pendant la série (wake lock tenu)", w is not None and w["requests"] == 1 and w["held"] == 1, f"({w})")
    check(f"{tag} progression : « Partie 1 sur 10 »", "Partie 1 sur 10" in main_text(page), f"({main_text(page)[:300]!r})")
    check(f"{tag} configuration figée pendant la série (panneau retiré)", page.locator("[data-testid=insights-config]").count() == 0 and page.locator("[data-testid=insights-run]").count() == 0)
    page.screenshot(path=f"{SHOTS}/insights_progress_852.png")

    # Page masquée : la recherche en cours se termine, la suivante attend le retour.
    set_hidden(page, True)
    ck.appears(f"{tag} page masquée : « En pause » affiché", page, "[data-testid=insights-paused]", timeout=5000)
    released = page.evaluate("() => window.__releaseUci()")
    page.evaluate("() => { window.__heldUci = [] }")
    page.wait_for_timeout(2000)
    check(f"{tag} page masquée : aucune nouvelle recherche lancée", released >= 1 and held_count(page) == 0, f"(relâchés {released}, nouveaux {held_count(page)})")
    set_hidden(page, False)
    check(f"{tag} page revenue : la série repart (nouvelle recherche)", wait_held(page, 15000))
    check(f"{tag} page revenue : « En pause » retiré", page.locator("[data-testid=insights-paused]").count() == 0)
    w = wake(page)
    check(f"{tag} page revenue : wake lock redemandé (le système l'avait relâché)", w is not None and w["requests"] == 2 and w["held"] == 1, f"({w})")

    # Annuler pendant une recherche retenue : l'interface n'attend pas le moteur.
    tap(f"{tag} bouton Annuler", page, "[data-testid=insights-cancel]")
    ck.appears(f"{tag} annulation : bandeau de reprise immédiat", page, "[data-testid=insights-resume]", timeout=3000)
    text = main_text(page)
    check(f"{tag} annulation : barre disparue, « 0 partie analysée sur 10 »", page.locator("[role=progressbar]").count() == 0 and "0 partie analysée sur 10" in text, f"({text[:300]!r})")
    released = page.evaluate("() => window.__releaseUci()")
    check(f"{tag} bestmove relâché après l'annulation (recherche orpheline terminée proprement)", released >= 1, f"({released})")
    page.wait_for_timeout(1500)
    check(f"{tag} aucune ligne en cache après l'annulation", len(rows_of(page, "reviews")) == 0)
    w = wake(page)
    check(f"{tag} annulation : wake lock relâché", w is not None and w["held"] == 0, f"({w})")
    check(f"{tag} toujours pas de rapport", page.locator("[data-testid=insights-report]").count() == 0)

    # Reprise : 10 parties courtes à la profondeur 12.
    tap(f"{tag} bouton Reprendre", page, "[data-testid=insights-resume]")
    if not ck.appears(f"{tag} reprise : rapport complet", page, "[data-testid=insights-report]", timeout=400000):
        ctx.close()
        return
    text = main_text(page)
    check(f"{tag} rapport : 10 parties de blitz (11 disponibles, 10 demandées)", "10 parties de blitz" in text, f"({text[:300]!r})")
    check(f"{tag} rapport : 4 victoires, 1 nulle, 5 défaites", all(s_ in text for s_ in ("4 victoires", "1 nulle", "5 défaites")), f"({text[:400]!r})")
    tm = "[data-testid=insights-time]"
    check(f"{tag} rapport : 1 défaite au temps, 10 parties avec horloges", data_attr(page, tm, "timeouts") == "1" and data_attr(page, tm, "games-with-clocks") == "10", f"({data_attr(page, tm, 'timeouts')}, {data_attr(page, tm, 'games-with-clocks')})")
    pm = int(data_attr(page, tm, "pressure-moves") or 0)
    pb = int(data_attr(page, tm, "pressure-blunders") or 0)
    check(f"{tag} rapport : coups sous pression (202, 203) dont la gaffe 3... Qh4?? à 14 s", pm >= 4 and pb >= 1, f"({pm}, {pb})")
    errs = page.locator("[data-testid=insights-errors] [data-kind=hanging]")
    check(f"{tag} rapport : pièce laissée en prise détectée (dame en h4)", errs.count() == 1 and page.locator("[data-testid=insights-errors] [data-kind=hanging] button[data-key='chesscom:202'][data-ply='6']").count() == 1, f"({errs.count()})")
    ops = page.locator("[data-testid=insights-openings]").inner_text()
    check(f"{tag} rapport : ouvertures en français (Partie espagnole, Défense sicilienne)", "Partie espagnole" in ops and "Défense sicilienne" in ops, f"({ops[:300]!r})")
    cached = rows_of(page, "reviews")
    keys = sorted(r["key"] for r in cached)
    want_keys = sorted(f"chesscom:{i}" for i in (202, 203, 204, 205, 206, 207, 208, 211, 212, 213))
    check(f"{tag} cache : les 10 parties les plus récentes (201 écartée), profondeur 12", keys == want_keys and all(r["source"] == "chesscom" and r["depth"] == 12 and r["username"] == USER for r in cached), f"({keys})")
    check(f"{tag} cache : la ligne 203 porte la défaite au temps", any(r["key"] == "chesscom:203" and r["lostOnTime"] is True and r["result"] == "loss" for r in cached))
    check(f"{tag} cache : Insights n'écrit rien dans « Mes erreurs »", len(rows_of(page, "mistakes")) == 0)
    saved = page.evaluate(f"() => JSON.parse(localStorage.getItem('{INSIGHTS_KEY}') || 'null')")
    check(f"{tag} configuration et rapport mémorisés", isinstance(saved, dict) and saved.get("config", {}).get("timeClass") == "blitz" and saved.get("config", {}).get("count") == 10 and len(saved.get("lastRun", {}).get("keys", [])) == 10, f"({saved})")
    w = wake(page)
    check(f"{tag} série finie : wake lock relâché", w is not None and w["held"] == 0, f"({w})")
    page.screenshot(path=f"{SHOTS}/insights_real_852.png", full_page=True)

    # Relance de la même configuration : tout est en cache, ni moteur ni rapport recalculé au moteur.
    before = calls["n"]
    page.evaluate("() => { window.__heldUci = [] }")
    tap(f"{tag} bouton Modifier", page, "[data-testid=insights-edit]")
    tap(f"{tag} panneau rouvert : bouton Analyser", page, "[data-testid=insights-run]")
    page.wait_for_timeout(300)
    ck.appears(f"{tag} relance : rapport", page, "[data-testid=insights-report] [data-testid=insights-coach]", timeout=30000)
    page.wait_for_timeout(1000)
    check(f"{tag} relance : la liste est relue sur chess.com (3 requêtes) mais aucune recherche moteur", calls["n"] == before + 3 and held_count(page) == 0, f"({calls['n'] - before} requêtes, {held_count(page)} bestmove)")
    page.evaluate("() => { window.__heldUci = null }")

    # Rechargement : rapport reconstruit depuis le cache, sans réseau.
    before = calls["n"]
    page.reload()
    ck.appears(f"{tag} rechargement : rapport depuis le cache", page, "[data-testid=insights-report]", timeout=15000)
    page.wait_for_timeout(500)
    check(f"{tag} rechargement : aucune requête chess.com", calls["n"] == before, f"({calls['n'] - before})")
    check(f"{tag} rechargement : pas de barre de progression", page.locator("[role=progressbar]").count() == 0)

    # Quitter la page en pleine série : moteur arrêté, aucune erreur, reprise depuis le cache.
    delete_row(page, "reviews", "chesscom:213")
    page.evaluate("() => { window.__heldUci = [] }")
    tap(f"{tag} départ : bouton Modifier", page, "[data-testid=insights-edit]")
    tap(f"{tag} départ : bouton Analyser", page, "[data-testid=insights-run]")
    check(f"{tag} départ : seule la partie retirée du cache est recherchée", wait_held(page))
    page.goto(f"{BASE}/#/stats")
    ck.appears(f"{tag} départ : Stats affichée", page, "main :text('Statistiques')", timeout=15000)
    page.evaluate("() => window.__releaseUci()")
    page.evaluate("() => { window.__heldUci = [] }")
    page.wait_for_timeout(1500)
    w = wake(page)
    check(f"{tag} départ : moteur arrêté (aucune recherche après le départ), wake lock relâché", held_count(page) == 0 and w is not None and w["held"] == 0, f"({held_count(page)}, {w})")
    check(f"{tag} départ : rien d'écrit pour la partie interrompue", not any(r["key"] == "chesscom:213" for r in rows_of(page, "reviews")))
    page.evaluate("() => { window.__heldUci = null }")
    page.goto(f"{BASE}/#/insights")
    ck.appears(f"{tag} retour : panneau (une partie du rapport manque au cache)", page, "[data-testid=insights-config]", timeout=15000)
    check(f"{tag} retour : pas de rapport incomplet", page.locator("[data-testid=insights-report]").count() == 0)
    tap(f"{tag} retour : bouton Analyser", page, "[data-testid=insights-run]")
    if ck.appears(f"{tag} retour : rapport, seule la partie manquante analysée", page, "[data-testid=insights-report]", timeout=120000):
        check(f"{tag} retour : 10 parties de blitz", "10 parties de blitz" in main_text(page), f"({main_text(page)[:200]!r})")
        cached = rows_of(page, "reviews")
        check(f"{tag} retour : 10 lignes en cache, toutes en profondeur 12", len(cached) == 10 and all(r["depth"] == 12 for r in cached), f"({[(r['key'], r['depth']) for r in cached]})")

    # Une ligne réécrite à une autre profondeur (série d'une autre taille quittée en cours) : le
    # rapport mémorisé ne se restaure pas, il mélangerait deux analyses.
    row = next((r for r in rows_of(page, "reviews") if r["key"] == "chesscom:202"), None)
    if check(f"{tag} profondeurs : ligne 202 en cache", row is not None):
        seed_db(page, {"reviews": [{**row, "depth": 10}]})
        page.reload()
        ck.appears(f"{tag} profondeurs mélangées : panneau plutôt que rapport", page, "[data-testid=insights-config]", timeout=15000)
        check(f"{tag} profondeurs mélangées : aucun rapport restauré", page.locator("[data-testid=insights-report]").count() == 0)
    ctx.close()


def offline_no_cache(p, browser):
    """chess.com injoignable et rien en cache : erreur française, Réessayer relance la lecture."""
    tag = "[injoignable]"
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": USER}, standalone=True, service_workers="block")
    calls = count_api_calls(ctx)
    ctx.route("https://api.chess.com/**", lambda route: route.abort())
    page = ctx.new_page()
    page.goto(f"{BASE}/#/insights")
    if not ck.appears(f"{tag} panneau", page, "[data-testid=insights-config]", timeout=15000):
        ctx.close()
        return
    tap(f"{tag} source ChessLocal retirée", page, "[data-testid=src-local]")
    tap(f"{tag} bouton Analyser", page, "[data-testid=insights-run]")
    if ck.appears(f"{tag} erreur affichée", page, "[role=alert]", timeout=15000):
        text = page.locator("[role=alert]").inner_text()
        check(f"{tag} message français, sans URL", "chess.com est injoignable" in text and "http" not in text, f"({text!r})")
        check(f"{tag} ni barre de progression ni rapport", page.locator("[role=progressbar]").count() == 0 and page.locator("[data-testid=insights-report]").count() == 0)
        before = calls["n"]
        if tap(f"{tag} bouton Réessayer", page, "[data-testid=insights-retry]"):
            page.wait_for_timeout(1500)
            check(f"{tag} Réessayer relance la lecture chess.com", calls["n"] > before and page.locator("[role=alert]").count() == 1, f"({calls['n'] - before})")
    ctx.close()


LOCAL_GAME = {"id": 7, "date": 1792500000000, "mode": "bot", "botId": "noa", "playerColor": "b", "timeControl": "illimité", "timeClass": "unlimited",
              "pgn": "[Event \"Partie vs Noa\"]\n[Site \"chess-local\"]\n[Result \"0-1\"]\n\n1. f3 e5 2. g4 Qh4# 0-1", "result": "0-1", "termination": "mat",
              "playerRatingAfter": 830}


def local_run(p, browser):
    """Cadence « Sans limite », source ChessLocal seule : aucune requête chess.com, la partie de
    l'archive est analysée et mise en cache sous `local:<id>`."""
    tag = "[ChessLocal]"
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
    calls = count_api_calls(ctx)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    ck.appears(f"{tag} Stats chargée", page, "main :text('Statistiques')", timeout=15000)
    if not check(f"{tag} base prête", wait_schema(page)):
        ctx.close()
        return
    seed_db(page, {"games": [LOCAL_GAME]})
    page.goto(f"{BASE}/#/insights")
    if not ck.appears(f"{tag} panneau", page, "[data-testid=insights-config]", timeout=15000):
        ctx.close()
        return
    tap(f"{tag} source ChessLocal retirée", page, "[data-testid=src-local]")
    page.fill("[data-testid=insights-username]", USER)
    check(f"{tag} chess.com seul en blitz : lancement possible", page.locator("[data-testid=insights-run]").is_enabled())
    tap(f"{tag} cadence Sans limite", page, "[data-testid=tc-unlimited]")
    check(f"{tag} chess.com seul sans limite : lancement désactivé et expliqué",
          page.locator("[data-testid=insights-run]").is_disabled() and "chess.com ne fournit pas la cadence « Sans limite »" in main_text(page))
    tap(f"{tag} source ChessLocal rétablie", page, "[data-testid=src-local]")
    check(f"{tag} sans limite avec ChessLocal : lancement réactivé", page.locator("[data-testid=insights-run]").is_enabled())
    tap(f"{tag} source chess.com retirée", page, "[data-testid=src-chesscom]")
    tap(f"{tag} choix 10 parties", page, "[data-testid=count-10]")
    check(f"{tag} sans pseudo ni chess.com : pas de champ pseudo, lancement possible", page.locator("[data-testid=insights-username]").count() == 0 and page.locator("[data-testid=insights-run]").is_enabled())
    tap(f"{tag} bouton Analyser", page, "[data-testid=insights-run]")
    if ck.appears(f"{tag} rapport", page, "[data-testid=insights-report]", timeout=60000):
        text = main_text(page)
        check(f"{tag} 1 partie de sans limite, gagnée (Noirs, mat du lion)", "1 partie de sans limite" in text and "1 victoire" in text, f"({text[:300]!r})")
        check(f"{tag} aucune requête chess.com", calls["n"] == 0, f"({calls['n']})")
        cached = rows_of(page, "reviews")
        check(f"{tag} cache : ligne local:7 contre Noa, profondeur 12", [(r["key"], r["opponent"], r["depth"], r["result"]) for r in cached] == [("local:7", "Noa", 12, "win")], f"({[(r['key'], r['opponent']) for r in cached]})")
        check(f"{tag} pendule : partie sans horloge signalée", "Aucune pendule" in page.locator("[data-testid=insights-time]").inner_text())
        saved = page.evaluate("key => JSON.parse(localStorage.getItem(key))", INSIGHTS_KEY)
        tables = {t: rows_of(page, t) for t in ("games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews")}
        for row in tables["games"] + tables["reviews"]:
            row["timeClass"] = "rapid"
            row["timeControl"] = "600"
        backup = {"_app": "chess-local", "_version": 3, "_date": "2026-10-14T12:00:00.000Z", **tables}
        page.goto(f"{BASE}/#/stats")
        if ck.appears(f"{tag} restauration disponible", page, "input[type=file]", state="attached"):
            page.set_input_files("input[type=file]", {"name": "autre-appareil.json", "mimeType": "application/json", "buffer": json.dumps(backup).encode()})
            if ck.appears(f"{tag} confirmation de restauration", page, "[data-testid=restore-confirm]"):
                page.click("[data-testid=restore-cancel]")
                check(f"{tag} restauration annulée : rapport conservé", page.evaluate("key => JSON.parse(localStorage.getItem(key))", INSIGHTS_KEY) == saved)
                page.set_input_files("input[type=file]", {"name": "autre-appareil.json", "mimeType": "application/json", "buffer": json.dumps(backup).encode()})
                if ck.appears(f"{tag} restauration confirmable", page, "[data-testid=restore-confirm]"):
                    page.click("[data-testid=restore-confirm]")
                    if ck.appears(f"{tag} restauration réussie", page, "[data-testid=backup-msg][data-kind=success]"):
                        check(f"{tag} restauration : toutes les données identiques au fichier", {t: rows_of(page, t) for t in tables} == tables)
                        restored = page.evaluate("key => JSON.parse(localStorage.getItem(key))", INSIGHTS_KEY)
                        check(f"{tag} restauration : dernier rapport invalidé, configuration conservée", restored == {"config": saved["config"], "lastRun": None})
                        page.goto(f"{BASE}/#/insights")
                        if ck.appears(f"{tag} retour au panneau après restauration", page, "[data-testid=insights-config]"):
                            check(f"{tag} aucune réutilisation du rapport avec les anciennes clés", page.locator("[data-testid=insights-report]").count() == 0)
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        if os.environ.get("INSIGHTS_CASE") == "f19":
            _, _, cases = node_bench(build_rows())
            if cases is not None:
                case_checks(cases)
            defense_guards(p, browser)
            trainer_links(p, browser)
            return
        if os.environ.get("INSIGHTS_CASE") == "trainers":
            trainer_links(p, browser)
            return
        rows = build_rows()
        ins, clocks, cases = node_bench(rows)
        if ins is not None:
            bench_checks(ins, clocks, rows)
            case_checks(cases)
            seeded_report(p, browser, rows, ins)
        trainer_links(p, browser)
        real_run(p, browser)
        offline_no_cache(p, browser)
        local_run(p, browser)
    finally:
        browser.close()


ck.run(suite)
