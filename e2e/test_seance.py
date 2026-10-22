"""E2E « Séance du jour » (/seance) : entraînement guidé de 10 à 15 minutes.

Deux volets :
- banc Node (src/lib/seance.ts bundlé par rolldown, comme test_insights) : poids des faiblesses
  (historique lissé sur 14 jours civils, rapport Insights prioritaire), planificateur sur une grille
  de cas (budget 10 à 15 minutes, plafonds, ordre, raisons, thème et famille tirés d'Insights),
  série de jours (aujourd'hui, à prolonger, trou, plusieurs séances un même jour, passage à
  l'heure d'été sous TZ=Europe/Paris), temps du bilan ;
- parcours UI (iPhone 14 Pro standalone, base semée nativement après création du schéma, service
  worker bloqué, `puzzles.json` remplacé par des mats en 1) : tuile de l'accueil et série, plan
  affiché, révision (faute et puzzle), puzzles classés (Elo et `puzzleAttempts` comme /puzzles),
  aller-retour Analyser, rechargement en pleine séance, attaque abandonnée puis bilan, ligne
  `seance`, accueil « Faite aujourd'hui », réinitialisation qui efface la clé de séance ; second
  parcours sans puzzles (indisponibles) avec une variante ratée et une finale ; mises en page
  393x852, 393x660 et 1440x900.

Usage : npm run test:e2e -- --suite seance
        npm run test:e2e:dev -- --suite seance      (StrictMode : effets et updaters doublés)
"""
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime

from helpers import BASE, Checker, click_square, desktop_context, mobile_context, overflow_x, shot, tap_move

ck = Checker("seance")
check = ck.check

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
SESSION_KEY = "seance-session-v1"

with open(os.path.join(ROOT, "src", "data", "openings.json"), encoding="utf-8") as f:
    OPENINGS = json.load(f)
GORING = next(o for o in OPENINGS if o["name"] == "Scotch Game: Göring Gambit, Main Line")["uci"]

DAY = 86_400_000
TODAY0 = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)


def ago(days=0):
    """Midi il y a `days` jours ; `days=0` : aujourd'hui, une minute après minuit."""
    return TODAY0 + 60_000 if days == 0 else TODAY0 - days * DAY + DAY // 2


# ================================================================== banc Node

