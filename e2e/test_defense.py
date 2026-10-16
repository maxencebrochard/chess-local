"""E2E « Entraîneur de défense » (/defense) et « Mes défenses ratées » (/defenses-ratees).

1. Banque src/data/defenses.json : volume, répartition, légalité, défenseur au trait, catégorie
   recalculée par un code indépendant du générateur (attaquant = camp qui n'est pas au trait),
   thème/consigne/plan égaux à scripts/defense_facts.py, et invariants indépendants : pièces et
   pions cités de la bonne couleur, roi cité celui du défenseur, colonnes et tempête relues sur
   l'échiquier, comptes d'attaquants et de défenseurs égaux à un oracle python-chess.
2. Logique « tenir » sous Node (bundle rolldown de positionGame.ts et defense.ts) : réussite après
   12 coups au-dessus du plancher, échec après deux tours sous le plancher ou au mat, nulle et gain
   qui comptent, issues enregistrées, et non-régression de `decisiveStreak` et `judge` (attaque,
   finales).
3. Liste : entrée depuis Apprendre, onglets, niveau de l'attaquant (2100 par défaut, mémorisé à
   part de l'attaque).
4. Partie : défenseur au trait et en bas de l'échiquier, consigne, « Coup 0/12 », pas de Nulle,
   attaquant bridé (UCI espionné), oracle jamais bridé, abandon noté (`resign`), Recommencer noté
   (`abandon`), série sous le plancher rejouée après rechargement.
5. Vraie défense : attaquant à 1320, coups du défenseur par un second Stockfish dans la page,
   confirmation au 12e coup échiquier bloqué, « Défense réussie », ligne IndexedDB, Analyser et
   retour, liste « ✓ tenu à 1320 ».
6. Mes défenses ratées : faute semée sous une vraie attaque listée (comptes = oracle), témoins
   absents (pas d'attaque, classe « miss », camp inconnu), exercice du coup du bilan, état vide.
7. Mise en page : 393x852, 393x660 et 1440x900, sans débordement horizontal.

Usage : npm run test:e2e -- --suite defense
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import chess

from helpers import BASE, E2E_DIR, HOLD_BESTMOVE, Checker, desktop_context, mobile_context, overflow_x, shot, tap_move

ROOT = os.path.dirname(E2E_DIR)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import attack_facts  # noqa: E402
import defense_facts  # noqa: E402

ck = Checker("defense")
check = ck.check

DATA = os.path.join(ROOT, "src", "data", "defenses.json")
DEFENSES = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else []
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
GAME = "[data-testid='position-game']"
CATS = ("opposes", "meme", "centre")
SHORT = {"opposes": "Roques opposés", "meme": "Même aile", "centre": "Roi au centre"}
PREFS = "chess-local-defense"
ATTACK_PREFS = "chess-local-attack"
STORED = "chess-local-position-game-v1"

# Espion UCI (même principe que test_attaque) : workers numérotés, commandes journalisées.
UCI_SPY = """(() => {
  const Native = window.Worker
  window.__NativeWorker = Native
  window.__uci = []
  let n = 0
  window.Worker = class extends Native {
    constructor(...args) {
      super(...args)
      this.__idx = n++
    }
    postMessage(msg, ...rest) {
      if (typeof msg === 'string') window.__uci.push([this.__idx, msg])
      return super.postMessage(msg, ...rest)
    }
  }
})()"""
QA_WAIT = """
window.__qaWait = (pred) => new Promise((resolve) => {
  const t = setInterval(() => {
    const i = window.__qaLines.findIndex(pred)
    if (i >= 0) { clearInterval(t); resolve(window.__qaLines[i]) }
  }, 5)
})
"""
QA_ENGINE = """
async ([url, fen, depth]) => {
  if (!window.__qaWorker) {
    const w = new window.__NativeWorker(url)
    window.__qaLines = []
    w.onmessage = (e) => window.__qaLines.push(String(e.data))
    window.__qaWorker = w
    w.postMessage('uci')
    await window.__qaWait((l) => l === 'uciok')
  }
  const w = window.__qaWorker
  window.__qaLines.length = 0
  w.postMessage('position fen ' + fen)
  w.postMessage('go depth ' + depth)
  const bm = await window.__qaWait((l) => l.startsWith('bestmove'))
  return bm.split(' ')[1]
}
"""
IDB = """([store, body, arg]) => new Promise((resolve, reject) => {
  const req = indexedDB.open('chess-local')
  req.onerror = () => reject(req.error)
  req.onsuccess = () => {
    const db = req.result
    if (!db.objectStoreNames.contains(store)) { db.close(); resolve(null); return }
    new Function('db', 'arg', 'resolve', 'reject', body)(db, arg, (v) => { db.close(); resolve(v) }, reject)
  }
})"""


# ---------- 1. Données ----------

def rel(sq, color):
    r = chess.square_rank(sq)
    return r if color == chess.WHITE else 7 - r


def indep_category(board):
    """Catégorie recalculée à partir des seules cases des rois, attaquant = camp qui n'est pas au
    trait (écrit à part du générateur)."""
    dfn = board.turn
    att = not dfn

    def side(sq, color):
        if rel(sq, color) > 1:
            return None
        return {0: "q", 1: "q", 2: "q", 3: "c", 4: "c", 6: "k", 7: "k"}.get(chess.square_file(sq))

    d, a = side(board.king(dfn), dfn), side(board.king(att), att)
    if d == "c":
        # Roi du défenseur au centre : l'attaquant a seulement son roi sur ses deux premières rangées.
        return "centre" if rel(board.king(att), att) <= 1 else None
    if d in ("q", "k") and a in ("q", "k"):
        return "opposes" if d != a else "meme"
    return None


def zone_oracle(board):
    """Abords du roi du défenseur, définis à part : sa case, ses voisines, et les trois cases deux
    rangées devant lui (vers l'attaquant). Retourne (attaquants, défenseurs) : pièces hors pions et
    roi de chaque camp qui visent une de ces cases."""
    dfn = board.turn
    k = board.king(dfn)
    kf, kr = chess.square_file(k), chess.square_rank(k)
    step = 1 if dfn == chess.WHITE else -1
    cells = set()
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            f, r = kf + df, kr + dr
            if 0 <= f <= 7 and 0 <= r <= 7:
                cells.add(chess.square(f, r))
        f, r = kf + df, kr + 2 * step
        if 0 <= f <= 7 and 0 <= r <= 7:
            cells.add(chess.square(f, r))

    def pieces(color):
        out = set()
        for c in cells:
            for s in board.attackers(color, c):
                if board.piece_type_at(s) not in (chess.PAWN, chess.KING):
                    out.add(chess.square_name(s))
        return out

    return pieces(not dfn), pieces(dfn)


def squares_after(text, lead):
    """Cases citées après `lead` jusqu'au prochain « : » (« en g1 et h5 », « h4, g5 et f6 »)."""
    out = []
    for m in re.finditer(re.escape(lead) + r"([a-h][1-8](?:(?:, | et )[a-h][1-8])*)", text):
        out += re.findall(r"[a-h][1-8]", m.group(1))
    return out


def weakened(board):
    """Roque entamé du défenseur, vérifié à part (même règle que test_attaque, camp au trait)."""
    dfn = board.turn
    k = board.king(dfn)
    kf, kr = chess.square_file(k), rel(k, dfn)
    for f in (kf - 1, kf, kf + 1):
        if f not in (0, 1, 2, 5, 6, 7):
            continue
        ranks = sorted(rel(s, dfn) for s in board.pieces(chess.PAWN, dfn) if chess.square_file(s) == f and rel(s, dfn) > kr)
        if not ranks:
            return True
        if ranks[0] - kr >= 2:
            behind_rank = ranks[0] - 1
            sq = chess.square(f, behind_rank if dfn == chess.WHITE else 7 - behind_rank)
            p = board.piece_at(sq)
            if not (p and p.color == dfn and p.piece_type == chess.BISHOP):
                return True
    return False


def check_data():
    check("[données] banque présente", bool(DEFENSES), f"({DATA})")
    if not DEFENSES:
        return
    counts = {c: sum(1 for d in DEFENSES if d["category"] == c) for c in CATS}
    check("[données] au moins 45 positions", len(DEFENSES) >= 45, f"({len(DEFENSES)})")
    check("[données] au moins 10 par catégorie", min(counts.values()) >= 10, f"({counts})")
    check("[données] ids uniques, préfixe def-", len({d["id"] for d in DEFENSES}) == len(DEFENSES) and all(d["id"].startswith("def-") for d in DEFENSES))
    check("[données] positions uniques", len({" ".join(d["fen"].split()[:2]) for d in DEFENSES}) == len(DEFENSES))
    check("[données] une position par partie", len({d["source"]["game"] for d in DEFENSES}) == len(DEFENSES))
    keys = {"id", "fen", "defender", "category", "theme", "goal", "plan", "eval", "source"}
    check("[données] champs attendus", all(set(d) == keys for d in DEFENSES), f"({[sorted(d) for d in DEFENSES if set(d) != keys][:1]})")
    kinds = ("legal", "turn", "cat", "facts", "eval", "material", "head", "kings", "before", "file", "storm", "shield", "castle",
             "heavy", "storm_color", "own_pawn", "attackers", "defenders", "counts")
    bad = {k: [] for k in kinds}
    for d in DEFENSES:
        b = chess.Board(d["fen"])
        dfn, att = b.turn, not b.turn
        if not b.is_valid() or b.is_check():
            bad["legal"].append(d["id"])
        if ("w" if dfn == chess.WHITE else "b") != d["defender"]:
            bad["turn"].append(d["id"])
        if indep_category(b) != d["category"]:
            bad["cat"].append(d["id"])
        f = defense_facts.defense_facts(b)
        if (defense_facts.defense_theme(d["category"], f), defense_facts.goal(d["category"], f), defense_facts.plan(b, d["category"], f)) != (d["theme"], d["goal"], d["plan"]):
            bad["facts"].append(d["id"])
        if not (-200 <= d["eval"] <= 30):
            bad["eval"].append(d["id"])
        if attack_facts.material(b, att) - attack_facts.material(b, dfn) > 1:
            bad["material"].append(d["id"])
        if d["source"]["before"] not in (1, 3, 5):
            bad["before"].append(d["id"])
        g, plan = d["goal"], d["plan"]
        if not g.startswith(SHORT[d["category"]] + " : "):
            bad["head"].append(d["id"])
        dk, ak = b.king(dfn), b.king(att)
        if f"Ton roi est en {chess.square_name(dk)}" not in plan and f"au centre en {chess.square_name(dk)}" not in plan \
                and f"({chess.square_name(dk)} et {chess.square_name(ak)})" not in plan:
            bad["kings"].append(d["id"])
        near = {chess.square_file(dk) + i for i in (-1, 0, 1)}
        m = re.search(r"colonne ([a-h])\b", g)
        if m:
            fi = "abcdefgh".index(m.group(1))
            if any(chess.square_file(s) == fi for s in b.pieces(chess.PAWN, att)) or fi not in near:
                bad["file"].append(d["id"])
        m = re.search(r"freine (?:son pion|ses pions) ([a-h](?:(?:, | et )[a-h])*)\.", g)
        if m:
            for fl in re.findall(r"\b[a-h]\b", m.group(1)):
                fi = "abcdefgh".index(fl)
                if fi not in near or not any(chess.square_file(s) == fi and rel(s, att) >= 3 for s in b.pieces(chess.PAWN, att)):
                    bad["storm"].append(d["id"])
        if "roque affaibli" in g and not weakened(b):
            bad["shield"].append(d["id"])
        rights = d["fen"].split()[2]
        mine = [c for c in rights if (c.isupper() if dfn == chess.WHITE else c.islower())]
        if ("mets ton roi à l'abri" in g and not mine) or ("ne peux plus roquer" in g and mine):
            bad["castle"].append(d["id"])
        # Pièces citées : celles de l'attaquant (« sa / ses ») et du défenseur (« ton / tes »).
        for sq in squares_after(plan, "Sa pièce lourde en ") + squares_after(plan, "Ses pièces lourdes en "):
            p = b.piece_at(chess.parse_square(sq))
            if not (p and p.color == att and p.piece_type in (chess.ROOK, chess.QUEEN)):
                bad["heavy"].append(f"{d['id']}:{sq}")
        for sq in squares_after(plan, "Son pion ") + squares_after(plan, "Ses pions "):
            p = b.piece_at(chess.parse_square(sq))
            if not (p and p.color == att and p.piece_type == chess.PAWN):
                bad["storm_color"].append(f"{d['id']}:{sq}")
        for sq in squares_after(plan, "Ton pion ") + squares_after(plan, "Tes pions "):
            p = b.piece_at(chess.parse_square(sq))
            if not (p and p.color == dfn and p.piece_type == chess.PAWN):
                bad["own_pawn"].append(f"{d['id']}:{sq}")
        o_att, o_def = zone_oracle(b)
        cited = squares_after(plan, "abords de ton roi (")
        if set(cited) != o_att or len(o_att) < 2 or any(b.color_at(chess.parse_square(s)) != att for s in cited):
            bad["attackers"].append(d["id"])
        cited_def = squares_after(plan, "Tes pièces en ") + squares_after(plan, "Ta pièce en ")
        m = re.search(r"\((\d) contre (\d)\)", plan)
        if m:
            if (int(m.group(1)), int(m.group(2))) != (len(o_att), len(o_def)) or len(o_def) >= len(o_att):
                bad["counts"].append(d["id"])
        elif set(cited_def) != o_def or any(b.color_at(chess.parse_square(s)) != dfn for s in cited_def) or len(o_def) < len(o_att):
            bad["defenders"].append(d["id"])
    labels = {
        "legal": "positions légales, pas d'échec au départ",
        "turn": "défenseur au trait",
        "cat": "catégorie recalculée depuis les rois (attaquant = camp pas au trait)",
        "facts": "thème, consigne et plan égaux à defense_facts.py",
        "eval": "éval de sélection entre -2 et +0,3 pour le défenseur",
        "material": "défenseur pas plus d'un pion derrière",
        "head": "consigne commencée par la catégorie",
        "kings": "plan qui cite le roi du défenseur",
        "before": "recul impair (1, 3 ou 5 demi-coups) : défenseur au trait",
        "file": "colonne citée : sans pion de l'attaquant, voisine du roi du défenseur",
        "storm": "pions à freiner : de l'attaquant, sur leur 4e rangée ou plus, voisins du roi",
        "shield": "« roque affaibli » vérifié sur l'échiquier",
        "castle": "droits de roque conformes à la consigne",
        "heavy": "pièces lourdes citées : tours ou dame de l'attaquant",
        "storm_color": "« son pion / ses pions » : pions de l'attaquant",
        "own_pawn": "« ton pion / tes pions » : pions du défenseur",
        "attackers": "attaquants cités = oracle python-chess (au moins deux, de l'attaquant)",
        "defenders": "défenseurs cités = oracle python-chess (du défenseur)",
        "counts": "« n contre d » = oracle python-chess",
    }
    for k, label in labels.items():
        check(f"[données] {label}", not bad[k], f"({bad[k][:5]})")
    check("[données] plusieurs thèmes", len({d["theme"] for d in DEFENSES}) >= 3)
    check("[données] la banque fait défendre les Blancs et les Noirs", {d["defender"] for d in DEFENSES} == {"w", "b"})
    # Le contrôle des cases citées sait échouer : un plan dont la pièce lourde est un cavalier.
    fake = "r1bq1rk1/pp3ppp/2n1p3/3pP1N1/3P4/2NB4/PP3PPP/R2QK2R b KQ - 1 10"
    fb = chess.Board(fake)
    check("[données] témoin : une case citée vide n'est pas une pièce lourde de l'attaquant",
          not (fb.piece_at(chess.parse_square("g5")) and fb.piece_at(chess.parse_square("g5")).piece_type in (chess.ROOK, chess.QUEEN)))


# ---------- 2. Logique « tenir » sous Node ----------

NODE_ENTRY = """
export * from '%(pg)s'
export { defenseOutcomeOf, defenseSucceeded } from '%(def)s'
"""
NODE_RUN = r"""
globalThis.location ??= { href: '' }
const m = await import(process.argv[2])
const out = {}
const F = m.HOLD_FLOOR_CP
// Réussite : 12 tours au-dessus du plancher, puis confirmation au plancher.
let s = 0
for (let i = 0; i < m.HOLD_MOVES; i++) s = m.holdStreak(s, -250, null, F)
out.streakAbove = s
const held = m.holdsAt(-280, null, F) ? m.heldEnd({ cp: -280, mate: null }) : null
out.held = held && { judge: m.judge(held, 'w', 'hold'), text: m.verdictText(held, 'w', 'hold', m.HOLD_MOVES), outcome: m.defenseOutcomeOf(held, 'w') }
// Échec : deux tours à -7, ou au mat ; un tour seul ne suffit pas, un retour au-dessus remet à zéro.
out.seven = [m.holdStreak(0, -700, null, F), m.holdStreak(m.holdStreak(0, -700, null, F), -720, null, F)]
out.mate = [m.holdStreak(0, null, -4, F), m.holdStreak(1, null, -2, F)]
out.reset = m.holdStreak(1, -120, null, F)
out.edges = { at: m.holdStreak(0, -300, null, F), below: m.holdStreak(0, -301, null, F), mateFor: m.holdStreak(1, null, 3, F) }
out.turns = m.DECISIVE_TURNS
out.confirm = { at: m.holdsAt(-300, null, F), below: m.holdsAt(-301, null, F), mated: m.holdsAt(null, -5, F), mating: m.holdsAt(null, 2, F), none: m.holdsAt(null, null, F) }
const col = m.collapsedEnd('b', { cp: -712, mate: null })
out.collapsed = { judge: m.judge(col, 'b', 'hold'), text: m.verdictText(col, 'b', 'hold', 5), outcome: m.defenseOutcomeOf(col, 'b'), result: col.result }
const colMate = m.collapsedEnd('w', { cp: null, mate: -3 })
out.collapsedMate = m.verdictText(colMate, 'w', 'hold', 1)
// Nulles de l'échiquier et gain : réussites ; mat subi et abandon : échecs.
const end = (result, kind) => ({ result, kind })
out.hold = {
  repetition: m.judge(end('1/2-1/2', 'repetition'), 'w', 'hold'),
  stalemate: m.judge(end('1/2-1/2', 'stalemate'), 'b', 'hold'),
  win: m.judge(end('0-1', 'mate'), 'b', 'hold'),
  mated: m.judge(end('1-0', 'mate'), 'b', 'hold'),
  resign: m.judge(m.resignEnd('w'), 'w', 'hold'),
}
out.holdTitles = {
  draw: m.verdictText(end('1/2-1/2', 'repetition'), 'w', 'hold', 7),
  mated: m.verdictText(end('1-0', 'mate'), 'b', 'hold', 6),
}
out.outcomes = {
  draw: m.defenseOutcomeOf(end('1/2-1/2', 'fifty'), 'w'), win: m.defenseOutcomeOf(end('1-0', 'mate'), 'w'),
  mated: m.defenseOutcomeOf(end('1-0', 'mate'), 'b'), resign: m.defenseOutcomeOf(m.resignEnd('b'), 'b'),
}
out.succeeded = ['held', 'draw', 'win', 'mated', 'collapsed', 'resign', 'abandon'].filter((o) => m.defenseSucceeded(o))
// Non-régression : attaque (gain, avantage décisif) et finales (nulle).
out.decisive = [m.decisiveStreak(0, 700, null, 700), m.decisiveStreak(1, 699, null, 700), m.decisiveStreak(1, null, 3, 700), m.decisiveStreak(2, null, -3, 700)]
out.win = {
  mate: m.judge(end('1-0', 'mate'), 'w', 'win'), draw: m.judge(end('1/2-1/2', 'stalemate'), 'w', 'win'),
  decisive: m.judge(m.decisiveEnd('b'), 'b', 'win'), title: m.verdictText(end('1-0', 'mate'), 'w', 'win', 3),
  fail: m.verdictText(end('1/2-1/2', 'repetition'), 'w', 'win', 3),
}
out.draw = { draw: m.judge(end('1/2-1/2', 'fifty'), 'b', 'draw'), win: m.judge(end('0-1', 'mate'), 'b', 'draw'), loss: m.judge(end('1-0', 'mate'), 'b', 'draw') }
out.free = m.judge(end('1-0', 'mate'), 'w', null)
out.evalText = [m.evalText({ cp: -128, mate: null }), m.evalText({ cp: 45, mate: null }), m.evalText({ cp: 0, mate: null }), m.evalText({ cp: null, mate: -2 })]
console.log(JSON.stringify(out))
"""


def node_logic():
    with tempfile.TemporaryDirectory() as d:
        entry = os.path.join(d, "entry.ts")
        with open(entry, "w", encoding="utf-8") as f:
            f.write(NODE_ENTRY % {"pg": os.path.join(ROOT, "src", "lib", "positionGame.ts"), "def": os.path.join(ROOT, "src", "lib", "defense.ts")})
        bundle = os.path.join(d, "hold.mjs")
        r = subprocess.run([ROLLDOWN, entry, "--format", "esm", "--file", bundle], cwd=ROOT, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            ck.fail("[logique] bundle rolldown de positionGame.ts et defense.ts", (r.stderr or r.stdout)[-300:])
            return None
        script = os.path.join(d, "run.mjs")
        with open(script, "w", encoding="utf-8") as f:
            f.write(NODE_RUN)
        r = subprocess.run(["node", script, "file://" + bundle], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        ck.fail("[logique] exécution sous Node", r.stderr.strip()[-400:])
        return None
    return json.loads(r.stdout.strip().splitlines()[-1])


def check_logic():
    o = node_logic()
    if o is None:
        return
    t = "[logique]"
    check(f"{t} 12 tours à -2,5 : aucune série sous le plancher", o["streakAbove"] == 0, f"({o['streakAbove']})")
    h = o["held"]
    check(f"{t} 12 coups puis confirmation à -2,8 : « Défense réussie »", h and h["judge"] == "success" and h["text"]["title"] == "Défense réussie", f"({h})")
    check(f"{t} raison : coups tenus et éval finale", h and h["text"]["reason"] == "Tu as tenu 12 coups : éval -2,8.", f"({h and h['text']})")
    check(f"{t} issue `held`", h and h["outcome"] == "held")
    check(f"{t} -7 deux tours de suite : la série atteint DECISIVE_TURNS (2)", o["seven"] == [1, 2] and o["turns"] == 2, f"({o['seven']}, {o['turns']})")
    check(f"{t} mat contre le joueur deux tours de suite", o["mate"] == [1, 2], f"({o['mate']})")
    check(f"{t} retour au-dessus du plancher : série remise à zéro", o["reset"] == 0)
    check(f"{t} plancher : -3,00 tient, -3,01 tombe, un mat pour le joueur remet à zéro", o["edges"] == {"at": 0, "below": 1, "mateFor": 0}, f"({o['edges']})")
    check(f"{t} confirmation : -3 tient, -3,01 non, mat contre lui non, mat pour lui oui, sans éval non",
          o["confirm"] == {"at": True, "below": False, "mated": False, "mating": True, "none": False}, f"({o['confirm']})")
    c = o["collapsed"]
    check(f"{t} effondrement : « La défense a cédé », échec, issue `collapsed`, défaite",
          c["judge"] == "fail" and c["text"]["title"] == "La défense a cédé" and c["outcome"] == "collapsed" and c["result"] == "1-0", f"({c})")
    check(f"{t} effondrement : raison avec coups tenus et éval", c["text"]["reason"] == "L'attaque a percé après 5 coups tenus : éval -7,1.", f"({c['text']})")
    check(f"{t} effondrement au mat annoncé, singulier", o["collapsedMate"]["reason"] == "L'attaque a percé après 1 coup tenu : mat en 3 contre toi.", f"({o['collapsedMate']})")
    check(f"{t} nulle (répétition, pat) et gain : réussites ; mat subi et abandon : échecs",
          o["hold"] == {"repetition": "success", "stalemate": "success", "win": "success", "mated": "fail", "resign": "fail"}, f"({o['hold']})")
    check(f"{t} nulle : titre « Défense réussie » ; mat subi : « La défense a cédé »",
          o["holdTitles"]["draw"]["title"] == "Défense réussie" and o["holdTitles"]["mated"] == {"title": "La défense a cédé", "reason": "Tu es mat après 6 coups."},
          f"({o['holdTitles']})")
    check(f"{t} issues : draw, win, mated, resign", o["outcomes"] == {"draw": "draw", "win": "win", "mated": "mated", "resign": "resign"}, f"({o['outcomes']})")
    check(f"{t} réussite = held, draw ou win", o["succeeded"] == ["held", "draw", "win"], f"({o['succeeded']})")
    check(f"{t} attaque inchangée : decisiveStreak (+7, +6,99, mat pour, mat contre)", o["decisive"] == [1, 0, 2, 0], f"({o['decisive']})")
    w = o["win"]
    check(f"{t} attaque inchangée : judge gain (mat, nulle, avantage décisif) et titres",
          w["mate"] == "success" and w["draw"] == "fail" and w["decisive"] == "success"
          and w["title"] == {"title": "Objectif atteint", "reason": "Mat en 3 coups."} and w["fail"]["title"] == "Objectif manqué", f"({w})")
    check(f"{t} finales inchangées : judge nulle", o["draw"] == {"draw": "success", "win": "success", "loss": "fail"}, f"({o['draw']})")
    check(f"{t} partie libre : pas de verdict", o["free"] is None)
    check(f"{t} éval lisible", o["evalText"] == ["éval -1,3", "éval +0,5", "éval 0,0", "mat en 2 contre toi"], f"({o['evalText']})")


# ---------- Outils de partie ----------

def attr(page, name):
    return page.evaluate(f"() => document.querySelector(\"{GAME}\")?.getAttribute('data-{name}') ?? null")


def wait_turn(page, color, timeout_s=30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if attr(page, "status") == "over":
            return "over"
        f = attr(page, "fen")
        if f and f.split(" ")[1] == color and attr(page, "thinking") == "0":
            return "turn"
        page.wait_for_timeout(100)
    return "timeout"


def best_move(page, fen, depth):
    return page.evaluate(QA_ENGINE, [f"{BASE}/engine/stockfish-18-lite-single.js", fen, depth])


def play(page, uci):
    tap_move(page, uci[:2], uci[2:4], pause=150)
    if len(uci) == 5:
        promo = page.locator("div.absolute.inset-0.z-20 button")
        promo.first.wait_for(timeout=3000)
        promo.nth("qrbn".index(uci[4])).tap()


def play_best(page, color, depth, tag):
    """Un coup du défenseur (second Stockfish). True si joué."""
    if wait_turn(page, color) != "turn":
        return False
    before = attr(page, "fen")
    uci = best_move(page, before, depth)
    play(page, uci)
    page.wait_for_timeout(150)
    if attr(page, "fen") == before:
        ck.fail(f"[{tag}] coup {uci} refusé par l'échiquier")
        return False
    return True


def workers(log):
    out = {}
    for idx, msg in log:
        out.setdefault(idx, []).append(msg)
    return out


def options_before_first_go(msgs):
    first_go = next((i for i, m in enumerate(msgs) if m.startswith("go ")), len(msgs))
    return [m for m in msgs[:first_go] if m.startswith("setoption")]


def rows(page, domain="defense"):
    r = page.evaluate(IDB, ["learnSessions", "const q = db.transaction('learnSessions').objectStore('learnSessions').getAll();"
                        "q.onsuccess = () => resolve(q.result); q.onerror = () => reject(q.error)", None])
    return [x for x in (r or []) if x.get("domain") == domain]


def counter(page):
    el = page.locator("[data-testid='hold-counter']")
    return (el.inner_text() or "").strip() if el.count() else None


def open_defense(page, pid):
    page.goto(f"{BASE}/#/defense/{pid}")
    ok = ck.appears(f"[{pid}] partie affichée", page, GAME)
    page.wait_for_timeout(300)
    return ok


def no_overflow(page, tag):
    check(f"[mise en page] {tag} : pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")


def bar_fits(page, tag):
    w = page.evaluate(f"""() => {{
      const g = document.querySelector("{GAME}")
      const bar = g && g.lastElementChild
      return bar ? bar.scrollWidth - bar.clientWidth : null
    }}""")
    check(f"[mise en page] {tag} : barre d'actions sans débordement", w is not None and w <= 0, f"({w})")


def white_at_bottom(page):
    a1 = page.locator("[data-square='a1']").first.bounding_box()
    a8 = page.locator("[data-square='a8']").first.bounding_box()
    return a1["y"] > a8["y"] if a1 and a8 else None


# ---------- Suite ----------

def part_list_and_game(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(UCI_SPY)
    ctx.add_init_script(HOLD_BESTMOVE)
    ctx.add_init_script(QA_WAIT)
    page = ctx.new_page()

    # --- 3. Entrée, liste, niveau ---
    page.goto(f"{BASE}/#/apprendre")
    tile = "main a:has-text(\"Entraîneur de défense\")"
    if ck.appears("[entrée] tuile sur l'accueil Apprendre", page, tile):
        page.locator(tile).tap()
    ck.appears("[liste] page de l'entraîneur", page, "[data-testid='defense-item']")
    check("[liste] URL #/defense", page.evaluate("() => location.hash").startswith("#/defense"), f"({page.url})")
    check("[liste] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
    check("[liste] niveau par défaut : 2100", page.locator("[data-testid='attacker'] [role='radio'][data-level='2100'][aria-checked='true']").count() == 1)
    for c in CATS:
        tab = page.locator(f"[role='tab'][data-category='{c}']")
        if tab.count():
            tab.tap()
            page.wait_for_timeout(150)
        n = page.locator("[data-testid='defense-item']").count()
        want = sum(1 for d in DEFENSES if d["category"] == c)
        check(f"[liste] onglet {SHORT[c]} : ses {want} positions", tab.count() == 1 and n == want and n > 0, f"({n})")
    page.locator("[role='tab'][data-category='opposes']").tap()
    page.wait_for_timeout(150)
    shot(page, "defense_list_852")
    no_overflow(page, "liste 393x852")

    page.get_by_role("button", name="Position au hasard").tap()
    ck.appears("[hasard] partie ouverte", page, GAME)
    rid = page.url.rsplit("/", 1)[-1]
    check("[hasard] position dans la catégorie affichée", any(d["id"] == rid and d["category"] == "opposes" for d in DEFENSES), f"({rid})")
    page.goto(f"{BASE}/#/defense")
    ck.appears("[niveau] retour liste", page, "[data-testid='attacker']")
    radio = page.locator("[data-testid='attacker'] [role='radio'][data-level='1500']")
    radio.tap() if radio.count() else ck.fail("[niveau] pastille 1500")
    page.reload()
    ck.appears("[niveau] liste rechargée", page, "[data-testid='attacker']")
    check("[niveau] 1500 mémorisé après rechargement", page.locator("[role='radio'][data-level='1500'][aria-checked='true']").count() == 1)
    check("[niveau] clé propre à la défense", page.evaluate(f"() => localStorage.getItem('{PREFS}')") == '{"level":1500}')
    check("[niveau] préférence de l'attaque intacte", page.evaluate(f"() => localStorage.getItem('{ATTACK_PREFS}')") is None)

    if not DEFENSES:
        ctx.close()
        return

    # --- 4. Partie : défenseur, consigne, compteur, attaquant bridé ---
    first = next(d for d in DEFENSES if d["category"] == "opposes")
    color = first["defender"]
    if open_defense(page, first["id"]):
        check("[partie] titre = thème", page.locator("h1", has_text=first["theme"]).count() == 1)
        check("[partie] objectif « tenir 12 coups »", page.locator("[data-testid='objective']", has_text="Objectif : tenir 12 coups").count() == 1)
        check("[partie] consigne affichée", page.locator("[data-testid='objective-subline']", has_text=first["goal"]).count() == 1)
        check("[partie] compteur « Coup 0/12 »", counter(page) == "Coup 0/12", f"({counter(page)})")
        check("[partie] le joueur a le trait (défenseur)", (attr(page, "fen") or "").split(" ")[1] == color)
        check("[partie] échiquier orienté du côté du défenseur", white_at_bottom(page) == (color == "w"), f"({white_at_bottom(page)})")
        check("[partie] pas de bouton Nulle", page.get_by_role("button", name="Nulle").count() == 0)
        check("[partie] puce « ⚔️ 1500 »", "⚔️ 1500" in (page.locator("[data-testid='level-chip']").text_content() or ""))
        check("[partie] ligne moteur « Elo 1500 »", page.locator(GAME, has_text="Elo 1500").count() == 1)
        shot(page, "defense_game_852")
        no_overflow(page, "partie 393x852")
        bar_fits(page, "partie 393x852")
        page.get_by_role("button", name="Conseils").tap()
        check("[partie] « Conseils » déplie le plan", page.locator(GAME, has_text=first["plan"][:40]).count() == 1)
        shot(page, "defense_conseils_852")
        page.get_by_role("button", name="Conseils").tap()

        play_best(page, color, 10, "uci")
        wait_turn(page, color)
        check("[partie] compteur « Coup 1/12 » après un coup", counter(page) == "Coup 1/12", f"({counter(page)})")
        ws = workers(page.evaluate("() => window.__uci"))
        attacker = [i for i, m in ws.items() if "go movetime 700" in m]
        check("[uci] un moteur attaquant a joué", len(attacker) == 1, f"({list(ws)})")
        if attacker:
            opts = options_before_first_go(ws[attacker[0]])
            check("[uci] attaquant : UCI_LimitStrength true et UCI_Elo 1500 avant son premier go",
                  "setoption name UCI_LimitStrength value true" in opts and "setoption name UCI_Elo value 1500" in opts, f"({opts})")
        page.wait_for_timeout(600)
        ws = workers(page.evaluate("() => window.__uci"))
        oracle = [i for i, m in ws.items() if "go movetime 300" in m]
        check("[uci] suivi de la défense : un autre moteur, jamais bridé",
              len(oracle) == 1 and oracle != attacker and not any("UCI_LimitStrength value true" in m for m in ws[oracle[0]]), f"({oracle} / {attacker})")

        # Recommencer après un coup : tentative notée abandonnée.
        n = len(rows(page))
        page.get_by_role("button", name="Recommencer").tap()
        page.wait_for_timeout(400)
        r = rows(page)
        check("[recommencer] position de départ et compteur à 0", attr(page, "fen") == first["fen"] and counter(page) == "Coup 0/12")
        check("[recommencer] tentative notée abandonnée", len(r) == n + 1 and r[-1]["outcome"] == "abandon" and r[-1]["success"] == 0
              and r[-1]["attackerElo"] == 1500 and r[-1]["itemId"] == first["id"], f"({r[-1:]})")

        # Abandon : enregistré `resign`, champs attendus, déterministe.
        play_best(page, color, 10, "abandon")
        wait_turn(page, color)
        page.get_by_role("button", name="Abandonner").tap()
        if ck.appears("[abandon] confirmation", page, "[data-testid='resign-confirm']", timeout=5000):
            page.locator("[data-testid='resign-confirm']").tap()
        page.wait_for_timeout(500)
        r = rows(page)
        last = r[-1] if r else {}
        check("[abandon] partie terminée, « La défense a cédé »", attr(page, "status") == "over" and attr(page, "verdict") == "fail"
              and page.locator("[data-testid='objective']", has_text="La défense a cédé").count() == 1)
        check("[abandon] raison : coups tenus", page.locator("[data-testid='objective-subline']", has_text="Tu as abandonné après 1 coup.").count() == 1,
              f"({page.locator('[data-testid=objective-subline]').inner_text()!r})")
        check("[abandon] ligne learnSessions : domaine, id, fen, issue, Elo de l'attaquant",
              last.get("domain") == "defense" and last.get("itemId") == first["id"] and last.get("fen") == first["fen"]
              and last.get("success") == 0 and last.get("outcome") == "resign" and last.get("attackerElo") == 1500
              and last.get("assisted") is False and "defenderElo" not in last and last.get("ratingAfter") is None, f"({last})")
        check("[abandon] fin d'abandon : pas d'« Annuler »", page.get_by_role("button", name="Annuler").count() == 0)
        page.goto(f"{BASE}/#/defense?c=opposes")
        ck.appears("[stats] liste", page, "[data-testid='defense-item']")
        item = page.locator(f"[data-testid='defense-item'][data-id='{first['id']}']")
        check("[stats] la liste compte les essais (2 essais)", item.count() == 1 and "2 essais" in (item.text_content() or ""), f"({item.text_content() if item.count() else None})")
        tab = page.locator("[role='tab'][data-category='opposes']").text_content() or ""
        check("[stats] onglet : 0 tenue, 0 % (une tentative terminée)", re.search(r"0/\d+ · 0 %", tab) is not None, f"({tab})")

    # Série sous le plancher persistée : la partie rouverte reprend l'alerte et la série.
    if open_defense(page, first["id"]):
        play_best(page, color, 10, "série")
        wait_turn(page, color)
        page.wait_for_timeout(600)
        stored = page.evaluate(f"() => JSON.parse(localStorage.getItem('{STORED}'))")
        check("[série] série persistée avec la partie", stored and stored.get("key") == f"defense:{first['id']}" and isinstance(stored.get("holdFall"), dict),
              f"({stored and stored.get('holdFall')})")
        if stored:
            stored["holdFall"] = {"count": 1, "ply": len(stored["uci"])}
            page.evaluate(f"(g) => localStorage.setItem('{STORED}', JSON.stringify(g))", stored)
            page.reload()
            ck.appears("[série] partie reprise", page, GAME)
            page.wait_for_timeout(400)
            check("[série] série rejouée après rechargement", attr(page, "hold-fall") == "1", f"({attr(page, 'hold-fall')})")
            check("[série] alerte « un tour de plus et la défense cède »",
                  page.locator("[data-testid='objective-subline']", has_text="un tour de plus et la défense cède").count() == 1)
            check("[série] compteur repris « Coup 1/12 »", counter(page) == "Coup 1/12", f"({counter(page)})")
            shot(page, "defense_alerte_852")
            page.get_by_role("button", name="Recommencer").tap()
            page.wait_for_timeout(300)
            check("[série] Recommencer remet la série à zéro", attr(page, "hold-fall") == "0")

    # --- 5. Vraie défense jusqu'à la réussite, attaquant à 1320 ---
    page.evaluate(f"() => localStorage.setItem('{PREFS}', JSON.stringify({{ level: 1320 }}))")
    # Pas la position déjà jouée plus haut : sa partie vierge persistée garderait l'attaquant à 1500.
    target = max((d for d in DEFENSES if d["id"] != first["id"]), key=lambda d: (d["eval"], d["id"]))
    tcolor = target["defender"]
    if open_defense(page, target["id"]):
        check("[défense] attaquant Elo 1320", "1320" in (page.locator("[data-testid='level-chip']").text_content() or ""))
        moves = 0
        blocked = None
        while moves < 12 and attr(page, "status") != "over":
            if wait_turn(page, tcolor) != "turn":
                break
            if moves == 11:
                # 12e coup : la réponse UCI retenue, la confirmation reste en cours.
                page.evaluate("() => { window.__heldUci = [] }")
            if not play_best(page, tcolor, 12, "défense"):
                break
            moves += 1
            if moves == 12 and attr(page, "status") != "over":
                page.wait_for_timeout(600)
                blocked = {
                    "status": attr(page, "status"), "thinking": attr(page, "thinking"),
                    "label": page.locator(GAME, has_text="vérifie ta défense").count(),
                    "counter": counter(page), "resign": page.get_by_role("button", name="Abandonner").is_enabled(),
                    "undo": page.get_by_role("button", name="Annuler").is_enabled(),
                }
                page.evaluate("() => window.__releaseUci()")
        if moves == 12:
            ck.appears("[défense] fin après la confirmation", page, f"{GAME}[data-status='over']", timeout=20000)
        end = attr(page, "end")
        print(f"[info] défense {target['id']} : {moves} coups, end={end}, verdict={attr(page, 'verdict')}")
        check("[défense] réussie (tenue, nulle ou gain)", attr(page, "status") == "over" and attr(page, "verdict") == "success" and end in ("held", "stalemate", "repetition", "fifty", "insufficient", "mate"),
              f"(end={end}, verdict={attr(page, 'verdict')})")
        check("[défense] titre « Défense réussie »", page.locator("[data-testid='objective']", has_text="Défense réussie").count() == 1)
        if end == "held":
            check("[confirmation] au 12e coup : échiquier bloqué, « vérifie ta défense… », compteur 12/12, Annuler grisé",
                  blocked and blocked["status"] == "playing" and blocked["thinking"] == "1" and blocked["label"] == 1
                  and blocked["counter"] == "Coup 12/12" and blocked["undo"] is False, f"({blocked})")
            check("[défense] raison : 12 coups tenus et éval", page.locator("[data-testid='objective-subline']", has_text=re.compile(r"Tu as tenu 12 coups : (éval [+-]?\d+,\d|mat en \d+ pour toi)\.")).count() == 1,
                  f"({page.locator('[data-testid=objective-subline]').inner_text()!r})")
            check("[défense] aucun coup repris après « tenue » (pas d'Annuler)", page.get_by_role("button", name="Annuler").count() == 0)
        r = rows(page)
        last = r[-1] if r else {}
        check("[défense] réussite notée", last.get("itemId") == target["id"] and last.get("success") == 1 and last.get("outcome") in ("held", "draw", "win")
              and last.get("attackerElo") == 1320 and last.get("assisted") is False, f"({last})")
        shot(page, "defense_reussie_852")
        bar_fits(page, "fin 393x852")
        no_overflow(page, "fin 393x852")

        page.get_by_role("button", name="Analyser").tap()
        page.wait_for_timeout(800)
        check("[analyse] ouverte", page.evaluate("() => location.hash").startswith("#/analyse"), f"({page.url})")
        back = page.get_by_role("button", name=re.compile("Retour à la défense"))
        if back.count():
            back.first.tap()
            ck.appears("[analyse] retour à la défense", page, GAME)
            page.wait_for_timeout(300)
            check("[analyse] partie terminée restaurée", attr(page, "status") == "over" and attr(page, "verdict") == "success")
        else:
            ck.fail("[analyse] bouton « Retour à la défense »")
        url_before = page.url
        page.get_by_role("button", name="Suivante").tap()
        page.wait_for_timeout(400)
        check("[suivante] autre position", page.url != url_before and "#/defense/" in page.url, f"({page.url})")
        page.goto(f"{BASE}/#/defense?c={target['category']}")
        ck.appears("[liste] retour", page, "[data-testid='defense-item']")
        item = page.locator(f"[data-testid='defense-item'][data-id='{target['id']}']")
        check("[liste] position marquée « ✓ tenu à 1320 »", item.count() == 1 and "✓ tenu à 1320" in (item.text_content() or ""), f"({item.text_content() if item.count() else None})")
        tab = page.locator(f"[role='tab'][data-category='{target['category']}']").text_content() or ""
        check("[liste] onglet : 1 position tenue", re.search(r"(?<!\d)1/\d+", tab) is not None, f"({tab})")

    # --- 7. Mise en page ---
    page.set_viewport_size({"width": 393, "height": 660})
    page.goto(f"{BASE}/#/defense")
    page.wait_for_timeout(400)
    shot(page, "defense_list_660")
    no_overflow(page, "liste 393x660")
    if open_defense(page, DEFENSES[0]["id"]):
        shot(page, "defense_game_660")
        no_overflow(page, "partie 393x660")
        box = page.get_by_role("button", name="Abandonner").bounding_box()
        check("[mise en page] 393x660 : barre d'actions à l'écran", box is not None and box["y"] + box["height"] <= 660)
    ctx.close()

    dctx = desktop_context(browser, ck)
    dpage = dctx.new_page()
    dpage.goto(f"{BASE}/#/defense")
    ck.appears("[desktop] liste", dpage, "[data-testid='defense-item']")
    shot(dpage, "defense_list_1440")
    no_overflow(dpage, "liste 1440x900")
    check("[desktop] onglet Apprendre allumé (nav latérale)", dpage.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
    if open_defense(dpage, DEFENSES[0]["id"]):
        shot(dpage, "defense_game_1440")
        no_overflow(dpage, "partie 1440x900")
    dctx.close()


# ---------- 6. Mes défenses ratées ----------

T0 = 1758000000000
G = {"color": "b", "gameKey": "game:7", "gameLabel": "10 min · 1-0 mat", "attempts": 0, "solved": 0}
# Dh5, Cg5 et Fd3 visent la zone du roi noir g8, Dd8 et Tf8 la défendent : 3 contre 2. Les Noirs
# (le joueur) ont joué ...Cb4 ; le bilan proposait ...Dxg5, qui échange l'attaquant (...hxg5 perd sur Dh7#).
ATTACKED = "r1bq1rk1/pp3pp1/2n1p2p/3pP1NQ/3P4/2NB4/PP3PPP/R3K2R b KQ - 0 1"
MISTAKES = [
    {"id": 41, "date": T0, "cls": "blunder", **G, "fenBefore": ATTACKED, "playedSan": "Nb4", "bestUci": "d8g5"},
    # Témoins : même attaque mais classe « miss » ; même attaque sans camp connu ; une faute
    # d'ouverture sans attaque sur le roi.
    {"id": 42, "date": T0 + 1000, "cls": "miss", **G, "fenBefore": ATTACKED, "playedSan": "Nb4", "bestUci": "d8g5"},
    {"id": 43, "date": T0 + 2000, "cls": "blunder", "gameLabel": "Partie analysée", "attempts": 0, "solved": 0,
     "fenBefore": ATTACKED, "playedSan": "Nb4", "bestUci": "d8g5"},
    {"id": 44, "date": T0 + 3000, "cls": "blunder", "color": "w", "gameKey": "game:8", "gameLabel": "5 min · 0-1", "attempts": 0, "solved": 0,
     "fenBefore": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "playedSan": "Qh5", "bestUci": "g1f3"},
]


def ring_oracle(fen):
    """Mêmes définitions que kingAttack.ts (anneau du roi de Stockfish) : comptes autour du roi au trait."""
    b = chess.Board(fen)
    color = b.turn
    k = b.king(color)
    f, r = min(6, max(1, chess.square_file(k))), min(6, max(1, chess.square_rank(k)))
    zone = [chess.square(ff, rr) for ff in (f - 1, f, f + 1) for rr in (r - 1, r, r + 1)]
    att, de = set(), set()
    for sq in zone:
        att |= {s for s in b.attackers(not color, sq) if b.piece_type_at(s) not in (chess.KING, chess.PAWN)}
        de |= {s for s in b.attackers(color, sq) if b.piece_type_at(s) not in (chess.KING, chess.PAWN)}
    return len(att), len(de)


def seed(page, store, data):
    return page.evaluate(IDB, [store, f"const tx = db.transaction('{store}', 'readwrite'); for (const r of arg) tx.objectStore('{store}').put(r);"
                                      "tx.oncomplete = () => resolve(true); tx.onerror = () => reject(tx.error)", data])


def part_missed(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    # État vide d'abord.
    page.goto(f"{BASE}/#/defenses-ratees")
    if ck.appears("[ratées] état vide explicatif", page, "[data-testid='defense-empty']"):
        check("[ratées] synthèse sans faute", "Aucune faute à ton nom" in page.locator("[data-testid='defense-summary']").inner_text())
        check("[ratées] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
        shot(page, "defense_ratees_vide_852")
    seeded = seed(page, "mistakes", MISTAKES)
    check("[ratées] fautes semées", seeded is True)
    page.goto(f"{BASE}/#/apprendre")
    card = page.locator("[data-testid=missed-defenses-card]")
    if ck.appears("[ratées] carte d'Apprendre", page, "[data-testid=missed-defenses-card]"):
        page.wait_for_timeout(600)
        check("[ratées] la carte compte 1 défense (témoins exclus)", card.get_attribute("data-count") == "1", f"({card.get_attribute('data-count')})")
        card.tap()
    ck.appears("[ratées] liste", page, "[data-testid='missed-defense-item']")
    items = page.locator("[data-testid='missed-defense-item']")
    ids = [i.get_attribute("data-id") for i in items.all()]
    check("[ratées] seule la vraie défense ratée est listée (pas la « miss », ni le camp inconnu, ni l'ouverture)", ids == ["41"], f"({ids})")
    check("[ratées] synthèse exacte", page.locator("[data-testid='defense-summary']").inner_text().strip()
          == "Dans tes fautes relevées sur 2 parties, 1 défense ratée.", f"({page.locator('[data-testid=defense-summary]').inner_text()!r})")
    if ids:
        text = items.first.inner_text()
        a, d = ring_oracle(ATTACKED)
        check("[ratées] comptes affichés = oracle python-chess (3 contre 2)", (a, d) == (3, 2) and f"⚔ {a}" in text and f"🛡 {d}" in text, f"({text!r}, {a}, {d})")
        check("[ratées] l'item dit le coup joué", "♞b4" in text and "Roque attaqué" in text, f"({text!r})")
    no_overflow(page, "défenses ratées 393x852")
    shot(page, "defense_ratees_852")
    page.goto(f"{BASE}/#/defenses-ratees/42")
    ck.appears("[ratées] témoin hors liste : message propre", page, "[data-testid='defense-missing']")

    page.goto(f"{BASE}/#/defenses-ratees/41")
    if ck.appears("[ratées] exercice monté", page, GAME):
        page.wait_for_timeout(500)
        check("[ratées] objectif « trouve la défense »", page.locator("[data-testid='objective']").inner_text().startswith("Objectif : trouve la défense"))
        check("[ratées] calque des comptes forcé", page.locator("[data-testid=king-zone]").count() == 2)
        check("[ratées] Noirs en bas (camp du joueur)", white_at_bottom(page) is False)
        legend = page.locator("[data-testid=attack-legend]").inner_text()
        check("[ratées] repère de la légende vu du défenseur", "Repère : neutralise la pièce la plus dangereuse ou rapproche un défenseur." in legend
              and "Attaque quand" not in legend and "attaque quand" not in legend, f"({legend!r})")
        shot(page, "defense_ratee_exercice_852")
        tap_move(page, "d8", "g5")
        if not ck.appears("[ratées] le coup du bilan est reconnu", page, "[data-testid=objective-subline]:has-text(\"C'est le coup du bilan : tiens bon !\")", timeout=8000):
            print(f"[diagnostic] sous-ligne : {page.locator('[data-testid=objective-subline]').inner_text()!r}, fen={attr(page, 'fen')}", flush=True)
        page.wait_for_timeout(400)
        r = rows(page, "missed-defense")
        check("[ratées] ligne learnSessions missed-defense réussie", len(r) == 1 and r[0].get("itemId") == "41" and r[0].get("success") == 1
              and r[0].get("fen") == ATTACKED, f"({r})")
        check("[ratées] aucune ligne missed-attack écrite", rows(page, "missed-attack") == [])
        page.get_by_role("button", name="Retour").tap()
        item41 = "[data-testid='missed-defense-item'][data-id='41']"
        # Partie entamée : « En cours » prime, comme dans « Mes attaques manquées ».
        ck.appears("[ratées] partie entamée : item « En cours »", page, f"{item41}:has-text('En cours')", timeout=10000)
        page.locator(item41).tap()
        ck.appears("[ratées] exercice repris", page, GAME)
        page.get_by_role("button", name="Abandonner").tap()
        page.locator("[data-testid='resign-confirm']").tap()
        page.get_by_role("button", name="Retour").tap()
        ck.appears("[ratées] partie terminée : item marqué « Retrouvée »", page, f"{item41}:has-text('Retrouvée')", timeout=10000)
    ctx.close()


def suite(p):
    check_data()
    check_logic()
    browser = p.chromium.launch(headless=True)
    part_list_and_game(p, browser)
    part_missed(p, browser)
    browser.close()


ck.run(suite)
