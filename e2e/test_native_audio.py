"""Mesure le signal Web Audio réel, sans émuler l'état du contexte iOS."""
import json
import os
from pathlib import Path

from helpers import BASE, SHOTS, Checker, shot, tap_move, drag_piece

ck = Checker('native_audio')

PROBE = r"""(() => {
  window.audioEvents = [];
  window.audioPeak = 0;
  window.audioRelease = 0;
  addEventListener('pointerup', () => window.audioRelease = performance.now(), true);
  const urls = new WeakMap(), names = new WeakMap();
  const arrayBuffer = Response.prototype.arrayBuffer;
  Response.prototype.arrayBuffer = async function(...args) {
    const data = await arrayBuffer.apply(this, args); urls.set(data, this.url); return data;
  };
  const decode = BaseAudioContext.prototype.decodeAudioData;
  BaseAudioContext.prototype.decodeAudioData = function(data, ...args) {
    const result = decode.call(this, data, ...args);
    result.then(buffer => names.set(buffer, urls.get(data)), () => {});
    return result;
  };
  const connect = AudioNode.prototype.connect;
  AudioNode.prototype.connect = function(destination, ...args) {
    const result = connect.call(this, destination, ...args);
    if (this instanceof GainNode && destination === this.context.destination) {
      // Garder le signal pendant le rendu React : 2048 échantillons (~46 ms)
      // disparaissaient avant que le thread principal puisse relire l'analyseur.
      const analyser = this.context.createAnalyser(); analyser.fftSize = 32768;
      connect.call(this, analyser);
      const samples = new Float32Array(analyser.fftSize);
      setInterval(() => {
        analyser.getFloatTimeDomainData(samples);
        for (const value of samples) window.audioPeak = Math.max(window.audioPeak, Math.abs(value));
      }, 5);
    }
    return result;
  };
  const start = AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start = function(...args) {
    const url = names.get(this.buffer);
    if (url) window.audioEvents.push({name: url.split('/').pop(), state: this.context.state, at: performance.now()});
    return start.apply(this, args);
  };
})()"""

HOLD = """(() => {
  const original = fetch;
  let release;
  const pending = new Promise(resolve => release = resolve);
  window.releaseAudio = release;
  window.fetch = async (...args) => {
    const response = await original(...args);
    if (String(args[0]).includes('/sounds/')) await pending;
    return response;
  };
})()"""


def suite(p):
    observations = []
    # Le lanceur standard installe Chromium. WebKit est une vérification locale
    # complémentaire : NATIVE_AUDIO_ENGINES=chromium,webkit.
    for engine in os.environ.get('NATIVE_AUDIO_ENGINES', 'chromium').split(','):
        browser = getattr(p, engine).launch()
        try:
            for delayed in (False, True):
                ctx = browser.new_context(**p.devices['iPhone 14 Pro'], service_workers='block')
                ck.watch(ctx)
                ctx.add_init_script(PROBE)
                if delayed:
                    ctx.add_init_script(HOLD)
                page = ctx.new_page()
                page.goto(f'{BASE}/#/analyse')
                page.wait_for_selector('[data-square=e2] [data-piece]')
                ck.check(f'{engine}: nouveau profil Atelier', page.locator('[data-piece] img[src*="/atelier/"]').count() == 32)
                tap_move(page, 'e2', 'e4')
                page.wait_for_timeout(1000)
                if delayed:
                    tap_move(page, 'e7', 'e5')
                    page.wait_for_timeout(400)
                    page.evaluate('releaseAudio()')
                    page.wait_for_timeout(600)
                    ck.check(f'{engine}: aucun son obsolète après chargement', page.evaluate('audioEvents.length === 0 && audioPeak === 0'))
                    tap_move(page, 'g1', 'f3')
                    expected = 'move-self.mp3'
                else:
                    ck.check(f'{engine}: premier coup émet un signal réel', page.evaluate("audioEvents.length === 1 && audioEvents[0].name === 'move-self.mp3' && audioEvents[0].state === 'running' && audioPeak > .001"))
                    page.evaluate('audioPeak = 0; audioEvents = []')
                    drag_piece(page, 'e7', 'e5')
                    expected = 'move-opponent.mp3'
                page.wait_for_timeout(600)
                result = page.evaluate('({events: audioEvents, peak: audioPeak})')
                ck.check(f'{engine}: coup suivant audible, chargement retardé={delayed}',
                         len(result['events']) == 1 and result['events'][0]['name'] == expected
                         and result['events'][0]['state'] == 'running' and result['peak'] > .001, str(result))
                if not delayed:
                    release = page.evaluate('audioRelease')
                    latency = result['events'][0]['at'] - release if len(result['events']) == 1 else -1
                    ck.check(f'{engine}: son à chaud dans les 80 ms après relâchement',
                             0 <= latency <= 80, f'{latency:.1f} ms')
                observations.append({'engine': engine, 'delayed': delayed, **result})
                shot(page, f'native_audio_{engine}_{delayed}')
                ctx.close()
        finally:
            browser.close()
    Path(SHOTS, 'native-audio.json').write_text(json.dumps(observations, indent=2))


ck.run(suite)
