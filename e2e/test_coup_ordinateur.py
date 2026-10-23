"""Coups de l'ordinateur : son du coup et retour haptique, sur chaque famille d'écran.

Un coup joué par l'ordinateur (bot de Jouer, Stockfish de PositionGame, des finales au chrono et
de Mats éclair, réponse précalculée d'un puzzle ou d'un cours, amorce, EngineContinuation) doit
produire le son adapté au coup (move-opponent, capture, castle, move-check, promote), une seule
fois, et dans l'app native un impact léger (moyen pour une prise, un échec ou une promotion),
plus discret que la pose du joueur.
Jamais de retour haptique sur la navigation de l'analyse ni au rechargement d'une partie.

Contexte : iPhone 14 Pro standalone, `WEBKIT_AUDIO` (politique audio de WebKit, journal des sons
audibles) et `CAPACITOR_IOS` (pont natif simulé, journal des appels haptiques).
Le coup de l'ordinateur est relu sur l'échiquier et son son attendu calculé par python-chess.
Usage : npm run test:e2e -- --suite coup_ordinateur
"""
import json
import sys

try:
    import chess
except ImportError:
    sys.exit("python-chess manquant : pip install -r e2e/requirements.txt")

from helpers import (
    open_learn_session,
    BASE,
    CAPACITOR_IOS,
    WEBKIT_AUDIO,
    Checker,
    fmt_sounds,
    haptic_log,
    mobile_context,
    shot,
    sound_log,
    tap_move,
    wait_sounds_ready,
)

ck = Checker("coup_ordinateur")
check = ck.check

LIFT, MOVE, CAPTURE = "impact:LIGHT", "impact:MEDIUM", "impact:HEAVY"
# Coup de l'ordinateur : impact léger, un cran plus marqué pour une prise, un échec ou une promotion.
REPLY, REPLY_STRONG = "impact:LIGHT", "impact:MEDIUM"
SOUND_ON = {"playSounds": True}

# Mat en 1 portant tous les thèmes, amorce ...Nc3 : quel que soit le thème tiré, la séance le sert.
LEARN_M1 = ["L10", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8", 1000,
            "fork pin skewer discoveredAttack mateIn1 mateIn2 mateIn3 backRankMate hangingPiece sacrifice "
            "deflection attraction promotion trappedPiece intermezzo defensiveMove rookEndgame pawnEndgame "
            "zugzwang exposedKing discoveredCheck advancedPawn kingsideAttack quietMove"]


def native_audio_context(p, browser, settings=SOUND_ON):
    ctx = mobile_context(p, browser, ck, settings=settings, standalone=True, service_workers="block")
    ctx.add_init_script(WEBKIT_AUDIO)
    ctx.add_init_script(CAPACITOR_IOS)
    return ctx


def ready(page, label, sounds=True):
    """Pilote haptique chargé et, sons allumés, tous les sons décodés sur un contexte actif.
    Le contexte ne tourne qu'après un premier geste (politique de WebKit) : un toucher hors
    échiquier le déverrouille, comme le premier toucher de l'utilisateur sur l'app."""
    try:
        page.wait_for_function("() => !!window.Capacitor?.Plugins?.Haptics", timeout=15000)
        native = True
    except Exception:
        native = False
    check(f"{label} : pilote haptique prêt", native)
    if sounds:
        page.locator("body").tap(position={"x": 5, "y": 5})
        check(f"{label} : sons décodés et contexte actif", wait_sounds_ready(page))


def marks(page):
    return len(sound_log(page)), len(haptic_log(page) or [])


def heard_since(page, n):
    return [e for e in sound_log(page)[n:] if e["name"] != "(muet)"]


def haptics_since(page, m):
    return (haptic_log(page) or [])[m:]


def sound_for(board, move, opponent):
    """Son attendu d'un coup, priorités de `moveSoundName` (sounds.ts)."""
    if board.gives_check(move):
        return "move-check"
    if move.promotion:
        return "promote"
    if board.is_castling(move):
        return "castle"
    if board.is_capture(move):
        return "capture"
    return "move-opponent" if opponent else "move-self"


def reply_haptic(board, move):
    return REPLY_STRONG if board.is_capture(move) or board.gives_check(move) or move.promotion else REPLY


