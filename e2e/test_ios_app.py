"""App iOS (coquille Capacitor, docs/ios-app.md) : haptique native, assets servis avec un statut 0 et
migration des données.

Le runtime natif est simulé par `CAPACITOR_IOS` (contrat de la native-bridge de Capacitor) ; sans
lui, c'est la PWA, qui doit rester strictement identique : ni `window.Capacitor`, ni chunk
haptique chargé, ni carte de migration.
Usage : npm run test:e2e -- --suite ios_app
"""
import json
import os
import tempfile

from helpers import (
    BASE,
    CAPACITOR_IOS,
    HOLD_BESTMOVE,
    ROOT_DIR,
    SOUND_FILES,
    WEBKIT_AUDIO,
    Checker,
    desktop_context,
    drag_piece,
    haptic_log,
    mobile_context,
    piece_on,
    shot,
    sound_log,
    sounds_heard,
    sq_center,
    tap_move,
    tap_square,
    wait_sounds_ready,
)

ck = Checker("ios_app")
check = ck.check

STORES = 7
CARD = "[data-testid=native-migration]"
LIFT, MOVE, CAPTURE = "impact:LIGHT", "impact:MEDIUM", "impact:HEAVY"
REFUSE = "notification:ERROR"
PREMOVE = ["selectionStart", "selectionChanged", "selectionEnd"]

# Chromium de bureau expose parfois navigator.share : l'export passe alors par le téléchargement.
NO_SHARE = "try { delete Navigator.prototype.share; delete Navigator.prototype.canShare } catch {}"

SEED = {
    "games": [
        {"id": 1, "pgn": "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0", "date": 1760000000000, "mode": "bot", "result": "1-0", "playerColor": "w"},
        {"id": 2, "pgn": "1. d4 d5 1/2-1/2", "date": 1760100000000, "mode": "bot", "result": "1/2-1/2", "playerColor": "b"},
    ],
    "ratings": [{"key": "blitz", "value": 1432, "games": 2}, {"key": "puzzle", "value": 1615, "games": 3}],
    "puzzleAttempts": [
        {"id": 1, "puzzleId": "00008", "date": 1760000000000, "success": True, "rating": 1500},
        {"id": 2, "puzzleId": "0000D", "date": 1760000100000, "success": False, "rating": 1600},
    ],
    "learnSessions": [{"id": 1, "domain": "course", "itemId": "finales:roi-pion", "date": 1760000200000, "success": True}],
}


def chunk_requests(ctx):
    """URLs demandées du chunk natif (`assets/native-*.js` : @capacitor/* et le pilote haptique),
    par la page ou par le service worker."""
    seen = []
    # Prod : assets/native-*.js ; dev : /src/lib/nativeHaptics.ts et .vite/deps/@capacitor_*.
    marks = ("/assets/native-", "nativeHaptics", "@capacitor", "capacitor_")
    ctx.on("request", lambda r: seen.append(r.url) if any(m in r.url for m in marks) else None)
    return seen


def play_visible(page, label):
    # Le viewport seul ne suffit pas : la navigation basse peut recouvrir le bas du bouton.
    bounds = page.get_by_role("button", name="Jouer").evaluate("""el => {
      const r = el.getBoundingClientRect()
      const visible = [r.top + 1, r.bottom - 1].every(y =>
        el.contains(document.elementFromPoint(r.x + r.width / 2, y)))
      return { top: r.top, bottom: r.bottom, visible }
    }""")
    check(label, bounds["visible"], str(bounds))


def since(page, start):
    page.wait_for_timeout(250)
    return (haptic_log(page) or [])[start:]


def mark(page):
    return len(haptic_log(page) or [])


def open_analysis(page, fen=None):
    page.goto(f"{BASE}/#/")
    if fen:
        page.evaluate("(fen) => history.replaceState({ usr: { fen }, key: 'e2e', idx: 0 }, '', '#/analyse')", fen)
        page.reload()
    else:
        page.goto(f"{BASE}/#/analyse")
    return ck.appears("analyse : plateau", page, "[data-square=e2] [data-piece]" if not fen else "[data-square=a7] [data-piece]")


