def verdict_text(page):
    return page.evaluate("() => { const b=[...document.querySelectorAll('div.flex.items-center.gap-2.px-3.py-2')][0]; return b ? b.innerText.replace(/\\n/g,' | ') : null }")
