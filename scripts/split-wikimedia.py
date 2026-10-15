"""Découpe vectorielle reproductible du sprite Commons (CC BY-SA 3.0)."""
import hashlib
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

URL = "https://upload.wikimedia.org/wikipedia/commons/b/b2/Chess_Pieces_Sprite.svg"
SOURCE = "https://commons.wikimedia.org/wiki/File:Chess_Pieces_Sprite.svg"
SHA256 = "454599e80f65fa502c8a5318e4e139dbfe5636b0aae96869a139d016b1a3e16a"
raw = subprocess.check_output(["curl", "--fail", "--location", "--silent", "--show-error", URL])
assert hashlib.sha256(raw).hexdigest() == SHA256, "Le sprite amont a changé"
ns = "http://www.w3.org/2000/svg"
ET.register_namespace("", ns)
sprite = ET.fromstring(raw)
assert (sprite.get("width"), sprite.get("height")) == ("270", "90")
groups = list(sprite)
assert len(groups) == 12 and all(g.tag == f"{{{ns}}}g" for g in groups)
out = Path(__file__).resolve().parents[1] / "public/pieces/wikimedia"
out.mkdir(exist_ok=True)
# Le carré source de 45 unités occupe 86,5 % de la case (45 / 52).
# Marge horizontale symétrique de 3,5 ; origine verticale à 0,5 :
# le dessin remonte de 4 unités pour dégager les coordonnées du bas.
# Les tracés commencent sous cette origine et restent intégralement visibles.
# La même marge suit la pièce agrandie pendant le glissé.
for i, group in enumerate(groups):
    assert group.attrib.pop("transform") == f"translate({i % 6 * 45},{i // 6 * 45})"
    code = "wb"[i // 6] + "KQBNRP"[i % 6]
    root = ET.Element(f"{{{ns}}}svg", {"width": "45", "height": "45", "viewBox": "-3.5 0.5 52 52"})
    ET.SubElement(root, f"{{{ns}}}desc").text = (
        f"jurgenwesterhof, d’après Cburnett. Source : {SOURCE}. "
        "CC BY-SA 3.0 : https://creativecommons.org/licenses/by-sa/3.0/. "
        "Modification : découpage du sprite en pièces individuelles et ajout de marges ; tracés et styles inchangés."
    )
    root.append(group)
    ET.ElementTree(root).write(out / f"{code}.svg", encoding="utf-8", xml_declaration=True)
