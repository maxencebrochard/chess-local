"""E2E parcours d'apprentissage (#/apprendre/parcours) et cours « Les bases » : contrôles hors ligne
des données et leurs mutations, logique pure sous Node, carte neuve et déblocage séquentiel, leçon
validée par le cours avec retour au parcours (rechargement compris), série de puzzles sous puis au
seuil (étoiles, ligne `path`), reprise d'une série après rechargement, test de placement, étapes
validées par l'existant (leçon `course`, finale `endgame`), séance de finale et retour, série
d'ouverture, réinitialisation, entrée Apprendre et Accueil, mises en page 393x852, 393x660, 1440x900.

Usage : npm run test:e2e -- --suite parcours
"""
import json
import os
import shutil
import subprocess
import tempfile

import chess
from playwright.sync_api import expect

from helpers import BASE, Checker, desktop_context, mobile_context, overflow_x, shot, tap_move

ck = Checker("parcours")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")


def load_json(*parts, default=None):
    p = os.path.join(ROOT, *parts)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


PATH = load_json("src", "data", "learningPath.json", default={"levels": []})
BASICS_RAW = open(os.path.join(ROOT, "src", "data", "basicsCourse.json"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "src", "data", "basicsCourse.json")) else "{}"
BASICS = json.loads(BASICS_RAW) if BASICS_RAW.strip() else {"chapters": [], "lessons": {}}
OPENINGS = load_json("src", "data", "openings.json", default=[])
STEPS = [s for lv in PATH["levels"] for s in lv["steps"]]
TOTAL = len(STEPS)
STEP = {s["id"]: s for s in STEPS}
FIRST_OF = {lv["id"]: lv["steps"][0]["id"] for lv in PATH["levels"]}

# ---------- puzzles.json réduit : un mat en un connu, sous des ids et des Elo propres à chaque série ----------
# Amorce ...Cc3 (coup adverse), puis Ta8 mat. Un coup faux : h3 (aucun autre mat n'est accepté).
MATE_FEN = "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1"
GOOD = ("a1", "a8")
BAD = ("h2", "h3")
PUZZLES = []
for s in STEPS:
    ex = s.get("exercise") or {}
    if ex.get("kind") == "puzzles":
        lo, hi = ex["rating"]
        for i in range(ex["count"] + 3):
            PUZZLES.append([f"{s['id']}-{i}", MATE_FEN, "e4c3 a1a8", lo + (hi - lo) * i // (ex["count"] + 3), " ".join(ex["themes"] + ["short"])])
for lv in PATH["levels"]:
    lo, hi = lv["placement"]["rating"]
    for i in range(6):
        PUZZLES.append([f"place-{lv['id']}-{i}", MATE_FEN, "e4c3 a1a8", lo + (hi - lo) * i // 6, "middlegame short"])

TABLES = ["games", "learnSessions", "mistakes", "puzzleAttempts", "ratings", "reviews", "rushScores"]
OPEN_DB = """() => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => res(r.result)
  r.onerror = () => rej(r.error)
})"""


def wait_schema(page, tries=40):
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


def seed_sessions(page, rows):
    page.evaluate(
        "async (rows) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const tx = db.transaction('learnSessions', 'readwrite')
          for (const r of rows) tx.objectStore('learnSessions').add(r)
          await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error) })
          db.close()
        }""",
        rows,
    )


def sessions(page, domain):
    rows = page.evaluate(
        "async () => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const rows = await new Promise((res, rej) => { const q = db.transaction('learnSessions').objectStore('learnSessions').getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
          db.close()
          return rows
        }"""
    )
    return sorted([r for r in rows if r["domain"] == domain], key=lambda r: r["date"])


def row(domain, item, ok=True, score=None):
    r = {"date": 1_700_000_000_000, "domain": domain, "itemId": item, "success": 1 if ok else 0, "ratingAfter": None}
    if score is not None:
        r["score"] = score
    return r


def context(p, browser, desktop=False, standalone=True):
    if desktop:
        ctx = desktop_context(browser, ck, service_workers="block")
    else:
        ctx = mobile_context(p, browser, ck, standalone=standalone, service_workers="block")
    body = json.dumps(PUZZLES)
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[contexte] Apprendre chargé", page, "[data-testid=path-hero]", timeout=20000)
    check("[contexte] schéma de la base créé par l'app", wait_schema(page))
    expect(page.locator("[data-testid=path-hero-progress]")).to_be_visible()
    return ctx, page


def go(page, hash_path):
    page.goto(f"{BASE}/#{hash_path}")
    page.wait_for_timeout(300)


def status(page, step_id):
    loc = page.locator(f"[data-step='{step_id}']")
    return loc.get_attribute("data-status") if loc.count() else None


def map_ready(page, label):
    return ck.appears(f"{label} carte du parcours affichée", page, "[data-testid=path-progress]", timeout=15000)


def progress(page):
    return page.locator("[data-testid=path-progress]").inner_text().strip()


