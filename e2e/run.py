"""Lanceur E2E autonome : `npm run test:e2e`.

Démarre SON serveur sur un port libre, vérifie que c'est bien lui qui répond, lance les suites
sur plusieurs workers, surveille le serveur pendant qu'elles tournent, et l'arrête toujours.

    python3 e2e/run.py                  # build de prod servi sous /chess-local/ (comme GitHub Pages)
    python3 e2e/run.py --mode dev       # serveur de dev : React StrictMode double les updaters,
                                        # ce qui révèle les effets de bord mal placés
    python3 e2e/run.py --suite learn    # une seule suite (option cumulable : --suite learn --suite v4)
    python3 e2e/run.py --suite all_buttons --live  # API chess.com réelle, hors gate
    python3 e2e/run.py --jobs 1         # une suite à la fois, sortie en direct (défaut : E2E_JOBS,
                                        # sinon 2 (1 sur un seul cœur))
    BASE=https://… python3 e2e/run.py   # cible externe : aucun serveur lancé

Navigateurs Playwright : dans un dossier propre au projet (BROWSERS_DIR), hors de ~/Library/Caches
que les nettoyages de disque vident, et installés automatiquement s'ils manquent.
`PLAYWRIGHT_BROWSERS_PATH` déjà défini par l'utilisateur est respecté tel quel.

Le bilan donne la durée de chaque suite et la durée totale. En parallèle, la sortie d'une suite est
imprimée d'un bloc à sa fin, et les suites les plus longues du dernier lancement partent d'abord
(durées dans e2e/shots/.durations.json).

Codes de sortie : 0 tout passe, 1 au moins un échec, 2 mauvais usage ou prérequis manquant.
"""
import argparse
import glob
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
BIN = os.path.join(ROOT, "node_modules", ".bin")
VITE = os.path.join(BIN, "vite")
HOST = "127.0.0.1"  # contexte sécurisé (service worker, presse-papiers) sans dépendre de la résolution de « localhost »
SUBPATH = "/chess-local/"  # le build est servi sous le même sous-chemin que GitHub Pages
APP_MARKER = "<title>ChessLocal"
PROD_ONLY = {"pwa", "upgrade"}  # suites qui n'ont de sens que sur le build local (service worker, manifest, hors ligne, montée de version)

# Hors de ~/Library/Caches : le cache Playwright par défaut y a été vidé quatre fois par des
# nettoyages de disque, et toutes les suites tombaient d'un coup.
BROWSERS_DIR = os.path.expanduser("~/.local/share/chess-local/ms-playwright")

# Dernière durée réussie par suite et par mode, pour l'ordonnancement parallèle (dossier gitignoré).
DURATIONS_PATH = os.path.join(E2E_DIR, "shots", ".durations.json")

READY_TIMEOUT_S = 60
STOP_GRACE_S = 5
PORT_ATTEMPTS = 5


ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Interrupted(Exception):
    """SIGINT, SIGTERM ou SIGHUP : tout passe par le même nettoyage."""


def say(message):
    """print qui ne lève jamais : sur un stdout fermé (pipe du gate, panneau fermé), un
    BrokenPipeError dans un `finally` ferait sauter l'arrêt du serveur qui le suit."""
    try:
        print(message, flush=True)
    except OSError:
        pass


def suites_available():
    names = {}
    for path in sorted(glob.glob(os.path.join(E2E_DIR, "test_*.py"))):
        names[os.path.basename(path)[len("test_"):-len(".py")]] = path
    return names


def free_port():
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:  # groupe réattribué à un autre utilisateur : plus le nôtre
        return False


