#!/usr/bin/env python3
"""Vérifie le cours « Les bases » (src/data/basicsCourse.json) avec Stockfish 18 et tamponne
scripts/basics-course.verified : c'est le vérificateur du cours « Démolir le roque »
(scripts/verify-attack-course.py), mêmes paliers et profondeurs, appliqué à ce JSON.

À lancer après toute modification du cours, puis committer le JSON réécrit et le tampon :
le contrôle hors ligne (scripts/check-basics-course.mjs, suite `parcours`) refuse un contenu
non revérifié. Le second mot du tampon est le sha de verify-attack-course.py : modifier ce
vérificateur impose de relancer les deux cours.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.exit(subprocess.call([
    sys.executable, os.path.join(HERE, "verify-attack-course.py"),
    os.path.join(ROOT, "src", "data", "basicsCourse.json"),
    os.path.join(HERE, "basics-course.verified"),
]))