def pose_haptic(board, move):
    return CAPTURE if board.is_capture(move) else MOVE


def move_between(board, placement):
    """Le coup légal de `board` qui mène au placement affiché, ou None."""
    for mv in board.legal_moves:
        b = board.copy()
        b.push(mv)
        if b.board_fen() == placement:
            return mv
    return None


def quiet_move(board):
    """Coup calme du joueur qui laisse la partie en cours : sons et retours attendus sans ambiguïté."""
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.is_castling(mv) or board.gives_check(mv):
            continue
        b = board.copy()
        b.push(mv)
        if not b.is_game_over() and any(True for _ in b.legal_moves):
            return mv
    raise RuntimeError("aucun coup calme")


PLACEMENT_JS = """(scope) => {
  const root = scope ? document.querySelector(scope) : document
  if (!root) return null
  const rows = []
  for (let r = 8; r >= 1; r--) {
    let row = '', empty = 0
    for (const f of 'abcdefgh') {
      const el = root.querySelector(`[data-square='${f}${r}'] [data-piece]`)
      const pc = el ? el.getAttribute('data-piece') : null
      if (!pc) { empty++; continue }
      if (empty) { row += empty; empty = 0 }
      row += pc[0] === 'w' ? pc[1] : pc[1].toLowerCase()
    }
    if (empty) row += empty
    rows.push(row)
  }
  return rows.join('/')
}"""


def placement(page, scope=None):
    return page.evaluate(PLACEMENT_JS, scope)


def wait_until(page, predicate, timeout=20000):
    waited = 0
    while waited < timeout:
        try:
            if predicate():
                return True
        except Exception:
            pass
        page.wait_for_timeout(100)
        waited += 100
    return False


def expect_feedback(label, page, n, m, sounds, haptics, settle=500):
    page.wait_for_timeout(settle)
    entries = heard_since(page, n)
    got = [(e["name"], e["audible"]) for e in entries]
    check(f"{label} : sons {sounds}", got == [(s, True) for s in sounds], f"(obtenu {fmt_sounds(entries)})")
    h = haptics_since(page, m)
    check(f"{label} : haptique {haptics}", h == haptics, f"(obtenu {h})")


def play_and_reply(label, page, board, scope=None):
    """Coup calme du joueur au toucher, puis réponse de l'ordinateur relue sur l'échiquier.
    Vérifie les deux sons (le mien puis le sien) et les trois retours (saisie, pose, réponse)."""
    mine = quiet_move(board)
    expected_self = sound_for(board, mine, False)
    pose = pose_haptic(board, mine)
    after_mine = board.copy()
    after_mine.push(mine)
    n, m = marks(page)
    prefix = f"{scope} " if scope else ""
    page.locator(f"{prefix}[data-square='{chess.square_name(mine.from_square)}']").first.tap()
    page.wait_for_timeout(200)
    page.locator(f"{prefix}[data-square='{chess.square_name(mine.to_square)}']").first.tap()
    replied = wait_until(page, lambda: move_between(after_mine, placement(page, scope)) is not None)
    if not check(f"{label} : l'ordinateur a répondu", replied, f"(placement {placement(page, scope)})"):
        return None
    reply = move_between(after_mine, placement(page, scope))
    expect_feedback(f"{label} ({mine.uci()} puis {reply.uci()})", page, n, m,
                    [expected_self, sound_for(after_mine, reply, True)],
                    [LIFT, pose, reply_haptic(after_mine, reply)])
    after_mine.push(reply)
    return after_mine


# ---------- Jouer : bot ----------

