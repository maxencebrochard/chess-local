"""Vérifie avec Stockfish natif que chaque finale a bien l'issue théorique annoncée (win/draw pour `side`)."""
import json, chess, chess.engine
eg = json.load(open('src/data/endgames.json'))
for e in eg:
    b = chess.Board(e['fen'])
    pov = chess.WHITE if e['side'] == 'w' else chess.BLACK
    turn_ok = (b.turn == chess.WHITE) == (e['side'] == 'w')
    out = []
    for lim in (chess.engine.Limit(depth=10), chess.engine.Limit(time=4.0)):
        try:
            eng = chess.engine.SimpleEngine.popen_uci('/usr/local/bin/stockfish')
            info = eng.analyse(b, lim)
            out.append(f"{info['score'].pov(pov)}@d{info.get('depth')}")
            pv = ' '.join(m.uci() for m in info.get('pv', [])[:6])
            eng.quit()
        except Exception as ex:
            out.append('ERR ' + type(ex).__name__)
    print(f"{e['id']:20} side={e['side']} obj={e['objective']:4} trait_ok={turn_ok} d10={out[0]:12} 4s={out[1]:14} pv={pv}")
