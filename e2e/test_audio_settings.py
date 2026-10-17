from helpers import BASE, WEBKIT_AUDIO, Checker, mobile_context, sounds_heard, drag_piece, tap_move, piece_on

ck = Checker("audio_settings")

HOLD_AUDIO = """(() => {
  const original = window.fetch
  let release
  const pending = new Promise(resolve => { release = resolve })
  window.__releaseAudio = release
  window.__audioHeld = false
  window.fetch = async (...args) => {
    const response = await original(...args)
    if (String(args[0]).includes('/sounds/')) {
      window.__audioHeld = true
      await pending
    }
    return response
  }
})()"""


def audio_context(p, browser):
    ctx = mobile_context(p, browser, ck, settings={"playSounds": True}, service_workers="block")
    ctx.add_init_script(WEBKIT_AUDIO)
    return ctx


def delayed_settings(p, browser, setting):
    ctx = audio_context(p, browser)
    ctx.add_init_script(HOLD_AUDIO)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    slider = page.get_by_label("Volume des sons")
    slider.focus()
    page.keyboard.press("End")
    page.wait_for_function("window.__audioHeld")
    ck.check(f"[{setting}] aperçu en attente", sounds_heard(page, 0) == [])
    if setting == "désactivé":
        page.get_by_role("switch", name="Sons", exact=True).click()
    else:
        slider.fill(setting)
    page.evaluate("window.__releaseAudio()")
    entries = sounds_heard(page, 0, settle=1000)
    if setting == "35":
        ck.check("[35] aperçu unique au nouveau volume",
                 len(entries) == 1 and entries[0]["audible"]
                 and abs(page.evaluate("window.__gain") - 0.35) < 1e-6)
    else:
        ck.check(f"[{setting}] aucun aperçu différé", entries == [], str(entries))
    ctx.close()


def prefixed_context(p, browser):
    ctx = audio_context(p, browser)
    ctx.add_init_script("window.webkitAudioContext = window.AudioContext; window.AudioContext = undefined")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    slider = page.get_by_label("Volume des sons")
    slider.focus()
    for mode in [None, "interrupted", "zombie"]:
        if mode:
            page.evaluate("mode => window.__background(mode)", mode)
        n = page.evaluate("window.__sounds.length")
        page.keyboard.press("ArrowLeft")
        entries = sounds_heard(page, n, settle=1000)
        ck.check(f"[préfixé {mode}] aperçu audible",
                 len(entries) == 1 and entries[0]["name"] == "move-self" and entries[0]["audible"], str(entries))
    ctx.close()


def first_move(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True, settings={"playSounds": True})
    ctx.add_init_script(WEBKIT_AUDIO)
    ctx.add_init_script("window.__release = 0; addEventListener('pointerup', () => window.__release = performance.now(), true)")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    if ck.appears("[premier geste] plateau", page, "[data-square=e2] [data-piece]"):
        for label, src, dst, code, sound, background, limit in [
            ('froid', 'e2', 'e4', 'wP', 'move-self', None, 300),
            ('chaud', 'e7', 'e5', 'bP', 'move-opponent', None, 80),
            ('reprise', 'g1', 'f3', 'wN', 'move-self', 'interrupted', 300),
        ]:
            if background:
                page.evaluate("mode => window.__background(mode)", background)
            n = page.evaluate('window.__sounds.length')
            drag_piece(page, src, dst)
            entries = sounds_heard(page, n)
            release = page.evaluate('window.__release')
            ck.check(f"[premier geste {label}] coup et son audible à la pose",
                     piece_on(page, dst) == code and len(entries) == 1
                     and entries[0]["audible"] and entries[0]["name"] == sound
                     and 0 <= entries[0]['at'] - release <= limit,
                     str({'sounds': entries, 'release': release, 'limit': limit,
                          'piece': piece_on(page, dst)}))
    ctx.close()


def obsolete_moves(p, browser):
    ctx = audio_context(p, browser)
    ctx.add_init_script(HOLD_AUDIO)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    if ck.appears("[chargement lent] plateau", page, "[data-square=e2] [data-piece]"):
        tap_move(page, "e2", "e4")
        tap_move(page, "e7", "e5")
        page.wait_for_timeout(400)
        ck.check("[chargement lent] deux coups joués", piece_on(page, "e4") == "wP" and piece_on(page, "e5") == "bP")
        page.evaluate("window.__releaseAudio()")
        entries = sounds_heard(page, 0, settle=500)
        ck.check("[chargement lent] aucun coup obsolète en rafale", entries == [], str(entries))
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        first_move(p, browser)
        obsolete_moves(p, browser)
        for setting in ["0", "35", "désactivé"]:
            delayed_settings(p, browser, setting)
        prefixed_context(p, browser)
    finally:
        browser.close()


ck.run(suite)
