from helpers import BASE, WEBKIT_AUDIO, Checker, mobile_context, sounds_heard

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
        page.locator("div.flex.items-center.justify-between").filter(
            has=page.get_by_text("Sons", exact=True)).get_by_role("button").click()
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


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        for setting in ["0", "35", "désactivé"]:
            delayed_settings(p, browser, setting)
        prefixed_context(p, browser)
    finally:
        browser.close()


ck.run(suite)
