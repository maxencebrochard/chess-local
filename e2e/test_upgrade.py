"""E2E montée de version : les données de l'utilisateur survivent au passage de l'ancien build
déployé au build de ce checkout, et une sauvegarde de l'ancien build se restaure dans le nouveau.

Les parties, Elo, scores de puzzles, erreurs et réglages n'existent que dans l'IndexedDB
`chess-local` et le `localStorage['chess-local-settings']` de la PWA installée sur l'iPhone.
Cette suite est le garde-fou : elle rejoue ce que vit l'iPhone au déploiement.

Volet 1, montée de version sur place :
  l'ANCIEN build (SHA épinglé de la branche gh-pages, extrait de git) est servi sous
  /chess-local/ ; dans un profil navigateur PERSISTANT, de vraies données sont créées PAR
  L'INTERFACE (puzzles, Rush, partie vs Noa, bilan, Apprendre, thème) ; instantané brut de
  l'IndexedDB et des réglages ; puis le NOUVEAU build (E2E_DIST) remplace l'ancien sur le MÊME
  port, le même profil rouvre l'app, le service worker se met à jour, et tout doit être là :
  lignes identiques table par table, réglages identiques, chiffres AFFICHÉS identiques.
Volet 2, sauvegarde :
  « Exporter tout » de l'ancien build, restauré par « Restaurer » du nouveau build dans un
  profil vierge : instantané identique.

Preuve que la suite attrape une perte (elle DOIT alors être rouge), avec une copie mutée du
nouveau build à la place de E2E_DIST :
  E2E_MUTATION=rename-db       npm run test:e2e -- --suite upgrade   # la base Dexie est renommée
  E2E_MUTATION=clear-ratings   npm run test:e2e -- --suite upgrade   # `ratings` vidée à chaque ouverture
  E2E_MUTATION=drop-table      npm run test:e2e -- --suite upgrade   # version(3) qui supprime `learnSessions`
  E2E_MUTATION=clear-settings  npm run test:e2e -- --suite upgrade   # réglages effacés au démarrage

Usage : npm run test:e2e -- --suite upgrade   (prod uniquement : il faut E2E_DIST)
"""
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time

from helpers import Checker, mobile_context, mock_chesscom, settings_json
from run import HOST, ROOT, SUBPATH, free_port, port_is_listening

# Version installée sur l'iPhone : origin/gh-pages@388d3ed (deploy 2026-07-20 17:15), schéma Dexie
# version(2). SHA complet : `scripts/deploy.sh` réécrit la branche à chaque déploiement, ce
# commit ne restera joignable que par son SHA (ou un tag posé dessus).
OLD_SHA = "388d3edae6fd6ec152ccca70b0573d242d612090"
OLD_BUILD_LABEL = "2026-07-20 15:15"  # __BUILD__ de ce déploiement, affiché en bas de /#/import
DB_NAME = "chess-local"
SETTINGS_KEY = "chess-local-settings"
TABLES = ("games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions")
DEFAULT_RATING = 800
# Partie courte avec une gaffe nette (3... Cf6?? laisse le mat du berger) : le bilan en fait une
# ligne de `mistakes` sans attendre le bilan d'une partie de 40 coups.
PGN_BLUNDER = "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7#"
BUILD_RE = re.compile(r"[`\"'](20\d\d-\d\d-\d\d \d\d:\d\d)[`\"']")
RECORD_RE = re.compile(r"Record : (\d+)")
LEADING_INT_RE = re.compile(r"^\s*(\d+)")
MUTATION = os.environ.get("E2E_MUTATION", "")
# Libellés d'interface propres à chaque build : l'ancien garde les siens, le nouveau a les siens.
# Seuls des libellés vivent ici ; les chiffres et les données attendus sont communs aux deux builds.
OLD_LABELS = {"archive_bot": "vs Noa"}
NEW_LABELS = {"archive_bot": "contre Noa"}
# Copie mutée du nouveau build : (motif dans le bundle, remplacement). Chaque motif doit
# s'appliquer exactement une fois, sinon la « preuve » ne prouverait rien.
MUTATIONS = {
    # Une version qui ouvre une autre base : l'ancienne reste sur le disque, l'app ne la voit plus.
    "rename-db": (r"new (\w+)\(`chess-local`\)", r"new \1(`chess-local-v3`)"),
    # Une version qui vide `ratings` à chaque ouverture, dans le hook ready de Dexie (avant toute lecture).
    "clear-ratings": (r"(\w+)=new (\w+)\(`chess-local`\);", r"\1=new \2(`chess-local`);\1.on(`ready`,()=>\1.table(`ratings`).clear());"),
    # Un bloc version(3) qui supprime une table (`null` dans Dexie) : la régression contre laquelle CLAUDE.md met en garde.
    "drop-table": (r"(\w+)=new (\w+)\(`chess-local`\);", r"\1=new \2(`chess-local`);\1.version(3).stores({learnSessions:null});"),
    # Une version qui efface les réglages au démarrage.
    "clear-settings": (r"\A", "localStorage.removeItem(`chess-local-settings`);"),
}

ck = Checker("upgrade")
check = ck.check


def verify(name, cond, detail=""):
    """Comme `check`, le détail n'étant imprimé qu'en cas d'échec."""
    return check(name, cond, "" if cond else detail)


def expect(name, result):
    """`result` = (ok, détail) de `wait_until`."""
    return verify(name, *result)


