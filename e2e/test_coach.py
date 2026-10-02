"""E2E « coach » : bulle du coach (avatar, hauteur réservée, pastilles, figurines) et textes
du coach (bilan, résumé, entraîneur), lot QA l16.

Deux parties :
1. Textes, sans navigateur : `coach.ts` et `liveCoach.ts` sont bundlés avec rolldown puis
   exercés par `e2e/coach_texts.mjs` sur des bilans construits à la main (partie de référence,
   mat de Legal, dame pendue, mat raté, pat, partie longue, coach live). Déterministe.
2. Affichage, iPhone 14 Pro standalone (393x852) puis 393x660 : leçon d'Apprendre, résumé et
   bilan guidé d'une partie contre un bot (semée dans IndexedDB), Réessayer, entraîneur.

Usage : npm run test:e2e -- --suite coach   (COACH_TEXTS_ONLY=1 pour la partie 1 seule)
"""
import json
import os
import re
import subprocess
import tempfile

import coach_oracle as oracle
from helpers import BASE, SHOTS, Checker, click_square as sq, mobile_context

ck = Checker("coach")
check = ck.check

E2E = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"

SAN_EN = re.compile(r"\b[KQRBN]x?[a-h][1-8]")
FIG = "♔♕♖♗♘♚♛♜♝♞"
# Un coup en figurines ou en cases, pour normaliser les phrases avant de compter les variantes.
MOVE_TOKEN = re.compile(rf"(?:[{FIG}]?[a-h]?x?[a-h][1-8](?:=[{FIG}])?[+#]?|O-O(?:-O)?|\b[a-h][1-8]\b)")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")


# ---------------------------------------------------------------------------------------------
# Partie 1 : textes
# ---------------------------------------------------------------------------------------------
def all_texts(data):
    for s in data["scenarios"]:
        for c in s["comments"]:
            yield f"{s['label']}[{c['i']}] titre", c["headline"] or ""
            yield f"{s['label']}[{c['i']}] corps", c["body"] or ""
        yield f"{s['label']} résumé", s["summary"]
        yield f"{s['label']} punchline", s["quip"]
    for r in data["live"]:
        yield f"live {r['label']}[{r['i']}] texte", r["text"] or ""
        yield f"live {r['label']}[{r['i']}] titre", r["headline"] or ""
    for i, g in enumerate(data["greetings"]):
        yield f"salutation {i}", g


def comment_at(scn, i):
    return next((c for c in scn["comments"] if c["i"] == i), None)


def normalised(body):
    return MOVE_TOKEN.sub("{coup}", body)