def kill_group(proc, label):
    """SIGTERM au groupe, délai de grâce, puis SIGKILL. On vise le GROUPE même si son chef est
    déjà mort : Vite lance esbuild et des workers qui lui survivraient. La grâce attend la fin du
    groupe entier, pas seulement de son chef : un membre qui ignore SIGTERM reçoit SIGKILL."""
    if proc is None:
        return
    pgid = proc.pid
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            break
        deadline = time.time() + STOP_GRACE_S
        while time.time() < deadline:
            if proc.poll() is not None and not group_alive(pgid):
                break
            time.sleep(0.05)
        else:
            if sig == signal.SIGTERM:
                say(f"[run] {label} ne s'arrête pas après {sig.name}, on insiste")
            continue
        break
    try:
        proc.wait(timeout=STOP_GRACE_S)
    except subprocess.TimeoutExpired:
        pass


def run_in_group(cmd, label):
    """Commande bloquante dans son propre groupe, tuée proprement si le lanceur est interrompu."""
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = proc.communicate()
    except BaseException:
        kill_group(proc, label)
        raise
    return proc.returncode, out


def port_is_listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def tail(path, lines=30):
    return "".join(read(path).splitlines(keepends=True)[-lines:]) or "(journal vide ou illisible)"


def serves_app(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as res:
            return res.status == 200 and APP_MARKER in res.read(4096).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return False


def chromium_launches():
    """Vrai si Chromium démarre. Un lancement réel plutôt qu'un test de chemin : en headless,
    Playwright lance `chromium_headless_shell`, que `executable_path` ne désigne pas."""
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True, ""
    except Exception as e:
        return False, str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__


def ensure_browser():
    """Fixe le dossier des navigateurs (sauf choix de l'utilisateur), hérité par les suites via
    l'environnement, et installe Chromium une seule fois s'il manque."""
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        say(f"[run] navigateurs Playwright : PLAYWRIGHT_BROWSERS_PATH={os.environ['PLAYWRIGHT_BROWSERS_PATH']} (défini par l'utilisateur)")
    else:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSERS_DIR
    ok, why = chromium_launches()
    if ok:
        return True
    where = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
    say(f"[run] Chromium introuvable dans {where} ({why[:200]})\n[run] installation automatique : python3 -m playwright install chromium (une fois, environ 150 Mo)…")
    # Sans le GC, l'installation ne supprime pas les autres versions du dossier : un autre
    # checkout sur une autre version de Playwright garde la sienne.
    env = {**os.environ, "PLAYWRIGHT_SKIP_BROWSER_GC": "1"}
    code = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=ROOT, env=env).returncode
    ok, why = chromium_launches() if code == 0 else (False, f"code de sortie {code}")
    if not ok:
        say(f"[run] installation de Chromium ratée ({why[:200]}) : aucune suite lancée.")
        return False
    say(f"[run] Chromium installé dans {where}")
    return True


def build(out_dir):
    """Build de prod dans un dossier PROPRE à ce lancement : deux lancements simultanés dans le
    même checkout se volaient `dist/` (assets hashés en 404 pendant le rebuild de l'autre)."""
    say("[run] build de production…")
    for cmd in ([os.path.join(BIN, "tsc"), "-b"], [VITE, "build", "--outDir", out_dir, "--emptyOutDir"]):
        code, out = run_in_group(cmd, "build")
        if code != 0:
            say(out[-3000:])
            raise RuntimeError("le build de production a échoué : aucune suite lancée")


