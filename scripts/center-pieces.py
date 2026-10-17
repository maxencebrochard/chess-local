"""Mesure les marges des SVG sans modifier les assets sous licence.

python3 scripts/center-pieces.py [--check]
Le rendu Chromium à 512 px mesure la boîte alpha > 127 ; aucune entrée réseau.
Les pièces intégrées sont rendues depuis la dépendance installée.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".local/share/chess-local/ms-playwright"))
OUT = ROOT / "src/data/pieceCenters.json"
classic = json.loads(subprocess.check_output([
    "node", "--input-type=module", "-e",
    "import {defaultPieces} from 'react-chessboard'; import {renderToStaticMarkup} from 'react-dom/server'; console.log(JSON.stringify(Object.fromEntries(Object.entries(defaultPieces).map(([k,v])=>[k,renderToStaticMarkup(v())]))))",
], cwd=ROOT, text=True))
images = {f"classique/{code}": svg for code, svg in classic.items()}
for path in sorted((ROOT / "public/pieces").glob("*/*.svg")):
    images[f"{path.parent.name}/{path.stem}"] = path.read_text()

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    centers = {}
    for key, svg in images.items():
        url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        centers[key] = page.evaluate("""async src => {
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = c.height = 512;
          const g = c.getContext('2d'); g.drawImage(img,0,0,512,512);
          const d = g.getImageData(0,0,512,512).data;
          let x0=512,y0=512,x1=-1,y1=-1;
          for(let y=0;y<512;y++) for(let x=0;x<512;x++) if(d[(y*512+x)*4+3]>127) {
            x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);
          }
          if(x1<x0) throw new Error('Pièce vide');
          return [(0.5-(x0+x1+1)/1024)*100,(0.5-(y0+y1+1)/1024)*100];
        }""", url)
    browser.close()
content = json.dumps(centers, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
if "--check" in sys.argv:
    if not OUT.exists() or OUT.read_text() != content:
        sys.exit("Marges périmées : relancer scripts/center-pieces.py")
else:
    OUT.write_text(content)
print(f"Centres : {len(centers)} pièces vérifiées")