def texts_part():
    bundle_dir = tempfile.mkdtemp(prefix="chesslocal-coach-")
    bundle = os.path.join(bundle_dir, "bundle.mjs")
    r = subprocess.run([ROLLDOWN, os.path.join(E2E, "coach_texts_entry.ts"), "--format", "esm", "--file", bundle],
                       cwd=ROOT, capture_output=True, text=True)
    if not check("[textes] bundle rolldown", r.returncode == 0, (r.stderr or r.stdout)[-300:]):
        return
    r = subprocess.run(["node", os.path.join(E2E, "coach_texts.mjs"), bundle, os.path.join(ROOT, "public", "puzzles.json")],
                       cwd=ROOT, capture_output=True, text=True)
    if not check("[textes] harnais Node", r.returncode == 0, r.stderr[-400:]):
        return
    data = json.loads(r.stdout)
    texts = list(all_texts(data))

    def offenders(pred):
        return [label for label, t in texts if pred(t)]

    bad = offenders(lambda t: SAN_EN.search(t) is not None)
    check("[textes] aucun SAN anglais (figurines partout)", not bad, f"({len(bad)} : {bad[:3]})")
    bad = offenders(lambda t: re.search(r"\b1e\b", t) is not None)
    check("[textes] jamais « 1e »", not bad, f"({bad[:3]})")
    bad = offenders(lambda t: "—" in t)
    check("[textes] aucun tiret cadratin", not bad, f"({len(bad)} : {bad[:3]})")
    bad = offenders(lambda t: re.search(r"undefined|NaN|\bnull\b|\[object", t) is not None)
    check("[textes] ni undefined ni NaN", not bad, f"({bad[:3]})")
    bad = offenders(lambda t: re.search(r"\{[A-Za-z_0-9]+\}", t) is not None)
    check("[textes] aucun marqueur {…} non rempli", not bad, f"({bad[:3]})")
    bad = offenders(lambda t: t.strip() == "")
    check("[textes] aucun texte vide", not bad, f"({len(bad)} : {bad[:3]})")
    longest = max(((len(p), label, p) for label, t in texts for p in SENTENCE_SPLIT.split(t)), default=(0, "", ""))
    check("[textes] chaque phrase fait 140 caractères au plus", longest[0] <= 140, f"(max {longest[0]} : {longest[1]} « {longest[2][:60]}… »)")
    bad = offenders(lambda t: re.search(r"[^  \s][ ]+[!?;:]", t) is not None or re.search(r"\d [%]", t) is not None)
    check("[textes] espace insécable avant ! ? ; : et %", not bad, f"({len(bad)} : {bad[:3]})")
    bad = offenders(lambda t: re.search(r"\bvous\b", t, re.I) is not None)
    check("[textes] tutoiement (jamais « vous »)", not bad, f"({bad[:3]})")

    ref_w = next(s for s in data["scenarios"] if s["label"] == "ref_w")
    ref_b = next(s for s in data["scenarios"] if s["label"] == "ref_b")
    be2 = comment_at(ref_w, 12)
    check("[ref_w] 7.♗e2 : le mat autorisé passe en premier", be2 is not None and "mat" in be2["body"].lower(), f"({be2 and be2['body'][:90]})")
    check("[ref_w] 7.♗e2 n'est pas « déjà perdu » (7.♕e2 tenait)", be2 is not None and re.search(r"déjà|était fait", be2["body"]) is None, f"({be2 and be2['body'][:90]})")
    check("[ref_w] 7.♗e2 nomme la réponse ♞f3#", be2 is not None and "♞f3#" in be2["body"], f"({be2 and be2['body'][:90]})")
    nxf7 = comment_at(ref_w, 8)
    check("[ref_w] 5.♘xf7 est une gaffe commentée sans pléonasme « avec échec »",
          nxf7 is not None and nxf7["body"] and "avec échec" not in nxf7["body"], f"({nxf7 and nxf7['body'][:90]})")
    opp = [comment_at(ref_w, i) for i in (1, 3, 5, 7, 9, 11, 13)]
    check("[ref_w] coups adverses : bulle jamais vide, sévérité neutre",
          all(c is not None and c["body"].strip() and c["severity"] == "neutral" for c in opp),
          f"({[(c and c['severity'], c and c['body'][:30]) for c in opp[:3]]})")
    opp_blunder = comment_at(ref_b, 8)
    check("[ref_b] gaffe adverse (5.♘xf7) signalée comme une occasion pour le joueur",
          opp_blunder is not None and re.search(r"trompe|erreur|faute|occasion|offr", opp_blunder["body"], re.I) is not None,
          f"({opp_blunder and opp_blunder['body'][:90]})")
    praised = [c for s in data["scenarios"] for c in s["comments"] if c["own"] and c["cls"] in ("best", "excellent")]
    check("[moments clés] best et excellent ne sont plus des moments clés (sévérité neutre)",
          praised and all(c["severity"] == "neutral" for c in praised), f"({len(praised)} coups, sévérités {sorted({c['severity'] for c in praised})})")
    check("[moments clés] best garde un coach content (mood happy)",
          praised and all(c["mood"] == "happy" for c in praised if c["cls"] == "best"), f"({sorted({str(c['mood']) for c in praised})})")
    strong = [c for s in data["scenarios"] for c in s["comments"] if c["own"] and c["cls"] in ("brilliant", "great")]
    check("[moments clés] brillant et très bon restent des moments clés (praise)",
          strong and all(c["severity"] == "praise" for c in strong), f"({[(c['cls'], c['severity']) for c in strong]})")
    check("[ref_w] titre « le meilleur coup » (pas « le meilleur » tronqué)",
          all(not c["headline"].endswith("le meilleur") for s in data["scenarios"] for c in s["comments"]))
    check("[ref_w] résumé : coup pivot en figurines avec son numéro (5.♘xf7)", "5.♘xf7" in ref_w["summary"], f"({ref_w['summary'][-80:]})")
    custom = next(s for s in data["scenarios"] if s["label"] == "custom_black")
    check("[custom_black] numéro de coup réel depuis le compteur du FEN (6.♘c3)", "6.♘c3" in custom["summary"], f"({custom['summary'][-80:]})")
    summaries = [s["summary"] for s in data["scenarios"]]
    dotted = [t[:40] for t in summaries if re.search(r"\d\.\d", t) or "~" in t]
    check("[résumé] virgule décimale et pas de « ~ »", not dotted, f"({dotted[:2]})")

    legal_b = next(s for s in data["scenarios"] if s["label"] == "legal_b")
    bxd1 = comment_at(legal_b, 9)
    check("[legal_b] 5...♝xd1 : le fou n'est pas « abandonné » (il vient de prendre la dame), le mat est nommé",
          bxd1 is not None and "mat" in bxd1["body"].lower() and re.search(r"abandonne le fou|fou .{0,30}(en prise|capturé)", bxd1["body"]) is None,
          f"({bxd1 and bxd1['body'][:100]})")
    qhang_w = next(s for s in data["scenarios"] if s["label"] == "qhang_w")
    qg4 = comment_at(qhang_w, 2)
    fem = qg4 is not None and "dame" in qg4["body"] and re.search(r"défendue|capturée|prise|attaquée|laissée|perdue", qg4["body"]) is not None \
        and re.search(r"\b(défendu|capturé|pris|attaqué|laissé|perdu)\b", qg4["body"]) is None
    check("[qhang_w] 2.♕g4 : la dame en prise, accordée au féminin", fem, f"({qg4 and qg4['body'][:100]})")
    qhang_b = comment_at(next(s for s in data["scenarios"] if s["label"] == "qhang_b"), 3)
    check("[qhang_b] 2...♝xg4 : le gain de la dame est nommé", qhang_b is not None and "dame" in qhang_b["body"], f"({qhang_b and qhang_b['body'][:100]})")
    mate2 = comment_at(next(s for s in data["scenarios"] if s["label"] == "mate2"), 0)
    check("[mate2] mat en 1 raté nommé même sur un coup « excellent »",
          mate2 is not None and "mat en 1" in mate2["body"].lower() and "♕f8#" in mate2["body"], f"({mate2 and mate2['body'][:100]})")
    qtrade = comment_at(next(s for s in data["scenarios"] if s["label"] == "qtrade"), 0)
    check("[qtrade] ♕xd8+ est un échange, jamais « gagnait la dame »", qtrade is not None and "gagnait" not in qtrade["body"], f"({qtrade and qtrade['body'][:100]})")
    pat = comment_at(next(s for s in data["scenarios"] if s["label"] == "stalemate"), 0)
    check("[stalemate] le pat est appelé pat", pat is not None and "pat" in pat["body"].lower(), f"({pat and pat['body'][:100]})")

    long_ = next(s for s in data["scenarios"] if s["label"] == "long")
    bodies = [normalised(c["body"]) for c in long_["comments"][:100]]
    check("[long] au moins 8 formulations distinctes sur 100 bulles", len(set(bodies)) >= 8, f"({len(set(bodies))} distinctes)")
    repeats = sum(1 for a, b in zip(bodies, bodies[1:]) if a == b)
    check("[long] jamais deux bulles consécutives identiques", repeats == 0, f"({repeats} répétitions)")

    live = data["live"]
    en = [r for r in live if r["text"] and re.search(r"\b(Defense|Game|Opening|Attack|Variation|System)\b", r["text"])]
    check("[live] noms d'ouvertures en français", not en, f"({[r['text'][:40] for r in en][:2]})")
    nf3 = next(r for r in live if r["label"] == "nf3" and r["i"] == 0)
    check("[live] 1.♘f3 ne « prend pas le centre »", bool(nf3["text"]) and re.search(r"occupes le centre|centre d'abord|espace au centre|part du centre", nf3["text"]) is None, f"({nf3['text']})")
    botfirst = next(r for r in live if r["label"] == "botfirst" and r["i"] == 0)
    check("[live] le 1.e4 du bot ne dit pas « tu occupes le centre »", bool(botfirst["text"]) and re.search(r"\btu\b|\bton\b|\bta\b", botfirst["text"]) is None, f"({botfirst['text']})")
    named = [r for r in live if r["label"] == "italian" and r["text"] and "italienne" in r["text"].lower()]
    check("[live] l'ouverture est nommée une fois, quand son nom change", len(named) == 1, f"({len(named)} fois)")
    check("[live] titre présent sur chaque bulle (pastille de classe visible)", all(r["headline"] for r in live), f"({sum(1 for r in live if not r['headline'])} sans titre)")
    bare = [r for r in live if not r["byPlayer"] and (not r["text"] or len(r["text"]) < len(r["san"]) + 12)]
    check("[live] les coups du bot ne sont jamais réduits au seul coup", not bare, f"({[r['text'] for r in bare][:3]})")
    mate = next(r for r in live if r["label"] == "mate" and r["i"] == 6)
    check("[live] le mat du joueur est salué", mate["text"] and "mat" in mate["text"].lower(), f"({mate['text']})")
    chk = next(r for r in live if r["label"] == "botcheck" and r["i"] == 5)
    check("[live] l'échec du bot est signalé", chk["text"] and "échec" in chk["text"].lower(), f"({chk['text']})")
    bl = next(r for r in live if r["label"] == "blunder" and r["i"] == 2)
    check("[live] la gaffe du joueur nomme le coup en figurine", "♕h5" in (bl["text"] or "") + (bl["headline"] or ""), f"({bl['text']})")
    check("[live] salutations variées", len(set(data["greetings"])) >= 3, f"({len(set(data['greetings']))} distinctes sur 12)")
    q = data.get("quick") or {}
    want = {"noBest": "excellent", "best": "best", "drop3": "excellent", "drop5": "good", "drop8": "inaccuracy", "drop15": "mistake", "drop25": "blunder"}
    check("[live] quickClass : meilleur seulement pour le coup du moteur, seuils de review.ts", q == want, f"({q})")
    motifs_part(data)


