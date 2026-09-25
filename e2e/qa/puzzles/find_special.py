import json, chess, collections
from pz import all_puzzles
P = all_puzzles()
print("total", len(P))
ratings = [p[3] for p in P]
print("rating min/max", min(ratings), max(ratings))
hist = collections.Counter((r // 200) * 200 for r in ratings)
print("histo", sorted(hist.items()))
lens = collections.Counter(len(p[2].split()) for p in P)
print("longueurs (nb coups UCI)", sorted(lens.items()))
recapt = sum(1 for p in P if p[2].split()[1][2:4] == p[2].split()[0][2:4])
print("1er coup joueur = reprise sur la case d'arrivée du coup d'amorce:", recapt, f"({100*recapt/len(P):.1f} %)")
themes = collections.Counter(t for p in P for t in p[4].split())
print("thèmes les plus longs:", sorted(themes, key=len, reverse=True)[:8])
print("nb thèmes distincts", len(themes))
out = {}
# promotion joueur
for p in P:
    mv = p[2].split()
    if "promo" not in out and any(len(m) == 5 and m[4] == 'q' for m in mv[1::2]) and len(mv) <= 4 and 600 < p[3] < 1100:
        out["promo"] = p
    if "underpromo" not in out and any(len(m) == 5 and m[4] != 'q' for m in mv[1::2]):
        out["underpromo"] = p
    if "verylong" not in out and len(mv) >= 12:
        out["verylong"] = p
    if "recapture" not in out and len(mv) >= 4 and mv[1][2:4] == mv[0][2:4] and p[1].split()[1] == 'b':
        out["recapture"] = p
    if len(out) == 4: break
# mat alternatif au dernier coup
n_alt = 0
for p in P[:30000]:
    mv = p[2].split()
    if "mate" not in p[4].split(): continue
    b = chess.Board(p[1])
    for m in mv[:-1]: b.push_uci(m)
    alts = []
    for m in b.legal_moves:
        if m.uci() == mv[-1]: continue
        b.push(m)
        if b.is_checkmate(): alts.append(m.uci())
        b.pop()
    if alts:
        n_alt += 1
        if "altmate" not in out and len(mv) == 4:
            out["altmate"] = p; out["altmate_alt"] = alts
print("puzzles (sur 30000) avec un mat alternatif au dernier coup:", n_alt)
# longest themes string after filter
def label(p):
    return ", ".join([t for t in p[4].split() if t not in ("short","long","veryLong","oneMove")][:4])
longest = max(P, key=lambda p: len(label(p)))
out["longlabel"] = longest
print("libellé le plus long:", len(label(longest)), label(longest))
json.dump(out, open("special.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
