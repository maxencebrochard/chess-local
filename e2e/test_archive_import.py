"""Archive des parties et import chess.com (lot l12).

Archive : carte compacte sur iPhone (moins de 90 px), pagination par 50 (« Voir plus »),
suppression différée annulable (« Annuler ») validée après 5 s ou en quittant la page,
compteur relu en base. Import : aucune requête vers api.chess.com avant une action explicite
(SEC-3), « Actualiser » relance vraiment, erreur réseau puis « Réessayer », pseudo validé et
mémorisé seulement après un chargement réussi, lien profond confirmé par un bouton, variantes
exclues, libellés français. Banc unitaire Node de src/lib/chesscom.ts (extractGameId,
normalizeUsername, libellés), lancé avec le TypeScript lu tel quel par Node.

Fondée sur la fixture e2e/fixtures/chesscom.json : ignorée en --live.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

from helpers import BASE, LIVE, Checker, desktop_context, mobile_context, overflow_x, shot

if LIVE:
    print("[archive_import] suite fondée sur la fixture chess.com : ignorée en --live")
    sys.exit(0)

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
ck = Checker("archive_import")

PSEUDO_INPUT = "input[placeholder*='pseudo']"
LINK_INPUT = "input[placeholder*='colle un lien']"
API = "https://api.chess.com/**"


# ---------------------------------------------------------------- banc unitaire Node
UNIT_TS = r"""
// Banc unitaire de src/lib/chesscom.ts (fonctions pures). Une ligne JSON par cas : { name, ok, got }.
const mod = await import(process.argv[2])
const out: { name: string; ok: boolean; got: unknown }[] = []
const check = (name: string, got: unknown, want: unknown) => out.push({ name, ok: JSON.stringify(got) === JSON.stringify(want), got })
const call = (fn: string, ...args: unknown[]) => {
  try { return typeof mod[fn] === 'function' ? mod[fn](...args) : `ABSENT ${fn}` } catch (e) { return 'THROW ' + (e as Error).message }
}

for (const [url, id] of [
  ['https://www.chess.com/game/live/123456789', '123456789'],
  ['https://www.chess.com/game/daily/987654', '987654'],
  ['https://www.chess.com/live/game/123456789', '123456789'],
  ['https://www.chess.com/daily/game/987654', '987654'],
  ['https://www.chess.com/analysis/game/live/123456789?tab=review', '123456789'],
  ['https://www.chess.com/analysis/game/daily/987654/review', '987654'],
  ['https://www.chess.com/game/live/123456789?username=foo#b', '123456789'],
  ['HTTPS://WWW.CHESS.COM/GAME/LIVE/123456789', '123456789'],
  ['https://www.chess.com/fr/game/live/123456789', '123456789'],
  ['https://www.chess.com/game/123456789', '123456789'],
  ['https://chess.com/game/live/123456789/', '123456789'],
  ['  https://www.chess.com/game/live/123456789  ', '123456789'],
  ['https://www.chess.com/game/live/123456789.', '123456789'],
  ['www.chess.com/game/live/106', '106'],
]) check(`extractGameId accepte ${url.trim()}`, call('extractGameId', url), id)
for (const url of [
  'https://www.chess.com/events/2024/game/1/12',
  'https://www.chess.com/member/game/42',
  'https://www.chess.com/game/computer/55512345',
  'https://chess.com/a/2fGh3Kd9xLpQ?tab=review',
  'https://lichess.org/game/live/123456789',
  'https://evil.example/?u=chess.com/game/live/123456789',
  '',
]) check(`extractGameId refuse ${url || '(vide)'}`, call('extractGameId', url), null)
check('isComputerGameUrl /game/computer/', call('isComputerGameUrl', 'https://www.chess.com/game/computer/55512345'), true)
check('isComputerGameUrl /game/live/', call('isComputerGameUrl', 'https://www.chess.com/game/live/123'), false)