def play_suite(p, browser):
    for label, settings in (("[jouer bot]", SOUND_ON), ("[jouer entraîneur]", {**SOUND_ON, "playMode": "coach"})):
        ctx = native_audio_context(p, browser, {**settings, "playTcLabel": "Illimité"})
        page = ctx.new_page()
        page.goto(f"{BASE}/#/jouer")
        page.get_by_role("button", name="Jouer", exact=True).click()
        if ck.appears(f"{label} plateau", page, "[data-square=e2] [data-piece=wP]", timeout=20000):
            ready(page, label)
            board = play_and_reply(label, page, chess.Board())
            if board:
                play_and_reply(f"{label} 2e coup", page, board)
            shot(page, f"coup_ordinateur_{'bot' if 'bot' in label else 'coach'}")
        ctx.close()

    # Sons coupés : aucun son, mais l'haptique de la réponse reste (le bouton silencieux de
    # l'iPhone coupe Web Audio, pas les vibrations).
    ctx = native_audio_context(p, browser, {"playSounds": False, "playTcLabel": "Illimité"})
    page = ctx.new_page()
    page.goto(f"{BASE}/#/jouer")
    page.get_by_role("button", name="Jouer", exact=True).click()
    if ck.appears("[sons coupés] plateau", page, "[data-square=e2] [data-piece=wP]", timeout=20000):
        ready(page, "[sons coupés]", sounds=False)
        board = chess.Board()
        board.push_uci("e2e4")
        n, m = marks(page)
        tap_move(page, "e2", "e4")
        if check("[sons coupés] le bot a répondu", wait_until(page, lambda: move_between(board, placement(page)) is not None)):
            reply = move_between(board, placement(page))
            page.wait_for_timeout(500)
            check("[sons coupés] aucun son démarré", sound_log(page) == [], fmt_sounds(sound_log(page)))
            h = haptics_since(page, m)
            check("[sons coupés] haptique de la réponse conservée", h == [LIFT, MOVE, reply_haptic(board, reply)], str(h))
    ctx.close()


# ---------- PositionGame, finales au chrono, Mats éclair ----------

def data_fen(page, sel):
    return page.locator(sel).first.get_attribute("data-fen")


def position_game_suite(p, browser):
    ctx = native_audio_context(p, browser)
    page = ctx.new_page()
    # Audio déverrouillé AVANT la partie : chargée à froid, son game-start (demandé au montage,
    # contexte encore suspendu) partirait au toucher de `ready` une fois décodé, parfois après
    # le repère des sons du premier coup. Ouverte ensuite sans rechargement, il part au montage.
    page.goto(f"{BASE}/#/finales")
    ready(page, "[finales]")
    page.evaluate("() => { location.hash = '#/finales/lucena' }")
    game = "[data-testid='position-game']"
    if ck.appears("[finales] partie affichée", page, game, timeout=20000):
        check("[finales] son de début de partie au montage",
              wait_until(page, lambda: [e["name"] for e in heard_since(page, 0)] == ["game-start"], timeout=3000),
              fmt_sounds(heard_since(page, 0)))
        wait_until(page, lambda: page.locator(game).get_attribute("data-thinking") == "0")
        board = chess.Board(data_fen(page, game))
        after = play_and_reply("[finales PositionGame]", page, board)
        if after:
            wait_until(page, lambda: page.locator(game).get_attribute("data-thinking") == "0")
            # Rechargement : la partie reprend depuis le stockage sans rejouer un seul retour.
            page.reload()
            ck.appears("[finales] partie reprise", page, game, timeout=20000)
            page.wait_for_timeout(1500)
            check("[finales] reprise : aucun retour haptique", haptic_log(page) == [], str(haptic_log(page)))
            check("[finales] reprise : aucun son de coup", heard_since(page, 0) == [], fmt_sounds(heard_since(page, 0)))
            check("[finales] reprise : même position", chess.Board(data_fen(page, game)).board_fen() == after.board_fen())
    ctx.close()


def endgame_clock_suite(p, browser):
    ctx = native_audio_context(p, browser)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/finales/chrono")
    page.get_by_role("radio", name="30 s", exact=True).click()
    page.locator("[data-serie='kp-square']").click()
    run = "[data-run='endgame-clock']"
    if ck.appears("[finales chrono] série lancée", page, run, timeout=10000):
        ready(page, "[finales chrono]")
        play_and_reply("[finales chrono]", page, chess.Board(data_fen(page, run)))
    ctx.close()


def chrono_suite(p, browser):
    ctx = native_audio_context(p, browser)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/mats?d=chrono-krr")
    page.get_by_role("radio", name="15 s", exact=True).click()
    page.get_by_role("button", name="Commencer").click()
    run = "[data-run=chrono]"
    if ck.appears("[mats éclair] série lancée", page, run, timeout=10000):
        ready(page, "[mats éclair]")
        play_and_reply("[mats éclair]", page, chess.Board(data_fen(page, run)))
    ctx.close()