# ---------------------------------------------------------------------------
# Serveur statique : l'ancien build puis le nouveau, sous /chess-local/, sur le MÊME port.
# ---------------------------------------------------------------------------
class SubpathHandler(http.server.SimpleHTTPRequestHandler):
    """Sert `directory` sous SUBPATH uniquement (comme GitHub Pages), en HTTP/1.0 : pas de
    keep-alive, donc l'arrêt ne laisse aucune connexion pendante entre les deux builds."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".webmanifest": "application/manifest+json",
        ".json": "application/json",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".mp3": "audio/mpeg",
    }

    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if not path.startswith(SUBPATH):
            return os.path.join(self.directory, "__hors_du_sous_chemin__")
        full = os.path.normpath(os.path.join(self.directory, path[len(SUBPATH):]))
        if not full.startswith(os.path.normpath(self.directory)):
            return os.path.join(self.directory, "__hors_du_dossier__")
        return os.path.join(full, "index.html") if os.path.isdir(full) else full

    def end_headers(self):
        # Aucun cache HTTP : le second build a des fichiers de même chemin (sw.js, engine, sons)
        # et le navigateur ne doit jamais en garder un corps périmé. Le précache du service
        # worker, lui, n'est pas concerné : c'est justement lui qu'on teste.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *_args):
        pass


class StaticServer:
    def __init__(self, directory, port):
        self.directory = directory
        self.port = port
        self.srv = None

    @property
    def base(self):
        return f"http://{HOST}:{self.port}{SUBPATH.rstrip('/')}"

    def start(self):
        directory = self.directory
        # Le port est celui de l'origine du profil (IndexedDB et service worker y sont attachés) :
        # s'il n'est pas disponible, on échoue, on n'en choisit jamais un autre.
        self.srv = http.server.ThreadingHTTPServer((HOST, self.port), lambda *a, **k: SubpathHandler(*a, directory=directory, **k))
        self.srv.daemon_threads = True
        self.srv.block_on_close = False  # ne pas attendre un gros fetch en cours (puzzles.json) pour rendre le port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        if self.srv is None:
            return
        self.srv.shutdown()
        self.srv.server_close()
        self.srv = None


# ---------------------------------------------------------------------------
# Builds : l'ancien sort de git, le nouveau vient de e2e/run.py (E2E_DIST), muté sur demande.
# ---------------------------------------------------------------------------
def extract_old_build(dest):
    """Extrait le déploiement épinglé. Objet absent = échec explicite, jamais un passage silencieux."""
    probe = subprocess.run(["git", "-C", ROOT, "cat-file", "-e", f"{OLD_SHA}^{{commit}}"], capture_output=True, text=True)
    if probe.returncode != 0:
        ck.fail("[ancien build] commit introuvable dans ce dépôt",
                f"({OLD_SHA[:7]} : fais `git fetch origin gh-pages` ; si deploy.sh a réécrit la branche depuis, récupère ce commit par un tag posé dessus ou un clone qui l'a encore)")
        return False
    archive = subprocess.run(["git", "-C", ROOT, "archive", "--format=tar", OLD_SHA], capture_output=True)
    if archive.returncode != 0:
        ck.fail("[ancien build] git archive a échoué", f"({archive.stderr.decode(errors='replace')[:200]})")
        return False
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:  # Python sans le paramètre filter
            tar.extractall(dest)
    ok = os.path.exists(os.path.join(dest, "index.html")) and os.path.exists(os.path.join(dest, "sw.js"))
    return check("[ancien build] extrait de git (index.html + sw.js)", ok, f"({OLD_SHA[:7]})")


def bundles_of(dist):
    return sorted(os.path.join(dist, "assets", n) for n in os.listdir(os.path.join(dist, "assets")) if n.endswith(".js"))


def build_label_of(dist):
    """Horodatage __BUILD__ inscrit dans le bundle : ce que /#/import doit afficher une fois le
    service worker à jour."""
    for path in bundles_of(dist):
        with open(path, encoding="utf-8", errors="replace") as f:
            m = BUILD_RE.search(f.read())
        if m:
            return m.group(1)
    return None


def mutate_build(src, dest, mutation):
    """Copie du nouveau build qui perd les données : prouve que la suite voit la perte."""
    if mutation not in MUTATIONS:
        raise RuntimeError(f"E2E_MUTATION inconnue : {mutation} (attendu : {', '.join(MUTATIONS)})")
    pattern, repl = MUTATIONS[mutation]
    shutil.copytree(src, dest)
    total = 0
    for path in bundles_of(dest):
        with open(path, encoding="utf-8") as f:
            code = f.read()
        code, n = re.subn(pattern, repl, code, count=1)
        total += n
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
    if total != 1:
        raise RuntimeError(f"mutation {mutation} : {total} remplacement(s) dans les bundles au lieu de 1")


# ---------------------------------------------------------------------------
# Lecture brute du stockage (pas Dexie : on veut voir ce qu'il y a vraiment sur le disque).
# ---------------------------------------------------------------------------
SNAPSHOT_JS = f"""async () => {{
  const databases = (await indexedDB.databases()).map((d) => ({{ name: d.name, version: d.version }}))
    .sort((a, b) => a.name.localeCompare(b.name))
  const out = {{ databases, db: null, settings: null, settingsRaw: localStorage.getItem({json.dumps(SETTINGS_KEY)}) }}
  try {{ out.settings = JSON.parse(out.settingsRaw) }} catch {{ out.settings = null }}
  // Ne jamais ouvrir sans vérifier : open() sans version CRÉERAIT une base vide.
  if (!databases.some((d) => d.name === {json.dumps(DB_NAME)})) return out
  const db = await new Promise((res, rej) => {{
    const r = indexedDB.open({json.dumps(DB_NAME)})
    r.onsuccess = () => res(r.result)
    r.onerror = () => rej(r.error)
    r.onblocked = () => rej(new Error('open bloqué'))
  }})
  db.onversionchange = () => db.close()  // ne jamais bloquer une montée de version de l'app
  try {{
    const stores = {{}}
    for (const name of [...db.objectStoreNames]) {{
      const st = db.transaction(name, 'readonly').objectStore(name)
      const rows = await new Promise((res, rej) => {{ const r = st.getAll(); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) }})
      const indexes = [...st.indexNames].map((i) => {{ const ix = st.index(i); return {{ name: i, keyPath: ix.keyPath, unique: ix.unique, multiEntry: ix.multiEntry }} }})
      // Même sérialisation que la sauvegarde (JSON) : une clé à `undefined` disparaît des deux côtés.
      stores[name] = {{ keyPath: st.keyPath, autoIncrement: st.autoIncrement, indexes, rows: JSON.parse(JSON.stringify(rows)) }}
    }}
    out.db = {{ version: db.version, stores }}
  }} finally {{
    db.close()
  }}
  return out
}}"""


def snapshot(page):
    return page.evaluate(SNAPSHOT_JS)


def same(a, b):
    """Égalité stricte sur les types aussi (`True` n'est pas `1`, `null` n'est pas `0`)."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def row_key(store, row):
    kp = store["keyPath"]
    return json.dumps(row.get(kp) if isinstance(kp, str) else [row.get(k) for k in kp])