check('normalizeUsername " Hikaru "', call('normalizeUsername', ' Hikaru '), 'hikaru')
check('normalizeUsername caractères invisibles', call('normalizeUsername', '​hikaru﻿'), 'hikaru')
check('normalizeUsername URL /member/', call('normalizeUsername', 'https://www.chess.com/member/Hikaru'), 'hikaru')
check('normalizeUsername URL /fr/member/ avec barre finale', call('normalizeUsername', 'https://www.chess.com/fr/member/Hikaru/'), 'hikaru')
check('normalizeUsername tiret et souligné', call('normalizeUsername', 'Eric_59-x'), 'eric_59-x')
for (const bad of ['Éric_59', 'jean.dupont', 'magnus carlsen', 'hikaru!', '', '   '])
  check(`normalizeUsername rejette ${JSON.stringify(bad)}`, String(call('normalizeUsername', bad)).startsWith('THROW Pseudo'), true)

check('timeClassLabel rapid', call('timeClassLabel', 'rapid'), 'rapide')
check('timeClassLabel daily', call('timeClassLabel', 'daily'), 'différé')
check('timeClassLabel bullet', call('timeClassLabel', 'bullet'), 'bullet')
check('timeClassLabel inconnu = brut', call('timeClassLabel', 'xyz'), 'xyz')
const pgn = '[Event "Live Chess"]\n[White "a"]\n[Black "b"]\n\n1. d4 {[%clk 0:03:00]} 1... d5 {[%clk 0:02:59]} 2. c4 {[%clk 0:02:58]} 2... e6 {[%clk 0:02:57]} 3. Nc3 {[%clk 0:02:50]} 1-0\n'
check('moveCount PGN chess.com avec horloges', call('moveCount', pgn), 3)
check('moveCount PGN simple', call('moveCount', '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 1-0'), 4)
check('moveCount vide', call('moveCount', ''), 0)
const g = (me: string, opp: string, myColor: 'w' | 'b' = 'w') => ({ playerColor: myColor, white: { username: 'x', rating: 1, result: myColor === 'w' ? me : opp }, black: { username: 'y', rating: 1, result: myColor === 'w' ? opp : me } })
check('outcomeFor victoire', call('outcomeFor', g('win', 'checkmated')), 'win')
check('outcomeFor nulle (repetition)', call('outcomeFor', g('repetition', 'repetition')), 'draw')
check('outcomeFor défaite au temps', call('outcomeFor', g('timeout', 'win', 'b')), 'loss')
check('terminationLabel je gagne par mat', call('terminationLabel', g('win', 'checkmated')), 'mat')
check('terminationLabel je perds au temps', call('terminationLabel', g('timeout', 'win', 'b')), 'au temps')
check('terminationLabel nulle par accord', call('terminationLabel', g('agreed', 'agreed')), 'nulle par accord')
check('terminationLabel abandon adverse', call('terminationLabel', g('win', 'resigned')), 'abandon')
check('terminationLabel inconnu = brut', call('terminationLabel', g('win', 'zzz')), 'zzz')

