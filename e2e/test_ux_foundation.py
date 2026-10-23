"""Lot 1 : preuves sur les composants rendus, aux trois formats de référence."""
import json
import os
from pathlib import Path
from helpers import BASE, SHOTS, Checker, desktop_context, mobile_context, overflow_x

ck = Checker("ux_foundation")
OUT = Path(SHOTS) / "ux-lot1" / os.environ.get("UX_PHASE", "after")
OUT.mkdir(parents=True, exist_ok=True)
MEASURES = []

# Résolution par canvas : accepte aussi les couleurs oklch de Tailwind.
# Les fonds transparents sont composés avec leurs ancêtres (sRGB).
CONTRAST = """(e, graphic = false) => {
  const c = document.createElement('canvas').getContext('2d');
  c.canvas.width = c.canvas.height = 1;
  const rgba = color => { c.clearRect(0,0,1,1); c.fillStyle=color; c.fillRect(0,0,1,1);
    return [...c.getImageData(0,0,1,1).data].map((v,i)=>i===3?v/255:v); };
  const over = (a,b) => { if (!a[3]) return b; const alpha=a[3]+b[3]*(1-a[3]);
    return [...a.slice(0,3).map((v,i)=>(v*a[3]+b[i]*b[3]*(1-a[3]))/alpha),alpha]; };
  let bg=[0,0,0,0];
  for(let p=graphic ? e.parentElement : e;p;p=p.parentElement) {
    bg=over(bg,rgba(getComputedStyle(p).backgroundColor));
    if(bg[3]===1) break;
  }
  const fg=over(rgba(graphic ? getComputedStyle(e).backgroundColor : getComputedStyle(e).color),bg);
  const lum=a=>a.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
    .reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  const l=[lum(fg),lum(bg)].sort((a,b)=>b-a);
  return {text:e.innerText,ratio:(l[0]+.05)/(l[1]+.05),fg,bg};
}"""


def inspect(page, fmt, name):
    page.evaluate("""async () => {
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      await Promise.all(document.getAnimations().filter(a =>
        Number.isFinite(a.effect.getComputedTiming().endTime)).map(a => a.finished.catch(() => {})));
      await Promise.all([...document.images].map(img => img.decode().catch(() => {})));
    }""")
    ck.check(f"{fmt}/{name} : aucun débordement", not overflow_x(page))
    controls = page.locator("main .ui-card, main .ui-back, main .ui-cta, main .ui-empty a")
    dimensions = controls.evaluate_all("es=>es.filter(e=>!e.disabled).map(e=>({text:e.innerText,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))")
    ck.check(f"{fmt}/{name} : composants présents", len(dimensions) > 0)
    ck.check(f"{fmt}/{name} : cibles 44 px", bool(dimensions) and all(d["w"] >= 44 and d["h"] >= 44 for d in dimensions), str(dimensions))
    for selector in [".ui-cta:not(:disabled)", ".ui-description", ".ui-card-title", ".ui-card-description", ".ui-empty p", ".ui-back", ".ui-progress-text"]:
        for el in page.locator("main " + selector).all():
            m = el.evaluate(CONTRAST)
            MEASURES.append(dict(format=fmt, page=name, **m))
            ck.check(f"{fmt}/{name} : contraste {m['text'][:30]}", m["ratio"] >= 4.5, f"{m['ratio']:.2f}:1")
    # Capturer aussi les cartes sous la ligne de flottaison.
    main = page.locator("main")
    size = main.evaluate("e=>({h:e.clientHeight,total:e.scrollHeight})")
    for i, y in enumerate(range(0, size["total"], max(1, size["h"] - 50))):
        main.evaluate("(e,y)=>e.scrollTop=y", y)
        page.screenshot(path=str(OUT / f"{fmt}-{name}-{i}.png"))
    main.evaluate("e=>e.scrollTop=0")


