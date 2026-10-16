"""Phrases de défense d'une position (python-chess, sans moteur), vues du DÉFENSEUR, le camp au
trait. Les faits viennent de `scripts/attack_facts.py`, appelé avec l'attaquant explicite (le camp
qui n'est pas au trait) : mêmes catégories, mêmes abords du roi, même levier principal. Partagé par
`scripts/prepare-defenses.py` (génération de `src/data/defenses.json`) et `e2e/test_defense.py`
(qui recalcule tout et vérifie en plus des invariants indépendants sur l'échiquier).

Chaque phrase n'affirme qu'un fait mesuré : pièce, pion, colonne ou roi nommés sont relus sur
l'échiquier, et les conseils restent des conseils (« neutralise », « garde »), jamais un coup.
"""
import chess

from attack_facts import CATEGORY_SHORT, NUMBER_FR, _list, _storm_files, category, facts, lever, theme  # noqa: F401


def attacker_of(board):
    """L'attaquant d'une position de défense : le camp qui n'est pas au trait."""
    return not board.turn


def defense_category(board):
    return category(board, attacker_of(board))


def defense_facts(board):
    return facts(board, attacker_of(board))


def defense_theme(cat, f):
    """Même thème que l'attaque : il décrit la position, pas le camp."""
    return theme(cat, f)


def goal(cat, f):
    """Consigne courte (une ligne sur iPhone) : catégorie + l'action du défenseur contre le levier."""
    lv = lever(cat, f)
    cols = f["open"] + f["semiOpen"]
    if lv == "centre":
        action = "mets ton roi à l'abri" if f["canCastle"] else "tu ne peux plus roquer, ferme le jeu"
    elif lv == "storm":
        action = f"freine son pion {f['storm'][0][0]}" if len(f["storm"]) == 1 else f"freine ses pions {_list(_storm_files(f))}"
    elif lv == "file":
        action = f"couvre la colonne {f['heavyOn'][0][0]}" if f["heavyOn"] else f"garde la colonne {cols[0]}"
    else:
        action = "tiens ton roque affaibli"
    return f"{CATEGORY_SHORT[cat]} : {action}."


def plan(board, cat, f):
    """Trois à cinq phrases, chacune tirée d'un fait mesuré, le levier d'abord, vues du défenseur."""
    dfn = board.turn
    dk, ak = chess.square_name(board.king(dfn)), chess.square_name(board.king(not dfn))
    lv = lever(cat, f)
    if cat == "opposes":
        out = [f"Ton roi est en {dk}, le sien en {ak} : les roques sont opposés, il peut lancer ses pions sans découvrir son roi."]
    elif cat == "meme":
        out = [f"Les deux rois sont sur la même aile ({dk} et {ak}) : s'il pousse ses pions contre toi, il découvre aussi son roi."]
    else:
        out = [
            f"Ton roi est resté au centre en {dk}"
            + (" et peut encore roquer : mets-le à l'abri dès que tu peux." if f["canCastle"] else " et ne peut plus roquer : ne lui ouvre pas de colonne.")
        ]
    if len(f["storm"]) == 1:
        storm = f"Son pion {f['storm'][0]} est déjà lancé vers ton roi : ne lui donne pas de cible pour ouvrir une colonne."
    elif f["storm"]:
        storm = f"Ses pions {_list(f['storm'])} sont déjà lancés vers ton roi : ne leur donne pas de cible pour ouvrir une colonne."
    else:
        storm = None
    if len(f["heavyOn"]) == 1:
        file_ = f"Sa pièce lourde en {f['heavyOn'][0]} est déjà sur une colonne sans pion à lui, devant ton roi : oppose-lui une pièce."
    elif f["heavyOn"]:
        file_ = f"Ses pièces lourdes en {_list(f['heavyOn'])} sont déjà sur des colonnes sans pion à lui, devant ton roi : oppose-leur tes pièces."
    elif f["open"]:
        file_ = (
            f"La colonne {f['open'][0]} est ouverte près de ton roi : ne la laisse pas à ses tours ni à sa dame." if len(f["open"]) == 1
            else f"Les colonnes {_list(f['open'])} sont ouvertes près de ton roi : ne les laisse pas à ses tours ni à sa dame."
        )
    elif f["semiOpen"]:
        file_ = (f"La colonne {f['semiOpen'][0]} est semi-ouverte" if len(f["semiOpen"]) == 1 else f"Les colonnes {_list(f['semiOpen'])} sont semi-ouvertes") + " pour lui : surveille l'arrivée de ses tours et de sa dame."
    else:
        file_ = None
    if f["shieldMissing"]:
        cols = f"la colonne {f['shieldMissing'][0]}" if len(f["shieldMissing"]) == 1 else f"les colonnes {_list(f['shieldMissing'])}"
        shield = f"Ton roi n'a plus de pion devant lui sur {cols} : chaque défenseur compte."
    elif len(f["shieldAdvanced"]) == 1:
        shield = f"Ton pion {f['shieldAdvanced'][0]} a avancé devant ton roi : les cases derrière lui sont faibles."
    elif f["shieldAdvanced"]:
        shield = f"Tes pions {_list(f['shieldAdvanced'])} ont avancé devant ton roi : les cases derrière eux sont faibles."
    else:
        shield = None
    order = {"storm": [storm, file_, shield], "file": [file_, shield, storm], "shield": [shield, file_, storm], "centre": [file_, shield, storm]}[lv]
    out += [s for s in order if s]
    n, d = len(f["attackers"]), len(f["defenders"])
    out.append(f"{NUMBER_FR.get(n, str(n))} de ses pièces visent déjà les abords de ton roi ({_list(f['attackers'])}) : neutralise d'abord la plus dangereuse.")
    if d < n:
        out.append(f"Ses attaquants dépassent tes défenseurs ({n} contre {d}) : rapproche une pièce ou échange un attaquant.")
    elif d == 1:
        out.append(f"Ta pièce en {f['defenders'][0]} défend les abords de ton roi : garde-la près de lui.")
    else:
        out.append(f"Tes pièces en {_list(f['defenders'])} défendent les abords de ton roi : garde-les près de lui.")
    return " ".join(out)