# Seuils minimaux de phrases par motif sur les positions réelles : prouvent que chaque
# détecteur est branché (bilan et live), pas seulement écrit.
MIN_CLAIMS = {"fourchette": 40, "clouage": 5, "enfilade": 3, "couloir": 5, "pion_passe": 3, "mat_en_1": 20, "prise_gratuite": 10, "non_defendue": 3}
MIN_LIVE = {"fourchette": 10, "mat_en_1": 3}


def motifs_part(data):
    """Détecteurs contre l'oracle python-chess, puis chaque motif annoncé revérifié sur l'échiquier."""
    rows = data.get("detectors") or []
    check("[motifs] détecteurs exercés sur des positions de puzzles", len(rows) > 2000, f"({len(rows)} coups)")
    mism = {"fork": [], "line": [], "br": [], "pp": []}
    pos = dict.fromkeys(mism, 0)
    for r in rows:
        f = oracle.fork(r["fen"], r["uci"])
        if sorted(f or []) != sorted(r["fork"] or []):
            mism["fork"].append((r["id"], r["j"], r["fork"], f))
        lm = oracle.line_motif(r["fen"], r["uci"])
        if (list(lm) if lm else None) != r["line"]:
            mism["line"].append((r["id"], r["j"], r["line"], lm))
        if oracle.back_rank_mate(r["fen"], r["uci"]) != r["br"]:
            mism["br"].append((r["id"], r["j"], r["br"]))
        if oracle.passed_pawn_created(r["fen"], r["uci"]) != r["pp"]:
            mism["pp"].append((r["id"], r["j"], r["pp"]))
        pos["fork"] += bool(r["fork"]); pos["line"] += bool(r["line"]); pos["br"] += r["br"]; pos["pp"] += r["pp"]
    abs_bad = [(r["id"], r["j"]) for r in rows if r["line"] and r["line"][0] == "clouage" and r["line"][2] == "k" and not oracle.absolute_pin(r["fen"], r["uci"])]
    abs_n = sum(1 for r in rows if r["line"] and r["line"][0] == "clouage" and r["line"][2] == "k")
    check(f"[motifs] chaque clouage sur le roi est un clouage absolu pour python-chess (Board.pin, {abs_n} cas)", abs_n > 0 and not abs_bad, f"({abs_bad[:3]})")
    check("[motifs] aucune exception dans le harnais (marqueur manquant, détecteur)", not data.get("errors"), f"({len(data.get('errors') or [])} : {(data.get('errors') or [])[:2]})")
    for k, label in (("fork", "fourchette"), ("line", "clouage / enfilade"), ("br", "mat du couloir"), ("pp", "pion passé créé")):
        check(f"[motifs] {label} : détecteur identique à l'oracle python-chess sur chaque coup ({pos[k]} positifs)",
              rows and not mism[k] and pos[k] > 0, f"({len(mism[k])} écarts : {mism[k][:2]})")
    # Rappel sur les thèmes lichess (un thème porte sur tout le puzzle : rappel seulement).
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(r)
    fork_tag = [rs for rs in by.values() if "fork" in rs[0]["themes"].split()]
    fork_hit = [rs for rs in fork_tag if any(r["fork"] for r in rs if r["j"] % 2 == 1 and r["j"] < len(rs) - 1)]
    check("[motifs] rappel fourchette sur les puzzles étiquetés « fork » ≥ 90 %", fork_tag and len(fork_hit) >= 0.9 * len(fork_tag), f"({len(fork_hit)}/{len(fork_tag)})")
    br_tag = [rs for rs in by.values() if "backRankMate" in rs[0]["themes"].split()]
    br_hit = [rs for rs in br_tag if rs[-1]["br"]]
    check("[motifs] rappel mat du couloir sur les puzzles « backRankMate » ≥ 90 %", br_tag and len(br_hit) >= 0.9 * len(br_tag), f"({len(br_hit)}/{len(br_tag)})")
    hand = data.get("hand") or []
    for h in hand:
        got = {k: h["got"][k] for k in h["want"]}
        if "fork" in got and got["fork"]:
            got["fork"] = sorted(got["fork"]); h["want"]["fork"] = sorted(h["want"]["fork"])
        check(f"[motifs] cas à la main : {h['label']}", got == h["want"], f"(obtenu {got}, attendu {h['want']})")

    # Chaque motif annoncé par le coach doit exister sur l'échiquier.
    def audit_all(name, items, mins):
        counts, errors = {}, []
        for it in items:
            claims, errs = oracle.audit(it)
            for c in claims:
                counts[c] = counts.get(c, 0) + 1
            errors += [f"{it['label']}#{it.get('i', '')} {e} « {it['body'][:70]} »" for e in errs]
        check(f"[{name}] chaque motif annoncé existe sur l'échiquier ({sum(counts.values())} annonces)", not errors, f"({len(errors)} : {errors[:3]})")
        for motif, n in mins.items():
            check(f"[{name}] motif « {motif} » branché (≥ {n} annonces)", counts.get(motif, 0) >= n, f"({counts.get(motif, 0)})")
        return counts

    scen = [{**c, "label": s["label"], "mover": c.get("mover") or "w"} for s in data["scenarios"] for c in s["comments"] if c.get("fenBefore")]
    audit_all("bilan, scénarios", scen, {})
    audit_all("bilan, puzzles", data.get("puzzleComments") or [], MIN_CLAIMS)
    audit_all("live, puzzles", data.get("puzzleLive") or [], MIN_LIVE)
    narrative = re.compile(r"Phase par phase|Le fil de la partie|Ton ouverture a été|En résumé : une ouverture")
    custom = next(s for s in data["scenarios"] if s["label"] == "custom_black")
    check("[phases] départ custom : pas de phase d'ouverture", bool(custom.get("phases")) and custom["phases"]["opening"] == {"w": "none", "b": "none"}, f"({custom.get('phases')})")
    ref_w = next(s for s in data["scenarios"] if s["label"] == "ref_w")
    check("[phases] partie de 14 demi-coups : pas de récit par phases", narrative.search(ref_w["summary"]) is None, f"({ref_w['summary'][:120]})")
    long_ = next(s for s in data["scenarios"] if s["label"] == "long")
    check("[phases] partie de 120 demi-coups : récit par phases", narrative.search(long_["summary"]) is not None, f"({long_['summary'][:120]})")
    # Garde-fou de régression (secondes de gel), large : la machine de test peut être chargée.
    check("[motifs] coach rapide : 120 demi-coups commentés en moins de 800 ms (Node)", long_.get("ms", 1e9) < 800, f"({long_.get('ms', 0):.0f} ms)")
    guided = [c["body"] for s in data["scenarios"] for c in s["comments"]] + [c["body"] for c in data.get("puzzleComments") or []] \
        + [r["text"] or "" for r in (data.get("puzzleLive") or []) + data["live"]]
    too_long = sorted({b for b in guided if len(b) > 135}, key=len, reverse=True)
    check("[motifs] bulles (bilan et live) : corps de 135 caractères au plus", not too_long, f"({len(too_long)} : {too_long[:2]})")


