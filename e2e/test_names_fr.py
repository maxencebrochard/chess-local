"""E2E noms FR : ouvertures et thèmes de puzzles entièrement en français.

Usage : npm run test:e2e -- --suite names_fr

Partie 1, sans navigateur : Node 22 importe directement `src/lib/openingNames.ts` et
`src/lib/puzzleThemes.ts` (type stripping natif, aucun bundler) et les exécute sur les VRAIES données
(3 803 noms de `src/data/openings.json`, 73 thèmes de `public/puzzles.json`). Python asserte : aucun
token anglais survivant hors de la liste de noms propres vérifiés à la main (lexique OUVERT), aucune
chaîne vide, et une table écrite à la main de noms courants avec leur traduction EXACTE (c'est elle
qui protège l'usage, pas le détecteur).
Partie 2, navigateur iPhone : bandeau d'ouverture sur /analyse, pastilles de thèmes sur /puzzles.
"""
import json
import os
import re
import subprocess
import tempfile

from helpers import BASE, Checker, click_square as sq, mobile_context, shot

ck = Checker("names_fr")
check = ck.check

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
OPENINGS_JSON = os.path.join(ROOT, "src", "data", "openings.json")
PUZZLES_JSON = os.path.join(ROOT, "public", "puzzles.json")
NB_OUVERTURES = 3803
NB_THEMES = 73