def compare_rows(tag, name, rows_before, rows_after, keypath):
    """Chaque ligne d'avant, retrouvée par sa clé, avec chacun de ses champs identique. Les
    champs ajoutés sont tolérés (migration additive) et cités."""
    store = {"keyPath": keypath}
    verify(f"{tag} table {name} : {len(rows_before)} ligne(s) avant, autant après", len(rows_after) == len(rows_before), f"(après : {len(rows_after)})")
    by_key = {row_key(store, r): r for r in rows_after}
    lost, changed, extra = [], [], set()
    for rb in rows_before:
        ra = by_key.get(row_key(store, rb))
        if ra is None:
            lost.append(row_key(store, rb))
            continue
        diff = [k for k, v in rb.items() if not same(ra.get(k), v)]
        if diff:
            changed.append(f"{row_key(store, rb)}:{diff}")
        extra.update(k for k in ra if k not in rb)
    note = f" (champs ajoutés tolérés : {sorted(extra)})" if extra else ""
    verify(f"{tag} table {name} : chaque ligne d'avant retrouvée à l'identique{note}", not lost and not changed,
           f"(perdues : {lost[:5]}, modifiées : {changed[:5]})")


def compare_settings(tag, before, after):
    sa = after.get("settings") if isinstance(after, dict) else None
    if not check(f"{tag} réglages présents ({SETTINGS_KEY})", isinstance(sa, dict) and isinstance(sa.get("state"), dict), f"({after.get('settingsRaw')!r})"):
        return
    diff = {k: (v, sa["state"].get(k)) for k, v in before["settings"]["state"].items() if not same(sa["state"].get(k), v)}
    verify(f"{tag} réglages : chaque valeur d'avant conservée", not diff, f"({diff})")


def compare_snapshots(tag, before, after):
    """Base, tables, index, lignes et réglages d'avant se retrouvent après. Les ajouts (version
    supérieure, store, index ou champ nouveau) sont tolérés : une migration est additive."""
    names_before = [d["name"] for d in before["databases"]]
    names_after = [d["name"] for d in after["databases"]]
    verify(f"{tag} mêmes bases IndexedDB ({', '.join(names_before)})", names_before == names_after, f"(après : {names_after})")
    if not before["db"]:
        ck.fail(f"{tag} instantané d'avant sans base {DB_NAME} : rien à comparer")
        return
    if not check(f"{tag} base {DB_NAME} présente", bool(after["db"]), f"(bases : {names_after})"):
        return
    verify(f"{tag} version de la base conservée ou montée", after["db"]["version"] >= before["db"]["version"],
           f"({before['db']['version']} -> {after['db']['version']})")
    for name, sb in before["db"]["stores"].items():
        sa = after["db"]["stores"].get(name)
        if not check(f"{tag} table {name} présente", sa is not None):
            continue
        verify(f"{tag} table {name} : clé primaire et autoIncrement inchangés",
               same(sa["keyPath"], sb["keyPath"]) and sa["autoIncrement"] == sb["autoIncrement"],
               f"({sb['keyPath']}/{sb['autoIncrement']} -> {sa['keyPath']}/{sa['autoIncrement']})")
        idx_after = {i["name"]: i for i in sa["indexes"]}
        missing = [i["name"] for i in sb["indexes"] if not same(idx_after.get(i["name"]), i)]
        verify(f"{tag} table {name} : index d'avant intacts", not missing, f"(altérés ou absents : {missing})")
        compare_rows(tag, name, sb["rows"], sa["rows"], sb["keyPath"])
    compare_settings(tag, before, after)


def compare_backup(tag, before, backup):
    """Le JSON d'« Exporter tout » (lecture par Dexie, donc par l'app) contre l'instantané brut."""
    for name in TABLES:
        rows = backup.get(name)
        if not check(f"{tag} export : table {name} présente", isinstance(rows, list)):
            continue
        compare_rows(f"{tag} export :", name, before["db"]["stores"].get(name, {}).get("rows", []), rows, before["db"]["stores"].get(name, {}).get("keyPath", "id"))
    verify(f"{tag} export : réglages identiques", backup.get("settings") == before["settingsRaw"], f"({backup.get('settings')!r})")


