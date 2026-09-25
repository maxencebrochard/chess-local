import json, chess
from pz import all_puzzles
P = all_puzzles()
out = json.load(open("special.json"))
for p in P:
    mv = p[2].split()
    if "recapture1" not in out and len(mv) == 2 and mv[1][2:4] == mv[0][2:4] and len(mv[1]) == 4:
        b = chess.Board(p[1]); b.push_uci(mv[0]); b.push_uci(mv[1])
        if not b.is_checkmate():
            out["recapture1"] = p
    if "altmate2" not in out and "mate" in p[4].split() and len(mv) == 4:
        b = chess.Board(p[1])
        for m in mv[:-1]: b.push_uci(m)
        alts = []
        for m in b.legal_moves:
            if m.uci() == mv[-1] or m.promotion: continue
            b.push(m)
            if b.is_checkmate(): alts.append(m.uci())
            b.pop()
        if alts and len(mv[-1]) == 4:
            out["altmate2"] = p; out["altmate2_alt"] = alts
    # mat alternatif à un coup INTERMÉDIAIRE (la solution continue, mais un mat en 1 existe ?) -> rare, on ignore
    if "recapture1" in out and "altmate2" in out: break
json.dump(out, open("special.json", "w"), indent=1)
print(out["recapture1"]); print(out["altmate2"], out["altmate2_alt"])