# Lexique OUVERT : tout token du nom anglais qui se retrouve tel quel dans sa traduction est un reste
# d'anglais, SAUF s'il figure dans cette liste de noms propres et de mots conservés à dessein, relue
# à la main (patronymes, villes sans exonyme, surnoms gardés tels quels, mots identiques en français
# comme Gambit, Formation, Dragon, Stonewall, préfixes néo/anti, particules). Les coups SAN de pion
# (« e6 », « dxc4 ») sont identiques en français et reconnus par regex. Toute nouvelle fuite (« Slav »,
# « Scandinavian », « Check ») échoue ici ; tout nouveau patronyme dans openings.json s'ajoute ici.
NOMS_PROPRES = set("""
Monkey's Bum
150 Abbazia Abonyi Abrahams Achilles Acton Adams Adhiban Adler Adorjan Aires Aitken Akahi Alapin Alatortsev Albany
Albin Alburt Alekhine Alessi Alien Allgaier Alua Amar Ampel Anand Anderssen Andersson Andreaschek Anglo Anhanguera
Antal Anti Antoshin Apocalypse Arafat Arkhangelsk Arnold Aronin Asten Austriadactylus Averbakh Baeuerle Bahr Baird
Baldwin Balla Balogh Banker Banzai Barcza Bardeleben Barmen Barnes Barry Basman Bastrikov Batavo Battambang Bayonet
Bayreuth Beach Becker Beefeater Been Behting Belezky Belgrade Bello Bellon Belyavsky Benelux Benima Benjamin Benko
Benoni Berg Berger Berlin Bernard Bernstein Bertin Beta Beverwijk Beyer Bielefelder Bilguer Billinger Billockus Bird
Birmingham Blachly Black Blackburne Blackmar Bladel Blake Bled Bledow Blumenfeld Bobotsov Boden Boehnke Bogoljubow
Bogolubovia Boi Boleslavsky Bonet Bongcloud Bonsch Bonsdorf Boor Boren Borg Borisenko Botvinnik Bourdonnais Bowdler
Boyce Bradford Bradley Brandics Braune Bremen Brentano Breslau Breyer Brick Brinckmann Brix Brodsky Brombacher
Bronstein Brooklyn Browne Bruycker Bryan Buckley Budapest Buenos Buerger Bugayev Bulla Burgess Burille Burk Burn Busch
Byrne Bücker Cadet Calabrese Cambridge Campomanes Canal Canard Cannstatter Capablanca Carlo Carls Carlsbad Carlsen
Carlson Caro Carr Carrera Celadon Chabanon Chandler Charlick Charousek Chatard Chebanenko Cheese Chekhover
Chenoboskion Chicago Chigorin Chiodini Chistyakov Christensen Ciesielski Clam Clemenz Cobra Coca Cochrane Cola Coles
Colle Collijn Colman Cologne Colorado Columpio Cook Cordel Corkscrew Cortlever Cotter Cozio Crawly Creepy Crocodile
Cunningham Czerniak Damhaug Damiano De Debrecen Dekker Delmar Delta Denker Deppe Deutz Devin Diemer Diepstraten
Dilworth Dinic Dlugy Dodo Dog Doll Donner Dorfman Dougherty Dr. Dracula Dragon Drazic Dreyev Drill Dubois Dubov
Duchamp Dudweiler Dufresne Duhm Dunne Dunst Dunworthy Duras Durkin Duthilleul Duz Dyckhoff Dzindzi Döry Düsseldorf
Eastbourne Edge Eifel Eingorn Eisenberg Eisinger Ekolu Ekstrom El Elbert Elbow Eliskases Ellis Englund Erben
Erbenheimer Euwe Evans Everglades Fajarowicz Falkbeer Farago Fazekas Fegatello Felbecker Ferenc Finegold Fingerslip
Fischer Flohr Foltys Fontaine Forgacs Formation Fort Fox Francisco Franco Frankenstein Frappe Fraser Frederico Frenkel
Fricke Fried Friess Fritz Fuller Furman Fyfe Gaga Gajewski Gambit Gary Gass Gaw Gedult Geet Geller Gent George Geschev
Ghulam Gianutio Gibbins Gibbon Ginsberg Gipslis Giuoco Gladbacher Gledhill Glek Gligoric Gloria Godes Godiva Goglidze
Goldman Goldsmith Gossip Gottschall Grand Graz Greco Grigorian Grigoriev Grimm Grinberg Grivas Grob Gruber Grünfeld
Guatemala Gubinsky Gufeld Guimard Gunderam Gunsberg Gurevich Gurgenidze Gusev Göring Haag Haakert Haberditz Halasz
Hall Hammer Hammerschlag Hamppe Hanham Hanneken Hanstein Harding Harksen Harmonist Harrwitz Hartlaub Haxo Hay Hecht
Hector Heidenfeld Hein Heinola Hekili Henneberger Hennig Heral Herford Hergert Herrstrom Herzog Hevendehl Heyde Hicken
Hickmann Hillbilly Hinrichsen Hirschbach Hiva Hjørring Hobbs Hoffmann Holloway Hollywood Holwell Holzhausen Hook
Hooydoon Hopton Hornung Horny Hort Horus Horwitz Howell Hromádka Huisl Hula Hulsemann Hunt Hurst Hübner Hübsch
Ilundain Ilyin Inner Intermezzo Isis Ivanchuk Ivanov Ivkov Jadoul Jaenisch Jaffe Jalalabad Janeiro Janowski Jansa
Janzen Jendrossek Jerome Jobava Johansen Johner Jones Jorge Junge Kahiko Kaidanov Kalashnikov Kan Kann Kantscher
Karklins Karniewski Karpov Kasparov Kassim Katalimov Kaufmann Kaulich Kavalek Kecskemet Keene Keidansky Kennedy Keoni
Keres Kevitz Khan Kharlov Kholmov Khotimirsky Kiddie Kiel Kieseritzky Kitchener Klein Kling Kloosterboer Kloss Kluever
Kmoch Knorre Knox Koch Kolisch Kondratiyev Konikowski Konstantinopolsky Koola Koomen Kopec Korchnoi Kostić Kotov
Kotroc Kozul Kramer Kramnik Krasenkow Krause Krebs Krejcik Krenosz Kronberger Kruijs Kudischewitsch Kuijk Kunin
Kupreichik Kurajica Kurkin Kveinis Kádas La Labahn Lamb Lanc Landau Lange Langeheinicke Langheld Larobok Laroche
Larsen Lasa Lasker Lazard Lee Leko Lemberger Lemming Leningrad Leonardis Leong Leonhardt Levenfish Levitsky Lewis
Lichtenhein Liebig Liedmann Lilienthal Linares Linksspringer Lion Lipke Lipnitsky Lisitsyn Ljubojevic Loa Lobron
Locock Lolli Loman Long Lopez Louma Lputian Lucchini Lucena Lundin Lusophobe Luther Lutikov Löhn Löwenthal MacLeod
Macieja Mackenzie Mad Maddigan Mafia Magnus Makogonov Malaniuk Malich Malkin Malvinas Manhattan Mannheim Mar Marco
Maria Maric Marienbad Mariotti Marshall Martinez Martinovsky Maróczy Masi Mason Massachusetts Masur Matanovic
Matovinsky Matsukevich Matulovic Maurian Max Mayet Mazedonisch Mbembe McConnell McCormick McCutcheon McDonnell Meadow
Mecking Medusa Meitner Melbourne Melleby Mellon Melts Mengarini Mestel Metger Michel Middleton Mieses Miguel Mikenas
Mikhalchishin Miladinovic Miles Millennium Milner Minckwitz Mindeno Mittenberger Mlotkowski Moeller Mokele Mongoloid
Mongredien Monte Montevideo Monticelli Moody Morgado Morozevich Morphy Morra Morris Mortimer Motzko Mujannah Murrey
Mustang Mutkin Muzio Myers Möhring Møller Müller Nadanian Najdorf Nakhmanson Nanu Napoleon Napolitano Naroditsky
Naselwaus Navara Nei Nemeth Nenarokov Nescafe Neumann New Nikitin Nimzo Nimzowitsch Noa Norfolk Norwalde Noteboom
Novikov Nowokunski Nu Nyezhmetdinov Nyholm O'Kelly O'Sullivan Oldtimer Olland Omaha Omega Opocensky Orsini
Orthoschnapp Oshima Osmolovsky Owen Oxford Pachman Palatnik Paleface Palme Panno Panov Panteldakis Paoli Papa Paris
Parma Paulsen Pavlov Paw Pelikan Perenyi Perlis Perrenet Perreux Perrin Perseus Petronić Petrosian Petruccioli
Petursson Pfeiffer Pfrang Philidor Pianissimo Piano Picklepuss Pickler Pierce Pietrowsky Pillsbury Pilnik Pincus
Pinova Pirc Plasma Plata Platz Podebrady Polerio Polgar Poli Pollock Polovodin Polugaevsky Pomar Ponomariov Ponziani
Popiel Portisch Portland Portsmouth Potter Pounds Pozarek Prague Pratt Prianishenmo Prins Prix Przepiorka Psakhis
Pteranodon Pytel Quaade Quelle Quetzalcoatlus Quinteros Rabinovich Radisch Ragozin Randspringer Ranken Raphael Rapport
Raptor Rasa Rashkovsky Rasmussen Rat Rauzer Reefschläger Regina Reifir Reimer Relfsson Rellstab Remo Reshevsky Reuter
Rhamphorhynchus Rice Richardson Richter Riemann Riga Ringelbach Rio Ritter Riumin Riviere Robatsch Rochlin Romanishin
Romanovsky Romford Romih Roscher Rosen Rosenberg Rosenthal Rosentreter Ross Rossolimo Rotary Rotlewi Rousseau Ruban
Rubinstein Ruisdonk Rushmere Ryder Réti Saduleto Salvio San Sanders Sanky Santa Santasiere Sarratt Schaeffer Schallopp
Schara Schiffler Schiller Schippler Schlechter Schlenker Schliemann Schlutter Schmid Schmidt Schneider Schnepper
Schofman Schubert Schuehler Schulder Schultz Schulz Schulze Schurig Schwartz Schönemann Scorpion Sea Seidel Seirawan
Semmering Senechaud Shabalov Shaposhnikov Shaviliuk Sherbakov Sherzer Shirazi Shirov Shocron Short Showalter
Shropshire Shuffle Shumov Siegener Silberschmidt Simagin Simul Siroccopteryx Skipworth Sleipnir Smet Smith Smyslov
Snagglepuss Sneiders Sodium Sokolsky Soldatenkov Soller Soltis Somov Sosonko Soultanbeieff Sozin Spassky Speelsmet
Speers Spielmann Spike Spraggett Springs St. Stader Stafford Stahlberg Stamma Stanley Staunton Stein Steinbok Steiner
Steinitz Stockholm Stoltz Stone Stonewall Strautins Studier Stummer Sturm Suetin Suhle Suttles Svedenborg Svenonius
Sveshnikov Swiss Szabo Szén Sämisch Sörensen Sørensen Süchting Taimanov Tal Tamarkin Tan Tarrasch Tartakower Tarzan
Tate Tayler Teichmann Tennison Teplice Testa Therkatz Thomas Thorold Thunderbunny Ticulat Tiviakov Toikkanen Toilet
Tolush Topalov Torre Totsky Trajkovic Traxler Trencianske Trifunovic Troger Trompowsky Troon Tumbleweed Twyble
Tübingen Uhlmann Ulvestad Ulysses Unzicker Urusov Van Van't Vasquez Vavra Vehre Velimirovic Venezolana Veresov
Villemson Vinogradov Vistaneckis Vitolins Vitzthum Vos Vukovic Wade Wagenbach Wagner Wahls Walbrodt Walker Walkerling
Wall Waller Wallis Walthoffen Ware Warsteiner Weber Weenink Weersel Weidenhagen Weinsbach Weiss Welling Westerinen
Westermann Wheeler Whip Wiedenhagen Wiel Wiesbaden Williams Wimpy Winawer Winckelmann Wind Winter Winterberg Wolferts
Woozle Wormald Worrall Wurzburger Wuss Yankovich Yates Yefimov York Young Yurdansky Zagorovsky Zagoryansky Zagreb
Zaitsev Zeller Zhenevsky Zhuravlev Ziegler Zilbermints Zinnowitz Zollner Zukertort Zurich Zvjaginsev Zwitersch de del
der l'Hermet von
""".split())
SAN = re.compile(r"^(?:[KQRBN][a-h]?[1-8]?x?[a-h][1-8]|[a-h](?:x[a-h])?[1-8](?:=[QRBN])?|O-O(?:-O)?)[+#]?$")