def wait_schema(page, tries=60):
    for _ in range(tries):
        n = page.evaluate("""() => new Promise((res) => indexedDB.databases().then((list) => {
          if (!list.some((d) => d.name === 'chess-local')) return res(0)
          const r = indexedDB.open('chess-local')
          r.onsuccess = () => { const n = r.result.objectStoreNames.length; r.result.close(); res(n) }
          r.onerror = () => res(-1)
        }))""")
        if n == STORES:
            return True
        page.wait_for_timeout(250)
    return False


def seed(page, data):
    page.evaluate("""async (data) => {
      const db = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
      const tx = db.transaction(Object.keys(data), 'readwrite')
      for (const [t, rows] of Object.entries(data)) for (const r of rows) tx.objectStore(t).put(r)
      await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error) })
      db.close()
    }""", data)


def snapshot(page):
    return page.evaluate("""async () => {
      const db = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
      const names = [...db.objectStoreNames]
      const tx = db.transaction(names, 'readonly')
      const out = {}
      for (const n of names) out[n] = await new Promise((res) => { const q = tx.objectStore(n).getAll(); q.onsuccess = () => res(q.result) })
      db.close()
      return out
    }""")


def settings_state(page):
    return page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-settings') || 'null')?.state ?? null")


# ---------- PWA : rien ne change ----------