class Server:
    """Serveur Vite (dev ou preview d'un build) sur un port libre, arrêté par groupe de process."""

    def __init__(self, mode, out_dir=None, own_group=True):
        self.mode = mode
        self.out_dir = out_dir
        # own_group=False : le serveur reste dans le groupe de process de l'appelant. Une suite qui
        # démarre son propre serveur l'utilise : si le lanceur tue le groupe de la suite (délai,
        # serveur principal mort, interruption), ce serveur meurt avec elle au lieu de rester orphelin.
        self.own_group = own_group
        self.proc = None
        self.port = None
        self.log_path = None

    @property
    def base(self):
        path = SUBPATH.rstrip("/") if self.mode == "prod" else ""
        return f"http://{HOST}:{self.port}{path}"

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        # Le choix du port n'est pas atomique (un autre lancement peut le prendre entre-temps) :
        # --strictPort fait échouer Vite proprement dans ce cas, et on retente avec un autre port.
        for attempt in range(1, PORT_ATTEMPTS + 1):
            self.port = free_port()
            fd, self.log_path = tempfile.mkstemp(prefix=f"chesslocal-e2e-{self.mode}-", suffix=".log")
            cmd = [VITE] + (["preview", "--outDir", self.out_dir, "--base", SUBPATH] if self.mode == "prod"
                            else ["--config", os.path.join(E2E_DIR, "vite.config.ts")])
            cmd += ["--host", HOST, "--port", str(self.port), "--strictPort"]
            # Sortie sans couleurs : avec FORCE_COLOR (fréquent en CI), Vite écrit le port entre des
            # séquences ANSI et le critère « prêt » ne le retrouverait jamais dans son journal.
            env = {k: v for k, v in os.environ.items() if k != "FORCE_COLOR"}
            env["NO_COLOR"] = "1"
            self.proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=fd, stderr=subprocess.STDOUT, start_new_session=self.own_group)
            os.close(fd)
            if self._wait_ready():
                say(f"[run] serveur {self.mode} prêt : {self.base}/ (pid {self.proc.pid})")
                return
            say(f"[run] démarrage raté sur le port {self.port} (essai {attempt}/{PORT_ATTEMPTS}), journal conservé : {self.log_path}\n{tail(self.log_path, 8)}")
            self.stop(check_port=False, keep_log=True)
        raise RuntimeError("impossible de démarrer le serveur")

    def _wait_ready(self):
        """Prêt = NOTRE Vite annonce NOTRE port dans son journal, est toujours vivant, et la page
        servie est ChessLocal. Un port qui répond 200 ne prouve rien : ce peut être le serveur
        d'un autre worktree, arrivé sur ce port juste avant nous."""
        deadline = time.time() + READY_TIMEOUT_S
        announced = False
        while time.time() < deadline:
            if not self.alive():
                return False
            announced = announced or f"{HOST}:{self.port}" in ANSI.sub("", read(self.log_path))
            if announced and serves_app(f"{self.base}/"):
                return self.alive()
            time.sleep(0.3)
        return False

    def stop(self, check_port=True, keep_log=False):
        if self.own_group:
            kill_group(self.proc, "serveur")
        elif self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=STOP_GRACE_S)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=STOP_GRACE_S)
        self.proc = None
        if self.log_path and not keep_log:
            try:
                os.remove(self.log_path)
            except OSError:
                pass
        if check_port and self.port and port_is_listening(self.port):
            raise RuntimeError(f"le port {self.port} écoute encore après l'arrêt du serveur")