# Table écrite à la main : les ouvertures les plus courantes, familles ET combinaisons usuelles,
# avec la traduction exacte attendue (usage FFE / Europe Échecs / Wikipédia FR).
ATTENDU = {
    "Sicilian Defense": "Défense sicilienne",
    "Sicilian Defense: Najdorf Variation": "Défense sicilienne · variante Najdorf",
    "Sicilian Defense: Dragon Variation, Yugoslav Attack": "Défense sicilienne · variante du Dragon, attaque yougoslave",
    "Sicilian Defense: Closed": "Défense sicilienne · variante fermée",
    "Sicilian Defense: Alapin Variation": "Défense sicilienne · variante Alapin",
    "Sicilian Defense: Smith-Morra Gambit": "Défense sicilienne · gambit Smith-Morra",
    "Sicilian Defense: Accelerated Dragon": "Défense sicilienne · Dragon accéléré",
    "Sicilian Defense: Scheveningen Variation": "Défense sicilienne · variante de Scheveningue",
    "French Defense": "Défense française",
    "French Defense: Advance Variation": "Défense française · variante d'avance",
    "French Defense: Winawer Variation": "Défense française · variante Winawer",
    "Caro-Kann Defense: Advance Variation": "Défense Caro-Kann · variante d'avance",
    "Caro-Kann Defense: Exchange Variation": "Défense Caro-Kann · variante d'échange",
    "Scandinavian Defense": "Défense scandinave",
    "Pirc Defense": "Défense Pirc",
    "Alekhine Defense": "Défense Alekhine",
    "Modern Defense": "Défense moderne",
    "Ruy Lopez": "Partie espagnole",
    "Ruy Lopez: Berlin Defense": "Partie espagnole · défense berlinoise",
    "Ruy Lopez: Open Berlin Defense, l'Hermet Variation": "Partie espagnole · défense berlinoise ouverte, variante l'Hermet",
    "Ruy Lopez: Morphy Defense": "Partie espagnole · défense Morphy",
    "Ruy Lopez: Exchange Variation": "Partie espagnole · variante d'échange",
    "Italian Game": "Partie italienne",
    "Italian Game: Two Knights Defense": "Partie italienne · défense des deux cavaliers",
    "Italian Game: Two Knights Defense, Fried Liver Attack": "Partie italienne · défense des deux cavaliers, attaque du Foie frit",
    "Italian Game: Evans Gambit": "Partie italienne · gambit Evans",
    "Italian Game: Giuoco Piano": "Partie italienne · Giuoco Piano",
    "Scotch Game": "Partie écossaise",
    "Vienna Game": "Partie viennoise",
    "Four Knights Game": "Partie des quatre cavaliers",
    "Petrov's Defense": "Défense Petrov",
    "Philidor Defense": "Défense Philidor",
    "King's Gambit Accepted": "Gambit du roi accepté",
    "King's Gambit Declined: Classical Variation": "Gambit du roi refusé · variante classique",
    "Bishop's Opening": "Début du fou",
    "Queen's Gambit Declined": "Gambit dame refusé",
    "Queen's Gambit Declined: Exchange Variation": "Gambit dame refusé · variante d'échange",
    "Queen's Gambit Accepted": "Gambit dame accepté",
    "Slav Defense": "Défense slave",
    "Semi-Slav Defense: Meran Variation": "Défense semi-slave · variante de Méran",
    "King's Indian Defense": "Défense est-indienne",
    "King's Indian Defense: Orthodox Variation": "Défense est-indienne · variante orthodoxe",
    "Nimzo-Indian Defense": "Défense nimzo-indienne",
    "Queen's Indian Defense": "Défense ouest-indienne",
    "Grünfeld Defense: Exchange Variation": "Défense Grünfeld · variante d'échange",
    "Benoni Defense: Modern Variation": "Défense Benoni · variante moderne",
    "Dutch Defense: Leningrad Variation": "Défense hollandaise · variante de Leningrad",
    "Catalan Opening": "Ouverture catalane",
    "London System": "Système de Londres",
    "Trompowsky Attack": "Attaque Trompowsky",
    "English Opening": "Partie anglaise",
    "English Opening: Symmetrical Variation": "Partie anglaise · variante symétrique",
    "Réti Opening": "Ouverture Réti",
    "King's Indian Attack": "Attaque est-indienne",
    "King's Indian Attack, with Bf5": "Attaque est-indienne, avec Ff5",
    "Queen's Pawn Game": "Début du pion dame",
    "King's Pawn Game": "Début du pion roi",
    "Benko Gambit": "Gambit Benko",
    "Tarrasch Defense: Swedish Variation, Central Break": "Défense Tarrasch · variante suédoise, rupture centrale",
    "Trompowsky Attack: Classical Defense, Big Center Variation": "Attaque Trompowsky · défense classique, variante du grand centre",
    "Bogo-Indian Defense: New England Variation": "Défense bogo-indienne · variante de Nouvelle-Angleterre",
    "Indian Defense: Budapest Gambit": "Défense indienne · gambit de Budapest",
}