def suite(p):
    browser = p.chromium.launch()
    for fmt, height in [("iphone852",852),("iphone660",660),("desktop",900)]:
        ctx = desktop_context(browser, ck, service_workers="block") if fmt == "desktop" else mobile_context(p, browser, ck, standalone=True, viewport={"width":393,"height":height}, service_workers="block")
        page = ctx.new_page()
        for path, name, marker in [("/","accueil","[data-testid=home][data-review-ready]:not([data-home-primary=pending]) [data-home-cta]"),("/apprendre","apprendre","h1"),
                ("/apprendre/bases","bases","h1:text('Les bases')"),("/apprendre/finales","finales","h1:text('Cours de finales')"),
                ("/apprendre/roque","roque","h1:text('Démolir le roque')"),("/archive","archive","text=Aucune partie enregistrée"),
                ("/attaques-manquees","attaques","[data-testid=attack-empty]"),("/defenses-ratees","defenses","[data-testid=defense-empty]"),
                ("/apprendre/moments-critiques","moments","[data-testid=moments-empty]")]:
            page.goto(f"{BASE}/#{path}")
            if not ck.appears(f"{fmt}/{name} : prêt", page, marker):
                continue
            if name in ("bases", "finales", "roque") and not ck.appears(f"{fmt}/{name} : progression chargée", page, "[data-testid=course-progress]"):
                continue
            inspect(page, fmt, name)
            if name == "accueil":
                # Lot 4 : le CTA principal de l'accueil est celui de sa carte (séance du jour sur base vide).
                page.locator("[data-testid=home]:not([data-home-primary=pending])").wait_for(timeout=10000)
                cta = page.locator("[data-home-cta]")
                m = cta.evaluate(CONTRAST)
                ck.check(f"{fmt} : CTA vert AA", m["ratio"] >= 4.5, f"{m['ratio']:.2f}:1")
                # Mesurer la couleur finale, pas une frame de transition entre les deux textes.
                cta.evaluate("e=>{e.style.transition='none'; e.style.color='white'}")
                bad = cta.evaluate(CONTRAST)["ratio"]
                ck.check(f"{fmt} : le contrôle rejette le blanc sur vert", 2.40 < bad < 2.42, f"{bad:.2f}:1")
                cta.evaluate("e=>{e.style.removeProperty('color'); getComputedStyle(e).color; e.style.removeProperty('transition')}")
                if fmt == "desktop":
                    cta.focus()
                    page.keyboard.press("Tab")
                    page.keyboard.press("Shift+Tab")
                    ck.check("Focus clavier visible", cta.evaluate("e=>e.matches(':focus-visible') && getComputedStyle(e).outlineStyle !== 'none' && parseFloat(getComputedStyle(e).outlineWidth)>=2"))
                    page.screenshot(path=str(OUT / "desktop-focus.png"))
                    cta.hover()
                    ck.check("CTA survol AA", cta.evaluate(CONTRAST)["ratio"] >= 4.5)
            if name in ("bases","finales","roque"):
                bar = page.get_by_role("progressbar")
                ck.check(f"{fmt}/{name} : progression réelle et nommée", bar.count() == 1 and bar.get_attribute("aria-valuenow") == "0" and int(bar.get_attribute("aria-valuemax") or 0) > 0 and bool(bar.get_attribute("aria-label")))
                if bar.count() == 1:
                    ck.check(f"{fmt}/{name} : contraste graphique AA", bar.locator("span").evaluate(CONTRAST, True)["ratio"] >= 3)
                # Propriétaire des cours depuis le lot 5 : Toutes les leçons.
                back = page.get_by_role("button", name="Retour à Toutes les leçons", exact=True)
                if back.count():
                    back.click()
                    page.wait_for_url("**/#/apprendre/lecons")
                    ck.appears(f"{fmt}/{name} : hub restauré", page, "h1:has-text('Toutes les leçons')")
                ck.check(f"{fmt}/{name} : retour explicite", page.url.endswith("#/apprendre/lecons"))
            if name == "attaques":
                title = page.locator("h1")
                title.evaluate("e=>e.textContent='Mes attaques manquées et toutes les occasions à retravailler dans mes parties'")
                ck.check(f"{fmt} : titre long sans débordement", not overflow_x(page) and title.evaluate("e=>e.scrollWidth<=e.clientWidth"))
                page.screenshot(path=str(OUT / f"{fmt}-titre-long.png"))
            if name in ("archive","attaques","defenses","moments"):
                action = page.locator(".ui-empty a")
                ck.check(f"{fmt}/{name} : action état vide", action.count() == 1)
                if action.count():
                    target = action.get_attribute("href")
                    action.click()
                    page.wait_for_url(f"**/{target}")
                    ck.check(f"{fmt}/{name} : destination état vide", page.url.endswith(target))
        page.goto(f"{BASE}/#/apprendre/parcours")
        if ck.appears(f"{fmt} : parcours prêt", page, "[data-current-step] button"):
            node = page.locator("[data-current-step] button").first
            m = node.evaluate(CONTRAST)
            ck.check(f"{fmt} : numéro du parcours AA", m["ratio"] >= 4.5, f"{m['ratio']:.2f}:1")
            ck.check(f"{fmt} : progression du parcours nommée", page.get_by_role("progressbar", name="Étapes terminées du parcours").count() == 1)
            page.screenshot(path=str(OUT / f"{fmt}-parcours.png"))
        ctx.close()
        # Retenir l'ouverture réelle de la base : la progression inconnue ne doit pas
        # être affichée comme un zéro acquis, et l'en-tête doit rester disponible.
        loading = desktop_context(browser, ck, service_workers="block") if fmt == "desktop" else mobile_context(p, browser, ck, standalone=True, viewport={"width":393,"height":height}, service_workers="block")
        loading.add_init_script("""(() => {
          const open = indexedDB.open.bind(indexedDB);
          window.__schemaRequests = [];
          indexedDB.open = (...args) => {
            const req = open(...args);
            req.addEventListener('success', e => {
              if (!window.__schemaReleased) { e.stopImmediatePropagation(); window.__schemaRequests.push(req); }
            }, true);
            return req;
          };
          window.__releaseSchema = () => {
            window.__schemaReleased = true;
            for (const req of window.__schemaRequests) req.dispatchEvent(new Event('success'));
          };
        })()""")
        lp = loading.new_page()
        lp.goto(f"{BASE}/#/apprendre/finales")
        ck.appears(f"{fmt} : chargement annoncé", lp, "[role=status]:text('Chargement de la progression')")
        ck.check(f"{fmt} : chargement sans faux zéro", lp.get_by_role("progressbar").count() == 0)
        ck.check(f"{fmt} : en-tête conservé pendant le chargement", lp.locator("h1").is_visible() and lp.get_by_role("button", name="Retour à Toutes les leçons", exact=True).is_visible())
        lp.screenshot(path=str(OUT / f"{fmt}-chargement.png"))
        lp.wait_for_function("window.__schemaRequests.length > 0")
        lp.evaluate("window.__releaseSchema()")
        ck.appears(f"{fmt} : progression après chargement", lp, "[role=progressbar][aria-valuenow='0']")
        loading.close()
    browser.close()
    (OUT / "contrast.json").write_text(json.dumps(MEASURES, ensure_ascii=False, indent=2))


ck.run(suite)