BENCH_JS = r"""
globalThis.location ??= { href: '' }
const m = await import(process.argv[2])
const out = {}
const NOW = new Date(2026, 9, 16, 15, 0).getTime() // 16 octobre 2026, 15 h locales
const at = (d, h = 12) => { const x = new Date(NOW); x.setHours(h, 0, 0, 0); x.setDate(x.getDate() - d); return x.getTime() }
// Générateur déterministe (graine fixe) : les tirages du banc sont reproductibles.
const rng = (seed = 7) => () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296 } // mulberry32
const sess = (domain, itemId, d, ok, extra = {}) => ({ date: at(d), domain, itemId, success: ok ? 1 : 0, ...extra })
const pz = (d, ok) => ({ date: at(d), success: ok })
const attacks = [{ id: 'a1', solved: true }, { id: 'a2', solved: false }, { id: 'a3', solved: false }]
const endgames = [{ id: 'e1', solved: false }, { id: 'e2', solved: true }]
const base = { now: NOW, due: [], puzzleRating: 1500, puzzles: [], sessions: [], findings: null, attacks, endgames, variants: [] }
const brief = (p) => ({ blocks: p.blocks.map((b) => ({ kind: b.kind, count: b.count, ref: b.ref ?? null, reason: b.reason })), minutes: p.minutes,
  weights: Object.fromEntries(Object.entries(p.weights).map(([k, v]) => [k, v.weight])) })

// ---------- poids ----------
out.wHistory = m.domainWeights({ now: NOW, findings: null,
  // 2 réussites sur 6 dans la fenêtre (J-13 compris), 3 réussites hors fenêtre (J-14, J-40) et une date future ignorées.
  puzzles: [pz(0, true), pz(1, false), pz(3, false), pz(5, true), pz(10, false), pz(13, false), pz(14, true), pz(40, true), pz(40, true), { date: NOW + DAY_MS(), success: true }],
  sessions: [sess('attack', 'x', 1, true), sess('attack', 'y', 2, false, { outcome: 'abandon' }), sess('opening-drill', 'full:w:e2e4', 2, false), sess('opening-drill', 'next:w:e2e4', 3, false),
    sess('tactic', 'p1', 4, true), sess('revision', 'puzzle:p2', 4, false), sess('revision', 'mistake', 4, false), sess('mistakes', '3', 4, false), sess('course', 'finales:x', 1, true)] })
function DAY_MS() { return 86400000 }
const findings = [
  { id: 'phase-endgame', title: 'Finale fragile', severity: 0.8, plan: [] },
  { id: 'conversion', title: 'Positions gagnantes non converties', severity: 0.5, plan: [] },
  { id: 'tactiques-manquees', title: 'Tactiques manquées', severity: 0.6, plan: [{ label: 'x', to: '/apprendre', state: { tactic: 'fork' } }, { label: 'Problèmes', to: '/puzzles' }] },
  { id: 'gaffes', title: 'Trop de gaffes', severity: 0.3, plan: [{ label: 'y', to: '/apprendre', state: { tactic: 'hangingPiece' } }] },
  { id: 'ouverture-Caro-Kann Defense-b', title: 'Caro-Kann avec les Noirs', severity: 0.4, plan: [] },
  { id: 'ouverture-Sicilian Defense-w', title: 'Défense sicilienne avec les Blancs', severity: 0.9, plan: [] },
  { id: 'inconnue', title: '?', severity: 1, plan: [] },
]
out.wInsights = m.domainWeights({ now: NOW, puzzles: [], sessions: [], findings })
out.wInsightsEmpty = m.domainWeights({ now: NOW, puzzles: [], sessions: [], findings: [] })
out.theme = m.tacticTheme(findings)
out.themeNone = m.tacticTheme(null)
out.openings = m.weakOpenings(findings)
out.domainOf = Object.fromEntries(['gaffes', 'mats-manques', 'attaque', 'phase-endgame', 'phase-opening', 'phase-middlegame', 'couleur', 'ouverture-x-w', 'tendance', 'zzz'].map((id) => [id, m.findingDomain(id)]))

// ---------- plans ----------
const due = (n) => Array.from({ length: n }, (_, i) => ({ kind: i % 3 === 0 ? 'mistake' : i % 3 === 1 ? 'puzzle' : 'variant', key: i % 3 === 2 ? `w:v${i}` : String(i) }))
const cases = {
  vide: base,
  dus2: { ...base, due: due(2) },
  dus10: { ...base, due: due(10) },
  sansAttaque: { ...base, attacks: [] },
  sansLong: { ...base, attacks: [], endgames: [] },
  rienDuTout: { ...base, attacks: [], endgames: [], puzzlesAvailable: false },
  sansPuzzles: { ...base, puzzlesAvailable: false, variants: [{ key: 'w:e2e4 e7e5', last: at(0), family: null }] },
  finalesFaibles: { ...base, sessions: [sess('endgame-play', 'e1', 1, false), sess('endgame-play', 'e1', 2, false), sess('endgame-play', 'e2', 3, false)] },
  insights: { ...base, findings, due: due(1), variants: [
    { key: 'w:old', last: at(5), family: null }, { key: 'w:recent', last: at(1), family: null },
    { key: 'b:ck', last: 0, family: 'Caro-Kann Defense' }, { key: 'w:sic', last: 0, family: 'Sicilian Defense' }] },
  variantesSeules: { ...base, variants: [{ key: 'w:old', last: at(5), family: null }, { key: 'w:recent', last: at(1), family: null }] },
  // Variante déjà due dans la révision : jamais deux fois.
  varianteDue: { ...base, due: [{ kind: 'variant', key: 'w:recent' }], variants: [{ key: 'w:recent', last: at(1), family: null }] },
  // Budget déjà à 12 min avec le minimum de puzzles (4 dus + attaque) : la variante n'entre que si
  // les ouvertures pèsent au moins 0,4.
  ouverturesFaibles: { ...base, due: due(4).map((d) => ({ ...d, kind: 'mistake' })), sessions: [sess('opening-drill', 'full:w:a', 1, false), sess('opening-drill', 'full:w:b', 2, false)], variants: [{ key: 'w:a', last: at(1), family: null }] },
  ouverturesFortes: { ...base, due: due(4).map((d) => ({ ...d, kind: 'mistake' })), sessions: [sess('opening-drill', 'full:w:a', 1, true), sess('opening-drill', 'full:w:b', 2, true)], variants: [{ key: 'w:a', last: at(1), family: null }] },
  tactiqueFaible: { ...base, puzzles: [pz(1, false), pz(2, false), pz(3, false), pz(4, false)] },
}
out.plans = Object.fromEntries(Object.entries(cases).map(([k, c]) => [k, brief(m.planSeance(c, rng()))]))
// Grille : budget et plafonds sur toutes les combinaisons de dus, variantes, poids et disponibilités.
const grid = []
for (const n of [0, 1, 3, 4, 5, 12]) for (const v of [0, 1]) for (const f of [null, findings, []]) for (const pa of [true, false]) for (const long of ['both', 'attack', 'endgame', 'none']) {
  const input = { ...base, due: due(n), findings: f, puzzlesAvailable: pa,
    attacks: long === 'both' || long === 'attack' ? attacks : [], endgames: long === 'both' || long === 'endgame' ? endgames : [],
    variants: v ? [{ key: 'w:x', last: at(1), family: null }] : [] }
  const p = m.planSeance(input, rng(n + 1))
  grid.push({ n, v, f: f === null ? 'null' : f.length, pa, long, blocks: p.blocks.map((b) => [b.kind, b.count]), minutes: p.minutes,
    sum: p.blocks.reduce((s, b) => s + m.BLOCK_META[b.kind].minutes * b.count, 0) })
}
out.grid = grid
// Tirage du bloc long : jamais réussi d'abord (a2 ou a3, jamais a1), sur 40 graines.
out.longRefs = [...new Set(Array.from({ length: 40 }, (_, i) => m.planSeance(base, rng(i + 11)).blocks.find((b) => b.kind === 'attack')?.ref))].sort()
out.longAllSolved = [...new Set(Array.from({ length: 40 }, (_, i) => m.planSeance({ ...base, attacks: [{ id: 'z1', solved: true }, { id: 'z2', solved: true }] }, rng(i + 3)).blocks.find((b) => b.kind === 'attack')?.ref))].sort()

// ---------- série ----------
const S = (ds, now = NOW) => m.streak(ds, now)
out.streak = {
  vide: S([]),
  aujourdhui: S([at(0)]),
  hierAvantHier: S([at(1), at(2)]),
  avecAujourdhui: S([at(0), at(1), at(2)]),
  trou: S([at(0), at(2), at(3)]),
  trouHier: S([at(2), at(3)]),
  memeJour: S([at(0, 8), at(0, 9), at(0, 14), at(1, 23)]),
  minuit: S([at(1, 23), at(0, 0)]), // 23 h hier puis minuit pile : deux jours
  futur: S([NOW + 3600000]),
}
// Heure d'été : la nuit du 28 au 29 mars 2026 dure 23 h à Paris. Séances le 27, le 28 à 23 h 30,
// le 29 à 0 h 30 et le 30 : quatre jours consécutifs le 30.
const dst = [new Date(2026, 2, 27, 12).getTime(), new Date(2026, 2, 28, 23, 30).getTime(), new Date(2026, 2, 29, 0, 30).getTime(), new Date(2026, 2, 30, 9).getTime()]
out.streakDst = m.streak(dst, new Date(2026, 2, 30, 20).getTime())
out.streakDstHier = m.streak(dst.slice(0, 3), new Date(2026, 2, 30, 20).getTime())
out.streakLabel = [m.streakLabel(1), m.streakLabel(3)]

// ---------- temps et bilan ----------
out.durations = [m.stepDuration(1000, 61000), m.stepDuration(0, 25 * 60000), m.stepDuration(5000, 1000)]
out.minutes = [m.minutesLabel(0), m.minutesLabel(29000), m.minutesLabel(90000), m.minutesLabel(11 * 60000 + 20000)]
out.summary = m.summarize(['revision', 'revision', 'puzzles', 'puzzles', 'puzzles', 'attack'],
  [{ idx: 0, kind: 'revision', ok: true, ms: 1 }, { idx: 1, kind: 'revision', ok: false, ms: 1 }, { idx: 2, kind: 'puzzles', ok: true, ms: 1 }, { idx: 4, kind: 'puzzles', ok: true, ms: 1 }])
out.estimate = m.estimateMinutes(['revision', 'puzzles', 'puzzles', 'opening', 'attack'])
console.log(JSON.stringify(out))
"""


def node_bench():
    src = os.path.join(ROOT, "src", "lib", "seance.ts")
    if not os.path.exists(src):
        ck.fail("[banc] src/lib/seance.ts existe")
        return None
    with tempfile.TemporaryDirectory() as d:
        bundle = os.path.join(d, "seance.mjs")
        r = subprocess.run([ROLLDOWN, src, "--format", "esm", "--file", bundle], cwd=ROOT, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            ck.fail("[banc] bundle rolldown de seance.ts", (r.stderr or r.stdout)[-300:])
            return None
        script = os.path.join(d, "bench.mjs")
        with open(script, "w", encoding="utf-8") as f:
            f.write(BENCH_JS)
        # Fuseau fixé : le cas « heure d'été » vise la nuit du 28 au 29 mars 2026 à Paris.
        r = subprocess.run(["node", script, "file://" + bundle], cwd=ROOT, capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "Europe/Paris"})
    if r.returncode != 0:
        ck.fail("[banc] seance.ts sous Node", r.stderr.strip()[-400:])
        return None
    return json.loads(r.stdout.strip().splitlines()[-1])


