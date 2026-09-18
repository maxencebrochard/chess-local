"""Lanceur E2E autonome : `npm run test:e2e`.

Démarre SON serveur sur un port libre, vérifie que c'est bien lui qui répond, lance les suites
une par une, surveille le serveur pendant qu'elles tournent, et l'arrête toujours.

    python3 e2e/run.py                  # build de prod servi sous /chess-local/ (comme GitHub Pages)
    python3 e2e/run.py --mode dev       # serveur de dev : React StrictMode double les updaters,
                                        # ce qui révèle les effets de bord mal placés
    python3 e2e/run.py --suite learn    # une seule suite (option cumulable : --suite learn --suite v4)
    BASE=https://… python3 e2e/run.py   # cible externe : aucun serveur lancé

Codes de sortie : 0 tout passe, 1 au moins un échec, 2 mauvais usage ou prérequis manquant.
"""
import argparse
import glob
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
PROD_ONLY = {"pwa"}  # suites qui n'ont de sens que sur le build local (service worker, manifest, hors ligne)

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


def kill_group(proc, label):
    """SIGTERM au groupe, délai de grâce, puis SIGKILL. On vise le GROUPE même si son chef est
    déjà mort : Vite lance esbuild et des workers qui lui survivraient."""
    if proc is None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            break
        try:
            proc.wait(timeout=STOP_GRACE_S)
            break
        except subprocess.TimeoutExpired:
            say(f"[run] {label} ne s'arrête pas après {sig.name}, on insiste")
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
            cmd = [VITE] + (["preview", "--outDir", self.out_dir, "--base", SUBPATH] if self.mode == "prod" else [])
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


def run_suite(name, path, base, server, timeout_s, extra_env):
    """Lance une suite et la surveille. Sans ça, une suite attend jusqu'à 180 s sur un serveur
    mort puis échoue ailleurs, et on cherche un bug qui n'existe pas."""
    say(f"\n{'=' * 60}\n[run] suite {name}\n{'=' * 60}")
    env = {**os.environ, **extra_env, "BASE": base, "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen([sys.executable, path], cwd=ROOT, env=env, start_new_session=True)
    started = time.time()
    try:
        while proc.poll() is None:
            if server is not None and not server.alive():
                return f"serveur mort pendant la suite (code {server.proc.returncode})\n{tail(server.log_path)}"
            if time.time() - started > timeout_s:
                return f"délai de {timeout_s} s dépassé"
            time.sleep(0.5)
    finally:
        kill_group(proc, f"suite {name}")
    return None if proc.returncode == 0 else f"code de sortie {proc.returncode}"


def main():
    available = suites_available()
    parser = argparse.ArgumentParser(description="Lanceur E2E de ChessLocal")
    parser.add_argument("--mode", choices=["prod", "dev"], default="prod")
    parser.add_argument("--suite", action="append", metavar="NOM", help=f"cumulable, parmi : {', '.join(available)}")
    parser.add_argument("--timeout", type=int, default=900, help="délai maximum par suite, en secondes")
    args = parser.parse_args()

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
        import playwright  # noqa: F401
    except ImportError:
        say("[run] Playwright absent : `pip install -r e2e/requirements.txt` puis `python3 -m playwright install chromium`.")
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
    try:
        extra_env = {}
        if not external:
            if args.mode == "prod":
                out_dir = tempfile.mkdtemp(prefix="chesslocal-e2e-dist-")
                build(out_dir)
                extra_env["E2E_DIST"] = out_dir
            server = Server(args.mode, out_dir)
            server.start()
        base = external or server.base
        for name in wanted:
            if name in PROD_ONLY and (external or args.mode != "prod"):
                results[name] = "SKIP"
                say(f"\n[run] suite {name} ignorée : elle n'a de sens que sur le build local (--mode prod)")
                continue
            results[name] = run_suite(name, available[name], base, server, args.timeout, extra_env)
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

    say(f"\n{'=' * 60}\n[run] bilan ({'cible externe' if external else 'mode ' + args.mode})")
    for name, problem in results.items():
        status = "SKIP" if problem == "SKIP" else ("OK" if problem is None else "ÉCHEC")
        first_line = "" if problem in (None, "SKIP") else " : " + problem.splitlines()[0]
        say(f"  {status:6} {name}{first_line}")
    failed = [n for n, problem in results.items() if problem not in (None, "SKIP")]
    ran = [n for n, problem in results.items() if problem is None]
    if not failed and not ran:
        say("[run] aucune suite exécutée")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