for (const r of out) console.log(JSON.stringify(r))
"""


def unit_node():
    """Fonctions pures de chesscom.ts, hors navigateur : Node 22 lit le TypeScript directement."""
    with tempfile.TemporaryDirectory() as d:
        script = os.path.join(d, "unit_chesscom.mts")
        with open(script, "w", encoding="utf-8") as f:
            f.write(UNIT_TS)
        r = subprocess.run(
            ["node", "--experimental-strip-types", "--no-warnings", script, "file://" + os.path.join(ROOT, "src", "lib", "chesscom.ts")],
            capture_output=True, text=True, timeout=60, cwd=ROOT,
        )
    if r.returncode != 0:
        ck.fail("[unit] banc Node de chesscom.ts", f"(code {r.returncode} : {r.stderr.strip()[-300:]})")
        return
    for line in r.stdout.splitlines():
        row = json.loads(line)
        ck.check("[unit] " + row["name"], row["ok"], "" if row["ok"] else f"(obtenu {row['got']!r})")


# ---------------------------------------------------------------- archive
PGN = '[Event "ChessLocal"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 1-0'
TERMINATIONS = ["par échec et mat", "par abandon", "au temps", "par la règle des 50 coups", "par matériel insuffisant"]
BOTS = ["noa", "marty", "lea", "nina", "maximus"]


def seed_games(n):
    """n parties aux dates toutes distinctes (ordre d'affichage déterministe). La plus récente,
    donc la première ligne, est une partie locale perdue par les Blancs (« 0-1 ») avec le motif
    de fin le plus long de Play.tsx : le pire cas pour la hauteur de ligne."""
    out = []
    for i in range(n):
        local = i % 7 == 3 or i == n - 1
        g = {
            "date": 1_790_000_000_000 + i * 5 * 3600 * 1000,
            "mode": "local" if local else "bot",
            "playerColor": "w" if i % 2 == 0 else "b",
            "timeControl": ["5+0", "10+0", "3+2", "illimité"][i % 4],
            "timeClass": ["blitz", "rapid", "blitz", "unlimited"][i % 4],
            "pgn": PGN,
            "result": ["1-0", "0-1", "1/2-1/2"][i % 3],
            "termination": TERMINATIONS[i % 5],
        }
        if i == n - 1:
            g.update(result="0-1", termination="par la règle des 50 coups")
        if not local:
            g.update(botId=BOTS[i % 5], playerRatingAfter=800 + i)
        out.append(g)
    return out


# La base est créée par Dexie (l'app) ; on y écrit ensuite en IndexedDB brut, sans version,
# pour ne jamais concurrencer son schéma.
SEED_JS = """async (games) => {
  const db = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const tx = db.transaction('games', 'readwrite')
  for (const g of games) tx.objectStore('games').add(g)
  await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error) })
  const n = await new Promise((res) => { const r = db.transaction('games').objectStore('games').count(); r.onsuccess = () => res(r.result) })
  db.close()
  return n
}"""
COUNT_JS = """async () => {
  const db = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const n = await new Promise((res) => { const r = db.transaction('games').objectStore('games').count(); r.onsuccess = () => res(r.result) })
  db.close()
  return n
}"""


def wait_db(page):
    for _ in range(50):
        if page.evaluate("async () => (await indexedDB.databases()).some((d) => d.name === 'chess-local')"):
            return True
        page.wait_for_timeout(100)
    return False


def db_count(page):
    return page.evaluate(COUNT_JS)


def tap(name, locator):
    """Clique si l'élément existe, sinon échec nommé : un clic direct sur un élément absent
    (ancien code, régression) attendrait 30 s puis couperait la suite au lieu d'un [FAIL]."""
    if locator.count() == 0:
        return ck.fail(name, "(élément absent)")
    locator.first.click()
    return True


def seed_archive(page, n, tag):
    page.goto(BASE + "/#/")
    ck.check(f"[archive {tag}] base Dexie créée par l'app", wait_db(page))
    seeded = page.evaluate(SEED_JS, seed_games(n))
    ck.check(f"[archive {tag}] {n} parties injectées", seeded == n, f"({seeded})")
    page.goto(BASE + "/#/archive")
    ck.appears(f"[archive {tag}] titre Archive ({n})", page, f"h1:has-text('Archive ({n})')", timeout=10000)