# ---------- Réponses précalculées : séance d'Apprendre, cours, EngineContinuation ----------

def learn_suite(p, browser):
    ctx = native_audio_context(p, browser)
    body = json.dumps([LEARN_M1])
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    open_learn_session(page, "tactic")
    if not ck.appears("[séance] leçon tactique", page, "button:has-text(\"C'est parti\")", timeout=20000):
        ctx.close()
        return
    ready(page, "[séance]")
    n, m = marks(page)
    page.get_by_role("button", name="C'est parti").click()
    wait_until(page, lambda: page.locator("[data-square=c3] [data-piece=bN]").count() == 1)
    expect_feedback("[séance] amorce adverse ...Nc3", page, n, m, ["move-opponent"], [REPLY])

    # Coup faux : montré puis repris, aucun retour de réponse ; puis EngineContinuation.
    tap_move(page, "h2", "h3")
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Jouer contre le moteur").click()
    dialog = "[data-continuation]"
    if ck.appears("[continuation] dialogue", page, f"{dialog} [data-square=h2] [data-piece=wP]", timeout=10000):
        page.wait_for_timeout(500)
        play_and_reply("[continuation]", page, chess.Board("6k1/5ppp/8/8/8/2n5/5PPP/R5K1 w - - 1 2"), scope=dialog)
    ctx.close()

    # Solution : le coup du joueur ne vibre qu'une fois (pose), sans retour de réponse.
    ctx = native_audio_context(p, browser)
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    open_learn_session(page, "tactic")
    if ck.appears("[séance mat] leçon tactique", page, "button:has-text(\"C'est parti\")", timeout=20000):
        ready(page, "[séance mat]")
        page.get_by_role("button", name="C'est parti").click()
        wait_until(page, lambda: page.locator("[data-square=c3] [data-piece=bN]").count() == 1)
        page.wait_for_timeout(400)
        n, m = marks(page)
        tap_move(page, "a1", "a8", pause=200)
        expect_feedback("[séance mat] mon coup gagnant", page, n, m, ["success", "move-check"], [LIFT, MOVE], settle=800)
    ctx.close()


def course_suite(p, browser):
    ctx = native_audio_context(p, browser)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre/finales/mat-deux-tours")
    if ck.appears("[cours] leçon", page, "button:has-text('Continuer')", timeout=20000):
        ready(page, "[cours]")
        n, m = marks(page)
        page.get_by_role("button", name="Continuer", exact=True).click()
        page.wait_for_timeout(400)
        expect_feedback("[cours] passage au diagramme suivant", page, n, m, [], [])
        n, m = marks(page)
        tap_move(page, "a1", "a4")
        wait_until(page, lambda: len(heard_since(page, n)) >= 2)
        expect_feedback("[cours] mon coup puis la réponse du cours", page, n, m, ["move-self", "move-opponent"], [LIFT, MOVE, REPLY])
    ctx.close()


# ---------- Analyse : navigation, son sans haptique ----------

def analysis_suite(p, browser):
    ctx = native_audio_context(p, browser)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    if ck.appears("[analyse] plateau", page, "[data-square=e2] [data-piece=wP]", timeout=30000):
        ready(page, "[analyse]")
        n, m = marks(page)
        tap_move(page, "e2", "e4")
        tap_move(page, "e7", "e5")
        expect_feedback("[analyse] deux coups joués à la main", page, n, m, ["move-self", "move-opponent"], [LIFT, MOVE, LIFT, MOVE])
        page.get_by_role("button", name="Précédent").click()
        page.wait_for_timeout(300)
        n, m = marks(page)
        page.get_by_role("button", name="Suivant").click()
        expect_feedback("[analyse] navigation vers ...e5", page, n, m, ["move-opponent"], [])
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        play_suite(p, browser)
        position_game_suite(p, browser)
        endgame_clock_suite(p, browser)
        chrono_suite(p, browser)
        learn_suite(p, browser)
        course_suite(p, browser)
        analysis_suite(p, browser)
    finally:
        browser.close()


ck.run(suite)
