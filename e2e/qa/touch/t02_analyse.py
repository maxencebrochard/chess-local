"""/#/analyse : drags 4 directions, pièce non jouable, case vide, coordonnées, bordure. 3 viewports.
Usage : python3 t02_analyse.py [fix]   ('fix' injecte le CSS candidat pour la preuve avant/après)"""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

FIX = sys.argv[1] if len(sys.argv) > 1 else ""
FIX_CSS = {"fix": ".boardbox { touch-action: none; }", "fix2": ".boardbox { touch-action: none; } [data-square] > span, [data-square] > span > span { pointer-events: none; }"}.get(FIX, "")
import os
VIEWPORTS = [("standalone852", dict(standalone=True)), ("safari660", dict(standalone=False)), ("force560", dict(standalone=False, width=393, height=560))]

ONLY = os.environ.get('ONLY')
with sync_playwright() as p:
    for name, kw in [v for v in VIEWPORTS if not ONLY or v[0] == ONLY]:
        browser, ctx, page, logs = open_mobile_t(p, **kw)
        install(page)
        page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
        if FIX:
            page.add_style_tag(content=FIX_CSS)
        s0 = snap(page)
        print(f"\n=== analyse | {name} | fix={FIX} | scrollers={s0['scrollers']} boardTop={s0['boardTop']}")
        c = lambda sq: sq_center(page, sq)
        # 1. pièces jouables, 4 directions
        for frm, to, d in [("e2", "e4", "haut"), ("e7", "e5", "bas"), ("g1", "f3", "haut-gauche"), ("b8", "c6", "bas-droite"), ("h1", "g1", "gauche"), ("a8", "b8", "droite")]:
            r = gesture(page, *c(frm), *c(to)); v = line(f"jouable {frm}->{to} ({d})", r)
            if not v["moved"]:
                print("      !! coup non joué, events:", r["events"][:12])
        shot(page, f"t02_{name}_{'fix' if FIX else 'base'}_apres_coups")
        # 2. pièce NON jouable (trait aux blancs : on tire un pion noir), long drag vertical dans les deux sens
        r = gesture(page, *c("d7"), c("d7")[0], c("d7")[1] + 260); line("non jouable d7 (noir, trait blancs) drag bas 260px", r)
        r = gesture(page, *c("d2"), c("d2")[0], c("d2")[1] - 300); v = line("jouable d2 drag haut 300px (lâché hors case légale)", r)
        # 3. case vide : long drag vertical haut puis bas
        r = gesture(page, *c("d5"), c("d5")[0], c("d5")[1] - 200); line("case VIDE d5 drag haut 200px", r)
        r = gesture(page, *c("d4"), c("d4")[0], c("d4")[1] + 200); line("case VIDE d4 drag bas 200px", r)
        # 4. départ sur le CHIFFRE de coordonnée par-dessus une pièce jouable (coin haut-gauche de a2)
        b = sq_rect(page, "a2"); r = gesture(page, b["x"] + 5, b["y"] + 7, *c("a4")); v = line("pièce a2 saisie sur le chiffre '2' -> a4", r)
        # si a2-a4 a été joué, le trait est aux noirs : coup noir de remplissage pour que d1 soit TOUJOURS testée trait aux blancs
        if v["moved"]:
            gesture(page, *c("h7"), *c("h6"))
        b = sq_rect(page, "d1"); r = gesture(page, b["x"] + b["width"] - 6, b["y"] + b["height"] - 6, *c("e2")); line("pièce d1 saisie sur la lettre 'd' -> e2", r)
        # 5. bordure : départ dans la marge de 6 px à gauche du board, et juste sous le board
        b = sq_rect(page, "a4"); r = gesture(page, 2, b["y"] + 20, 2, b["y"] - 180); line("marge gauche x=2 drag haut 200px", r)
        shot(page, f"t02_{name}_{'fix' if FIX else 'base'}_fin")
        if logs:
            print("   logs:", logs[:5])
        browser.close()