class SuiteRun:
    """Une suite lancée dans son propre groupe de process et son propre TMPDIR. Avec plusieurs
    workers, sa sortie va dans un fichier, imprimé d'un bloc à la fin : des suites entrelacées
    ligne à ligne seraient illisibles. Seule, elle écrit directement sur la sortie du lanceur.

    Le TMPDIR propre attrape ce que le groupe ne couvre pas : Playwright lance Chromium détaché
    (autre groupe), avec son profil dans le dossier temporaire. Tout process dont la ligne de
    commande cite ce dossier est tué à la fin, puis le dossier est supprimé."""

    def __init__(self, name, path, base, extra_env, buffered):
        self.name = name
        self.problem = None
        self.duration = None
        self.tmp = tempfile.mkdtemp(prefix=f"chesslocal-e2e-{name}-")
        env = {k: v for k, v in os.environ.items() if k != "E2E_LIVE"}
        env.update(extra_env)
        env.update({"BASE": base, "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": self.tmp})
        self.log_path = os.path.join(self.tmp, "sortie.log") if buffered else None
        if not buffered:
            say(f"\n{'=' * 60}\n[run] suite {name}\n{'=' * 60}")
        out = open(self.log_path, "w") if buffered else None
        self.started = time.time()
        try:
            self.proc = subprocess.Popen([sys.executable, path], cwd=ROOT, env=env, stdout=out,
                                         stderr=subprocess.STDOUT if buffered else None, start_new_session=True)
        finally:
            if out:
                out.close()

    def elapsed(self):
        return time.time() - self.started

    def done(self):
        return self.proc.poll() is not None

    def progress(self):
        text = read(self.log_path) if self.log_path else ""
        return f"{self.name} {self.elapsed():.0f} s ({text.count('[PASS]')} PASS, {text.count('[FAIL]')} FAIL)"

    def finish(self, problem=None):
        """Arrête le groupe (toujours, même après une sortie normale : un Chromium ou un serveur
        propre à la suite ne doit pas lui survivre) et fixe le résultat."""
        kill_group(self.proc, f"suite {self.name}")
        subprocess.run(["pkill", "-KILL", "-f", self.tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.duration = self.elapsed()
        if problem is None and self.proc.returncode != 0:
            problem = "suite impossible à arrêter" if self.proc.returncode is None else f"code de sortie {self.proc.returncode}"
        self.problem = problem
        if self.log_path:
            say(f"\n{'=' * 60}\n[run] suite {self.name} ({self.duration:.0f} s)\n{'=' * 60}\n{read(self.log_path).rstrip()}")
        shutil.rmtree(self.tmp, ignore_errors=True)
        status = "OK" if problem is None else f"ÉCHEC : {problem.splitlines()[0]}"
        say(f"[run] fin de {self.name} en {self.duration:.0f} s : {status}")
        return problem


# Ordre de grandeur des durées (s, build de prod, Mac au repos, mesuré le 2026-10-16). Ne sert
# qu'à lancer les longues d'abord quand aucune mesure locale n'existe (worktree neuf du gate) ;
# une suite absente compte comme courte. Les mesures locales le remplacent dès le premier lancement.
TYPICAL_S = {
    "viewport": 150, "endgame_course": 115, "analysis_robust": 110, "coach": 90, "cours_roque": 85,
    "upgrade": 75, "all_buttons": 70, "learn": 70, "play_lifecycle": 60, "mats": 55, "edge_navigation": 50,
    "premove": 50, "pieces_sons": 45, "openings": 40, "diagnostic_attaque": 40, "revision": 37,
    "insights": 36, "puzzles": 36, "shell": 34, "continuation": 34, "endgames": 33,
}


def load_durations():
    """Dernière durée réussie par suite et par mode (fichier local, gitignoré), pour lancer les plus longues
    d'abord : une suite de 3 min démarrée en dernier allongerait tout le lancement d'autant."""
    try:
        with open(DURATIONS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: float(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_durations(durations):
    """Fusion avec les durées connues : un lancement d'une seule suite ne fait pas oublier les
    autres. Écriture atomique : deux lanceurs simultanés ne laissent jamais un fichier tronqué."""
    merged = {**load_durations(), **durations}
    try:
        os.makedirs(os.path.dirname(DURATIONS_PATH), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DURATIONS_PATH), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({k: round(v, 1) for k, v in sorted(merged.items())}, f, indent=1)
        os.replace(tmp, DURATIONS_PATH)
    except OSError:
        pass


HEARTBEAT_S = 60


def run_suites(names, available, base, server, timeout_s, extra_env, jobs, results, durations):
    """Lance `names` sur au plus `jobs` workers. Chaque suite a son navigateur, son groupe de
    process, son TMPDIR, et les suites qui démarrent un serveur prennent un port libre : rien
    n'est partagé hormis le serveur de l'app, en lecture seule. Surveillance commune : un serveur
    mort arrête toutes les suites en cours, une suite trop longue est tuée seule."""
    pending = list(names)
    running = []
    buffered = jobs > 1
    last_beat = time.time()

    def close(run, problem=None):
        results[run.name] = run.finish(problem)
        durations[run.name] = run.duration

    try:
        while pending or running:
            if server is not None and not server.alive():
                why = f"serveur mort pendant la suite (code {server.proc.returncode})\n{tail(server.log_path)}"
                while running:
                    close(running[0], why)
                    running.pop(0)
                for name in pending:
                    results[name] = "non lancée : serveur mort"
                return
            while pending and len(running) < jobs:
                name = pending.pop(0)
                if buffered:
                    say(f"[run] début de {name}")
                running.append(SuiteRun(name, available[name], base, extra_env, buffered))
            time.sleep(0.5)
            for run in list(running):
                # Retirée seulement une fois arrêtée : interrompue en plein arrêt, le `finally`
                # la reprend.
                if run.done():
                    close(run)
                    running.remove(run)
                elif run.elapsed() > timeout_s:
                    close(run, f"délai de {timeout_s} s dépassé")
                    running.remove(run)
            if buffered and running and time.time() - last_beat >= HEARTBEAT_S:
                last_beat = time.time()
                say(f"[run] en cours : {', '.join(r.progress() for r in running)} ; {len(pending)} en attente")
    finally:
        # Interruption (signal) : plus aucun signal ne doit couper ce nettoyage, et aucune suite
        # en cours ne doit survivre au lanceur.
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        while running:
            close(running.pop(0), "interrompue")


def default_jobs():
    """Deux workers au plus par défaut : chaque suite lance Chromium et parfois Stockfish."""
    return min(2, os.cpu_count() or 1)


def main():
    available = suites_available()
    parser = argparse.ArgumentParser(description="Lanceur E2E de ChessLocal")
    parser.add_argument("--mode", choices=["prod", "dev"], default="prod")
    parser.add_argument("--suite", action="append", metavar="NOM", help=f"cumulable, parmi : {', '.join(available)}")
    parser.add_argument("--timeout", type=int, default=900, help="délai maximum par suite, en secondes")
    parser.add_argument("--live", action="store_true", help="utilise l'API chess.com réelle (hors gate)")
    env_jobs = os.environ.get("E2E_JOBS", "")
    parser.add_argument("--jobs", type=int, default=None, metavar="N",
                        help=f"suites lancées en parallèle (défaut : E2E_JOBS, sinon {default_jobs()} sur cette machine)")
    args = parser.parse_args()
    if args.jobs is None:
        try:
            args.jobs = int(env_jobs) if env_jobs else default_jobs()
        except ValueError:
            say(f"[run] E2E_JOBS invalide : {env_jobs!r} (entier attendu)")
            return 2
    if args.jobs < 1:
        say(f"[run] --jobs doit valoir au moins 1 (reçu {args.jobs})")
        return 2

    # Une suite demandée deux fois ne tourne qu'une fois : sinon le second résultat écraserait
    # le premier, et un échec suivi d'un succès finirait en code 0.
    wanted = list(dict.fromkeys(args.suite or available))
    unknown = [s for s in wanted if s not in available]
    if unknown:
        say(f"[run] suite inconnue : {', '.join(unknown)}. Suites disponibles : {', '.join(available)}")
        return 2

    external = os.environ.get("BASE", "").rstrip("/")
    if not external and not os.path.exists(VITE):
        say("[run] node_modules absent : lance `npm ci` d'abord.")
        return 2
    try:
        import chess  # noqa: F401
        import playwright  # noqa: F401
    except ImportError as e:
        say(f"[run] prérequis Python absent ({e.name}) : `pip install -r e2e/requirements.txt` (Chromium s'installe ensuite tout seul).")
        return 2
    if not ensure_browser():
        return 2
    if external:
        # Un BASE resté exporté dans le shell ferait tester autre chose que ce checkout, sans build :
        # on l'annonce, et on exige au moins que la cible soit bien ChessLocal.
        say(f"[run] CIBLE EXTERNE : BASE={external} (aucun build, aucun serveur local). `unset BASE` pour tester ce checkout.")
        if not serves_app(f"{external}/"):
            say(f"[run] {external}/ ne sert pas ChessLocal : aucune suite lancée.")
            return 2

    def interrupt(signum, _frame):
        raise Interrupted(signal.Signals(signum).name)

    # SIGHUP compris : terminal ou panneau fermé. Les enfants sont dans leurs propres sessions,
    # donc sans ce nettoyage Vite et la suite survivraient en serveurs fantômes.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupt)

    server = None
    out_dir = None
    results = {}
    durations = {}
    jobs = args.jobs
    t_total = time.time()
    try:
        extra_env = {}
        if args.live:
            say("\n" + "!" * 60 + "\n[run] MODE RÉSEAU RÉEL : API chess.com, HORS GATE\n" + "!" * 60)
            extra_env["E2E_LIVE"] = "1"
        if not external:
            if args.mode == "prod":
                out_dir = tempfile.mkdtemp(prefix="chesslocal-e2e-dist-")
                build(out_dir)
                extra_env["E2E_DIST"] = out_dir
            server = Server(args.mode, out_dir)
            server.start()
        base = external or server.base
        to_run = []
        for name in wanted:
            results[name] = "non lancée"  # le bilan suit l'ordre demandé, pas celui d'exécution
            if name in PROD_ONLY and (external or args.mode != "prod"):
                results[name] = "SKIP"
                say(f"\n[run] suite {name} ignorée : elle n'a de sens que sur le build local (--mode prod)")
            else:
                to_run.append(name)
        known = load_durations()
        if args.jobs > 1:
            # Les plus longues d'abord (tri stable : ordre alphabétique à durée égale).
            to_run.sort(key=lambda n: -known.get(f"{args.mode}:{n}", TYPICAL_S.get(n, 0)))
        jobs = min(args.jobs, max(1, len(to_run)))
        say(f"[run] {len(to_run)} suite(s), {jobs} en parallèle")
        run_suites(to_run, available, base, server, args.timeout, extra_env, jobs, results, durations)
    except Interrupted as e:
        say(f"\n[run] interrompu ({e})")
        results["(lanceur)"] = f"interrompu ({e})"
    except RuntimeError as e:
        say(f"[run] {e}")
        results["(lanceur)"] = str(e)
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)  # le nettoyage ne doit pas être interrompu à son tour
        # Nettoyer D'ABORD, parler ensuite : rien ne doit pouvoir s'intercaler avant l'arrêt du serveur.
        failed_so_far = any(problem not in (None, "SKIP") for problem in results.values())
        kept_log = server.log_path if server and failed_so_far else None
        if server:
            try:
                server.stop(keep_log=failed_so_far)
            except RuntimeError as e:
                results["(nettoyage)"] = str(e)
        if out_dir:
            shutil.rmtree(out_dir, ignore_errors=True)
        if kept_log:
            say(f"[run] journal du serveur conservé : {kept_log}")

    # Seules les suites réussies renseignent l'ordonnancement : une suite tuée au délai ou par un
    # serveur mort fausserait sa durée.
    if not external:
        save_durations({f"{args.mode}:{n}": d for n, d in durations.items() if results.get(n) is None})
    say(f"\n{'=' * 60}\n[run] bilan ({'cible externe' if external else 'mode ' + args.mode}, {jobs} en parallèle)")
    for name, problem in results.items():
        status = "SKIP" if problem == "SKIP" else ("OK" if problem is None else "ÉCHEC")
        took = f"{durations[name]:6.0f} s" if name in durations else " " * 8
        first_line = "" if problem in (None, "SKIP") else " : " + problem.splitlines()[0]
        say(f"  {status:6} {took}  {name}{first_line}")
    say(f"[run] durée totale : {time.time() - t_total:.0f} s (somme des suites : {sum(durations.values()):.0f} s)")
    failed = [n for n, problem in results.items() if problem not in (None, "SKIP")]
    ran = [n for n, problem in results.items() if problem is None]
    if not failed and not ran:
        say("[run] aucune suite exécutée")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