# « de + article + famille », pour les phrases d'Apprendre et du coach (I18N-4).
DE_ATTENDU = {
    "Sicilian Defense: Najdorf Variation": "de la défense sicilienne",
    "Queen's Gambit Declined": "du gambit dame refusé",
    "English Opening": "de la partie anglaise",
    "London System": "du système de Londres",
    "Réti Opening": "de l'ouverture Réti",
    "King's Indian Attack": "de l'attaque est-indienne",
    "Italian Game": "de la partie italienne",
}

# displayThemes sur des tags tels que puzzles.json les fournit (ordre alphabétique) : le but (mat en N)
# d'abord, puis les motifs, la phase, l'issue ; méta (longueur, origine) exclus ; « mate » absorbé par
# « mateInN » ; 3 au plus. Sans ordre de priorité, « crushing » et « middlegame » éjecteraient l'enfilade.
DISPLAY_CAS = [
    (["crushing", "fork", "master", "middlegame", "pin", "short", "skewer"], ["Fourchette", "Clouage", "Enfilade"]),
    (["backRankMate", "endgame", "long", "mate", "mateIn3"], ["Mat en 3", "Mat du couloir", "Finale"]),
]
# Libellés figés : termes consacrés (Wikipédia FR) là où lichess fr-FR ou une traduction littérale trompent.
LIBELLES_ATTENDUS = {
    "smotheredMate": "Mat étouffé",
    "arabianMate": "Mat arabe",
    "backRankMate": "Mat du couloir",
    "dovetailMate": "Mat de Cozio",
    "swallowstailMate": "Mat du guéridon",
    "fork": "Fourchette",
    "mateIn1": "Mat en 1",
}