# ---------- Contrôles hors ligne ----------
def run_node(args):
    res = subprocess.run(["node", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)
    return res.returncode, res.stdout + res.stderr


def part_data():
    code, out = run_node(["scripts/check-learning-path.mjs"])
    check("[données] check-learning-path.mjs passe", code == 0 and "[KO]" not in out, f"(code {code}) {out[-400:]}")
    check("[données] 4 niveaux, Elo croissants", [lv["elo"] for lv in PATH["levels"]] == sorted({lv["elo"] for lv in PATH["levels"]}) and len(PATH["levels"]) == 4)

    def m_lesson(d):
        d["levels"][0]["steps"][0]["lesson"] = "bases:inconnue"

    def m_rename(d):
        d["levels"][0]["steps"][0]["id"] = "valeur-des-pieces-bis"

    def m_theme(d):
        d["levels"][0]["steps"][1]["exercise"]["themes"] = ["pasUnTheme"]

    def m_band(d):
        d["levels"][0]["steps"][1]["exercise"]["rating"] = [1900, 2100]

    def m_pass(d):
        d["levels"][0]["steps"][1]["exercise"]["pass"] = 7

    def m_dash(d):
        d["levels"][0]["steps"][0]["title"] += " — vite"

    def m_read(d):
        d["levels"][0]["steps"][0]["read"] = "inconnu"

    def m_no_lesson(d):
        del d["levels"][0]["steps"][0]["lesson"]

    def m_no_read(d):
        del d["levels"][0]["steps"][1]["read"]

    def m_no_exercise(d):
        del d["levels"][0]["steps"][0]["exercise"]

    def m_order(d):
        d["levels"][0], d["levels"][1] = d["levels"][1], d["levels"][0]

    def m_course_order(d):
        a = next(s for s in d["levels"][0]["steps"] if s["id"] == "mat-deux-tours")
        b = next(s for s in d["levels"][0]["steps"] if s["id"] == "mat-tour")
        a["lesson"], b["lesson"] = b["lesson"], a["lesson"]

    def m_family(d):
        e = next(s for s in d["levels"][0]["steps"] if s["id"] == "partie-italienne")
        e["exercise"]["family"] = "Pas Une Ouverture"

    def m_endgame(d):
        e = next(s for s in d["levels"][0]["steps"] if s["id"] == "mat-dame")
        e["exercise"]["id"] = "inconnue"

    def m_placement(d):
        d["levels"][0]["steps"][0]["id"] = "placement"

    muts = [
        (m_lesson, "leçon inconnue"), (m_rename, "supprimée ou renommée"), (m_theme, "thème inconnu"), (m_band, "loin de l'Elo"),
        (m_pass, "seuil"), (m_dash, "tiret"), (m_read, "cours détaillé inconnu"), (m_order, "ordre figé"),
        (m_course_order, "avant une leçon qui la suit"), (m_family, "famille d'ouverture inconnue"), (m_endgame, "finale inconnue"),
        (m_placement, "réservé"), (m_no_lesson, "leçon absente"), (m_no_read, "leçon absente"), (m_no_exercise, "exercice absent"),
    ]
    with tempfile.TemporaryDirectory() as d:
        for fn, expect in muts:
            data = json.loads(json.dumps(PATH))
            fn(data)
            path = os.path.join(d, f"{fn.__name__}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            code, out = run_node(["scripts/check-learning-path.mjs", path])
            check(f"[mutation parcours] {fn.__name__} refusée ({expect})", code == 1 and expect in out, f"(code {code}) {out[-300:]}")

    # Cours « Les bases » : contrôle, tampon, et un texte modifié sans revérification refusé.
    code, out = run_node(["scripts/check-basics-course.mjs"])
    check("[bases] check-basics-course.mjs passe (tampon à jour)", code == 0 and "[KO]" not in out, f"(code {code}) {out[-400:]}")
    with tempfile.TemporaryDirectory() as d:
        data = json.loads(BASICS_RAW)
        first = next(iter(data["lessons"].values()))
        first["summary"] = first["summary"].rstrip(".") + " ici."
        path = os.path.join(d, "bases.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False))
        code, out = run_node(["scripts/check-basics-course.mjs", path, "scripts/basics-course.verified"])
        check("[bases] JSON modifié sans revérification refusé", code == 1 and "a changé depuis sa vérification" in out, f"(code {code}) {out[-300:]}")
        # Le contrôle d'origine (cours du roque) garde ses messages après l'extraction des règles.
        code, out = run_node(["scripts/check-attack-course.mjs", path, "scripts/attack-course.verified"])
        check("[bases] le contrôle du roque refuse aussi un JSON non tamponné", code == 1 and "verify-attack-course.py" in out, f"(code {code})")


LOGIC_JS = r"""
import * as m from './entry.mjs'
const out = []
const ok = (name, cond, detail = '') => out.push([name, Boolean(cond), detail])
const facts = (o = {}) => ({ lessons: new Set(o.lessons ?? []), endgames: new Set(o.endgames ?? []), passed: new Set(o.passed ?? []), best: new Map(Object.entries(o.best ?? {})), placement: o.placement ?? 0 })
const ids = m.STEPS.map((s) => s.id)
let st = m.computePath(facts())
ok('neuf : première étape courante', st.current?.step.id === ids[0])
ok('neuf : deuxième verrouillée', !st.steps[1].unlocked)
ok('neuf : 0 fait', st.done === 0 && st.total === ids.length)
st = m.computePath(facts({ lessons: ['bases:valeur-des-pieces'] }))
ok('leçon faite : crédit conservé, exercice requis', st.steps[0].lessonDone && !st.steps[0].done && st.current?.index === 0 && !st.steps[1].unlocked)
st = m.computePath(facts({ lessons: ['bases:valeur-des-pieces'], passed: [ids[0]] }))
ok('leçon et exercice : étape 1 validée, étape 2 courante', st.steps[0].done && st.current?.index === 1 && st.steps[1].unlocked)
ok('leçon faite : étape 3 encore verrouillée', !st.steps[2].unlocked)
st = m.computePath(facts({ lessons: ['finales:mat-deux-tours'], endgames: ['rr-mate'] }))
const i2t = ids.indexOf('mat-deux-tours')
ok('îlot : étape validée hors ordre, la suivante se débloque', st.steps[i2t].done && st.steps[i2t + 1].unlocked)
ok("îlot : l'étape courante reste la première", st.current?.index === 0)
st = m.computePath(facts({ lessons: ['finales:mat-dame'] }))
ok('leçon + exercice : leçon seule ne valide pas', !st.steps[ids.indexOf('mat-dame')].done)
st = m.computePath(facts({ lessons: ['finales:mat-dame'], endgames: ['kq-mate'] }))
ok('leçon + finale réussie (domaine endgame) : validée', st.steps[ids.indexOf('mat-dame')].done)
st = m.computePath(facts({ lessons: ['finales:mat-dame'], passed: ['mat-dame'] }))
ok('leçon + finale réussie depuis le parcours (domaine path) : validée', st.steps[ids.indexOf('mat-dame')].done)
st = m.computePath(facts({ best: { 'pieces-en-prise': 2 } }))
ok('série sous le seuil : 0 étoile, non validée', st.steps[1].stars === 0 && !st.steps[1].done)
st = m.computePath(facts({ passed: ['pieces-en-prise'], best: { 'pieces-en-prise': 4 } }))
ok('série à 4/5 (seuil 3) : 2 étoiles', st.steps[1].stars === 2 && st.steps[1].done)
const first2 = m.LEVELS[1].steps[0].id
st = m.computePath(facts({ placement: 1 }))
ok('placement 1 : niveau 1 acquis, courante = première du niveau 2', st.levels[0].acquired && st.levels[0].complete && st.current?.step.id === first2)
ok('placement 1 : étapes du niveau 1 jouables', st.steps.filter((s) => s.level === 0).every((s) => s.unlocked && s.acquired))
ok('placement 1 : deuxième étape du niveau 2 verrouillée', !st.steps[ids.indexOf(first2) + 1].unlocked)
st = m.computePath(facts({ placement: 4 }))
ok('placement 4 : parcours terminé, aucune courante', st.current === null && st.levels.every((l) => l.complete))
st = m.computePath(facts({ placement: 99 }))
ok('placement hors bornes : plafonné', st.placement === m.LEVELS.length)
ok('étoiles 5/5 = 3, 3/5 = 1, 2/5 = 0, 9/5 plafonné à 3', m.starsFor(5, 5, 3) === 3 && m.starsFor(3, 5, 3) === 1 && m.starsFor(2, 5, 3) === 0 && m.starsFor(9, 5, 3) === 3)
ok('étoiles 2/3 = 1, 3/3 = 3', m.starsFor(2, 3, 2) === 1 && m.starsFor(3, 3, 2) === 3)
const T = true, F = false
ok('placement [T,T,F] : 1 niveau, pas fini', m.placementLevels([T, T, F]) === 1 && !m.placementOver([T, T, F]))
ok('placement [T,F,F] : arrêt, 0 niveau', m.placementOver([T, F, F]) && m.placementLevels([T, F, F]) === 0)
ok('placement [F,F] : arrêt dès le 2e raté', m.placementOver([F, F]))
ok('placement [T,T,T,F,F] : arrêt, 1 niveau', m.placementOver([T, T, T, F, F]) && m.placementLevels([T, T, T, F, F]) === 1)
ok('placement 12 réussis : 4 niveaux, fini', m.placementOver(Array(12).fill(T)) && m.placementLevels(Array(12).fill(T)) === 4)
for (const step of m.STEPS) {
  const lesson = step.lesson ? [step.lesson] : []
  const onlyLesson = m.computePath(facts({ lessons: lesson })).steps.find((s) => s.step.id === step.id)
  ok(`${step.id} : leçon seule insuffisante`, !onlyLesson.done)
  const completed = m.computePath(facts({ lessons: lesson, passed: [step.id] })).steps.find((s) => s.step.id === step.id)
  ok(`${step.id} : leçon et exercice suffisants`, completed.done)
}
console.log(JSON.stringify(out))
"""


def part_logic():
    with tempfile.TemporaryDirectory() as d:
        bundle = os.path.join(d, "entry.mjs")
        r = subprocess.run([ROLLDOWN, "scripts/learning-path-entry.ts", "--format", "esm", "--platform", "node", "--file", bundle], cwd=ROOT, capture_output=True, text=True, timeout=120)
        if not check("[logique] bundle rolldown de learningPath.ts", r.returncode == 0, (r.stderr or r.stdout)[-300:]):
            return
        script = os.path.join(d, "logic.mjs")
        with open(script, "w", encoding="utf-8") as f:
            f.write(LOGIC_JS)
        r = subprocess.run(["node", script], cwd=d, capture_output=True, text=True, timeout=60)
        if not check("[logique] script Node exécuté", r.returncode == 0, r.stderr[-300:]):
            return
        for name, ok, detail in json.loads(r.stdout.strip().splitlines()[-1]):
            check(f"[logique] {name}", ok, detail)


# ---------- Leçons ----------
def continue_btn(page):
    return page.get_by_role("button", name="Continuer", exact=True)


def play_lesson(page, label, max_clicks=60):
    """Joue la leçon ouverte jusqu'au bilan : Continuer sur les diagrammes, Solution sur les lignes."""
    for _ in range(max_clicks):
        if page.get_by_role("button", name="Retour au parcours").count() or page.get_by_role("button", name="Sommaire").count():
            return True
        page.wait_for_timeout(150)
        if continue_btn(page).count() and continue_btn(page).is_enabled():
            step = page.locator("[data-testid=lesson-step]")
            previous = step.inner_text()
            continue_btn(page).click()
            expect(step).not_to_have_text(previous)
            continue
        sol = page.get_by_role("button", name="💡 Solution")
        if sol.count() and sol.is_enabled():
            sol.click()
            page.wait_for_timeout(200)
        else:
            page.wait_for_timeout(300)
    return check(f"{label} leçon jouée jusqu'au bilan", False)


def part_all_basics(page):
    for lid in [x for ch in BASICS["chapters"] for x in ch["lessons"]]:
        go(page, f"/apprendre/bases/{lid}")
        if ck.appears(f"[bases] leçon {lid} ouverte", page, "[data-testid=lesson-step]", timeout=10000):
            ok = play_lesson(page, f"[bases {lid}]")
            check(f"[bases] leçon {lid} jouable jusqu'au bilan", ok and page.locator("text=Leçon terminée").count() > 0)
    go(page, "/apprendre/bases")
    n = sum(len(ch["lessons"]) for ch in BASICS["chapters"])
    ck.appears("[bases] sommaire du cours", page, "[data-testid=course-progress]")
    check("[bases] sommaire : toutes les leçons terminées", page.locator("[data-testid=course-progress]").inner_text().strip() == f"{n}/{n}")


# ---------- Puzzles du lecteur ----------
def solve_current(page, good=True, label=""):
    """Joue le puzzle affiché (mat en un connu) : bon coup ou coup faux. Retourne le verdict lu."""
    if not ck.appears(f"{label} puzzle affiché", page, "[data-run] [data-square='a1'] [data-piece='wR']", timeout=10000):
        return None
    # Amorce ...Cc3 jouée par l'app.
    try:
        page.wait_for_selector("[data-run] [data-square='c3'] [data-piece='bN']", timeout=6000)
    except Exception:
        check(f"{label} amorce jouée", False)
        return None
    tap_move(page, *(GOOD if good else BAD))
    try:
        page.wait_for_selector("text=✓ Réussi" if good else "text=✗ Raté", timeout=8000)
        return good
    except Exception:
        check(f"{label} verdict {'réussi' if good else 'raté'}", False)
        return None


def next_item(page):
    btn = page.locator("[data-run] button", has_text="Suivant")
    if btn.count():
        btn.first.click()
    else:
        page.locator("[data-run] button", has_text="Voir le résultat").first.click()
    page.wait_for_timeout(300)


def run_idx(page):
    v = page.get_attribute("[data-run]", "data-run-idx")
    return int(v) if v is not None else -1


def part_fresh_and_lesson(p, browser):
    ctx, page = context(p, browser)
    hero = page.locator("[data-testid=path-hero]")
    check("[apprendre] carte héro « Commencer » en tête d'Apprendre", "Commencer" in hero.inner_text() and f"0/{TOTAL}" in hero.inner_text(), f"({hero.inner_text()!r})")
    check("[apprendre] parcours avant les autres cartes", hero.evaluate("el => el.parentElement.querySelector('button, a') === el"))
    box = hero.bounding_box()
    check("[apprendre] carte héro visible sans défiler (393x852)", box is not None and box["y"] + box["height"] <= 852)
    shot(page, "parcours_apprendre_852")
    hero.click()
    map_ready(page, "[neuf]")
    check("[neuf] URL #/apprendre/parcours", page.evaluate("() => location.hash") == "#/apprendre/parcours")
    check("[neuf] progression 0/N", progress(page) == f"0/{TOTAL}", progress(page))
    check("[neuf] première étape courante", status(page, STEPS[0]["id"]) == "current")
    check("[neuf] deuxième étape verrouillée", status(page, STEPS[1]["id"]) == "locked")
    check("[neuf] dernière étape verrouillée", status(page, STEPS[-1]["id"]) == "locked")
    check("[neuf] carte du test de placement proposée", page.locator("[data-testid=placement-card]").count() == 1)
    check("[neuf] « Commencer » sur la carte de reprise", "Commencer" in page.locator("[data-testid=path-continue]").inner_text())
    check("[neuf] pas de débordement horizontal", overflow_x(page) <= 0, f"({overflow_x(page)})")
    shot(page, "parcours_carte_852")

    # URL directe d'une étape verrouillée : message et lien vers l'étape courante.
    go(page, f"/apprendre/parcours/{STEPS[2]['id']}")
    if ck.appears("[verrou] étape verrouillée annoncée", page, "[data-testid=step-locked]", timeout=8000):
        shot(page, "parcours_verrou_852")
        page.get_by_role("button", name="Aller à l'étape en cours").click()
        page.wait_for_timeout(400)
        check("[verrou] le bouton mène à l'étape courante", page.evaluate("() => location.hash") == f"#/apprendre/parcours/{STEPS[0]['id']}")

    # Étape 1 : leçon du cours « Les bases », ouverte depuis l'étape, rechargée en cours de route.
    first = STEPS[0]
    go(page, f"/apprendre/parcours/{first['id']}")
    if ck.appears("[étape 1] page d'étape", page, "[data-testid=part-lesson]", timeout=8000):
        check("[étape 1] leçon à faire", page.get_attribute("[data-testid=part-lesson]", "data-done") == "0")
        shot(page, "parcours_etape_lecon_852")
        page.get_by_role("button", name="Ouvrir la leçon").click()
        ck.appears("[étape 1] leçon ouverte", page, "[data-testid=lesson-step]", timeout=8000)
        lesson = first["lesson"].split(":")[1]
        check("[étape 1] URL de la leçon porte ?parcours=", f"/apprendre/bases/{lesson}?parcours={first['id']}" in page.evaluate("() => location.hash"), page.evaluate("() => location.hash"))
        continue_btn(page).click()
        page.wait_for_timeout(300)
        check("[étape 1] l'étape suivante de la leçon garde ?parcours=", "parcours=" in page.evaluate("() => location.hash") and "etape=2" in page.evaluate("() => location.hash"))
        page.reload()
        ck.appears("[étape 1] leçon rechargée", page, "[data-testid=lesson-step]", timeout=10000)
        page.get_by_role("button", name="Fermer la leçon").click()
        page.wait_for_timeout(400)
        check("[étape 1] ✕ après rechargement ramène à l'étape", page.evaluate("() => location.hash") == f"#/apprendre/parcours/{first['id']}")
        page.get_by_role("button", name="Ouvrir la leçon").click()
        ck.appears("[étape 1] leçon rouverte", page, "[data-testid=lesson-step]", timeout=8000)
        if play_lesson(page, "[étape 1]"):
            shot(page, "parcours_lecon_bilan_852")
            check("[étape 1] bilan : ni « Leçon suivante » ni « Sommaire »", page.get_by_role("button", name="Leçon suivante").count() == 0 and page.get_by_role("button", name="Sommaire").count() == 0)
            page.get_by_role("button", name="Retour au parcours").click()
            ck.appears("[étape 1] exercice disponible au retour", page, "[data-testid=part-exercise]", timeout=8000)
            check("[étape 1] Solution seule ne valide pas", page.locator("[data-testid=step-validated]").count() == 0)
            check("[étape 1] retour sur la page d'étape", page.evaluate("() => location.hash") == f"#/apprendre/parcours/{first['id']}")
            check("[étape 1] ligne `course` écrite", any(r["itemId"] == first["lesson"] for r in sessions(page, "course")))
            check("[étape 1] aucune ligne `path` pour une leçon seule", len(sessions(page, "path")) == 0)
            page.locator("[data-testid=part-exercise] button", has_text="Commencer").click()
            for i in range(first["exercise"]["count"]):
                check(f"[étape 1] validation {i + 1}", solve_current(page, True, "[étape 1]") is True)
                next_item(page)
            ck.appears("[étape 1] série validée", page, "[data-run-end=passed]", timeout=8000)
            shot(page, "parcours_etape_validee_852")
            page.get_by_role("button", name="Étape suivante").click()
            page.wait_for_timeout(400)
            check("[étape 1] « Étape suivante » ouvre l'étape 2", page.evaluate("() => location.hash") == f"#/apprendre/parcours/{STEPS[1]['id']}")

    go(page, "/apprendre/parcours")
    map_ready(page, "[après étape 1]")
    check("[après étape 1] progression 1/N", progress(page) == f"1/{TOTAL}", progress(page))
    check("[après étape 1] étape 1 validée", status(page, STEPS[0]["id"]) == "done")
    check("[après étape 1] étape 2 courante (débloquée)", status(page, STEPS[1]["id"]) == "current")
    check("[après étape 1] étape 3 verrouillée", status(page, STEPS[2]["id"]) == "locked")

    part_puzzle_step(page)
    part_reset(page)
    ctx.close()



def block_path_writes(page):
    page.evaluate("""() => {
      if (!window.originalAdd) window.originalAdd = IDBObjectStore.prototype.add
      IDBObjectStore.prototype.add = function(value, ...args) {
        if (value.domain === 'path') throw new DOMException('Disque plein', 'QuotaExceededError')
        return window.originalAdd.call(this, value, ...args)
      }
    }""")


def retry_save(page, label, key, end_selector, reload=False):
    if not ck.appears(f"{label} erreur récupérable", page, "[role=alert]", timeout=8000):
        return
    check(f"{label} aucun résultat annoncé avant sauvegarde", page.locator(end_selector).count() == 0)
    saved = page.evaluate("key => JSON.parse(sessionStorage.getItem(key))", key)
    check(f"{label} résultat conservé", saved is not None)
    before = sessions(page, "path")
    page.get_by_role("button", name="Réessayer l’enregistrement").click()
    ck.appears(f"{label} nouvel échec encore récupérable", page, "[role=alert]", timeout=8000)
    check(f"{label} aucune écriture partielle", sessions(page, "path") == before)
    if reload:
        page.reload()
        ck.appears(f"{label} résultat repris après rechargement", page, "button:has-text('Enregistrer le résultat')", timeout=10000)
        page.get_by_role("button", name="Enregistrer le résultat", exact=True).click()
    else:
        page.evaluate("() => { IDBObjectStore.prototype.add = window.originalAdd }")
        page.get_by_role("button", name="Réessayer l’enregistrement").click()
    ck.appears(f"{label} résultat enregistré", page, end_selector, timeout=10000)
    check(f"{label} une seule écriture après réessai", len(sessions(page, "path")) == len(before) + 1)


def part_puzzle_step(page):
    step = STEPS[1]
    ex = step["exercise"]
    go(page, f"/apprendre/parcours/{step['id']}")
    if not ck.appears("[série] page d'étape avec le cours détaillé", page, "[data-testid=part-read]", timeout=8000):
        return
    shot(page, "parcours_etape_puzzles_852")
    page.locator("[data-testid=part-exercise] button", has_text="Commencer").click()
    ck.appears("[série] lecteur ouvert", page, "[data-run]", timeout=10000)
    shot(page, "parcours_serie_852")
    # Première série : 2/5 (seuil 3) => non validée. Rechargement au 3e puzzle : reprise identique.
    plan = [False, True, False, False, True]
    for i, good in enumerate(plan):
        if i == 2:
            pid = page.get_attribute("[data-run]", "data-puzzle-id")
            page.reload()
            ck.appears("[reprise] série restaurée après rechargement", page, "[data-run]", timeout=10000)
            check("[reprise] même puzzle après rechargement", page.get_attribute("[data-run]", "data-puzzle-id") == pid and run_idx(page) == 2, f"({page.get_attribute('[data-run]', 'data-puzzle-id')} vs {pid})")
            dots = page.locator("[data-testid=run-dots] span")
            check("[reprise] verdicts déjà rendus conservés (pastilles)", dots.count() == ex["count"] and "bg-red-400" in (dots.nth(0).get_attribute("class") or "") and "bg-accent" in (dots.nth(1).get_attribute("class") or ""))
        verdict = solve_current(page, good, f"[série 1, puzzle {i + 1}]")
        check(f"[série 1] puzzle {i + 1} : verdict {'réussi' if good else 'raté'}", verdict == good)
        if i == 0:
            banner = page.locator("[data-run] p", has_text="Puzzle").first.inner_text()
            check("[série 1] thèmes affichés après le verdict", "Pièce en prise" in banner, f"({banner!r})")
        next_item(page)
    if ck.appears("[série 1] écran de fin « non validée »", page, "[data-run-end='failed']", timeout=8000):
        shot(page, "parcours_serie_ratee_852")
        txt = page.locator("[data-run-end]").inner_text()
        check("[série 1] score 2/5 et seuil annoncé", "2/5" in txt and f"Il en faut {ex['pass']} sur {ex['count']}" in txt, f"({txt[:200]!r})")
        rows = [r for r in sessions(page, "path") if r["itemId"] == step["id"]]
        check("[série 1] ligne `path` : échec, score 2", len(rows) == 1 and rows[0]["itemId"] == step["id"] and rows[0]["success"] == 0 and rows[0]["score"] == 2, f"({rows})")
        check("[série 1] série effacée de sessionStorage", page.evaluate("() => sessionStorage.getItem('path-session-v1')") is None)
        page.get_by_role("button", name="Recommencer").click()
    # Seconde série : 4/5 => validée, 2 étoiles.
    ck.appears("[série 2] nouvelle série", page, "[data-run]", timeout=10000)
    check("[série 2] repart du premier puzzle", run_idx(page) == 0)
    for i, good in enumerate([True, True, False, True, True]):
        check(f"[série 2] puzzle {i + 1}", solve_current(page, good, f"[série 2, puzzle {i + 1}]") == good)
        if i == ex["count"] - 1:
            block_path_writes(page)
        next_item(page)
    retry_save(page, "[série 2]", "path-session-v1", "[data-run-end]", reload=True)
    if ck.appears("[série 2] écran de fin « validée »", page, "[data-run-end='passed']", timeout=8000):
        shot(page, "parcours_serie_validee_852")
        check("[série 2] 2 étoiles", page.locator("[data-run-end] [data-stars='2']").count() == 1)
        rows = [r for r in sessions(page, "path") if r["itemId"] == step["id"]]
        check("[série 2] seconde ligne `path` : réussite, score 4", len(rows) == 2 and rows[1]["success"] == 1 and rows[1]["score"] == 4, f"({rows})")
        page.get_by_role("button", name="Étape suivante").click()
        page.wait_for_timeout(400)
        check("[série 2] « Étape suivante » ouvre l'étape 3", page.evaluate("() => location.hash") == f"#/apprendre/parcours/{STEPS[2]['id']}")
    go(page, f"/apprendre/parcours/{step['id']}")
    if ck.appears("[série 2] étape validée", page, "[data-testid=step-validated]", timeout=8000):
        best = page.locator("[data-testid=step-best]").inner_text()
        check("[série 2] meilleur score 4/5 affiché", "4/5" in best, f"({best!r})")
    # Reprise de la carte après rechargement : même état, étape courante visible.
    go(page, "/apprendre/parcours")
    page.reload()
    map_ready(page, "[reprise carte]")
    check("[reprise carte] progression 2/N après rechargement", progress(page) == f"2/{TOTAL}", progress(page))
    check("[reprise carte] étape 2 : 2 étoiles", page.locator(f"[data-step='{step['id']}'] [data-stars='2']").count() == 1)
    check("[reprise carte] étape 3 courante", status(page, STEPS[2]["id"]) == "current")
    cur = page.locator("[data-current-step] button").first.bounding_box()
    vp = page.viewport_size
    check("[reprise carte] étape courante dans l'écran à l'ouverture", cur is not None and 0 <= cur["y"] and cur["y"] + cur["height"] <= vp["height"])
    check("[reprise carte] carte du test de placement remplacée par le lien", page.locator("[data-testid=placement-card]").count() == 0 and page.get_by_role("button", name="Refaire le test de placement").count() == 1)
    go(page, "/apprendre")
    # La carte s'affiche avant la progression (« … ») : attendre le compteur, lu après coup dans Dexie.
    ck.appears("[apprendre] carte héro relue", page, "[data-testid=path-hero-progress]")
    hero = page.locator("[data-testid=path-hero]").inner_text()
    check("[apprendre] carte héro : Continuer, étape courante, 2/N", "Continuer" in hero and STEPS[2]["title"] in hero and f"2/{TOTAL}" in hero, f"({hero!r})")


def part_reset(page):
    """La réinitialisation efface la série en cours du parcours (sessionStorage)."""
    step = STEPS[1]
    go(page, f"/apprendre/parcours/{step['id']}")
    ck.appears("[reset] page d'étape", page, "[data-testid=part-exercise]", timeout=8000)
    page.locator("[data-testid=part-exercise] button", has_text="Recommencer").click()
    ck.appears("[reset] série ouverte", page, "[data-run]", timeout=10000)
    check("[reset] série en cours dans sessionStorage", page.evaluate("() => sessionStorage.getItem('path-session-v1')") is not None)
    go(page, "/donnees")
    ck.appears("[reset] Mes données", page, "[data-testid=reset-btn]", timeout=10000)
    page.click("[data-testid=reset-btn]")
    ck.appears("[reset] première confirmation", page, "[data-testid=reset-sheet]")
    page.click("[data-testid=reset-confirm]")
    ck.appears("[reset] deuxième confirmation", page, "[data-testid=reset-final-sheet]")
    page.click("[data-testid=reset-final-confirm]")
    ck.appears("[reset] l'app redémarre", page, "main :text('Problèmes')", timeout=20000)
    check("[reset] série du parcours effacée", page.evaluate("() => sessionStorage.getItem('path-session-v1')") is None)
    go(page, "/apprendre/parcours")
    map_ready(page, "[reset]")
    check("[reset] parcours remis à zéro", progress(page) == f"0/{TOTAL}")


def part_placement_and_existing(p, browser):
    ctx, page = context(p, browser)
    go(page, "/apprendre/parcours")
    map_ready(page, "[placement]")
    page.locator("[data-testid=placement-card]").click()
    ck.appears("[placement] page du test", page, "[data-step-page='placement']", timeout=8000)
    shot(page, "parcours_placement_852")
    page.get_by_role("button", name="Commencer le test").click()
    ck.appears("[placement] lecteur ouvert", page, "[data-run='placement']", timeout=10000)
    check("[placement] niveau annoncé", page.locator("[data-run] p", has_text="Niveau Débutant").count() == 1)
    # Débutant : 2/3 (validé) ; Intermédiaire : 2 ratés de suite => arrêt, 1 niveau acquis.
    for i, good in enumerate([True, False, True, False, False]):
        check(f"[placement] puzzle {i + 1}", solve_current(page, good, f"[placement {i + 1}]") == good)
        if i == 3:
            check("[placement] 4e puzzle : niveau Intermédiaire", page.locator("[data-run] p", has_text="Niveau Intermédiaire").count() == 1)
        if i == 4:
            block_path_writes(page)
        next_item(page)
    retry_save(page, "[placement]", "path-session-v1", "[data-placement-end]")
    if ck.appears("[placement] fin du test après le 2e raté du niveau 2", page, "[data-placement-end='1']", timeout=8000):
        shot(page, "parcours_placement_fin_852")
        check("[placement] niveau de départ Intermédiaire", "Niveau de départ : Intermédiaire" in page.locator("[data-placement-end]").inner_text())
        rows = sessions(page, "path")
        check("[placement] ligne `path` placement, score 1", len(rows) == 1 and rows[0]["itemId"] == "placement" and rows[0]["score"] == 1, f"({rows})")
        page.get_by_role("button", name="Voir le parcours").click()
    map_ready(page, "[placement]")
    lv0 = PATH["levels"][0]
    check("[placement] Débutant marqué « acquis au test »", page.locator(f"[data-level='{lv0['id']}'] [data-testid=level-acquired]").count() == 1)
    check("[placement] étapes du Débutant acquises", all(status(page, s["id"]) == "acquired" for s in lv0["steps"]))
    check("[placement] 🎓 du Débutant allumé", page.locator(f"[data-level='{lv0['id']}'] [data-level-end='complete']").count() == 1)
    first2 = FIRST_OF[PATH["levels"][1]["id"]]
    check("[placement] étape courante = première de l'Intermédiaire", status(page, first2) == "current")
    check("[placement] deuxième de l'Intermédiaire verrouillée", status(page, PATH["levels"][1]["steps"][1]["id"]) == "locked")
    shot(page, "parcours_carte_placement_852")

    # Un second test moins bon ne fait rien perdre.
    seed_sessions(page, [row("path", "placement", ok=False, score=0)])
    # Étapes validées par l'existant : leçons du cours de finales et finale réussie dans Apprendre.
    seed_sessions(page, [row("course", "finales:mat-deux-tours"), row("endgame", "rr-mate"), row("course", "finales:mat-dame"), row("endgame", "kq-mate"), row("course", "finales:mat-tour")])
    page.reload()
    map_ready(page, "[existant]")
    check("[existant] placement conservé malgré un test à 0", status(page, first2) == "current")
    check("[existant] mat des deux tours validé par le cours", status(page, "mat-deux-tours") == "done")
    check("[existant] mat dame validé (leçon + finale d'Apprendre)", status(page, "mat-dame") == "done")
    check("[existant] mat roi et tour : leçon seule, étape non validée (acquise au test)", status(page, "mat-tour") == "acquired")
    check("[existant] progression 2/N", progress(page) == f"2/{TOTAL}", progress(page))
    go(page, f"/apprendre/parcours/{PATH['levels'][1]['steps'][2]['id']}")
    ck.appears("[existant] étape plus loin toujours verrouillée", page, "[data-testid=step-locked]", timeout=8000)
    go(page, "/apprendre/parcours/mat-tour")
    ck.appears("[existant] page du mat roi et tour", page, "[data-testid=part-exercise]", timeout=8000)
    check("[existant] mat roi et tour : leçon faite, exercice à faire", page.get_attribute("[data-testid=part-lesson]", "data-done") == "1" and page.get_attribute("[data-testid=part-exercise]", "data-done") == "0")

    # Finale : la séance existante d'Apprendre, retour à l'étape par ✕.
    page.locator("[data-testid=part-exercise] button", has_text="Commencer").click()
    if ck.appears("[finale] séance de finale d'Apprendre", page, "button:has-text(\"C'est parti\")", timeout=10000):
        check("[finale] URL #/apprendre", page.evaluate("() => location.hash") == "#/apprendre")
        stored = page.evaluate("() => JSON.parse(sessionStorage.getItem('learn-session-v1') || 'null')")
        check("[finale] séance liée à l'étape (pathStep)", stored is not None and stored.get("pathStep") == "mat-tour")
        page.locator("header button", has_text="✕").first.click()
        page.wait_for_timeout(500)
        check("[finale] ✕ ramène à l'étape", page.evaluate("() => location.hash") == "#/apprendre/parcours/mat-tour")

    part_opening(page)
    ctx.close()


def drill_uci(page):
    v = page.get_attribute("[data-drill]", "data-uci")
    return v.split(" ") if v else []


def wait_plies(page, n, timeout=15000):
    try:
        page.wait_for_function(
            """(n) => { const d = document.querySelector('[data-drill]');
                        const u = d && d.getAttribute('data-uci'); return (u ? u.split(' ').length : 0) >= n }""",
            arg=n, timeout=timeout,
        )
        return True
    except Exception:
        return False


def part_opening(page):
    step = STEP["partie-italienne"]
    ex = step["exercise"]
    go(page, f"/apprendre/parcours/{step['id']}")
    if not ck.appears("[ouverture] page d'étape", page, "[data-testid=part-exercise]", timeout=8000):
        return
    check("[ouverture] objectif annoncé", "variantes" in page.locator("[data-testid=part-exercise]").inner_text())
    page.locator("[data-testid=part-exercise] button", has_text="Commencer").click()
    by_uci = {o["uci"]: o for o in OPENINGS}
    for n in range(ex["count"]):
        if not ck.appears(f"[ouverture] drill {n + 1}", page, "[data-drill]", timeout=10000):
            return
        if n == 0:
            shot(page, "parcours_ouverture_852")
        # La variante jouée : la ligne lichess la plus longue que la position prolonge, lue au départ.
        page.wait_for_timeout(300)
        line = None
        title = page.locator("[data-drill]").inner_text()
        check(f"[ouverture] drill {n + 1} : compteur {n + 1}/{ex['count']}", f"{n + 1}/{ex['count']}" in title)
        # La variante est connue de sessionStorage (série persistée).
        stored = page.evaluate("() => JSON.parse(sessionStorage.getItem('path-session-v1') || 'null')")
        if stored:
            line = stored["items"][stored["idx"]]["uci"].split(" ")
        if not check(f"[ouverture] drill {n + 1} : variante lue dans la série", line is not None and " ".join(line) in by_uci):
            return
        me = 0 if ex["color"] == "w" else 1
        for i in range(len(line)):
            if i % 2 != me:
                continue
            if not wait_plies(page, i):
                check(f"[ouverture] réponse avant le demi-coup {i}", False)
                return
            tap_move(page, line[i][0:2], line[i][2:4])
            if not wait_plies(page, i + 1, 5000):
                check(f"[ouverture] coup {line[i]} accepté", False, f"({drill_uci(page)})")
                return
        if not ck.appears(f"[ouverture] drill {n + 1} : variante maîtrisée", page, "[data-result='ok']", timeout=8000):
            return
        if n in (0, ex["count"] - 1):
            variant_round_trip(page, f"[ouverture:analyse {n + 1}]")
        btn = page.locator("[data-result] button", has_text="Voir le résultat" if n + 1 == ex["count"] else "Suivant")
        if not check(f"[ouverture] drill {n + 1} : bouton suivant", btn.count() > 0):
            return
        if n == ex["count"] - 1:
            block_path_writes(page)
        btn.first.click()
        page.wait_for_timeout(400)
    retry_save(page, "[ouverture]", "path-session-v1", "[data-run-end]", reload=True)
    if ck.appears("[ouverture] série validée", page, "[data-run-end='passed']", timeout=8000):
        check("[ouverture] 3 étoiles", page.locator("[data-run-end] [data-stars='3']").count() == 1)
        rows = [r for r in sessions(page, "path") if r["itemId"] == step["id"]]
        check("[ouverture] ligne `path` score 3", len(rows) == 1 and rows[0]["score"] == ex["count"] and rows[0]["success"] == 1, f"({rows})")
        drills = sessions(page, "opening-drill")
        check("[ouverture] chaque variante compte aussi dans l'entraîneur", len(drills) == ex["count"] and all(r["itemId"].startswith("full:w:") and r["success"] == 1 for r in drills), f"({len(drills)})")


def variant_round_trip(page, tag):
    """Variante jugée de la série : « Analyser » puis « Retour au parcours » rendent le même drill
    sur son verdict (pas l'item suivant, ni le drill rejoué), sans nouvelle écriture."""
    uci, title, result = page.get_attribute("[data-drill]", "data-uci"), page.locator("[data-drill] header").inner_text(), page.locator("[data-result]").inner_text()
    page.wait_for_timeout(500)  # écriture du verdict en cours
    n_drills = len(sessions(page, "opening-drill"))
    page.locator("[data-result] button", has_text="Analyser").click()
    if not ck.appears(f"{tag} « Retour au parcours » dans l'analyseur", page, "button:has-text('Retour au parcours')", timeout=15000):
        return
    check(f"{tag} analyseur ouvert", page.evaluate("() => location.hash") == "#/analyse")
    page.get_by_role("button", name="Retour au parcours").click()
    if not ck.appears(f"{tag} retour : drill sur son verdict", page, "[data-drill] [data-result='ok']", timeout=10000):
        return
    check(f"{tag} retour : même variante au même rang", page.locator("[data-drill] header").inner_text() == title
          and page.get_attribute("[data-drill]", "data-uci") == uci, f"({page.locator('[data-drill] header').inner_text()!r})")
    check(f"{tag} retour : même verdict", page.locator("[data-result]").inner_text() == result)
    page.wait_for_timeout(400)
    check(f"{tag} retour : aucune écriture de plus", len(sessions(page, "opening-drill")) == n_drills)


def part_endgame_save(p, browser):
    for first_failure in (False, True):
        ctx, page = context(p, browser)
        seed_sessions(page, [row("path", "placement", score=1), row("course", "finales:mat-dame")])
        go(page, "/apprendre/parcours/mat-dame")
        ck.appears("[sauvegarde finale] étape ouverte", page, "[data-testid=part-exercise]", timeout=8000)
        page.locator("[data-testid=part-exercise] button", has_text="Commencer").click()
        ck.appears("[sauvegarde finale] leçon ouverte", page, "button:has-text(\"C'est parti\")", timeout=8000)
        page.evaluate("""() => {
          const saved = JSON.parse(sessionStorage.getItem('learn-session-v1'))
          saved.session.items[0].endgame.fen = '7k/5K2/8/6Q1/8/8/8/8 w - - 0 1'
          sessionStorage.setItem('learn-session-v1', JSON.stringify(saved))
          history.replaceState({...history.state, usr: {restore: true}}, '')
        }""")
        page.reload()
        ck.appears("[sauvegarde finale] position restaurée", page, "button:has-text(\"C'est parti\")", timeout=8000)
        page.get_by_role("button", name="C'est parti", exact=True).click()
        if first_failure:
            tap_move(page, "g5", "g6")
            ck.appears("[sauvegarde finale] premier essai : pat", page, "text=✗ À revoir", timeout=8000)
            page.get_by_role("button", name="Réessayer").click()
        before = sessions(page, "endgame")
        block_path_writes(page)
        tap_move(page, "g5", "g7")
        ck.appears("[sauvegarde finale] écriture refusée", page, "[role=alert]", timeout=8000)
        check("[sauvegarde finale] note annulée avec la transaction", sessions(page, "endgame") == before)
        retry_save(page, "[sauvegarde finale]", "learn-session-v1", "text=✓ Réussi", reload=first_failure)
        rows = sessions(page, "endgame")
        check("[sauvegarde finale] seule la première tentative compte pour l’Elo", len(rows) == 1 and rows[0]["success"] == (0 if first_failure else 1))
        if first_failure:
            check("[sauvegarde finale] réessai sans nouvelle note", rows == before)
        else:
            check("[sauvegarde finale] position finale conservée après écriture", page.locator("[data-square=g7] [data-piece=wQ]").count() == 1)
        go(page, "/apprendre/parcours/mat-dame")
        ck.appears("[sauvegarde finale] validation persistée", page, "[data-testid=step-validated]", timeout=8000)
        ctx.close()


def part_layouts(p, browser):
    for name, kw in (("660", {"standalone": False}), ("1440", {"desktop": True})):
        ctx, page = context(p, browser, **kw)
        seed_sessions(page, [row("course", STEPS[0]["lesson"]), row("path", STEPS[0]["id"], score=5)])  # étape 2 débloquée
        if name == "660":
            go(page, "/")
            ck.appears("[660] accueil", page, "[data-testid=home-path]", timeout=10000)
            # Progression calculée après le premier affichage (learningPathStore.ts, import dynamique de Home.tsx).
            ck.appears("[660] progression du parcours connue", page, "[data-path-ready]", timeout=10000)
            fits = page.evaluate("() => { const m = document.querySelector('main'); return m.scrollHeight <= m.clientHeight + 1 }")
            check("[660] l'Accueil tient sans défiler avec la tuile Parcours", fits)
            check("[660] tuile Parcours : progression", page.locator("[data-testid=home-path-progress]").inner_text().strip() == f"1/{TOTAL}", page.locator("[data-testid=home-path]").inner_text())
            shot(page, "parcours_accueil_660")
            page.locator("[data-testid=home-path]").click()
            map_ready(page, "[660 accueil]")
            check("[660] la tuile ouvre le parcours", page.evaluate("() => location.hash") == "#/apprendre/parcours")
        for path, sel, slug in (
            ("/apprendre", "[data-testid=path-hero]", "apprendre"),
            ("/apprendre/parcours", "[data-testid=path-progress]", "carte"),
            (f"/apprendre/parcours/{STEPS[1]['id']}", "[data-testid=part-read]", "etape"),
            ("/apprendre/parcours/placement", "[data-step-page='placement']", "placement"),
        ):
            go(page, path)
            if ck.appears(f"[{name}] {path} affiché", page, sel, timeout=10000):
                page.wait_for_timeout(300)
                check(f"[{name}] {path} sans débordement horizontal", overflow_x(page) <= 0, f"({overflow_x(page)})")
                shot(page, f"parcours_{slug}_{name}")
        go(page, f"/apprendre/parcours/{STEPS[0]['id']}")
        ck.appears(f"[{name}] étape 1", page, "[data-testid=part-lesson]", timeout=8000)
        shot(page, f"parcours_etape1_{name}")
        # Série ouverte : échiquier entier dans l'écran.
        go(page, f"/apprendre/parcours/{STEPS[1]['id']}")
        ck.appears(f"[{name}] étape 2", page, "[data-testid=part-exercise]", timeout=8000)
        page.locator("[data-testid=part-exercise] button", has_text="Commencer").click()
        if ck.appears(f"[{name}] série ouverte", page, "[data-run] [data-square='a1']", timeout=10000):
            if not ck.appears(f"[{name}] amorce jouée avant la capture", page, "[data-run] [data-square='c3'] [data-piece='bN']", timeout=6000):
                ctx.close()
                continue
            # L'amorce attend 500 ms ; laisser ensuite finir les 120 ms d'animation du Board.
            page.wait_for_timeout(150)
            a1 = page.locator("[data-run] [data-square='a1']").bounding_box()
            h8 = page.locator("[data-run] [data-square='h8']").bounding_box()
            vp = page.viewport_size
            check(f"[{name}] échiquier de la série dans l'écran", a1 and h8 and h8["y"] >= 0 and a1["y"] + a1["height"] <= vp["height"])
            check(f"[{name}] série sans débordement horizontal", overflow_x(page) <= 0)
            shot(page, f"parcours_serie_{name}")
        ctx.close()


def suite(p):
    part_data()
    part_logic()
    browser = p.chromium.launch()
    try:
        ctx, page = context(p, browser)
        part_all_basics(page)
        ctx.close()
        part_fresh_and_lesson(p, browser)
        part_placement_and_existing(p, browser)
        part_endgame_save(p, browser)
        part_layouts(p, browser)
    finally:
        browser.close()


ck.run(suite)