def laplace(ok, n):
    return round(1 - (ok + 1) / (n + 2), 3)


def bench_checks(out):
    t = "[banc]"
    w = {k: v["weight"] for k, v in out["wHistory"].items()}
    n = {k: (v["n"], v["ok"]) for k, v in out["wHistory"].items()}
    # Puzzles : 6 classés dans la fenêtre (2 réussis) + tactic réussi + revision puzzle raté = 8, 3 réussis.
    check(f"{t} poids historique tactique : 3 réussites sur 8 (fenêtre de 14 jours, futur ignoré, revision puzzle et tactic comptés)", n["tactics"] == (8, 3) and w["tactics"] == laplace(3, 8), f"({n['tactics']}, {w['tactics']})")
    check(f"{t} poids historique attaque : abandon ignoré (1 réussite sur 1)", n["attack"] == (1, 1) and w["attack"] == laplace(1, 1), f"({n['attack']}, {w['attack']})")
    check(f"{t} poids historique ouvertures : toutes les tentatives du drill (0 sur 2)", n["opening"] == (2, 0) and w["opening"] == laplace(0, 2), f"({n['opening']})")
    check(f"{t} poids historique finales : sans données, 0,5 (cours et fautes hors domaines)", n["endgame"] == (0, 0) and w["endgame"] == 0.5, f"({n['endgame']}, {w['endgame']})")
    wi = {k: v["weight"] for k, v in out["wInsights"].items()}
    fi = {k: (v["finding"] or {}).get("id") for k, v in out["wInsights"].items()}
    exp = {"tactics": round(0.7 * 0.6 + 0.3 * 0.5, 3), "attack": round(0.3 * 0.5, 3), "endgame": round(0.7 * 0.8 + 0.3 * 0.5, 3), "opening": round(0.7 * 0.9 + 0.3 * 0.5, 3)}
    check(f"{t} poids avec Insights : 70 % sévérité max du domaine + 30 % historique", wi == exp, f"({wi} vs {exp})")
    check(f"{t} faiblesse retenue = la plus sévère du domaine (id inconnu ignoré)", fi == {"tactics": "tactiques-manquees", "attack": None, "endgame": "phase-endgame", "opening": "ouverture-Sicilian Defense-w"}, f"({fi})")
    we = {k: v["weight"] for k, v in out["wInsightsEmpty"].items()}
    check(f"{t} rapport Insights sans faiblesse : 30 % de l'historique seulement", all(v == 0.15 for v in we.values()), f"({we})")
    check(f"{t} thème de puzzle : celui de la faiblesse tactique la plus sévère (fork), aucun sans rapport", out["theme"] == "fork" and out["themeNone"] is None, f"({out['theme']}, {out['themeNone']})")
    check(f"{t} familles d'ouvertures signalées, la plus sévère d'abord, clé lichess à tiret (Caro-Kann)", out["openings"] == [{"family": "Sicilian Defense", "color": "w"}, {"family": "Caro-Kann Defense", "color": "b"}], f"({out['openings']})")
    check(f"{t} rattachement des faiblesses aux domaines", out["domainOf"] == {"gaffes": "tactics", "mats-manques": "attack", "attaque": "attack", "phase-endgame": "endgame", "phase-opening": "opening",
                                                                         "phase-middlegame": "tactics", "couleur": "opening", "ouverture-x-w": "opening", "tendance": "tactics", "zzz": None}, f"({out['domainOf']})")

    P = out["plans"]

    def kinds(p):
        return [(b["kind"], b["count"]) for b in p["blocks"]]

    check(f"{t} plan vide : 7 puzzles plafonnés à 6, attaque en dernier (égalité de poids : attaque), 11 min",
          kinds(P["vide"]) == [("puzzles", 6), ("attack", 1)] and P["vide"]["minutes"] == 11, f"({kinds(P['vide'])}, {P['vide']['minutes']})")
    check(f"{t} plan vide : raisons « Autour de ton classement (1500) » et « Pas travaillé ces 14 derniers jours »",
          P["vide"]["blocks"][0]["reason"] == "Autour de ton classement (1500)" and P["vide"]["blocks"][1]["reason"] == "Pas travaillé ces 14 derniers jours", f"({[b['reason'] for b in P['vide']['blocks']]})")
    check(f"{t} 2 dus : révision 2 en tête, « 2 éléments dus aujourd'hui »", kinds(P["dus2"])[0] == ("revision", 2) and P["dus2"]["blocks"][0]["reason"] == "2 éléments dus aujourd'hui", f"({kinds(P['dus2'])})")
    check(f"{t} 10 dus : révision plafonnée à 4, « 4 des 10 éléments dus aujourd'hui »", kinds(P["dus10"])[0] == ("revision", 4) and P["dus10"]["blocks"][0]["reason"] == "4 des 10 éléments dus aujourd'hui", f"({kinds(P['dus10'])})")
    check(f"{t} sans attaque : la finale prend le bloc long", [k for k, _ in kinds(P["sansAttaque"])] == ["puzzles", "endgame"] and P["sansAttaque"]["blocks"][1]["ref"] == "e1", f"({kinds(P['sansAttaque'])})")
    check(f"{t} sans bloc long : 6 puzzles seuls (moins de 10 min faute de candidats)", kinds(P["sansLong"]) == [("puzzles", 6)], f"({kinds(P['sansLong'])})")
    check(f"{t} rien à proposer : plan vide", kinds(P["rienDuTout"]) == [], f"({kinds(P['rienDuTout'])})")
    check(f"{t} puzzles indisponibles : variante et attaque, aucun bloc puzzles", kinds(P["sansPuzzles"]) == [("opening", 1), ("attack", 1)], f"({kinds(P['sansPuzzles'])})")
    check(f"{t} finales ratées (0 sur 3) : la finale passe devant l'attaque, raison chiffrée",
          kinds(P["finalesFaibles"])[-1] == ("endgame", 1) and P["finalesFaibles"]["blocks"][-1]["reason"] == "0 réussite sur 3 ces 14 derniers jours", f"({P['finalesFaibles']['blocks']})")
    pi = {b["kind"]: b for b in P["insights"]["blocks"]}
    check(f"{t} Insights : ordre révision, puzzles, variante, finale", [b["kind"] for b in P["insights"]["blocks"]] == ["revision", "puzzles", "opening", "endgame"], f"({kinds(P['insights'])})")
    check(f"{t} Insights : puzzles ciblés sur le thème fourchette", pi.get("puzzles", {}).get("ref") == "fork" and pi["puzzles"]["reason"] == "Fourchette : point faible d'après Insights", f"({pi.get('puzzles')})")
    check(f"{t} Insights : variante de la famille la plus sévère (sicilienne), raison Insights", pi.get("opening", {}).get("ref") == "w:sic" and pi["opening"]["reason"] == "Point faible d'après Insights : Défense sicilienne avec les Blancs", f"({pi.get('opening')})")
    check(f"{t} Insights : finale, « Point faible d'après Insights : Finale fragile »", pi.get("endgame", {}).get("reason") == "Point faible d'après Insights : Finale fragile", f"({pi.get('endgame')})")
    check(f"{t} Insights : budget dans 10 à 15 min", 10 <= P["insights"]["minutes"] <= 15, f"({P['insights']['minutes']})")
    vs = {b["kind"]: b for b in P["variantesSeules"]["blocks"]}
    check(f"{t} variante ratée la plus récente d'abord, « Ratée à ta dernière tentative » (budget sous 10 min sinon)",
          vs.get("opening", {}).get("ref") == "w:recent" and vs["opening"]["reason"] == "Ratée à ta dernière tentative", f"({P['variantesSeules']['blocks']})")
    check(f"{t} variante déjà due en révision : pas de bloc variante", "opening" not in [k for k, _ in kinds(P["varianteDue"])], f"({kinds(P['varianteDue'])})")
    check(f"{t} ouvertures faibles (0 sur 2, poids 0,75) : variante même avec le budget atteint", "opening" in [k for k, _ in kinds(P["ouverturesFaibles"])], f"({kinds(P['ouverturesFaibles'])})")
    check(f"{t} ouvertures solides (2 sur 2, poids 0,25), budget atteint : pas de variante", "opening" not in [k for k, _ in kinds(P["ouverturesFortes"])], f"({kinds(P['ouverturesFortes'])})")
    tf = dict(kinds(P["tactiqueFaible"]))
    check(f"{t} tactique la plus faible : un puzzle de plus (6 plafond : 12 - 5 = 7 -> 6)", tf.get("puzzles") == 6, f"({kinds(P['tactiqueFaible'])})")

    bad_budget = [g for g in out["grid"] if g["minutes"] > 15 or g["sum"] != g["minutes"] or (g["long"] != "none" and g["pa"] and g["minutes"] < 10)]
    check(f"{t} grille ({len(out['grid'])} cas) : jamais plus de 15 min, au moins 10 dès qu'un bloc long et les puzzles existent, minutes = somme des blocs", not bad_budget, f"({bad_budget[:3]})")
    caps = [g for g in out["grid"] if any((k == "revision" and not 1 <= c <= 4) or (k == "puzzles" and not 3 <= c <= 6) or (k in ("attack", "endgame", "opening") and c != 1) for k, c in g["blocks"])]
    check(f"{t} grille : révision 1 à 4, puzzles 3 à 6, un seul long et une seule variante", not caps, f"({caps[:3]})")
    order = {"revision": 0, "puzzles": 1, "opening": 2, "attack": 3, "endgame": 3}
    disorder = [g for g in out["grid"] if [order[k] for k, _ in g["blocks"]] != sorted(order[k] for k, _ in g["blocks"]) or sum(1 for k, _ in g["blocks"] if k in ("attack", "endgame")) > 1]
    check(f"{t} grille : ordre révision, puzzles, variante, bloc long", not disorder, f"({disorder[:3]})")
    rev = [g for g in out["grid"] if (g["n"] > 0) != any(k == "revision" for k, _ in g["blocks"])]
    check(f"{t} grille : un bloc révision si et seulement si quelque chose est dû", not rev, f"({rev[:3]})")
    nopz = [g for g in out["grid"] if not g["pa"] and any(k == "puzzles" for k, _ in g["blocks"])]
    check(f"{t} grille : aucun bloc puzzles quand puzzles.json est indisponible", not nopz, f"({nopz[:3]})")
    check(f"{t} bloc long : positions jamais réussies d'abord (a2, a3 ; jamais a1 sur 40 tirages)", out["longRefs"] == ["a2", "a3"], f"({out['longRefs']})")
    check(f"{t} bloc long : toutes réussies, tirage parmi toutes", out["longAllSolved"] == ["z1", "z2"], f"({out['longAllSolved']})")

    s = out["streak"]
    check(f"{t} série vide : 0", s["vide"] == {"days": 0, "today": False}, f"({s['vide']})")
    check(f"{t} série : aujourd'hui seul = 1, faite", s["aujourdhui"] == {"days": 1, "today": True}, f"({s['aujourdhui']})")
    check(f"{t} série : hier et avant-hier, pas aujourd'hui = 2, à prolonger", s["hierAvantHier"] == {"days": 2, "today": False}, f"({s['hierAvantHier']})")
    check(f"{t} série : aujourd'hui, hier, avant-hier = 3", s["avecAujourdhui"] == {"days": 3, "today": True}, f"({s['avecAujourdhui']})")
    check(f"{t} série : trou hier, elle repart d'aujourd'hui (1)", s["trou"] == {"days": 1, "today": True}, f"({s['trou']})")
    check(f"{t} série : ni aujourd'hui ni hier = 0", s["trouHier"] == {"days": 0, "today": False}, f"({s['trouHier']})")
    check(f"{t} série : plusieurs séances un même jour comptent pour un jour", s["memeJour"] == {"days": 2, "today": True}, f"({s['memeJour']})")
    check(f"{t} série : 23 h hier et minuit pile aujourd'hui = deux jours civils", s["minuit"] == {"days": 2, "today": True}, f"({s['minuit']})")
    check(f"{t} série : une date future est ignorée", s["futur"] == {"days": 0, "today": False}, f"({s['futur']})")
    check(f"{t} série : nuit de 23 h du passage à l'heure d'été (Paris) = 4 jours civils", out["streakDst"] == {"days": 4, "today": True}, f"({out['streakDst']})")
    check(f"{t} série : à prolonger le lendemain du passage à l'heure d'été (3)", out["streakDstHier"] == {"days": 3, "today": False}, f"({out['streakDstHier']})")
    check(f"{t} libellés de série", out["streakLabel"] == ["🔥 1 jour", "🔥 3 jours"], f"({out['streakLabel']})")
    check(f"{t} durée d'étape : réelle, plafonnée à 10 min, jamais négative", out["durations"] == [60000, 600000, 0], f"({out['durations']})")
    check(f"{t} temps : au moins 1 min, arrondi à la minute", out["minutes"] == ["1 min", "1 min", "2 min", "11 min"], f"({out['minutes']})")
    check(f"{t} bilan par bloc (étapes consécutives d'un type, non jugées comptées dans le total prévu)",
          out["summary"] == [{"kind": "revision", "ok": 1, "total": 2, "steps": 2}, {"kind": "puzzles", "ok": 2, "total": 2, "steps": 3}, {"kind": "attack", "ok": 0, "total": 0, "steps": 1}], f"({out['summary']})")
    check(f"{t} durée estimée = somme des minutes par étape (1 + 2 + 2 + 5)", out["estimate"] == 10, f"({out['estimate']})")