# Script Node : importe les modules TypeScript (type stripping natif de Node 22), traduit les VRAIES
# données et rend tout en JSON.
NODE_SCRIPT = r"""
import fs from 'node:fs'
const [openingsTs, themesTs, openingsJson, puzzlesJson, deNames, displayCas] = process.argv.slice(2)
const out = { fr: [], de: {}, themes: null, cles: null, display: null, erreurs: [] }
try {
  const on = await import(openingsTs)
  const d = JSON.parse(fs.readFileSync(openingsJson, 'utf8'))
  out.fr = d.map((e) => [e.name, on.openingFr(e.name)])
  for (const n of JSON.parse(deNames)) out.de[n] = typeof on.openingDe === 'function' ? on.openingDe(n) : null
} catch (e) { out.erreurs.push('ouvertures: ' + String(e)) }
try {
  const pt = await import(themesTs)
  const tags = new Set()
  for (const p of JSON.parse(fs.readFileSync(puzzlesJson, 'utf8'))) for (const t of p[4].split(' ')) tags.add(t)
  out.themes = Object.fromEntries([...tags].sort().map((t) => [t, pt.puzzleThemeLabel(t)]))
  out.cles = Object.keys(pt.PUZZLE_THEMES_FR)
  out.display = JSON.parse(displayCas).map((tags) => pt.displayThemes(tags))
} catch (e) { out.erreurs.push('thèmes: ' + String(e)) }
process.stdout.write(JSON.stringify(out))
"""