# ---------------------------------------------------------------------------------------------
# Partie 2 : affichage
# ---------------------------------------------------------------------------------------------
METRICS_JS = """(scope) => {
  const root = scope ? document.querySelector(scope) : document
  if (!root) return null
  const bubble = [...root.querySelectorAll('.bg-white')].find(e => e.offsetParent)
  if (!bubble) return null
  const circle = bubble.parentElement.firstElementChild
  // Après correctif : le dessin du visage ([data-face]) ; avant : le span emoji.
  const face = circle.querySelector('[data-face]') || circle.querySelector('span')
  const body = bubble.querySelector('[data-coach-body]') || bubble.lastElementChild
  const c = circle.getBoundingClientRect(), b = bubble.getBoundingClientRect()
  const f = face ? face.getBoundingClientRect() : null
  const board = document.querySelector('[id^=chessboard-]')
  const fig = bubble.querySelector('[data-figurine]')
  const figRatio = fig ? parseFloat(getComputedStyle(fig).fontSize) / parseFloat(getComputedStyle(fig.parentElement).fontSize) : null
  return {
    circle: { x: c.x, y: c.y, w: c.width, h: c.height, cx: c.x + c.width / 2, cy: c.y + c.height / 2 },
    face: f ? { x: f.x, y: f.y, w: f.width, h: f.height, cx: f.x + f.width / 2, cy: f.y + f.height / 2 } : null,
    bubbleH: b.height, bubbleW: b.width,
    bodyText: body ? body.innerText.trim() : '',
    hasIcon: !!bubble.querySelector('[data-class-icon]'),
    boardY: board ? board.getBoundingClientRect().y : null,
    figRatio,
    // Visibilité réelle : ce qui est sous le centre de l'avatar est bien l'avatar (pas un rect hors écran).
    avatarVisible: (() => { const el = document.elementFromPoint(c.x + c.width / 2, c.y + c.height / 2); return !!el && circle.contains(el) })(),
    // Le corps tient sans défiler (dernière ligne visible, iOS n'affiche pas de barre).
    bodyFits: body ? body.scrollHeight <= body.clientHeight + 1 : true,
  }
}"""