# ---------------------------------------------------------------------------
# Ce que l'utilisateur VOIT : les chiffres affichés doivent refléter l'instantané.
# ---------------------------------------------------------------------------
def expectations(snap):
    stores = snap["db"]["stores"] if snap["db"] else {}
    rows = lambda t: stores.get(t, {}).get("rows", [])  # noqa: E731
    ratings = {r["key"]: r for r in rows("ratings")}
    rating = lambda k: ratings[k]["value"] if k in ratings else DEFAULT_RATING  # noqa: E731
    attempts = rows("puzzleAttempts")
    games = rows("games")
    bot_games = [g for g in games if g["mode"] == "bot"]
    wins = sum(1 for g in bot_games if g["result"] != "1/2-1/2" and (g["result"] == "1-0") == (g["playerColor"] == "w"))
    draws = sum(1 for g in bot_games if g["result"] == "1/2-1/2")
    records = {m: max([s["score"] for s in rows("rushScores") if s["mode"] == m], default=0) for m in ("3min", "5min", "survival")}
    return {
        "puzzle": rating("puzzle"), "rapid": rating("rapid"), "blitz": rating("blitz"), "bullet": rating("bullet"),
        "learn-tactic": rating("learn-tactic"),
        "solved": sum(1 for a in attempts if a["success"] is True), "attempts": len(attempts),
        "games": len(games), "wins": wins, "draws": draws, "losses": len(bot_games) - wins - draws,
        "records": records, "pending_mistakes": sum(1 for m in rows("mistakes") if m["solved"] == 0),
    }


def wait_until(page, fn, timeout_ms=8000, step_ms=250):
    """Attend qu'une lecture de page satisfasse `fn` (les pages lisent Dexie après le premier
    rendu : lire trop tôt montrerait les valeurs par défaut). Retourne la dernière lecture."""
    deadline = time.time() + timeout_ms / 1000
    last = (False, "(jamais évalué)")
    while True:
        try:
            last = fn()
            if last[0]:
                return last
        except Exception as e:  # locator disparu entre deux rendus
            last = (False, f"({type(e).__name__}: {str(e)[:120]})")
        if time.time() > deadline:
            return last
        page.wait_for_timeout(step_ms)


def cards_of(cards):
    """Cartes « icône / valeur / libellé » : {libellé: valeur}."""
    got = {}
    for card in cards.all():
        lines = [l.strip() for l in card.inner_text().split("\n") if l.strip()]
        if len(lines) >= 3:
            got[lines[2].split(" ·")[0]] = lines[1]
    return got


def displayed_ok(tag, page, base, exp, labels):
    """Une visite de chaque page qui affiche des données, un check par chiffre attendu.
    `labels` : libellés du build affiché (OLD_LABELS ou NEW_LABELS)."""
    def has_all(needles):
        def fn():
            text = page.locator("main").first.inner_text()
            missing = [n for n in needles if n not in text]
            return (not missing, f"(manque {missing} dans « {' | '.join(text.split(chr(10))[:12])[:300]} »)")
        return fn

    def cards_match(cards, want):
        def fn():
            got = cards_of(cards)
            return (got == want, f"(affiché {got}, attendu {want})")
        return fn

    elo_cards = {"Rapide": str(exp["rapid"]), "Blitz": str(exp["blitz"]), "Bullet": str(exp["bullet"]), "Puzzles": str(exp["puzzle"])}

    page.goto(f"{base}/#/")
    ck.appears(f"{tag} accueil chargé", page, "text=Résolvez !", timeout=15000)
    expect(f"{tag} accueil : résolus, classement puzzles, nombre de parties",
           wait_until(page, has_all([f"{exp['solved']} résolus · classement {exp['puzzle']}", f"{exp['games']} partie"])))
    expect(f"{tag} accueil : 4 cartes Elo", wait_until(page, cards_match(page.locator("main a[href='#/stats']"), elo_cards)))

    page.goto(f"{base}/#/puzzles")
    ck.appears(f"{tag} puzzles chargés", page, "text=Classement puzzles", timeout=45000)
    shown = lambda: page.locator("main .text-3xl").first.inner_text()  # noqa: E731
    expect(f"{tag} puzzles : Elo affiché = {exp['puzzle']}",
           wait_until(page, lambda: (LEADING_INT_RE.match(shown()) is not None and int(LEADING_INT_RE.match(shown()).group(1)) == exp["puzzle"], f"(affiché {shown()!r})")))

    page.goto(f"{base}/#/rush")
    ck.appears(f"{tag} rush chargé", page, "text=Puzzle Rush", timeout=15000)
    want = [str(exp["records"][m]) for m in ("3min", "5min", "survival")]
    records = lambda: RECORD_RE.findall(page.locator("main").inner_text())  # noqa: E731
    expect(f"{tag} rush : records 3 min / 5 min / survie = {'/'.join(want)}", wait_until(page, lambda: (records() == want, f"(affiché {records()})")))

    page.goto(f"{base}/#/archive")
    ck.appears(f"{tag} archive chargée", page, "main h1:has-text('Archive')", timeout=15000)
    expect(f"{tag} archive : compteur et partie contre Noa listée",
           wait_until(page, has_all([f"Archive ({exp['games']})"] + ([labels["archive_bot"]] if exp["games"] else []))))

    page.goto(f"{base}/#/stats")
    ck.appears(f"{tag} stats chargées", page, "text=Statistiques", timeout=15000)
    expect(f"{tag} stats : bilan parties et puzzles",
           wait_until(page, has_all([f"{exp['wins']} gagnées", f"{exp['draws']} nulles", f"{exp['losses']} perdues",
                                     f"{exp['solved']} résolus / {exp['attempts']} tentés", f"Puzzles · {exp['attempts']} essais"])))
    expect(f"{tag} stats : 4 cartes Elo", wait_until(page, cards_match(page.locator("main .grid").first.locator("> div"), elo_cards)))

    page.goto(f"{base}/#/apprendre")
    ck.appears(f"{tag} apprendre chargé", page, "text=Séance", timeout=15000)

    def learn():
        got = cards_of(page.locator("main .grid").first.locator("> div"))
        btn = page.locator("button", has_text="Mes erreurs")
        pending = re.sub(r"\D", "", btn.inner_text())
        ok = got.get("Tactiques") == str(exp["learn-tactic"]) and pending == str(exp["pending_mistakes"]) \
            and btn.is_enabled() == (exp["pending_mistakes"] > 0)
        return (ok, f"(pastilles {got}, Mes erreurs {pending!r} actif={btn.is_enabled()}, attendu {exp['learn-tactic']} / {exp['pending_mistakes']})")
    expect(f"{tag} apprendre : Elo tactiques et compteur Mes erreurs", wait_until(page, learn))


