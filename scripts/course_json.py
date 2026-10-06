"""Écriture déterministe des JSON de cours (src/data/*Course.json), commune aux scripts de
vérification : le tampon sha256 porte sur ce texte exact."""
import json


# Écriture déterministe : un coup par ligne, le reste indenté de 2 espaces.
def dump(obj, indent=0):
    pad = "  " * indent
    if isinstance(obj, dict):
        if indent >= 4 and all(not isinstance(v, (dict,)) for v in obj.values()) and "san" in obj:
            return json.dumps(obj, ensure_ascii=False)
        items = [f'{pad}  {json.dumps(k, ensure_ascii=False)}: {dump(v, indent + 1)}' for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(obj, list):
        if all(isinstance(x, str) for x in obj) and sum(len(x) for x in obj) < 60:
            return json.dumps(obj, ensure_ascii=False)
        if all(isinstance(x, list) for x in obj):
            return json.dumps(obj, ensure_ascii=False)
        items = [f"{pad}  {dump(x, indent + 1)}" for x in obj]
        return "[\n" + ",\n".join(items) + f"\n{pad}]"
    return json.dumps(obj, ensure_ascii=False)
