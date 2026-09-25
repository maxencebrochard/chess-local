"""Jeu de données réaliste injecté dans IndexedDB `chess-local` (schéma src/lib/db.ts, version(2))."""
import time

NOW = int(time.time() * 1000)
DAY = 86_400_000

PGN_WIN = '[Event "Partie vs Marty"]\n[Site "chess-local"]\n[White "Moi"]\n[Black "Marty"]\n[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0'
PGN_DRAW = '[Event "Partie vs Léa"]\n[Site "chess-local"]\n[White "Moi"]\n[Black "Léa"]\n[Result "1/2-1/2"]\n\n1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 1/2-1/2'
PGN_LOSS = '[Event "Partie vs Nina"]\n[Site "chess-local"]\n[White "Moi"]\n[Black "Nina"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1'


def g(i, mode, color, result, tclass, tcontrol, bot=None, term="par abandon", rating=None):
    pgn = PGN_WIN if result == "1-0" else PGN_LOSS if result == "0-1" else PGN_DRAW
    row = {"date": NOW - i * DAY // 2, "mode": mode, "playerColor": color, "timeControl": tcontrol, "timeClass": tclass,
           "pgn": pgn, "result": result, "termination": term}
    if bot:
        row["botId"] = bot
    if rating:
        row["playerRatingAfter"] = rating
    return row


GAMES = [
    g(1, "bot", "w", "1-0", "blitz", "5 min", "marty", "par échec et mat", 838),       # victoire blancs
    g(2, "bot", "b", "0-1", "blitz", "3 | 2", "lea", "par abandon", 868),              # victoire noirs
    g(3, "bot", "w", "0-1", "rapid", "10 min", "nina", "par échec et mat", 790),       # défaite blancs
    g(4, "bot", "b", "1-0", "rapid", "15 | 10", "iris", "au temps", 772),              # défaite noirs
    g(5, "bot", "w", "1/2-1/2", "rapid", "10 min", "lea", "par répétition", 781),      # nulle blancs
    g(6, "bot", "b", "1/2-1/2", "bullet", "1 min", "marty", "par pat", 803),           # nulle noirs
    g(7, "bot", "w", "1-0", "unlimited", "Illimité", "noa", "par échec et mat", 822),  # victoire illimité
    g(8, "local", "w", "1-0", "unlimited", "Illimité", None, "par échec et mat"),      # local : hors bilan
    g(9, "local", "w", "1/2-1/2", "rapid", "10 min", None, "par accord mutuel"),       # local : hors bilan
    g(10, "local", "w", "0-1", "blitz", "5 min", None, "par abandon"),                 # local : hors bilan
]
EXPECTED = {"wins": 3, "draws": 2, "losses": 2, "bot_total": 7, "all_games": 10}

RATINGS = [
    {"key": "bullet", "value": 803, "games": 1},
    {"key": "blitz", "value": 868, "games": 2},
    {"key": "rapid", "value": 781, "games": 3},
    {"key": "unlimited", "value": 822, "games": 1},
    {"key": "puzzle", "value": 1034, "games": 12},
    {"key": "learn-endgame", "value": 850, "games": 4},
    {"key": "learn-tactic", "value": 905, "games": 5},
]

PUZZLE_ATTEMPTS = [
    {"puzzleId": f"qa{i:03d}", "date": NOW - i * 3_600_000, "success": i % 3 != 0, "puzzleRating": 900 + i * 15, "ratingAfter": 1034 - i * 9}
    for i in range(12)
]  # i%3==0 -> échec : i=0,3,6,9 => 4 échecs, 8 réussites
EXPECTED["solved"] = 8
EXPECTED["attempts"] = 12

RUSH = [
    {"mode": "3min", "score": 14, "date": NOW - 3 * DAY},
    {"mode": "3min", "score": 9, "date": NOW - 2 * DAY},
    {"mode": "5min", "score": 21, "date": NOW - DAY},
    {"mode": "survival", "score": 17, "date": NOW - DAY},
]

MISTAKES = [
    {"date": NOW - DAY, "gameLabel": "vs Nina", "fenBefore": "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2", "playedSan": "g4", "bestUci": "e2e4", "cls": "blunder", "attempts": 0, "solved": 0},
    {"date": NOW - 2 * DAY, "gameLabel": "vs Iris", "fenBefore": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3", "playedSan": "Nd4", "bestUci": "g8f6", "cls": "mistake", "attempts": 1, "solved": 0},
    {"date": NOW - 3 * DAY, "gameLabel": "vs Léa", "fenBefore": "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3", "playedSan": "Ng5", "bestUci": "f3e5", "cls": "miss", "attempts": 2, "solved": 1},
]

LEARN = [
    {"date": NOW - DAY, "domain": "endgame", "itemId": "kq-k", "success": 1, "ratingAfter": 850},
    {"date": NOW - DAY, "domain": "tactic", "itemId": "fork", "success": 0, "ratingAfter": 905},
    {"date": NOW - 2 * DAY, "domain": "strategy", "itemId": "s1", "success": 1, "ratingAfter": None},
]

DATA = {"games": GAMES, "ratings": RATINGS, "puzzleAttempts": PUZZLE_ATTEMPTS, "rushScores": RUSH, "mistakes": MISTAKES, "learnSessions": LEARN}

SEED_JS = """async (data) => {
  const open = () => new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const idb = await open()
  const names = Object.keys(data)
  await new Promise((res, rej) => {
    const tx = idb.transaction(names, 'readwrite')
    for (const n of names) { const st = tx.objectStore(n); st.clear(); for (const row of data[n]) st.put(row) }
    tx.oncomplete = res; tx.onerror = () => rej(tx.error)
  })
  idb.close()
  return true
}"""

DUMP_JS = """async () => {
  const open = () => new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const idb = await open()
  const out = {}
  for (const n of [...idb.objectStoreNames]) {
    out[n] = await new Promise((res, rej) => { const rq = idb.transaction(n).objectStore(n).getAll(); rq.onsuccess = () => res(rq.result); rq.onerror = () => rej(rq.error) })
  }
  idb.close()
  return out
}"""


def seed(page, data=None):
    """La base doit déjà exister (une visite préalable de l'app)."""
    return page.evaluate(SEED_JS, data or DATA)


def dump_counts(page):
    d = page.evaluate(DUMP_JS)
    return {k: len(v) for k, v in d.items()}