CONTRAST_JS = """(scope) => {
  const lum = (rgb) => {
    const m = rgb.match(/[\\d.]+/g).slice(0, 3).map(Number).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 })
    return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]
  }
  return [...document.querySelectorAll(scope + ' [data-class-icon]')].filter(e => e.offsetParent).map(e => {
    const cs = getComputedStyle(e)
    const l1 = lum(cs.color), l2 = lum(cs.backgroundColor)
    const r = e.getBoundingClientRect()
    return { cls: e.dataset.classIcon, ratio: (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05), size: Math.min(r.width, r.height), font: parseFloat(cs.fontSize) }
  })
}"""


def metrics(page, scope):
    return page.evaluate(METRICS_JS, scope)


def visible(name, m):
    return check(name, bool(m and m["avatarVisible"]), "(avatar sous le pli ou recouvert)")


def centred(name, m, tol=2.0):
    """Le visage est centré dans son cercle (tolérance 2 px) et tient entièrement dedans."""
    if not m or not m["face"]:
        return check(name, False, "(bulle ou visage introuvable)")
    f, c = m["face"], m["circle"]
    dx, dy = f["cx"] - c["cx"], f["cy"] - c["cy"]
    inside = f["x"] >= c["x"] - 0.5 and f["y"] >= c["y"] - 0.5 and f["x"] + f["w"] <= c["x"] + c["w"] + 0.5 and f["y"] + f["h"] <= c["y"] + c["h"] + 0.5
    return check(name, abs(dx) <= tol and abs(dy) <= tol and inside, f"(dx={dx:+.1f} dy={dy:+.1f} px, dans le cercle : {inside})")