def part_web(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    chunks = chunk_requests(ctx)
    ctx.add_init_script(VIBRATE_SPY)
    page = ctx.new_page()
    if open_analysis(page):
        drag_piece(page, "e2", "e4")
        check("web : coup joué au glissé", piece_on(page, "e4") == "wP")
        drag_piece(page, "g8", "g5")
        check("web : refus sans erreur", piece_on(page, "g8") == "bN")
        check("web : aucun runtime Capacitor", page.evaluate("() => window.Capacitor === undefined && window.__haptics === undefined"))
    page.goto(f"{BASE}/#/")
    ck.appears("web : accueil", page, "text=Résolvez !")
    page.wait_for_timeout(500)
    check("web : pas de carte de migration sur base vide", page.locator(CARD).count() == 0)
    page.goto(f"{BASE}/#/stats")
    ck.appears("web : Stats", page, "[data-testid=restore-btn]")
    check("web : pas de marche à suivre native dans Stats", page.locator("[data-testid=native-migration-help]").count() == 0)
    # Le service worker n'existe qu'en build de production (vite-plugin-pwa ne l'active pas en dev).
    sw = page.evaluate("""() => fetch('sw.js').then(async (r) =>
      (r.headers.get('content-type') || '').includes('javascript') ? r.text() : null)""")
    if sw is not None:
        check("web : chunk natif absent du précache", "assets/index-" in sw and "native-" not in sw)
        ready = page.evaluate("""() => Promise.race([navigator.serviceWorker.ready.then(() => true),
          new Promise((r) => setTimeout(() => r(false), 15000))])""")
        check("web : service worker installé", ready)
        page.reload()
        ck.appears("web : Stats rechargées sous service worker", page, "[data-testid=restore-btn]")
        check("web : page contrôlée par le service worker", page.evaluate("() => navigator.serviceWorker.controller !== null"))
    page.wait_for_timeout(500)
    check("web : chunk natif jamais demandé (page ni service worker)", chunks == [], str(chunks))
    check("web : aucune vibration", page.evaluate("window.__vibrate") == 0)
    ctx.close()


# ---------- App native : haptique ----------


# Espion de navigator.vibrate : le repli web du plugin (HapticsWeb) ne doit jamais servir.
VIBRATE_SPY = "window.__vibrate = 0; try { navigator.vibrate = () => { window.__vibrate++; return true } } catch {}"


def native_context(p, browser, **kw):
    ctx = mobile_context(p, browser, ck, standalone=True, **kw)
    ctx.add_init_script(CAPACITOR_IOS)
    ctx.add_init_script(VIBRATE_SPY)
    return ctx


def native_ready(page, label):
    """Le pilote est chargé (plugin enregistré par le chunk natif) : un geste ne peut plus se perdre."""
    try:
        page.wait_for_function("() => !!window.Capacitor?.Plugins?.Haptics", timeout=15000)
        page.wait_for_timeout(50)
        ready = True
    except Exception:
        ready = False
    return check(f"{label} : pilote haptique prêt", ready)


def part_haptics(p, browser):
    ctx = native_context(p, browser)
    chunks = chunk_requests(ctx)
    page = ctx.new_page()
    if not open_analysis(page):
        ctx.close()
        return
    native_ready(page, "analyse")
    check("natif : chunk natif chargé au démarrage", len(chunks) >= 1, str(chunks))
    ck.check("natif : rien au chargement", since(page, 0) == [], str(since(page, 0)))

    m = mark(page)
    x, y = sq_center(page, "e2")
    drag_piece(page, "e2", "e2", start=(x + 14, y))
    got = since(page, m)
    check("repos sur sa case : saisie seule, aucune pose", got == [LIFT] and piece_on(page, "e2") == "wP", str(got))

    m = mark(page)
    drag_piece(page, "e2", "e4")
    got = since(page, m)
    check("glissé : saisie légère puis pose moyenne", got == [LIFT, MOVE], str(got))

    m = mark(page)
    drag_piece(page, "d7", "d5")
    got = since(page, m)
    check("glissé noir (analyse) : même retour", got == [LIFT, MOVE], str(got))

    m = mark(page)
    drag_piece(page, "e4", "d5")
    got = since(page, m)
    check("prise : impact fort à la pose", got == [LIFT, CAPTURE] and piece_on(page, "d5") == "wP", str(got))

    m = mark(page)
    drag_piece(page, "g8", "g5")
    got = since(page, m)
    check("refus : saisie puis notification d'erreur", got == [LIFT, REFUSE] and piece_on(page, "g8") == "bN", str(got))

    m = mark(page)
    tap_move(page, "b8", "c6")
    got = since(page, m)
    check("clic-clic : sélection légère puis pose moyenne", got == [LIFT, MOVE] and piece_on(page, "c6") == "bN", str(got))

    m = mark(page)
    tap_square(page, "f1")
    tap_square(page, "f1")
    got = since(page, m)
    check("re-tap de désélection : une seule saisie, aucune pose", got == [LIFT], str(got))

    # Navigation arrière puis avant de l'analyse : la position change sans geste sur l'échiquier.
    m = mark(page)
    page.get_by_role("button", name="Précédent").click()
    page.wait_for_timeout(200)
    page.get_by_role("button", name="Suivant").click()
    got = since(page, m)
    check("navigation de l'analyse : aucun retour", got == [] and piece_on(page, "c6") == "bN", str(got))
    check("natif : jamais de repli navigator.vibrate", page.evaluate("window.__vibrate") == 0)
    ctx.close()

    # Promotion, avec et sans prise : le retour part au choix de la pièce.
    for label, to, expected in (("promotion", "a8", MOVE), ("promotion avec prise", "b8", CAPTURE)):
        ctx = native_context(p, browser)
        page = ctx.new_page()
        open_analysis(page, "1r5k/P7/8/8/8/8/8/K7 w - - 0 1")
        if not ck.appears(f"{label} : pion en a7", page, "[data-square=a7] [data-piece=wP]") or not native_ready(page, label):
            ctx.close()
            continue
        m = mark(page)
        drag_piece(page, "a7", to)
        got = since(page, m)
        check(f"{label} : saisie seule avant le choix", got == [LIFT], str(got))
        if ck.appears(f"{label} : choix de la pièce", page, "button[aria-label=Dame]"):
            m = mark(page)
            page.locator("button[aria-label=Dame]").click()
            got = since(page, m)
            check(f"{label} : retour au choix", got == [expected] and piece_on(page, to) == "wQ", str(got))
        ctx.close()


    ctx = native_context(p, browser)
    page = ctx.new_page()
    if open_analysis(page, "rnbqkbnr/ppp1ppp1/7p/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3") and native_ready(page, "en passant"):
        m = mark(page)
        drag_piece(page, "e5", "d6")
        got = since(page, m)
        check("en passant : impact de prise sur une case vide", got == [LIFT, CAPTURE] and piece_on(page, "d6") == "wP" and piece_on(page, "d5") is None, str(got))
    ctx.close()


def part_premove(p, browser):
    ctx = native_context(p, browser, settings={"premoves": True, "playBotId": "maximus", "playTcLabel": "Illimité"})
    ctx.add_init_script(HOLD_BESTMOVE)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/jouer")
    page.get_by_role("button", name="Jouer", exact=True).click()
    if not ck.appears("jouer : plateau", page, "[data-square=e2] [data-piece=wP]") or not native_ready(page, "jouer"):
        ctx.close()
        return

    def held():
        try:
            page.wait_for_function("window.__heldUci && window.__heldUci.length > 0", timeout=15000)
            return True
        except Exception:
            return False

    def release(uci):
        page.evaluate("uci => { for (const h of window.__heldUci) h[1] = 'bestmove ' + uci; window.__releaseUci(); window.__heldUci = [] }", uci)

    page.evaluate("window.__heldUci = []")
    m = mark(page)
    tap_move(page, "e2", "e4")
    got = since(page, m)
    check("jouer : mon coup, saisie puis pose", got == [LIFT, MOVE], str(got))
    if not check("jouer : réponse du moteur retenue", held()):
        ctx.close()
        return
    m = mark(page)
    release("e7e5")
    try:
        page.wait_for_function("() => !!document.querySelector('[data-square=e5] [data-piece=bP]')", timeout=15000)
    except Exception:
        pass
    got = since(page, m)
    check("jouer : coup du moteur sans retour", got == [] and piece_on(page, "e5") == "bP", f"{got} e5={piece_on(page, 'e5')}")

    if not check("jouer : deuxième réponse retenue", (tap_move(page, "g1", "f3") or True) and held()):
        ctx.close()
        return
    m = mark(page)
    tap_move(page, "d2", "d4")
    got = since(page, m)
    check("prémouvement en file : saisie puis tic de sélection", got == [LIFT, *PREMOVE], str(got))
    m = mark(page)
    release("b8c6")
    try:
        page.wait_for_function("() => !!document.querySelector('[data-square=d4] [data-piece=wP]')", timeout=15000)
    except Exception:
        pass
    got = since(page, m)
    check("prémouvement exécuté : une seule pose", got == [MOVE] and piece_on(page, "d4") == "wP", str(got))
    ctx.close()


# ---------- App native : assets locaux servis avec un statut 0 ----------


# Le gestionnaire du schéma capacitor:// répond aux assets de l'app avec leur corps, mais un statut 0
# (`ok` faux, type `basic`), comme vu dans la console de l'iPhone réel : « move-self.mp3 : HTTP 0 ».
# Seules les réponses réussies passent à 0 ; un vrai 404 garde son statut.
STATUS0 = r"""(() => {
  window.__status0 = []
  const native = window.fetch
  window.fetch = async function (...a) {
    const res = await native.apply(this, a)
    const path = new URL(res.url, location.href).pathname
    if (res.ok && res.type === 'basic' && /\/(sounds\/[^/]+\.mp3|puzzles\.json)$/.test(path)) {
      for (const [k, v] of [['status', 0], ['ok', false], ['statusText', '']]) Object.defineProperty(res, k, { value: v })
      window.__status0.push(path.split('/').pop())
    }
    return res
  }
})()"""

QUIET_PUZZLE = ["IOS0", "6k1/5ppp/8/8/8/8/5PPP/R5K1 b - - 0 1", "h7h6 a1a7 g8h7 a7f7", 1000, "endgame"]
NAV = "nav[aria-label='Navigation principale'] a:visible"


def status0_context(p, browser):
    ctx = native_context(p, browser, settings={"playSounds": True}, service_workers="block")
    ctx.add_init_script(WEBKIT_AUDIO)
    ctx.add_init_script(STATUS0)
    return ctx


def sound_warnings(page):
    warns = []
    page.on("console", lambda m: warns.append(m.text) if m.type == "warning" and "Son non chargé" in m.text else None)
    return warns


def part_status0(p, browser):
    body = json.dumps([QUIET_PUZZLE])

    # 1. Statut 0 sur une réponse servie : sons et puzzles se chargent.
    ctx = status0_context(p, browser)
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    warns = sound_warnings(page)
    page.goto(f"{BASE}/#/")
    if ck.appears("statut 0 : navigation", page, NAV):
        page.locator(NAV, has_text="Puzzles").first.tap()
        check("statut 0 : tous les sons décodés", wait_sounds_ready(page), str(page.evaluate("() => [...(window.__decoded ?? [])]")))
        if ck.appears("statut 0 : puzzle chargé et amorce jouée", page, "[data-square=h6] [data-piece=bP]"):
            page.wait_for_timeout(300)
            start = len(sound_log(page))
            drag_piece(page, "a1", "a7")
            check("statut 0 : coup du puzzle accepté", piece_on(page, "a7") == "wR")
            heard = sounds_heard(page, start, settle=800)
            check("statut 0 : le coup joue son son, audible", [e["name"] for e in heard][:1] == ["move-self"] and heard[0]["audible"], str(heard))
        zeroed = page.evaluate("() => window.__status0")
        check("statut 0 : réponses réellement servies avec un statut 0",
              "puzzles.json" in zeroed and set(SOUND_FILES) <= set(zeroed), str(zeroed))
        check("statut 0 : aucun avertissement « Son non chargé »", warns == [], str(warns))
    ctx.close()

    # 2. Un vrai 404 reste refusé, même avec un corps exploitable.
    with open(os.path.join(ROOT_DIR, "public", "sounds", "capture.mp3"), "rb") as f:
        mp3 = f.read()
    ctx = status0_context(p, browser)
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=404, content_type="application/json", body=body))
    ctx.route("**/sounds/capture.mp3", lambda route: route.fulfill(status=404, content_type="audio/mpeg", body=mp3))
    page = ctx.new_page()
    warns = sound_warnings(page)
    page.goto(f"{BASE}/#/")
    if ck.appears("404 : navigation", page, NAV):
        page.locator(NAV, has_text="Puzzles").first.tap()
        ck.appears("404 : puzzles indisponibles", page, "text=Puzzles indisponibles")
        check("404 : aucun puzzle affiché", page.locator("[data-square=h6] [data-piece=bP]").count() == 0)
        try:
            page.wait_for_function("(n) => window.__decoded && window.__decoded.size >= n", arg=len(SOUND_FILES) - 1, timeout=15000)
        except Exception:
            pass
        decoded = page.evaluate("() => [...(window.__decoded ?? [])]")
        check("404 : son refusé, jamais décodé", "capture.mp3" not in decoded and len(decoded) == len(SOUND_FILES) - 1, str(decoded))
        check("404 : avertissement du son refusé", any("(capture)" in w and "HTTP 404" in w for w in warns), str(warns))
    ctx.close()