def archive_layout(page, tag, max_height):
    rows = page.locator("main li")
    heights = [rows.nth(i).bounding_box()["height"] for i in range(rows.count())]
    ck.check(f"[archive {tag}] pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    ck.check(
        f"[archive {tag}] chaque carte sous {max_height} px",
        bool(heights) and max(heights) < max_height,
        f"(max {max(heights) if heights else 'aucune carte <li>'} px sur {len(heights)} cartes)",
    )
    first = rows.nth(0)
    res = first.locator("span").first
    one_line = first.count() > 0 and res.inner_text().strip() == "0-1" and res.bounding_box()["height"] <= 24
    ck.check(f"[archive {tag}] « 0-1 » d'une partie locale sur une seule ligne", one_line)
    ck.check(f"[archive {tag}] « contre » et non « vs »", page.locator("main li", has_text=re.compile(r"\bvs\b")).count() == 0)


def archive_mobile_standalone(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    seed_archive(page, 60, "852")
    links = page.locator("main a", has_text="Analyser")
    more = page.get_by_role("button", name=re.compile("Voir plus"))
    ck.check("[archive 852] 50 cartes rendues (pagination)", links.count() == 50, f"({links.count()})")
    ck.check("[archive 852] bouton « Voir plus »", more.count() == 1)
    archive_layout(page, "852", 90)
    shot(page, "l12_archive_852")

    # Double tap : la seconde lecture ne doit pas dupliquer la page suivante.
    if more.count():
        more.first.dblclick()
        page.wait_for_timeout(600)
    ck.check("[archive 852] « Voir plus » (double tap) charge les 10 restantes, sans doublon", links.count() == 60, f"({links.count()})")
    ck.check("[archive 852] « Voir plus » disparaît quand tout est chargé", more.count() == 0)

    rows = page.locator("main li")
    first = rows.nth(0)
    x = first.get_by_role("button", name="Supprimer la partie")
    ck.check("[archive 852] ✕ porte aria-label « Supprimer la partie »", x.count() == 1)
    box = x.first.bounding_box() if x.count() else None
    ck.check("[archive 852] ✕ cible d'au moins 44x44", bool(box) and box["width"] >= 44 and box["height"] >= 44, f"({box})")
    row_h = first.bounding_box()["height"] if first.count() else 0

    # Suppression annulable : la carte devient une barre « Partie supprimée » de même hauteur.
    if x.count():
        x.first.click()
    ck.appears("[archive 852] barre « Partie supprimée »", page, "main li [role='status']:has-text('Partie supprimée')", timeout=3000)
    bar_h = first.bounding_box()["height"] if first.count() else 0
    ck.check("[archive 852] la barre garde la hauteur de la carte (pas de saut)", abs(bar_h - row_h) <= 2, f"(carte {row_h}, barre {bar_h})")
    ck.check("[archive 852] la carte n'offre plus ses actions", links.count() == 59, f"({links.count()})")
    ck.check("[archive 852] rien n'est encore supprimé en base", db_count(page) == 60, f"({db_count(page)})")
    shot(page, "l12_archive_852_annuler")
    undo = page.get_by_role("button", name="Annuler")
    ck.check("[archive 852] bouton Annuler de 44 px", undo.count() == 1 and undo.first.bounding_box()["height"] >= 44)
    if undo.count():
        undo.first.click()
        page.wait_for_timeout(300)
    ck.check("[archive 852] Annuler restaure la carte", links.count() == 60 and page.locator("main [role='status']").count() == 0)
    ck.check("[archive 852] Annuler ne touche pas la base", db_count(page) == 60)

    # Sans annulation : suppression validée après 5 s, compteur relu.
    if x.count():
        x.first.click()
        page.wait_for_timeout(5500)
    ck.check("[archive 852] supprimée en base après 5 s", db_count(page) == 59, f"({db_count(page)})")
    ck.check("[archive 852] titre Archive (59)", page.locator("h1").inner_text().strip() == "Archive (59)", f"({page.locator('h1').inner_text()})")
    ck.check("[archive 852] la barre a disparu", page.locator("main [role='status']").count() == 0 and links.count() == 59)

    # Quitter la page pendant l'attente valide la suppression : rien ne ressuscite.
    x = rows.nth(0).get_by_role("button", name="Supprimer la partie")
    if x.count():
        x.first.click()
        page.wait_for_timeout(200)
    tap("[archive 852] nav Stats", page.locator("nav a:visible", has_text="Stats"))
    page.wait_for_timeout(800)
    ck.check("[archive 852] quitter la page valide la suppression en attente", db_count(page) == 58, f"({db_count(page)})")
    tap("[archive 852] nav Archive", page.locator("nav a:visible", has_text="Archive"))
    ck.appears("[archive 852] de retour : Archive (58)", page, "h1:has-text('Archive (58)')", timeout=5000)

    # Exporter tout relit la base (pas l'état paginé) : 58 parties dans le PGN.
    with page.expect_download(timeout=10000) as dl:
        page.click("button:has-text('Exporter tout')")
    path = dl.value.path()
    with open(path, encoding="utf-8") as f:
        n_pgn = f.read().count('[Event "ChessLocal"]')
    ck.check("[archive 852] export de toutes les parties de la base", n_pgn == 58, f"({n_pgn})")
    ctx.close()


def archive_mobile_safari(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=False)
    page = ctx.new_page()
    seed_archive(page, 60, "660")
    archive_layout(page, "660", 90)
    shot(page, "l12_archive_660")
    ctx.close()


def archive_desktop(browser):
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    seed_archive(page, 12, "1440")
    rows = page.locator("main li")
    heights = [rows.nth(i).bounding_box()["height"] for i in range(rows.count())]
    # Une seule rangée : les actions sont à côté des deux lignes de texte (centre vertical commun),
    # pas en dessous ; deux lignes de texte et leur marge font 64 px.
    card = rows.nth(0).bounding_box() if rows.count() else None
    link = rows.nth(0).locator("a", has_text="Analyser").bounding_box() if rows.count() else None
    centered = bool(card and link) and abs((link["y"] + link["height"] / 2) - (card["y"] + card["height"] / 2)) <= 4
    ck.check("[archive 1440] une seule rangée par carte (actions à côté des infos)", bool(heights) and max(heights) < 70 and centered, f"(max {max(heights) if heights else '-'} px, actions centrées : {centered})")
    shot(page, "l12_archive_1440")
    ctx.close()


# ---------------------------------------------------------------- import chess.com
def net_counter(ctx):
    """Compte les requêtes api.chess.com et sait couper le réseau (« cut ») ou retenir une requête
    (« hold ») : `set_offline` ne bloque pas les requêtes interceptées par `route`, il ne fait que
    basculer navigator.onLine. Enregistrée après mock_chesscom, cette route tourne en premier et
    passe la main à la fixture par fallback()."""
    net = {"n": 0, "cut": False, "hold": False, "held": []}

    def handle(route):
        net["n"] += 1
        if net["cut"]:
            route.abort("internetdisconnected")
        elif net["hold"]:
            net["held"].append(route)
        else:
            route.fallback()

    ctx.route(API, handle)
    return net


def stored_username(page):
    raw = page.evaluate("() => localStorage.getItem('chess-local-settings')")
    return (json.loads(raw) if raw else {}).get("state", {}).get("chesscomUsername")


def import_mobile(p, browser):
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": "popeye232"}, standalone=True)
    net = net_counter(ctx)
    page = ctx.new_page()
    page.goto(BASE + "/#/import")
    page.wait_for_timeout(1500)
    ck.check("[import] aucune requête chess.com au chargement (SEC-3)", net["n"] == 0, f"({net['n']})")
    ck.check("[import] aucune liste avant action", page.locator("main button", has_text=re.compile("contre |vs ")).count() == 0)
    load = page.get_by_role("button", name="Voir mes parties")
    ck.check("[import] bouton « Voir mes parties »", load.count() == 1)
    if load.count():
        load.first.click()
    ck.appears("[import] liste « contre »", page, "main button:has-text('contre ')")
    rows = page.locator("main button", has_text="contre ")
    ck.check("[import] 8 parties standard (chess960 exclue)", rows.count() == 8, f"({rows.count()})")
    ck.check("[import] BotHotel (chess960) absent", page.get_by_text("BotHotel").count() == 0)
    india = page.locator("main button", has_text="BotIndia")
    india_txt = india.first.inner_text() if india.count() else ""
    ck.check("[import] cadence « différé » et nombre de coups", "différé" in india_txt and "coups" in india_txt, f"({india_txt[:80]!r})")
    echo = page.locator("main button", has_text="BotEcho")
    echo_txt = echo.first.inner_text() if echo.count() else ""
    ck.check("[import] cadence « rapide » et motif de fin", "rapide" in echo_txt and "accord" in echo_txt, f"({echo_txt[:80]!r})")
    ck.check("[import] pastille de couleur accessible", page.locator("main button [role='img'][aria-label='Blancs']").count() >= 1 and page.locator("main button [role='img'][aria-label='Noirs']").count() >= 1)
    ck.check("[import] pas de débordement horizontal", overflow_x(page) == 0)
    n1 = net["n"]
    ck.check("[import] chargement = 4 requêtes (archives + 3 mois)", n1 == 4, f"({n1})")
    shot(page, "l12_import_852_liste")

    refresh = page.get_by_role("button", name="Actualiser")
    ck.check("[import] bouton « Actualiser » une fois la liste affichée", refresh.count() == 1)
    tap("[import] clic Actualiser", refresh)
    ck.appears("[import] liste après Actualiser", page, "main button:has-text('contre ')")
    ck.check("[import] Actualiser relance le chargement (ANA-8)", net["n"] > n1, f"({n1} -> {net['n']})")

    # En ligne mais requête en échec : message court et « Réessayer » qui relance vraiment.
    net["cut"] = True
    n2 = net["n"]
    tap("[import] clic Actualiser (réseau coupé)", refresh)
    ck.appears("[import] requête en échec : bouton Réessayer", page, "button:has-text('Réessayer')", timeout=5000)
    ck.check("[import] la liste n'est plus affichée après l'échec", rows.count() == 0)
    ck.check("[import] message d'erreur court (sans URL technique)", page.locator("text=api.chess.com").count() == 0)
    net["cut"] = False
    tap("[import] clic Réessayer", page.get_by_role("button", name="Réessayer"))
    ck.appears("[import] Réessayer ramène la liste", page, "main button:has-text('contre ')")
    ck.check("[import] Réessayer relance le chargement", net["n"] > n2 + 1, f"({n2} -> {net['n']})")

    # Hors ligne : message dédié, puis Réessayer une fois en ligne.
    net["cut"] = True
    ctx.set_offline(True)
    tap("[import] clic Actualiser (hors ligne)", page.get_by_role("button", name="Actualiser"))
    ck.appears("[import] hors ligne : « Pas de connexion »", page, "text=Pas de connexion", timeout=5000)
    shot(page, "l12_import_852_horsligne")
    ctx.set_offline(False)
    net["cut"] = False
    tap("[import] clic Réessayer (en ligne)", page.get_by_role("button", name="Réessayer"))
    ck.appears("[import] de retour en ligne, Réessayer fonctionne", page, "main button:has-text('contre ')")
    ck.check("[import] l'erreur a disparu", page.locator("button:has-text('Réessayer')").count() == 0)

    # Champs : clavier iOS configuré, 16 px pour ne pas zoomer, Entrée qui soumet.
    inp = page.locator(PSEUDO_INPUT)
    if not ck.check("[import] champ pseudo présent", inp.count() == 1):
        ctx.close()
        return
    attrs = {a: inp.get_attribute(a) for a in ("autocapitalize", "autocorrect", "spellcheck", "enterkeyhint")}
    ck.check("[import] attributs clavier du champ pseudo", attrs == {"autocapitalize": "none", "autocorrect": "off", "spellcheck": "false", "enterkeyhint": "go"}, f"({attrs})")
    link = page.locator(LINK_INPUT)
    link_font = link.evaluate("(el) => getComputedStyle(el).fontSize") if link.count() else "absent"
    ck.check("[import] champ lien en 16 px (pas de zoom iOS)", link_font == "16px", f"({link_font})")
    ck.check("[import] champ lien en mode URL", link.count() == 1 and link.get_attribute("inputmode") == "url")

    n3 = net["n"]
    inp.fill("zz_qa_nobody_98765")
    inp.press("Enter")
    ck.appears("[import] Entrée soumet : pseudo inconnu → « Joueur introuvable sur chess.com. »", page, "text=Joueur introuvable sur chess.com.", timeout=5000)
    ck.check("[import] un pseudo inconnu n'est pas mémorisé", stored_username(page) == "popeye232", f"({stored_username(page)!r})")
    ck.check("[import] le bouton est de nouveau actif après l'erreur", page.get_by_role("button", name=re.compile("Voir mes parties|Actualiser")).first.is_enabled())
    n4 = net["n"]
    inp.fill("Éric_59")
    inp.press("Enter")
    ck.appears("[import] pseudo invalide refusé", page, "text=Pseudo invalide", timeout=3000)
    ck.check("[import] pseudo invalide : aucune requête (pas de recherche d'un autre joueur)", net["n"] == n4, f"({n4} -> {net['n']})")
    ck.check("[import] pseudo inconnu : une seule requête (archives 404)", n4 - n3 == 1, f"({n4 - n3})")

    inp.fill("popeye232")
    inp.press("Enter")
    ck.appears("[import] liste revenue", page, "main button:has-text('contre ')")

    # Liens : partie contre l'ordinateur et variante, sans requête inutile.
    n5 = net["n"]
    if not ck.check("[import] champ lien présent", link.count() == 1):
        ctx.close()
        return
    link.fill("https://www.chess.com/game/computer/55512345")
    link.press("Enter")
    ck.appears("[import] lien /game/computer/ : message dédié", page, "text=ordinateur", timeout=3000)
    ck.check("[import] lien ordinateur : aucune requête", net["n"] == n5)
    link.fill("https://www.chess.com/game/live/108")
    link.press("Enter")
    ck.appears("[import] lien vers une partie chess960 : « variante »", page, "text=variante", timeout=5000)

    # Bouton inactif pendant le chargement (requête retenue puis libérée).
    net["hold"] = True
    tap("[import] clic Actualiser (requête retenue)", page.get_by_role("button", name="Actualiser"))
    page.wait_for_timeout(400)
    btn = page.get_by_role("button", name=re.compile("Voir mes parties|Actualiser")).first
    ck.check("[import] bouton inactif pendant le chargement", btn.is_disabled() and page.get_by_text("Chargement").count() == 1)
    net["hold"] = False
    for r in net["held"]:
        r.fallback()
    net["held"].clear()
    ck.appears("[import] liste après libération", page, "main button:has-text('contre ')")
    ck.check("[import] bouton actif après le chargement", btn.is_enabled())
    ctx.close()


def import_persist(p, browser):
    """Sens positif d'ANA-22 : le pseudo mémorisé ne change qu'après un chargement réussi."""
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": "ancien_pseudo"}, standalone=True)
    net = net_counter(ctx)
    page = ctx.new_page()
    page.goto(BASE + "/#/import")
    page.wait_for_timeout(800)
    inp = page.locator(PSEUDO_INPUT)
    if not ck.check("[import] champ pseudo présent (persistance)", inp.count() == 1):
        ctx.close()
        return
    ck.check("[import] champ pré-rempli avec le pseudo mémorisé", inp.input_value() == "ancien_pseudo", f"({inp.input_value()!r})")
    ck.check("[import] pseudo mémorisé : aucune requête sans action", net["n"] == 0, f"({net['n']})")
    inp.fill("popeye232")
    inp.press("Enter")
    ck.appears("[import] chargement réussi d'un autre pseudo", page, "main button:has-text('contre ')")
    ck.check("[import] popeye232 remplace ancien_pseudo après succès", stored_username(page) == "popeye232", f"({stored_username(page)!r})")
    ctx.close()


def import_deeplink(p, browser):
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": "popeye232"}, standalone=True)
    net = net_counter(ctx)
    page = ctx.new_page()
    page.goto(BASE + "/#/import?url=https://www.chess.com/game/live/106?tab=review")
    page.wait_for_timeout(1200)
    ck.check("[lien profond] aucune requête avant confirmation (SEC-3)", net["n"] == 0, f"({net['n']})")
    ck.check("[lien profond] encart « Partie partagée »", page.get_by_text("Partie partagée").count() == 1)
    btn = page.get_by_role("button", name=re.compile("Chercher cette partie"))
    ck.check("[lien profond] bouton Chercher actif", btn.count() == 1 and btn.first.is_enabled())
    shot(page, "l12_import_852_lienprofond")
    if btn.count():
        btn.first.click()
    opened = False
    for _ in range(60):
        if "#/analyse" in page.url:
            opened = True
            break
        page.wait_for_timeout(100)
    ck.check("[lien profond] Chercher ouvre le bilan dans /analyse", opened, f"({page.url})")
    ck.check("[lien profond] requêtes seulement après confirmation", net["n"] >= 2, f"({net['n']})")

    page.goto(BASE + "/#/")
    page.wait_for_timeout(300)
    page.goto(BASE + "/#/import?url=https://lichess.org/abc")
    page.wait_for_timeout(500)
    ck.check("[lien profond] lien non reconnu : message sans bouton", page.get_by_text("n'est pas une partie chess.com").count() == 1 and page.get_by_role("button", name=re.compile("Chercher")).count() == 0)

    page.goto(BASE + "/#/")
    page.wait_for_timeout(300)
    page.goto(BASE + "/#/import?user=autre_pseudo&url=https://www.chess.com/game/live/106")
    page.wait_for_timeout(500)
    ck.check("[lien profond] ?user= pré-remplit le champ et prime sur le pseudo mémorisé", page.locator(PSEUDO_INPUT).input_value() == "autre_pseudo", f"({page.locator(PSEUDO_INPUT).input_value()!r})")
    ctx.close()

    ctx = mobile_context(p, browser, ck, standalone=True)  # aucun pseudo mémorisé (Safari, IOS-9)
    net = net_counter(ctx)
    page = ctx.new_page()
    page.goto(BASE + "/#/import?url=https://www.chess.com/game/live/106")
    page.wait_for_timeout(800)
    btn = page.get_by_role("button", name=re.compile("Chercher cette partie"))
    ck.check("[lien profond] sans pseudo : bouton inactif et invite à saisir le pseudo", btn.count() == 1 and btn.first.is_disabled() and page.get_by_text("Entre d'abord ton pseudo").count() == 1)
    ck.check("[lien profond] sans pseudo : aucune requête", net["n"] == 0)
    if page.locator(PSEUDO_INPUT).count():
        page.locator(PSEUDO_INPUT).fill("popeye232")
    page.wait_for_timeout(200)
    ck.check("[lien profond] le bouton s'active dès que le pseudo est saisi", btn.count() == 1 and btn.first.is_enabled())
    ctx.close()


def main(p):
    browser = p.chromium.launch()
    try:
        unit_node()
        archive_mobile_standalone(p, browser)
        archive_mobile_safari(p, browser)
        archive_desktop(browser)
        import_mobile(p, browser)
        import_persist(p, browser)
        import_deeplink(p, browser)
    finally:
        browser.close()


ck.run(main)