# ================================================================== IndexedDB natif

TABLES = sorted(["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews"])

OPEN_DB = """
() => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => res(r.result)
  r.onerror = () => rej(r.error)
})
"""


def wait_schema(page, tries=40):
    """L'app (Dexie) crée la base au premier accès : attendre les tables du schéma courant avant d'y écrire."""
    for _ in range(tries):
        tables = page.evaluate(
            """() => new Promise((res) => {
              indexedDB.databases().then((list) => {
                if (!list.some((d) => d.name === 'chess-local')) return res(0)
                const r = indexedDB.open('chess-local')
                r.onsuccess = () => { const t = Array.from(r.result.objectStoreNames).sort(); r.result.close(); res(t) }
                r.onerror = () => res(-1)
              })
            })"""
        )
        if tables == TABLES:
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


def db_rows(page, table):
    return page.evaluate(
        "async (t) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const rows = await new Promise((res, rej) => { const q = db.transaction(t).objectStore(t).getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
          db.close()
          return rows
        }""",
        table,
    )


def domain_rows(page, domain):
    return sorted((r for r in db_rows(page, "learnSessions") if r["domain"] == domain), key=lambda r: r["date"])


# ================================================================== données semées

# Mat en 1 : amorce ...Nc3 (coup adverse), puis Ra8#. Même position sous plusieurs ids.
MATE_FEN = "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1"
RATED_IDS = [f"S{i:02d}" for i in range(1, 13)]
PUZZLES = [[pid, MATE_FEN, "e4c3 a1a8", 820, "backRankMate mate mateIn1 short"] for pid in ["R1", *RATED_IDS]]
# Faute : Dxd8+ gagne la dame (bestUci d1d8).
MISTAKE_FEN = "3q2k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1"


def ls(i, domain, item, date, ok, **extra):
    return {"id": i, "date": date, "domain": domain, "itemId": item, "success": 1 if ok else 0, "ratingAfter": None, **extra}


# Parcours principal : dus = faute 1 (créée J-10) et puzzle R1 (raté J-5) ; séances du jour terminées
# hier et avant-hier (série 2, à prolonger). Historique : R1 raté (tactique 0 sur 1, poids 0,667 > 0,5)
# -> bloc long attaque (égalité attaque/finale), puzzles 12 - 2 - 5 = 5, +1 (tactique la plus faible) = 6.
SEED = {
    "puzzleAttempts": [{"id": 1, "puzzleId": "R1", "date": ago(5), "success": False, "puzzleRating": 820, "ratingAfter": 790}],
    "mistakes": [{"id": 1, "date": ago(10), "gameLabel": "Partie 1", "fenBefore": MISTAKE_FEN, "playedSan": "h3", "bestUci": "d1d8", "cls": "blunder", "attempts": 0, "solved": 0}],
    "learnSessions": [ls(1, "seance", "puzzles+attack", ago(1), True, score=5), ls(2, "seance", "puzzles+endgame", ago(2), True, score=4)],
    "ratings": [{"key": "puzzle", "value": 800, "games": 30}],
}
EXPECTED_STEPS = 9  # 2 révisions + 6 puzzles + 1 attaque

# Second parcours : puzzles.json indisponible ; variante Göring ratée aujourd'hui (due demain : hors
# révision, candidate du bloc variante) ; trois finales jouées ratées (poids 0,8) -> bloc long finale.
SEED2 = {
    "learnSessions": [
        ls(1, "opening-drill", f"full:w:{GORING}", ago(0), False),
        ls(2, "endgame-play", "kq-k", ago(1), False), ls(3, "endgame-play", "kq-k", ago(2), False), ls(4, "endgame-play", "kq-k", ago(3), False),
    ],
}


def seeded(p, browser, seed, puzzles_ok=True, standalone=True, desktop=False):
    if desktop:
        ctx = desktop_context(browser, ck, service_workers="block")
    elif standalone is None:
        ctx = mobile_context(p, browser, ck, service_workers="block")
    else:
        ctx = mobile_context(p, browser, ck, standalone=standalone, service_workers="block")
    body = json.dumps(PUZZLES)
    if puzzles_ok:
        ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    else:
        ctx.route("**/puzzles.json", lambda route: route.fulfill(status=404, body="absent"))
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    ck.appears("[seed] Stats chargée", page, "main :text('Statistiques')", timeout=15000)
    if check("[seed] schéma courant créé par l'app", wait_schema(page)):
        seed_db(page, seed)
    return ctx, page


# ================================================================== lecture de la page

def progress(page):
    el = page.locator("[data-seance-progress]")
    return el.first.inner_text().strip() if el.count() else ""


def stored(page):
    raw = page.evaluate(f"() => sessionStorage.getItem('{SESSION_KEY}')")
    return json.loads(raw) if raw else None


def wait_step(page, n, total, timeout=15000):
    """Attend l'étape n/total (pastille de progression) ; True si elle est affichée."""
    try:
        page.wait_for_function(
            "(t) => [...document.querySelectorAll('[data-seance-progress]')].some((e) => e.textContent.includes(t))",
            arg=f"{n}/{total}", timeout=timeout,
        )
        return True
    except Exception:
        return False