# ---------- Migration PWA -> app ----------


def part_migration(p, browser, tmp):
    # 1. Dans la PWA : de vraies données, exportées par le bouton de Stats.
    web = desktop_context(browser, ck, settings={"themeId": "purple"})
    web.add_init_script(NO_SHARE)
    page = web.new_page()
    page.goto(f"{BASE}/#/stats")
    if not check("pwa : base prête", ck.appears("pwa : Stats", page, "[data-testid=export-btn]") and wait_schema(page)):
        web.close()
        return
    seed(page, SEED)
    page.reload()
    ck.appears("pwa : Stats rechargée", page, "[data-testid=export-btn]")
    before = snapshot(page)
    settings_before = settings_state(page)
    with page.expect_download() as dl:
        page.click("[data-testid=export-btn]")
    path = os.path.join(tmp, "pwa.json")
    dl.value.save_as(path)
    check("pwa : fichier exporté", os.path.getsize(path) > 0)
    web.close()

    # 2. Dans l'app : origine neuve, base vide, la carte de l'accueil guide la restauration.
    ctx = native_context(p, browser)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/")
    if ck.appears("app : carte de migration sur base vide", page, CARD):
        shot(page, "ios_migration_393x852")
        box = page.locator(CARD).bounding_box()
        check("app : carte dans la largeur de l'écran", box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 393, str(box))
        play_visible(page, "app : Jouer entièrement à l'écran sous la carte")
        page.click("[data-testid=native-migration-go]")
        ck.appears("app : Stats, section Tes données", page, "[data-testid=restore-btn]")
        ck.appears("app : marche à suivre depuis la PWA", page, "[data-testid=native-migration-help]")
        page.wait_for_timeout(400)
        # Défilé jusqu'au titre : en haut de l'écran, ou défilement au maximum si la page est trop courte.
        pos = page.evaluate("""() => {
          const h = document.querySelector('[data-testid=data-heading]')
          let el = h.parentElement
          while (el && !(el.scrollHeight > el.clientHeight && /(auto|scroll)/.test(getComputedStyle(el).overflowY))) el = el.parentElement
          el ??= document.scrollingElement
          const r = h.getBoundingClientRect()
          return { y: r.y, bottom: r.bottom, vh: innerHeight, scrolled: el.scrollTop, atEnd: el.scrollTop + el.clientHeight >= el.scrollHeight - 2 }
        }""")
        check("app : Tes données amené à l'écran", (pos["scrolled"] > 0 or pos["atEnd"]) and 0 <= pos["y"] and pos["bottom"] <= pos["vh"] and (pos["y"] < 120 or pos["atEnd"]), str(pos))
        check("app : state de navigation consommé", page.evaluate("() => history.state?.usr == null"))
        page.set_input_files("input[type=file]", path)
        if ck.appears("app : confirmation de restauration", page, "[data-testid=restore-sheet]"):
            page.click("[data-testid=restore-confirm]")
            try:
                page.wait_for_function("() => document.querySelector('[data-testid=restore-sheet]') === null", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(500)
            after = snapshot(page)
            check("app : toutes les tables identiques à la PWA", after == before, json.dumps({t: len(after.get(t, [])) for t in after}))
            st = settings_state(page)
            check("app : réglages repris de la PWA", st is not None and st.get("themeId") == "purple" and st == settings_before, str(st))
            page.goto(f"{BASE}/#/")
            ck.appears("app : accueil après restauration", page, "text=Résolvez !")
            page.wait_for_timeout(600)
            check("app : carte disparue une fois les données restaurées", page.locator(CARD).count() == 0)
            check("app : chiffres de la PWA à l'accueil", page.locator("text=1432").count() >= 1 and page.locator("text=1615").count() >= 1)
    ctx.close()

    # 3. Nouveau départ : « Non merci » est retenu après rechargement, la réinitialisation l'efface.
    ctx = native_context(p, browser)
    ctx.add_init_script(NO_SHARE)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/")
    if ck.appears("app vierge : carte", page, CARD):
        page.click("[data-testid=native-migration-dismiss]")
        check("non merci : carte masquée", page.locator(CARD).count() == 0)
        page.reload()
        ck.appears("non merci : accueil rechargé", page, "text=Résolvez !")
        page.wait_for_timeout(600)
        check("non merci : retenu après rechargement", page.locator(CARD).count() == 0)
        page.goto(f"{BASE}/#/stats")
        if ck.appears("non merci : réinitialiser", page, "[data-testid=reset-btn]"):
            downloads = []
            page.on("download", lambda d: downloads.append(d))
            page.click("[data-testid=export-btn]")
            ck.appears("export natif sans partage : échec explicite", page, "text=aucun fichier enregistré")
            check("export natif sans partage : aucun faux téléchargement", downloads == [])
            check("export natif sans partage : aucune date de succès", page.evaluate("() => localStorage.getItem('chess-local-last-export') === null"))
            page.click("[data-testid=reset-btn]")
            if ck.appears("réinitialisation : première confirmation", page, "[data-testid=reset-confirm]"):
                page.click("[data-testid=reset-confirm]")
            if ck.appears("réinitialisation : confirmation finale", page, "[data-testid=reset-final-confirm]"):
                page.click("[data-testid=reset-final-confirm]")
            if ck.appears("non merci : accueil après réinitialisation", page, "text=Résolvez !"):
                check("réinitialisation : clé de refus effacée", page.evaluate("() => localStorage.getItem('chess-local-native-migration') === null"))
                ck.appears("réinitialisation : la carte revient", page, CARD)
    ctx.close()

    # 4. Écrans annexes : petit écran et bureau.
    for label, make in (
        ("393x660", lambda: (lambda c: (c.add_init_script(CAPACITOR_IOS), c)[1])(mobile_context(p, browser, ck))),
        ("1440x900", lambda: (lambda c: (c.add_init_script(CAPACITOR_IOS), c)[1])(desktop_context(browser, ck))),
    ):
        ctx = make()
        page = ctx.new_page()
        page.goto(f"{BASE}/#/")
        if ck.appears(f"{label} : carte", page, CARD):
            shot(page, f"ios_migration_{label}")
            check(f"{label} : pas de débordement horizontal", page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"))
            play_visible(page, f"{label} : Jouer entièrement à l'écran")
        ctx.close()


def suite(p):
    browser = p.chromium.launch()
    part_web(p, browser)
    part_haptics(p, browser)
    part_premove(p, browser)
    part_status0(p, browser)
    with tempfile.TemporaryDirectory() as tmp:
        part_migration(p, browser, tmp)
    browser.close()


if __name__ == "__main__":
    ck.run(suite)