def displayed_build(page, base, reload=True):
    """Horodatage en bas de /#/import, après un VRAI chargement de document (goto vers la même
    URL à hash ne rechargerait rien). `reload=False` pour le premier document d'un profil
    rouvert : le goto suffit, et un reload pourrait déjà être servi par le service worker
    suivant (skipWaiting + clientsClaim)."""
    page.goto(f"{base}/#/import")
    if reload:
        page.reload()
    loc = page.locator("main p", has_text="build ")
    try:
        loc.wait_for(timeout=15000)
        return loc.inner_text().replace("build", "").strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Jouer un puzzle par l'interface. La solution est lue dans les props React du PuzzlePlayer
# (walk du fiber depuis l'échiquier) : le seul endroit où elle existe côté page.
# ---------------------------------------------------------------------------
FIBER_JS = """() => {
  const el = document.querySelector("[id^='chessboard-']")
  if (!el) return null
  const key = Object.keys(el).find((k) => k.startsWith('__reactFiber$'))
  let f = key ? el[key] : null
  const out = { board: null, puzzle: null }
  for (let hops = 0; f && hops < 80; hops++, f = f.return) {
    const p = f.memoizedProps
    if (!p) continue
    if (!out.board && typeof p.fen === 'string' && p.onMove) out.board = { fen: p.fen, movable: p.movableColor ?? null }
    if (p.puzzle && Array.isArray(p.puzzle.moves)) { out.puzzle = { id: p.puzzle.id, moves: p.puzzle.moves, fen: p.puzzle.fen }; break }
  }
  return out.puzzle ? out : null
}"""
LEGAL_TARGETS_JS = """() => {
  const has = (root, pred) => [root, ...root.querySelectorAll('*')].some(pred)
  return [...document.querySelectorAll('[data-square]')]
    .filter((e) => has(e, (n) => getComputedStyle(n).background.includes('rgba(0, 0, 0, 0.34)')))
    .map((e) => e.getAttribute('data-square'))
}"""
OWN_PIECES_JS = """(c) => [...document.querySelectorAll('[data-square] [data-piece]')]
  .filter((e) => e.getAttribute('data-piece').startsWith(c))
  .map((e) => e.closest('[data-square]').getAttribute('data-square'))"""


def click_sq(page, square):
    page.locator(f"[data-square='{square}']").first.click()


def read_puzzle(page):
    """Attend l'échiquier, la solution et le coup d'amorce joué (la position n'est plus la FEN de départ)."""
    deadline = time.time() + 15
    while time.time() < deadline:
        info = page.evaluate(FIBER_JS)
        if info and info["board"] and info["board"]["fen"] != info["puzzle"]["fen"]:
            return info
        page.wait_for_timeout(200)
    raise RuntimeError("puzzle illisible (props React introuvables ou coup d'amorce jamais joué)")


def play_solution(page, info):
    """Joue tous les coups du joueur. Retourne False si un coup promeut (boîte de promotion) :
    on passe alors ce puzzle plutôt que de dépendre de son UI."""
    moves = info["puzzle"]["moves"]
    if any(len(m) > 4 for m in moves[1::2]):
        return False
    for i in range(1, len(moves), 2):
        click_sq(page, moves[i][:2])
        page.wait_for_timeout(150)
        click_sq(page, moves[i][2:4])
        page.wait_for_timeout(700)  # réponse adverse automatique
    return True


def play_wrong_move(page, info):
    """Un coup légal qui n'est pas la solution. Retourne le coup joué, ou None."""
    expected = info["puzzle"]["moves"][1]
    own = [expected[:2]] + [sq for sq in page.evaluate(OWN_PIECES_JS, info["board"]["movable"] or "w") if sq != expected[:2]]
    for frm in own:
        click_sq(page, frm)
        page.wait_for_timeout(150)
        targets = [t for t in page.evaluate(LEGAL_TARGETS_JS) if frm + t != expected[:4]]
        if targets:
            click_sq(page, targets[0])
            page.wait_for_timeout(500)
            return frm + targets[0]
        click_sq(page, frm)  # désélection
        page.wait_for_timeout(100)
    return None


def puzzle_outcome(page, timeout_ms=8000):
    ok, _ = wait_until(page, lambda: (page.locator("text=Résolu").count() > 0 or page.locator("text=Raté").count() > 0, ""), timeout_ms)
    if not ok:
        return None
    return "solved" if page.locator("text=Résolu").count() else "failed"