def seed_bot_game(page, pgn=PGN, color="w", result="0-1"):
    """Partie contre un bot dans la table Dexie `games` : `reviewColor` posé, coups adverses commentés."""
    page.goto(f"{BASE}/#/archive")
    page.wait_for_timeout(800)
    return page.evaluate("""([pgn, color, result]) => new Promise((resolve, reject) => {
      const req = indexedDB.open('chess-local')
      req.onerror = () => reject(req.error)
      req.onsuccess = () => {
        const db = req.result
        const tx = db.transaction('games', 'readwrite')
        const add = tx.objectStore('games').add({
          date: Date.now(), mode: 'bot', botId: 'noa', playerColor: color, timeControl: 'illimité',
          timeClass: 'unlimited', pgn, result, termination: 'mat',
        })
        add.onsuccess = () => resolve(add.result)
        add.onerror = () => reject(add.error)
      }
    })""", [pgn, color, result])


def run_review(page, game_id, tag):
    page.goto(f"{BASE}/#/analyse?game={game_id}&review=1")
    return ck.appears(f"[{tag}] bilan calculé (résumé affiché)", page, "text=Démarrer le bilan", timeout=240000)


def display_852(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()

    # --- Leçon d'Apprendre ---
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1500)
    page.locator("main button", has_text="Finales").click()
    page.wait_for_timeout(1500)
    m = metrics(page, ".fixed")
    centred("[leçon 852] avatar centré dans son cercle", m)
    check("[leçon 852] lien « Voir le cours complet » dans la bulle", page.locator(".fixed .bg-white", has_text="Voir le cours complet").count() == 1)
    check("[leçon 852] pas de « ❓ »", "❓" not in page.locator(".fixed").inner_text())
    page.screenshot(path=f"{SHOTS}/coach_lesson_852.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(300)

    # --- Entraîneur ---
    page.goto(f"{BASE}/#/jouer")
    page.wait_for_timeout(1200)
    page.click("button:has-text('Entraîneur')")
    page.wait_for_timeout(300)
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text="Blancs").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(1000)
    m0 = metrics(page, "main")
    centred("[entraîneur 852] avatar centré (salutation)", m0)
    check("[entraîneur 852] salutation non vide", bool(m0 and m0["bodyText"]), f"({m0 and m0['bodyText'][:50]})")
    sq(page, "e2"); page.wait_for_timeout(200); sq(page, "e4")
    page.wait_for_timeout(6000)  # éval + réponse du bot + éval
    m1 = metrics(page, "main")
    check("[entraîneur 852] pastille de classe dans la bulle après un coup", bool(m1 and m1["hasIcon"]))
    check("[entraîneur 852] échiquier immobile quand la bulle change", m0 and m1 and m0["boardY"] == m1["boardY"], f"({m0 and m0['boardY']} -> {m1 and m1['boardY']})")
    check("[entraîneur 852] commentaire en français, jamais nu", bool(m1 and len(m1["bodyText"]) > 12 and not re.search(r"\b(Defense|Game|Opening)\b", m1["bodyText"])), f"({m1 and m1['bodyText'][:60]})")
    page.screenshot(path=f"{SHOTS}/coach_trainer_852.png")
    page.click("button:has-text('Abandonner')")
    page.wait_for_timeout(800)

    # --- Résumé du bilan d'une partie contre un bot ---
    game_id = seed_bot_game(page)
    if not run_review(page, game_id, "bilan 852"):
        ctx.close()
        return
    page.wait_for_timeout(400)
    centred("[résumé 852] avatar centré", metrics(page, ".fixed"))
    body = page.locator(".fixed").inner_text()
    check("[résumé 852] précision avec virgule décimale", re.search(r"\d,\d", body) is not None and re.search(r"\b\d+\.\d\b", body) is None)
    check("[résumé 852] libellé « Occasion manquée » et « Milieu de partie »", "Occasion manquée" in body and "Milieu de partie" in body)
    icons = page.evaluate(CONTRAST_JS, ".fixed")
    low = [i for i in icons if i["ratio"] < 3]
    check("[résumé 852] 11 pastilles de classe accessibles (role img)", len(icons) >= 11, f"({len(icons)})")
    check("[résumé 852] glyphe lisible sur chaque pastille (contraste ≥ 3:1)", icons and not low, f"({[(i['cls'], round(i['ratio'], 2)) for i in low][:4]})")
    check("[résumé 852] police du glyphe ≥ 11 px", icons and min(i["font"] for i in icons) >= 11, f"({icons and min(i['font'] for i in icons)})")
    page.screenshot(path=f"{SHOTS}/coach_summary_852.png")

    # --- Bilan guidé : chaque demi-coup, coups adverses compris ---
    page.click("text=Démarrer le bilan")
    page.wait_for_timeout(600)
    page.locator(".fixed button[data-current]").first.click()
    page.wait_for_timeout(400)
    board_ys, empties, overflow, steps = set(), [], [], 0
    while True:
        m = metrics(page, ".fixed")
        if not m:
            empties.append(f"étape {steps} : bulle absente")
            break
        board_ys.add(m["boardY"])
        if not m["bodyText"]:
            empties.append(f"étape {steps}")
        if not m["bodyFits"]:
            overflow.append(f"étape {steps} : {m['bodyText'][:50]}")
        steps += 1
        cta = page.locator(".fixed button", has_text=re.compile(r"^(Suivant|Résumé)$")).last
        if cta.inner_text().strip() == "Résumé" or steps > 20:
            break
        cta.click()
        page.wait_for_timeout(350)
    check("[guidé 852] 14 demi-coups parcourus", steps == 14, f"({steps})")
    check("[guidé 852] bulle jamais vide (coups adverses compris)", not empties, f"({empties[:3]})")
    check("[guidé 852] échiquier immobile d'un coup à l'autre", len(board_ys) == 1, f"(y = {sorted(board_ys)})")
    check("[guidé 852] corps de bulle sans défilement à chaque pas", not overflow, f"({overflow[:3]})")
    icons = page.evaluate(CONTRAST_JS, ".fixed")
    check("[guidé 852] pastilles de la bande ≥ 18 px", icons and min(i["size"] for i in icons) >= 18, f"({icons and min(i['size'] for i in icons)})")
    # 7.♗e2 : mat autorisé, Réessayer disponible
    page.locator(".fixed button[data-current]", has_text="e2").first.click()
    page.wait_for_timeout(500)
    m_g = metrics(page, ".fixed")
    centred("[guidé 852] avatar centré", m_g)
    visible("[guidé 852] avatar réellement visible", m_g)
    check("[guidé 852] titre en figurine agrandie (≥ 1,2 × le texte)", bool(m_g and m_g["figRatio"] and m_g["figRatio"] >= 1.2), f"({m_g and m_g['figRatio']})")
    check("[guidé 852] 7.♗e2 : la bulle parle du mat", bool(m_g and "mat" in m_g["bodyText"].lower()), f"({m_g and m_g['bodyText'][:80]})")
    page.screenshot(path=f"{SHOTS}/coach_guided_852.png")
    page.locator(".fixed button", has_text="Réessayer").click()
    page.wait_for_timeout(600)
    m_r = metrics(page, ".fixed")
    check("[réessayer 852] échiquier immobile", bool(m_g and m_r and m_g["boardY"] == m_r["boardY"]), f"({m_g and m_g['boardY']} -> {m_r and m_r['boardY']})")
    check("[réessayer 852] hauteur de bulle inchangée", bool(m_g and m_r and abs(m_g["bubbleH"] - m_r["bubbleH"]) < 1), f"({m_g and m_g['bubbleH']} -> {m_r and m_r['bubbleH']})")
    check("[réessayer 852] boutons Solution et Quitter dans la bulle",
          page.locator(".fixed .bg-white button", has_text="Solution").count() == 1 and page.locator(".fixed .bg-white button", has_text="Quitter").count() == 1)
    check("[réessayer 852] consigne sans emoji", "🎯" not in page.locator(".fixed .bg-white").first.inner_text())
    centred("[réessayer 852] avatar centré", m_r)
    visible("[réessayer 852] avatar réellement visible", m_r)
    page.screenshot(path=f"{SHOTS}/coach_retry_852.png")
    ctx.close()
    return game_id