SEPARATEURS = re.compile(r"[\s·,\-()]+")


def module(rel):
    """Chemin d'un module TypeScript du repo ; son absence est un échec compté, pas une exception."""
    path = os.path.join(ROOT, rel)
    check(f"[module] {rel} présent", os.path.exists(path))
    return path


def mots_anglais(en, fr):
    """Tokens du nom anglais restés tels quels dans la traduction (hors noms propres et coups SAN), plus les fautes de forme."""
    en_toks = set(SEPARATEURS.split(en.replace(": ", " "))) - {""}
    toks = [t for t in SEPARATEURS.split(fr) if t]
    bad = [t for t in toks if t in en_toks and t not in NOMS_PROPRES and not SAN.match(t)]
    bad += [t for t in toks if t.endswith("'s") and t not in NOMS_PROPRES]  # possessif anglais (« Bird's »)
    if "Gambit" in toks[1:]:
        bad.append("Gambit(majuscule en milieu de nom)")
    return bad


def partie_node():
    on = module("src/lib/openingNames.ts")
    pt = module("src/lib/puzzleThemes.ts")
    with tempfile.TemporaryDirectory(prefix="chesslocal-names-fr-") as tmp:
        script = os.path.join(tmp, "dump.mjs")
        with open(script, "w", encoding="utf-8") as f:
            f.write(NODE_SCRIPT)
        proc = subprocess.run(
            ["node", script, on, pt, OPENINGS_JSON, PUZZLES_JSON, json.dumps(list(DE_ATTENDU)), json.dumps([c[0] for c in DISPLAY_CAS])],
            cwd=ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            ck.fail("[node] script de traduction", f"({proc.stderr.strip()[-300:]})")
            return
        out = json.loads(proc.stdout)
    for err in out["erreurs"]:
        ck.fail("[node] module inutilisable", f"({err[:200]})")

    # --- Ouvertures : 3 803 noms, données réelles ---
    fr = dict(out["fr"])
    check("[ouvertures] 3 803 noms traduits", len(out["fr"]) == NB_OUVERTURES, f"({len(out['fr'])})")
    vides = [en for en, t in out["fr"] if not isinstance(t, str) or not t.strip() or re.search(r"undefined|null|\[object", t)]
    check("[ouvertures] aucune traduction vide ou undefined", not vides, f"({vides[:5]})")
    forme = [t for _, t in out["fr"] if "  " in t or t != t.strip() or re.search(r",\s*,|·\s*,|,\s*·|·\s*$|^\s*·", t)]
    check("[ouvertures] pas de double espace ni de séparateur orphelin", not forme, f"({forme[:5]})")
    restes = [(en, t, mots_anglais(en, t)) for en, t in out["fr"] if mots_anglais(en, t)]
    check(
        "[ouvertures] aucun token anglais survivant (hors noms propres) dans les 3 803 noms",
        not restes,
        f"({len(restes)} noms, ex. " + " | ".join(f"{t} <{'/'.join(b)}>" for _, t, b in restes[:8]) + ")",
    )
    absents = [en for en in ATTENDU if en not in fr]
    check("[ouvertures] chaque entrée de la table existe dans openings.json", not absents, f"({absents})")
    ecarts = [(en, fr.get(en)) for en, voulu in ATTENDU.items() if fr.get(en) != voulu]
    check(
        f"[ouvertures] les {len(ATTENDU)} noms courants ont EXACTEMENT la traduction attendue",
        not ecarts,
        f"({len(ecarts)} écarts, ex. " + " | ".join(f"{en} -> {got!r} (voulu {ATTENDU[en]!r})" for en, got in ecarts[:5]) + ")",
    )
    ecarts_de = [(en, out["de"].get(en)) for en, voulu in DE_ATTENDU.items() if out["de"].get(en) != voulu]
    check("[ouvertures] openingDe accorde l'article", not ecarts_de, f"({ecarts_de[:4]})")

    # --- Thèmes : 73 tags, données réelles ---
    themes = out["themes"]
    if themes is None:
        ck.fail("[thèmes] src/lib/puzzleThemes.ts absent ou inutilisable")
        return
    check(f"[thèmes] {NB_THEMES} tags dans puzzles.json", len(themes) == NB_THEMES, f"({len(themes)})")
    # Un identifiant brut commence par une minuscule et contient une majuscule (« mateIn1 »,
    # « discoveredAttack ») ; « Attaque sur f2 ou f7 » n'en est pas un.
    # Le repli lisible de puzzleThemeLabel rend ce check impossible à faire échouer sur le libellé seul :
    # chaque tag réel doit être une CLÉ de la table (un tag lichess nouveau ou renommé échoue ici).
    hors_table = [t for t in themes if t not in (out["cles"] or [])]
    check("[thèmes] chaque tag de puzzles.json est une clé de PUZZLE_THEMES_FR", not hors_table, f"({hors_table[:8]})")
    sans_libelle = [t for t, lab in themes.items() if not lab or lab == t or re.search(r"\b[a-z]+[A-Z]\w*", lab)]
    check("[thèmes] chaque libellé est français (ni brut, ni camelCase)", not sans_libelle, f"({sans_libelle[:8]})")
    ecarts_lib = [(t, themes.get(t)) for t, voulu in LIBELLES_ATTENDUS.items() if themes.get(t) != voulu]
    check("[thèmes] libellés consacrés (mat étouffé, mat arabe, Cozio, guéridon...)", not ecarts_lib, f"({ecarts_lib})")
    for i, (entree, voulu) in enumerate(DISPLAY_CAS):
        got = (out["display"] or [None, None])[i]
        check(f"[thèmes] displayThemes cas {i + 1} : priorité but > motifs > phase > issue, méta exclus", got == voulu, f"({got})")


# ---------- navigateur ----------

# Un puzzle : mat du berger. Position avant 3...Cf6?? (coup d'amorce joué par l'app), puis Dxf7#.
# Tags dans l'ordre alphabétique réel de puzzles.json : sans priorité, « Mat » et « Mat en 1 » doublonneraient.
PUZZLE_FIXTURE = [["e2e01", "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3", "g8f6 h5f7", 600,
                   "attackingF2F7 master mate mateIn1 oneMove opening"]]


def bandeau(page):
    return page.locator("main div.truncate.bg-surface-2").first.inner_text().strip()


def attendre_bandeau(page, contient, timeout_ms=5000):
    page.wait_for_timeout(300)
    for _ in range(timeout_ms // 200):
        if contient in bandeau(page):
            break
        page.wait_for_timeout(200)
    return bandeau(page)


def partie_navigateur(p, browser, standalone, tag):
    ctx = mobile_context(p, browser, ck, standalone=standalone, service_workers="block")
    page = ctx.new_page()

    # --- /analyse : 1.e4 c5 2.Cf3 d6 (variante nommée), puis 3.d4 (famille seule) ---
    page.goto(f"{BASE}/#/analyse")
    ck.appears(f"[analyse {tag}] échiquier", page, "[data-square='e2']", timeout=20000)
    page.wait_for_timeout(800)
    for frm, to in (("e2", "e4"), ("c7", "c5"), ("g1", "f3"), ("d7", "d6")):
        sq(page, frm)
        page.wait_for_timeout(150)
        sq(page, to)
        page.wait_for_timeout(250)
    texte = attendre_bandeau(page, "variantes modernes")
    check(f"[analyse {tag}] bandeau entièrement français après 2...d6", texte == "Défense sicilienne · variantes modernes", f"({texte!r})")
    shot(page, f"names_fr_analyse_{tag}")
    sq(page, "d2")
    page.wait_for_timeout(150)
    sq(page, "d4")
    texte = attendre_bandeau(page, "Défense sicilienne")
    check(f"[analyse {tag}] bandeau famille seule après 3.d4", texte == "Défense sicilienne", f"({texte!r})")

    # --- /puzzles : la donnée est remplacée par un puzzle connu ; le service worker est bloqué
    # sur ce contexte, sinon puzzles.json (précaché) ne passerait jamais par la route. ---
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(PUZZLE_FIXTURE)))
    page.goto(f"{BASE}/#/puzzles")
    ck.appears(f"[puzzles {tag}] page chargée", page, "text=Classement puzzles", timeout=20000)
    page.wait_for_timeout(1500)  # coup d'amorce 3...Cf6 joué par l'app après 500 ms
    sq(page, "h5")
    page.wait_for_timeout(150)
    sq(page, "f7")
    ck.appears(f"[puzzles {tag}] puzzle résolu", page, "text=Résolu", timeout=8000)
    carte = page.locator("main p", has_text="Puzzle e2e01").first.inner_text().strip()
    pastilles = carte.split(" · ", 2)[2].split(", ") if carte.count(" · ") >= 2 else []
    check(f"[puzzles {tag}] pastilles en français, but puis motif puis phase, « mate » absorbé", pastilles == ["Mat en 1", "Attaque sur f2 ou f7", "Ouverture"], f"({carte!r})")
    check(f"[puzzles {tag}] aucun identifiant brut ni méta-thème", not re.search(r"mateIn1|oneMove|master|opening|Partie de maîtres|Un coup", carte), f"({carte!r})")
    shot(page, f"names_fr_puzzle_{tag}")
    ctx.close()


def suite(p):
    partie_node()
    browser = p.chromium.launch(headless=True)
    partie_navigateur(p, browser, standalone=True, tag="852")
    partie_navigateur(p, browser, standalone=False, tag="660")
    browser.close()


ck.run(suite)