def puzzles_phase(page, base):
    """Puzzles : des réussites et un raté, jusqu'à un Elo différent de la valeur par défaut (800),
    sinon l'affichage ne prouverait rien."""
    page.goto(f"{base}/#/puzzles")
    ck.appears("[ancien] puzzles chargés", page, "text=Classement puzzles", timeout=45000)
    outcomes, rating = [], DEFAULT_RATING
    shown = lambda: page.locator("main .text-3xl").first.inner_text()  # noqa: E731
    for attempt in range(8):
        info = read_puzzle(page)
        # Un raté voulu dès le 2e puzzle, et tant qu'aucun raté n'est acquis (un mauvais coup qui
        # mate compte comme réussi).
        want_fail = attempt >= 1 and "failed" not in outcomes
        if want_fail:
            if play_wrong_move(page, info) is None:
                page.click("button:has-text('Passer')")
                continue
        elif not play_solution(page, info):
            page.click("button:has-text('Passer')")
            continue
        outcome = puzzle_outcome(page)
        if outcome is None:
            ck.fail("[ancien] puzzle sans verdict après le coup", f"(puzzle {info['puzzle']['id']}, {'raté voulu' if want_fail else 'solution jouée'})")
            page.click("button:has-text('Passer')")
            continue
        outcomes.append(outcome)
        # Le delta à côté de l'Elo n'apparaît qu'une fois applyRating + puzzleAttempts.add terminés.
        wait_until(page, lambda: (re.search(r"[+-]\d+", shown()) is not None, ""))
        rating = int(LEADING_INT_RE.match(shown()).group(1))
        page.click("button:has-text('Suivant')")
        page.wait_for_timeout(600)
        if "solved" in outcomes and "failed" in outcomes and rating != DEFAULT_RATING:
            break
    check("[ancien] puzzles : au moins un résolu et un raté", "solved" in outcomes and "failed" in outcomes, f"({outcomes})")
    check("[ancien] puzzles : Elo puzzles sorti de la valeur par défaut", rating != DEFAULT_RATING, f"({rating})")


def rush_phase(page, base):
    page.goto(f"{base}/#/rush")
    ck.appears("[ancien] rush chargé", page, "text=Puzzle Rush", timeout=15000)
    btn = page.locator("main button", has_text="3 minutes")
    wait_until(page, lambda: (btn.is_enabled(), ""), 45000)
    btn.click()
    solved = False
    for _ in range(4):
        info = read_puzzle(page)
        if play_solution(page, info):
            solved = wait_until(page, lambda: (page.locator("main .text-2xl.font-black").first.inner_text().strip() == "1", ""), 5000)[0]
            if solved:
                break
        else:
            play_wrong_move(page, info)  # promotion : on sacrifie ce puzzle (une croix), le suivant arrive
            page.wait_for_timeout(800)
    check("[ancien] rush : un puzzle résolu (score 1)", solved)
    page.locator("main button", has_text="✕").click()
    ck.appears("[ancien] rush : arrêt → écran de fin", page, "text=puzzles résolus", timeout=10000)
    page.click("button:has-text('Menu')")
    expect("[ancien] rush : record 1 relu depuis la base dans le menu",
           wait_until(page, lambda: ("Record : 1" in page.locator("main").inner_text(), "(record 1 absent du menu)")))


def game_phase(page, base):
    page.goto(f"{base}/#/jouer")
    ck.appears("[ancien] jouer chargé", page, "text=Adversaire", timeout=15000)
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text="Blancs").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(900)
    click_sq(page, "e2")
    page.wait_for_timeout(200)
    click_sq(page, "e4")
    expect("[ancien] partie vs Noa : e4 puis réponse du bot", wait_until(page, lambda: (page.locator("main [data-current]").count() >= 2, "(pas de réponse du bot)"), 20000))
    page.click("button:has-text('Abandonner')")
    ck.appears("[ancien] partie vs Noa : abandon → modale de fin", page, "text=gagnent", timeout=10000)
    check("[ancien] partie classée (delta de classement affiché)", "Classement" in page.locator("div.fixed").inner_text())
    page.locator("div.fixed button", has_text="Nouvelle partie").click()
    page.wait_for_timeout(300)


def review_phase(page, base):
    page.goto(f"{base}/#/analyse")
    ck.appears("[ancien] analyse chargée", page, "main button:has-text('Options')", timeout=15000)
    page.locator("main button", has_text="Options").click()
    page.click("text=Importer PGN ou FEN")
    page.fill("textarea", PGN_BLUNDER)
    page.click("button:has-text('Charger')")
    page.wait_for_timeout(400)
    page.get_by_role("button", name="★ Bilan").click()
    ck.appears("[ancien] bilan terminé (résumé affiché)", page, "text=Démarrer le bilan", timeout=180000)
    page.click("header button:has-text('✕')")
    # recordMistakes tourne après l'affichage du résumé : la preuve d'écriture, c'est Apprendre.
    page.goto(f"{base}/#/apprendre")
    btn = page.locator("button", has_text="Mes erreurs")
    expect("[ancien] bilan : « Mes erreurs » alimenté", wait_until(page, lambda: (btn.is_enabled(), "(bouton toujours grisé)"), 20000))


def learn_phase(page, base):
    page.goto(f"{base}/#/apprendre")
    ck.appears("[ancien] apprendre chargé", page, "text=Séance", timeout=15000)
    page.locator("main button", has_text="Tactiques").click()
    ck.appears("[ancien] apprendre : leçon tactique", page, "button:has-text(\"C'est parti\")", timeout=30000)
    page.get_by_role("button", name="C'est parti").click()
    info = read_puzzle(page)
    if not play_solution(page, info):
        play_wrong_move(page, info)  # promotion : n'importe quel coup donne un verdict, donc une séance enregistrée
    expect("[ancien] apprendre : verdict de l'exercice (séance enregistrée)",
           wait_until(page, lambda: (page.locator("text=Réussi").count() > 0 or page.locator("text=Raté").count() > 0, "(pas de verdict)"), 15000))
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(300)


def theme_phase(page, base):
    page.goto(f"{base}/#/stats")
    ck.appears("[ancien] stats chargées", page, "button[title='Bois']", timeout=15000)
    page.locator("button[title='Bois']").click()
    expect("[ancien] thème Bois enregistré dans les réglages",
           wait_until(page, lambda: ('"themeId":"brown"' in (page.evaluate(f"() => localStorage.getItem({json.dumps(SETTINGS_KEY)})") or ""), "(themeId brown absent)")))