# Partie de l'Opéra (Morphy, 1858), vue des Noirs : bilan Stockfish réel, chaque bulle auditée.
OPERA = ("1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 "
         "10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8#")


# L'Immortelle (Anderssen, 1851), vue des Blancs : sacrifices, mat final ♗e7#.
IMMORTELLE = ("1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5 8. Nh4 Qg5 9. Nf5 c6 "
              "10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8 15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 "
              "18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6 21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7#")


def real_game_audit(p, browser):
    audit_game(p, browser, "opéra", OPERA, "b", "1-0")
    audit_game(p, browser, "immortelle", IMMORTELLE, "w", "1-0")


def audit_game(p, browser, tag, pgn, color, result):
    import chess
    import chess.pgn
    import io
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    game_id = seed_bot_game(page, pgn, color, result)
    if not run_review(page, game_id, tag):
        ctx.close()
        return
    page.click("text=Démarrer le bilan")
    page.wait_for_timeout(600)
    page.locator(".fixed button[data-current]").first.click()
    page.wait_for_timeout(400)
    bodies = []
    while len(bodies) < 80:
        m = metrics(page, ".fixed")
        bodies.append(m["bodyText"] if m else "")
        cta = page.locator(".fixed button", has_text=re.compile(r"^(Suivant|Résumé)$")).last
        if cta.inner_text().strip() == "Résumé":
            break
        cta.click()
        page.wait_for_timeout(300)
    board = chess.pgn.read_game(io.StringIO(pgn)).board()
    moves = list(chess.pgn.read_game(io.StringIO(pgn)).mainline_moves())
    rows, claims, errors = [], {}, []
    for i, mv in enumerate(moves[:len(bodies)]):
        fb = board.fen()
        mover = "w" if board.turn else "b"
        board.push(mv)
        row = {"label": tag, "i": i, "body": bodies[i], "fenBefore": fb, "fenAfter": board.fen(), "uci": mv.uci(), "mover": mover, "cls": None, "any": True}
        cl, errs = oracle.audit(row)
        for c in cl:
            claims[c] = claims.get(c, 0) + 1
        errors += [f"{i} {e} « {bodies[i][:60]} »" for e in errs]
    check(f"[{tag}] bilan Stockfish réel parcouru en entier ({len(moves)} demi-coups)", len(bodies) == len(moves), f"({len(bodies)})")
    check(f"[{tag}] chaque motif annoncé existe sur l'échiquier ({claims})", not errors, f"({errors[:3]})")
    page.screenshot(path=f"{SHOTS}/coach_{tag}_852.png")
    ctx.close()