def click_text_button(page, text, scope=""):
    loc = page.locator(f"{scope} button", has_text=text) if scope else page.locator("button", has_text=text)
    if loc.count():
        loc.last.click()
        return True
    return False


def play_mate(page, ok=True):
    """Puzzle de mat en 1 : amorce ...Nc3 puis Ra8# (ok) ou Ra7 (faux)."""
    page.wait_for_timeout(1200)
    tap_move(page, "a1", "a8" if ok else "a7")


def go_next(page, label="Suivant"):
    btn = page.get_by_role("button", name=label, exact=True)
    if ck.appears(f"[séance] bouton « {label} »", page, f"button:text-is('{label}')", timeout=8000):
        btn.last.click()
        page.wait_for_timeout(400)


# ================================================================== parcours principal

def part_main(p, browser):
    ctx, page = seeded(p, browser, SEED)

    # --- accueil : tuile et série semée ---
    page.goto(f"{BASE}/#/")
    ck.appears("[accueil] série chargée", page, "[data-seance-ready]", timeout=10000, state="attached")
    tile = page.locator("[data-seance-tile]")
    if check("[accueil] tuile « Séance du jour »", tile.count() == 1 and "Séance du jour" in tile.inner_text()):
        status = page.locator("[data-seance-status]").inner_text()
        check("[accueil] sous-titre : « 10 à 15 min guidées · 🔥 2 jours » (hier et avant-hier)", status == "10 à 15 min guidées · 🔥 2 jours", f"({status!r})")
        check("[accueil] aucun débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
        shot(page, "seance_home_852")
        hist = page.evaluate("() => history.length")
        tile.click()
        page.wait_for_timeout(400)
        check("[accueil] la tuile mène à #/seance (descente empilée)", page.evaluate("() => location.hash") == "#/seance" and page.evaluate("() => history.length") == hist + 1)
    actives = page.locator("nav a[aria-current]").locator("visible=true").all_inner_texts()
    check("[nav] onglet Accueil allumé sur /seance", len(actives) == 1 and "Accueil" in actives[0], f"({actives})")

    # --- accueil de la séance : plan attendu ---
    if ck.appears("[plan] accueil de la séance", page, "[data-seance-intro]", timeout=20000):
        plan = [(e.get_attribute("data-seance-plan"), e.inner_text()) for e in page.locator("[data-seance-plan]").all()]
        check("[plan] blocs révision, puzzles, attaque dans cet ordre", [k for k, _ in plan] == ["revision", "puzzles", "attack"], f"({plan})")
        if len(plan) == 3:
            check("[plan] révision · 2, « 2 éléments dus aujourd'hui »", "· 2" in plan[0][1] and "2 éléments dus aujourd'hui" in plan[0][1], f"({plan[0][1]!r})")
            check("[plan] puzzles · 6, « Autour de ton classement (800) »", "· 6" in plan[1][1] and "Autour de ton classement (800)" in plan[1][1], f"({plan[1][1]!r})")
            check("[plan] attaque, « Pas travaillé ces 14 derniers jours »", "Pas travaillé ces 14 derniers jours" in plan[2][1], f"({plan[2][1]!r})")
        est = page.locator("[data-seance-estimate]").inner_text()
        check("[plan] durée estimée « ≈ 13 min » (2 + 6 + 5)", est == "≈ 13 min", f"({est!r})")
        streak = page.locator("[data-seance-streak]").inner_text()
        check("[plan] série « 🔥 2 jours », pas encore faite aujourd'hui", "🔥 2 jours" in streak and "Faite aujourd'hui" not in streak, f"({streak!r})")
        check("[plan] rien en sessionStorage avant « Commencer »", stored(page) is None)
        check("[plan] pas de débordement horizontal", overflow_x(page) == 0)
        shot(page, "seance_intro_852")
        click_text_button(page, "Commencer")

    # --- étape 1 : faute de partie (révision, la plus en retard) ---
    if ck.appears("[révision] étape 1/9 : faute", page, "[data-seance-item=mistake]", timeout=10000):
        check("[révision] pastille « 1/9 »", progress(page) == f"1/{EXPECTED_STEPS}", f"({progress(page)!r})")
        st = stored(page)
        check("[persistance] séance écrite en sessionStorage dès le départ", st is not None and len(st["steps"]) == EXPECTED_STEPS and st["idx"] == 0, f"({st and (len(st['steps']), st['idx'])})")
        shot(page, "seance_step_mistake_852")
        tap_move(page, "d1", "d8")
        ck.appears("[révision] faute : « Réussi » sans moteur", page, "text=✓ Réussi", timeout=8000)
        note = page.locator("[data-seance-note]").inner_text() if page.locator("[data-seance-note]").count() else ""
        check("[révision] note d'échéance « Revient dans 3 jours »", note == "Revient dans 3 jours", f"({note!r})")
        go_next(page)

    # --- étape 2 : puzzle de révision ---
    if ck.appears("[révision] étape 2/9 : puzzle R1", page, "[data-seance-item=puzzle] >> text=Puzzle R1", timeout=10000):
        play_mate(page)
        ck.appears("[révision] puzzle R1 « Réussi »", page, "text=✓ Réussi", timeout=8000)
        go_next(page)
    m1 = next((m for m in db_rows(page, "mistakes") if m["id"] == 1), {})
    check("[écritures] faute 1 : solved 1, attempts 1 (comme Mes erreurs)", m1.get("solved") == 1 and m1.get("attempts") == 1, f"({m1})")
    check("[écritures] ligne `mistakes` de réussite pour la faute 1", [(r["itemId"], r["success"]) for r in domain_rows(page, "mistakes")] == [("1", 1)])
    check("[écritures] ligne `revision` puzzle:R1 réussie, sans Elo", [(r["itemId"], r["success"], r["ratingAfter"]) for r in domain_rows(page, "revision")] == [("puzzle:R1", 1, None)])
    check("[écritures] la révision n'écrit pas dans puzzleAttempts", len(db_rows(page, "puzzleAttempts")) == 1)

    # --- étapes 3 à 8 : puzzles classés ---
    seen = []
    for k in range(6):
        n = 3 + k
        if not wait_step(page, n, EXPECTED_STEPS):
            check(f"[puzzles] étape {n}/9 affichée", False, f"({progress(page)!r})")
            break
        banner = page.locator("[data-seance-banner]")
        txt = banner.first.inner_text() if banner.count() else ""
        m = re.search(r"Puzzle (S\d\d)", txt)
        check(f"[puzzles] étape {n} : un puzzle classé S.. (jamais R1, déjà vu)", m is not None, f"({txt!r})")
        if m:
            seen.append(m.group(1))
        if k == 0:
            # Échec, puis Analyser et retour : même étape, même verdict, même note.
            play_mate(page, ok=False)
            ck.appears("[puzzles] coup faux : « Raté »", page, "text=✗ Raté", timeout=8000)
            ck.appears("[puzzles] note de classement après l'échec", page, "[data-seance-note]:has-text('Classement')", timeout=5000)
            note = page.locator("[data-seance-note]").inner_text()
            check("[puzzles] note « Classement N (-x) » en baisse", re.fullmatch(r"Classement \d+ \(-\d+\)", note) is not None, f"({note!r})")
            shot(page, "seance_step_puzzle_852")
            click_text_button(page, "Analyser")
            if ck.appears("[analyse] « Retour à la séance »", page, "button:has-text('Retour à la séance')", timeout=15000):
                page.locator("button", has_text="Retour à la séance").click()
                page.wait_for_timeout(800)
                check("[analyse] retour sur #/seance", page.evaluate("() => location.hash") == "#/seance")
                check("[analyse] même étape après le retour", progress(page) == f"{n}/{EXPECTED_STEPS}", f"({progress(page)!r})")
                check("[analyse] verdict et note conservés", page.locator("text=✗ Raté").count() > 0 and page.locator("[data-seance-note]").inner_text() == note)
            # Réessayer : sans enjeu (aucune écriture de plus).
            n_att = len(db_rows(page, "puzzleAttempts"))
            if click_text_button(page, "Réessayer"):
                play_mate(page)
                ck.appears("[puzzles] réessai : « Réussi » à l'écran", page, "text=✓ Réussi", timeout=8000)
                page.wait_for_timeout(300)
                check("[puzzles] réessai sans écriture", len(db_rows(page, "puzzleAttempts")) == n_att)
            go_next(page)
        elif k == 2:
            # Rechargement en plein puzzle : la séance reprend à la même étape.
            page.reload()
            check("[rechargement] reprise à la même étape", wait_step(page, n, EXPECTED_STEPS), f"({progress(page)!r})")
            play_mate(page)
            ck.appears(f"[puzzles] étape {n} « Réussi »", page, "text=✓ Réussi", timeout=8000)
            go_next(page)
        else:
            play_mate(page)
            ck.appears(f"[puzzles] étape {n} « Réussi »", page, "text=✓ Réussi", timeout=8000)
            go_next(page)
    check("[puzzles] six puzzles distincts", len(seen) == 6 and len(set(seen)) == 6, f"({seen})")
    att = sorted(db_rows(page, "puzzleAttempts"), key=lambda a: a["date"])[1:]
    check("[écritures] 6 lignes puzzleAttempts (1 ratée puis 5 réussies), comme /puzzles", [(a["puzzleId"], a["success"]) for a in att] == [(s, i != 0) for i, s in enumerate(seen)], f"({[(a['puzzleId'], a['success']) for a in att]})")
    rating = next((r for r in db_rows(page, "ratings") if r["key"] == "puzzle"), {})
    check("[écritures] Elo puzzle mis à jour par applyRating (36 parties)", rating.get("games") == 36 and rating.get("value") == att[-1]["ratingAfter"] if att else False, f"({rating})")
    check("[écritures] aucun autre Elo touché", sorted(r["key"] for r in db_rows(page, "ratings")) == ["puzzle"])

    # --- étape 9 : attaque, abandonnée ---
    if ck.appears("[attaque] étape 9/9 : PositionGame", page, "[data-seance-step=attack] [data-testid=position-game]", timeout=15000):
        check("[attaque] pastille « ☀️ 9/9 » dans l'en-tête", progress(page) == f"☀️ {EXPECTED_STEPS}/{EXPECTED_STEPS}", f"({progress(page)!r})")
        fen = page.get_attribute("[data-testid=position-game]", "data-fen")
        shot(page, "seance_step_attack_852")
        click_text_button(page, "Abandonner")
        if ck.appears("[attaque] confirmation d'abandon", page, "[data-testid=resign-confirm]", timeout=5000):
            page.click("[data-testid=resign-confirm]")
        ck.appears("[attaque] verdict, bouton « Voir le bilan »", page, "button:text-is('Voir le bilan')", timeout=10000)
        rows = domain_rows(page, "attack")
        check("[écritures] ligne `attack` comme l'entraîneur : outcome resign, échec, FEN de départ",
              len(rows) == 1 and rows[0]["outcome"] == "resign" and rows[0]["success"] == 0 and rows[0]["fen"] == fen, f"({rows})")
        page.get_by_role("button", name="Voir le bilan", exact=True).click()

    # --- bilan ---
    if ck.appears("[bilan] écran de fin", page, "[data-seance-end]", timeout=10000):
        score = page.locator("[data-seance-score]").inner_text()
        check("[bilan] « 7/9 réussis » (faute, R1, 5 puzzles ; un puzzle et l'attaque ratés)", score.startswith("7/9 réussis"), f"({score!r})")
        check("[bilan] temps « N min »", re.search(r"· \d+ min$", score) is not None, f"({score!r})")
        blocks = [(e.get_attribute("data-seance-block"), e.inner_text().split("\n")[-1]) for e in page.locator("[data-seance-block]").all()]
        check("[bilan] par bloc : révision 2/2, puzzles 5/6, attaque 0/1", blocks == [("revision", "2/2"), ("puzzles", "5/6"), ("attack", "0/1")], f"({blocks})")
        rt = page.locator("[data-seance-rating]").inner_text() if page.locator("[data-seance-rating]").count() else ""
        check("[bilan] classement puzzles « 800 → N »", rt == f"Classement 800 → {rating.get('value')}", f"({rt!r})")
        ck.appears("[bilan] série « 🔥 3 jours d'affilée »", page, "[data-seance-streak]:has-text('🔥 3 jours')", timeout=5000)
        check("[persistance] clé de séance retirée au bilan", stored(page) is None)
        rows = domain_rows(page, "seance")
        check("[écritures] une ligne `seance` : revision+puzzles+attack, score 7, sans Elo",
              len(rows) == 3 and rows[-1]["itemId"] == "revision+puzzles+attack" and rows[-1]["score"] == 7 and rows[-1]["success"] == 1 and rows[-1]["ratingAfter"] is None, f"({rows[-1:] })")
        check("[bilan] pas de débordement horizontal", overflow_x(page) == 0)
        shot(page, "seance_end_852")
        click_text_button(page, "Terminer")
    ck.appears("[accueil] retour à l'accueil", page, "[data-seance-tile]", timeout=8000)
    ck.appears("[accueil] série rechargée", page, "[data-seance-ready]", timeout=8000, state="attached")
    status = page.locator("[data-seance-status]").inner_text() if page.locator("[data-seance-status]").count() else ""
    check("[accueil] « ✓ Faite aujourd'hui · 🔥 3 jours »", status == "✓ Faite aujourd'hui · 🔥 3 jours", f"({status!r})")

    # --- nouvelle séance, quittée en cours : « Reprendre », puis réinitialisation ---
    page.locator("[data-seance-tile]").click()
    if ck.appears("[refaire] accueil de séance, « Faite aujourd'hui »", page, "[data-seance-intro] >> text=Faite aujourd'hui", timeout=20000):
        check("[refaire] CTA « Refaire une séance »", page.locator("button", has_text="Refaire une séance").count() == 1)
        click_text_button(page, "Refaire une séance")
        page.wait_for_timeout(500)
        click_text_button(page, "Quitter la séance") or page.get_by_label("Quitter la séance").click()
    ck.appears("[reprendre] accueil après ✕", page, "[data-seance-tile]", timeout=8000)
    status = page.locator("[data-seance-status]").inner_text() if page.locator("[data-seance-status]").count() else ""
    check("[reprendre] tuile « Reprendre · étape 1/N »", re.fullmatch(r"Reprendre · étape 1/\d+", status) is not None, f"({status!r})")
    check("[reprendre] séance gardée en sessionStorage", stored(page) is not None)
    page.goto(f"{BASE}/#/stats")
    if ck.appears("[reset] bouton Réinitialiser (Stats)", page, "[data-testid=reset-btn]", timeout=10000, state="attached"):
        page.locator("[data-testid=reset-btn]").scroll_into_view_if_needed()
        page.evaluate("() => sessionStorage.setItem('autre-cle', 'x')")
        page.click("[data-testid=reset-btn]")
        ck.appears("[reset] première confirmation", page, "[data-testid=reset-sheet]")
        page.click("[data-testid=reset-confirm]")
        ck.appears("[reset] deuxième confirmation", page, "[data-testid=reset-final-sheet]")
        page.click("[data-testid=reset-final-confirm]")
        ck.appears("[reset] l'app redémarre sur l'accueil", page, "main :text('Problèmes')", timeout=20000)
        check("[reset] clé de séance effacée", stored(page) is None)
        check("[reset] clé étrangère conservée", page.evaluate("() => sessionStorage.getItem('autre-cle')") == "x")
    ctx.close()


# ================================================================== parcours sans puzzles

def part_variant_endgame(p, browser):
    ctx, page = seeded(p, browser, SEED2, puzzles_ok=False)
    page.goto(f"{BASE}/#/seance")
    if ck.appears("[sans puzzles] accueil de la séance", page, "[data-seance-intro]", timeout=20000):
        check("[sans puzzles] bandeau « Puzzles indisponibles »", page.locator("[role=alert]", has_text="Puzzles indisponibles").count() == 1)
        plan = [(e.get_attribute("data-seance-plan"), e.inner_text()) for e in page.locator("[data-seance-plan]").all()]
        check("[sans puzzles] blocs variante puis finale (finales ratées 0 sur 3)", [k for k, _ in plan] == ["opening", "endgame"], f"({plan})")
        if len(plan) == 2:
            check("[sans puzzles] variante « Ratée à ta dernière tentative »", "Ratée à ta dernière tentative" in plan[0][1], f"({plan[0][1]!r})")
            check("[sans puzzles] finale « 0 réussite sur 3 ces 14 derniers jours »", "0 réussite sur 3 ces 14 derniers jours" in plan[1][1], f"({plan[1][1]!r})")
        click_text_button(page, "Commencer")
    if ck.appears("[variante] drill plein écran, étape 1/2", page, "[data-drill]", timeout=10000):
        h = page.locator("[data-drill] header h1").inner_text()
        check("[variante] en-tête « ☀️ Séance 1/2 »", "☀️ Séance 1/2" in h, f"({h!r})")
        check("[variante] la variante Göring", page.get_attribute("[data-drill]", "data-variant-uci") == GORING)
        shot(page, "seance_step_variant_852")
        line = GORING.split(" ")
        okp = True
        for i in range(0, len(line), 2):
            try:
                page.wait_for_function("(n) => { const u = document.querySelector('[data-drill]')?.getAttribute('data-uci'); return (u ? u.split(' ').length : 0) >= n }", arg=i, timeout=15000)
            except Exception:
                okp = check(f"[variante] réponse adverse avant le demi-coup {i}", False)
                break
            tap_move(page, line[i][0:2], line[i][2:4])
        if okp and ck.appears("[variante] « Variante maîtrisée »", page, "[data-result] >> text=Variante maîtrisée", timeout=10000):
            rows = [(r["itemId"], r["success"]) for r in domain_rows(page, "opening-drill")]
            check("[écritures] tentative `full` réussie écrite comme l'entraîneur", rows == [(f"full:w:{GORING}", 0), (f"full:w:{GORING}", 1)], f"({rows})")
            btn = page.locator("[data-result] button", has_text="Suivant")
            check("[variante] bouton « Suivant »", btn.count() > 0)
            if btn.count():
                btn.first.click()
    if ck.appears("[finale] étape 2/2 : PositionGame", page, "[data-seance-step=endgame] [data-testid=position-game]", timeout=15000):
        check("[finale] pastille « ☀️ 2/2 »", progress(page) == "☀️ 2/2", f"({progress(page)!r})")
        shot(page, "seance_step_endgame_852")
        click_text_button(page, "Abandonner")
        if ck.appears("[finale] confirmation d'abandon", page, "[data-testid=resign-confirm]", timeout=5000):
            page.click("[data-testid=resign-confirm]")
        rows = domain_rows(page, "endgame-play")
        ck.appears("[finale] « Voir le bilan »", page, "button:text-is('Voir le bilan')", timeout=10000)
        rows = domain_rows(page, "endgame-play")
        check("[écritures] ligne `endgame-play` ratée en plus des trois semées", len(rows) == 4 and rows[-1]["success"] == 0, f"({len(rows)})")
        page.get_by_role("button", name="Voir le bilan", exact=True).click()
    if ck.appears("[sans puzzles] bilan", page, "[data-seance-end]", timeout=10000):
        score = page.locator("[data-seance-score]").inner_text()
        check("[sans puzzles] « 1/2 réussi »", score.startswith("1/2 réussi ·"), f"({score!r})")
        ck.appears("[sans puzzles] série « 🔥 1 jour »", page, "[data-seance-streak]:has-text('🔥 1 jour')", timeout=5000)
        rows = domain_rows(page, "seance")
        check("[écritures] ligne `seance` opening+endgame", len(rows) == 1 and rows[0]["itemId"] == "opening+endgame" and rows[0]["score"] == 1, f"({rows})")
    ctx.close()


# ================================================================== mises en page

def part_layouts(p, browser):
    for tag, kw in (("660", {"standalone": False}), ("desktop", {"desktop": True})):
        ctx, page = seeded(p, browser, SEED, **kw)
        page.goto(f"{BASE}/#/")
        if ck.appears(f"[{tag}] tuile sur l'accueil", page, "[data-seance-tile]", timeout=10000):
            ck.appears(f"[{tag}] carte révision aussi présente", page, "main a:has-text(\"À réviser aujourd'hui\")", timeout=10000)
            check(f"[{tag}] accueil sans débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
            sc = page.evaluate("() => { const m = document.querySelector('main'); return m.scrollHeight - m.clientHeight }")
            check(f"[{tag}] accueil sans défilement vertical (Jouer visible en entier)", sc <= 0, f"({sc} px de trop)")
            shot(page, f"seance_home_{tag}")
            page.locator("[data-seance-tile]").click()
        if ck.appears(f"[{tag}] accueil de séance", page, "[data-seance-intro]", timeout=20000):
            check(f"[{tag}] accueil de séance sans débordement horizontal", overflow_x(page) == 0)
            cta = page.locator("button", has_text="Commencer").bounding_box()
            check(f"[{tag}] « Commencer » visible sans défiler", cta is not None and cta["y"] + cta["height"] <= page.viewport_size["height"], f"({cta})")
            shot(page, f"seance_intro_{tag}")
            click_text_button(page, "Commencer")
        if ck.appears(f"[{tag}] première étape", page, "[data-seance-item]", timeout=10000):
            check(f"[{tag}] étape sans débordement horizontal", overflow_x(page) == 0)
            board = page.locator("[id^='chessboard-']").first
            bb = board.bounding_box() if board.count() else None
            check(f"[{tag}] échiquier visible en entier", bb is not None and bb["y"] >= 0 and bb["y"] + bb["height"] <= page.viewport_size["height"], f"({bb})")
            if tag == "desktop":
                click_square(page, "d1")
                click_square(page, "d8")
            else:
                tap_move(page, "d1", "d8")
            ck.appears(f"[{tag}] verdict", page, "text=✓ Réussi", timeout=8000)
            nb = page.get_by_role("button", name="Suivant", exact=True).bounding_box()
            check(f"[{tag}] « Suivant » visible sans défiler", nb is not None and nb["y"] + nb["height"] <= page.viewport_size["height"], f"({nb})")
            shot(page, f"seance_step_{tag}")
        ctx.close()


def suite(p):
    out = node_bench()
    if out:
        bench_checks(out)
    browser = p.chromium.launch(headless=True)
    try:
        part_main(p, browser)
        part_variant_endgame(p, browser)
        part_layouts(p, browser)
    finally:
        browser.close()


ck.run(suite)