def export_backup(tag, page, base, dest):
    """Stats → Exporter tout, téléchargement intercepté et copié hors du contexte (Playwright
    supprime ses fichiers temporaires à la fermeture du contexte)."""
    page.goto(f"{base}/#/stats")
    ck.appears(f"{tag} stats : bouton Exporter tout", page, "button:has-text('Exporter tout')", timeout=15000)
    with page.expect_download(timeout=15000) as dl:
        page.click("button:has-text('Exporter tout')")
    dl.value.save_as(dest)
    with open(dest, encoding="utf-8") as f:
        data = json.load(f)
    check(f"{tag} sauvegarde exportée (JSON ChessLocal avec toutes les tables)",
          data.get("_app") == "chess-local" and all(isinstance(data.get(t), list) for t in TABLES), f"({sorted(data)})")
    return data


# ---------------------------------------------------------------------------
# Contextes
# ---------------------------------------------------------------------------
def open_profile(p, profile_dir, seed):
    """iPhone 14 Pro en PWA installée, profil persistant : `mobile_context` ne couvre pas ce cas.
    `seed` : réglages E2E semés à la PREMIÈRE ouverture seulement ; les resemer à la réouverture
    masquerait un build qui les efface."""
    opts = dict(p.devices["iPhone 14 Pro"])
    opts.pop("default_browser_type", None)
    opts["viewport"] = {"width": 393, "height": 852}
    for attempt in range(3):
        try:
            ctx = p.chromium.launch_persistent_context(profile_dir, headless=True, accept_downloads=True, **opts)
            break
        except Exception:  # verrou du profil pas encore relâché par le Chromium précédent
            if attempt == 2:
                raise
            time.sleep(1)
    ck.watch(ctx)
    if seed:
        ctx.add_init_script(
            f"try {{ if (!localStorage.getItem({json.dumps(SETTINGS_KEY)})) "
            f"localStorage.setItem({json.dumps(SETTINGS_KEY)}, {json.dumps(settings_json())}) }} catch {{}}"
        )
    mock_chesscom(ctx, ck)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)
    return ctx, page


def phase(name, fn, *args):
    """Une phase qui casse (sélecteur absent, délai) donne un échec nommé et la suite continue :
    les phases suivantes gardent leur valeur de diagnostic."""
    t0 = time.time()
    try:
        result = fn(*args)
    except Exception as e:
        ck.fail(f"[phase] {name} interrompue", f"({type(e).__name__}: {str(e)[:200]})")
        result = None
    print(f"[upgrade] {name} : {time.time() - t0:.0f} s", flush=True)
    return result


def wait_for_new_build(page, base, expected):
    """Le SW de l'ancien build sert encore l'ancienne coquille ; on force la vérification de
    mise à jour et on recharge jusqu'à voir le __BUILD__ du nouveau bundle."""
    deadline = time.time() + 90
    seen = None
    while time.time() < deadline:
        page.evaluate("async () => { const r = await navigator.serviceWorker.getRegistration(); if (r) await r.update() }")
        page.wait_for_timeout(1000)
        seen = displayed_build(page, base)
        if seen == expected:
            return seen
    return seen


def cached_paths(page):
    return page.evaluate("async () => { const out = []; for (const k of await caches.keys()) for (const r of await (await caches.open(k)).keys()) out.push(new URL(r.url).pathname); return out }")