def display_660(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=False)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1500)
    page.locator("main button", has_text="Finales").click()
    page.wait_for_timeout(1500)
    centred("[leçon 660] avatar centré", metrics(page, ".fixed"))
    page.screenshot(path=f"{SHOTS}/coach_lesson_660.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(300)

    game_id = seed_bot_game(page)
    if not run_review(page, game_id, "bilan 660"):
        ctx.close()
        return
    page.click("text=Démarrer le bilan")
    page.wait_for_timeout(600)
    page.locator(".fixed button[data-current]", has_text="e2").first.click()
    page.wait_for_timeout(500)
    m_g = metrics(page, ".fixed")
    centred("[guidé 660] avatar centré", m_g)
    visible("[guidé 660] avatar réellement visible", m_g)
    page.screenshot(path=f"{SHOTS}/coach_guided_660.png")
    page.locator(".fixed button", has_text="Réessayer").click()
    page.wait_for_timeout(600)
    m_r = metrics(page, ".fixed")
    check("[réessayer 660] échiquier immobile", bool(m_g and m_r and m_g["boardY"] == m_r["boardY"]), f"({m_g and m_g['boardY']} -> {m_r and m_r['boardY']})")
    visible("[réessayer 660] avatar réellement visible", m_r)
    check("[660] aucun débordement horizontal", page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    page.screenshot(path=f"{SHOTS}/coach_retry_660.png")
    ctx.close()


def suite(p):
    texts_part()
    if os.environ.get("COACH_TEXTS_ONLY"):
        return
    browser = p.chromium.launch(headless=True)
    display_852(p, browser)
    display_660(p, browser)
    real_game_audit(p, browser)
    browser.close()


ck.run(suite)