def suite(p):
    dist = os.environ.get("E2E_DIST")
    if not dist:
        ck.fail("[upgrade] E2E_DIST absent : lance cette suite par `npm run test:e2e -- --suite upgrade`")
        return
    work = tempfile.mkdtemp(prefix="chesslocal-upgrade-")
    old_dir = os.path.join(work, "old")
    profile = os.path.join(work, "profile")
    backup_path = os.path.join(work, "sauvegarde-ancien-build.json")
    server = ctx = browser = None
    try:
        if not extract_old_build(old_dir):
            return
        new_dir = dist
        if MUTATION:
            print("!" * 60 + f"\n[upgrade] MUTATION {MUTATION} : le nouveau build perd des données, la suite DOIT être rouge\n" + "!" * 60, flush=True)
            new_dir = os.path.join(work, "mutated")
            mutate_build(dist, new_dir, MUTATION)
        new_label = build_label_of(dist)
        check("[nouveau build] horodatage __BUILD__ lisible dans le bundle", bool(new_label) and new_label != OLD_BUILD_LABEL, f"({new_label})")
        old_assets = sorted(os.listdir(os.path.join(old_dir, "assets")))
        new_assets = sorted(os.listdir(os.path.join(dist, "assets")))

        port = free_port()
        server = StaticServer(old_dir, port)
        server.start()
        base = server.base
        t_start = time.time()

        # ---------- Volet 1a : l'ancien build, de vraies données par l'interface ----------
        ctx, page = open_profile(p, profile, seed=True)
        seen = displayed_build(page, base)
        check("[ancien] /#/import affiche le build de l'ancien déploiement", seen == OLD_BUILD_LABEL, f"({seen})")
        sw = page.evaluate("async () => { const r = await navigator.serviceWorker.ready; return { scope: r.scope, active: !!r.active } }")
        check("[ancien] service worker installé sous le sous-chemin", bool(sw) and sw["active"] and sw["scope"].endswith(SUBPATH), f"({sw})")
        phase("puzzles", puzzles_phase, page, base)
        phase("rush", rush_phase, page, base)
        phase("partie vs Noa", game_phase, page, base)
        phase("bilan", review_phase, page, base)
        phase("apprendre", learn_phase, page, base)
        phase("thème", theme_phase, page, base)
        backup = phase("export", export_backup, "[ancien]", page, base, backup_path)

        # Instantané dos à dos avec l'export : aucune écriture entre les deux.
        before = snapshot(page)
        stores = before["db"]["stores"] if before["db"] else {}
        counts = {t: len(s["rows"]) for t, s in stores.items()}
        print(f"[upgrade] instantané avant : {counts}, réglages {before['settings'] and before['settings'].get('state')}", flush=True)
        for t in TABLES:
            check(f"[ancien] table {t} alimentée avant la montée de version", counts.get(t, 0) > 0, f"({counts.get(t, 0)} ligne(s))")
        at_default = [r["key"] for r in stores.get("ratings", {}).get("rows", []) if r["value"] == DEFAULT_RATING]
        check("[ancien] aucun Elo à sa valeur par défaut (sinon l'affichage ne prouverait rien)", not at_default, f"({at_default})")
        if backup:
            compare_backup("[ancien]", before, backup)
        exp = expectations(before)
        phase("affichage avant", displayed_ok, "[ancien]", page, base, exp, OLD_LABELS)
        ctx.close()  # la PWA est quittée
        print(f"[upgrade] ancien build : {time.time() - t_start:.0f} s", flush=True)

        # ---------- Volet 1b : le nouveau build remplace l'ancien, même origine ----------
        server.stop()
        check("[bascule] ancien serveur arrêté, port rendu", not port_is_listening(port), f"(port {port})")
        server = StaticServer(new_dir, port)
        server.start()
        t_up = time.time()
        ctx, page = open_profile(p, profile, seed=False)
        # Premier lancement : l'ancien service worker sert encore l'ancienne coquille depuis son
        # cache. C'est bien le chemin de mise à jour d'une PWA installée qu'on emprunte. Sans
        # reload : ce goto déclenche la vérification de mise à jour, et un second document
        # pourrait déjà tomber sur le nouveau service worker (skipWaiting + clientsClaim).
        seen = displayed_build(page, base, reload=False)
        check("[nouveau] premier lancement servi par l'ancien service worker (ancien build affiché)", seen == OLD_BUILD_LABEL, f"({seen})")
        seen = wait_for_new_build(page, base, new_label)
        check("[nouveau] service worker mis à jour : /#/import affiche le nouveau build", seen == new_label, f"(affiché {seen}, attendu {new_label}, après {time.time() - t_up:.0f} s)")
        check("[nouveau] page contrôlée par le service worker", page.evaluate("() => !!navigator.serviceWorker.controller"))
        cached = cached_paths(page)
        check("[nouveau] précache : assets du nouveau build présents", all(f"{SUBPATH}assets/{n}" in cached for n in new_assets), f"({[c for c in cached if '/assets/' in c]})")
        check("[nouveau] précache : assets de l'ancien build purgés (nouveau service worker activé)", not any(f"{SUBPATH}assets/{n}" in cached for n in old_assets), f"({[c for c in cached if '/assets/' in c]})")
        # Instantané tout de suite : la mise à jour du service worker seule ne doit rien toucher.
        after = snapshot(page)
        compare_snapshots("[montée de version, avant usage]", before, after)
        phase("affichage après", displayed_ok, "[nouveau]", page, base, exp, NEW_LABELS)
        # Puis après usage : Dexie n'ouvre la base qu'à la première requête, donc un bloc
        # version(n) destructeur ou une purge au démarrage ne se voient qu'ici.
        compare_snapshots("[montée de version, après usage]", before, snapshot(page))
        # Lecture par l'app elle-même (Dexie) : ce que le nouveau build exporte doit être ce qu'il y avait.
        exported = phase("export après", export_backup, "[nouveau]", page, base, os.path.join(work, "sauvegarde-nouveau-build.json"))
        if exported:
            compare_backup("[nouveau]", before, exported)
        ctx.close()
        print(f"[upgrade] montée de version : {time.time() - t_up:.0f} s", flush=True)

        # ---------- Volet 2 : sauvegarde de l'ancien build restaurée dans le nouveau, profil vierge ----------
        t_restore = time.time()
        if backup:
            browser = p.chromium.launch(headless=True)
            ctx = mobile_context(p, browser, ck, standalone=True)
            page = ctx.new_page()
            page.set_default_timeout(15000)
            page.goto(f"{base}/#/stats")
            ck.appears("[restauration] nouveau build, profil vierge : bouton Restaurer", page, "button:has-text('Restaurer')", timeout=15000)
            page.set_input_files("input[type=file]", backup_path)
            # Nouveau flux : le fichier est d'abord validé, puis une feuille demande confirmation
            # avant d'écraser la base. Profil vierge : elle doit annoncer que rien ne sera perdu.
            # Sans feuille, pas de clic : les checks suivants échouent proprement au lieu d'une exception.
            if ck.appears("[restauration] feuille de confirmation", page, "[data-testid=restore-sheet]", timeout=15000):
                ck.appears("[restauration] feuille : base vide, rien ne sera perdu", page,
                           "[data-testid=restore-sheet] >> text=Ta base est vide", timeout=5000)
                page.click("[data-testid=restore-confirm]")
            ck.appears("[restauration] message de fin de restauration", page,
                       "[data-testid=backup-msg][data-kind=success] >> text=Sauvegarde restaurée", timeout=15000)
            page.reload()
            ck.appears("[restauration] app rechargée", page, "text=Statistiques", timeout=15000)
            restored = snapshot(page)
            compare_snapshots("[restauration]", before, restored)
            phase("affichage après restauration", displayed_ok, "[restauration]", page, base, exp, NEW_LABELS)
            ctx.close()
            browser.close()
        else:
            ck.fail("[restauration] pas de sauvegarde exportée par l'ancien build : volet 2 impossible")
        print(f"[upgrade] restauration : {time.time() - t_restore:.0f} s, total {time.time() - t_start:.0f} s", flush=True)
    finally:
        # Contexte et navigateur d'abord : sinon Chromium tient encore le profil pendant le rmtree.
        for closable in (ctx, browser):
            try:
                if closable is not None:
                    closable.close()
            except Exception:
                pass
        if server:
            server.stop()
        shutil.rmtree(work, ignore_errors=True)


ck.run(suite)
