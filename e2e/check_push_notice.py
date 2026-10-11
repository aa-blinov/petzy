"""The medicines list must not slide down under the person reading it.

The list sits under two things that are not always there on the first frame: a dose marked with
no connection, and the notice that this phone cannot hear reminders. Both asked the browser
something and drew nothing until the answer came. The push one costs `await
navigator.serviceWorker.ready`, which is seconds while the worker installs or activates, and
every deploy makes a new one. The notice then appeared above a list that had been on screen for
those seconds, and every card below it moved down at once (107 px on a 390 px screen).

So the rule is: what the browser last answered is known, the notice is on screen with the list
instead of under it, and nothing on the page moves while it settles.

Headless Chromium will not grant the notifications permission, so the phone this stands for is
built in the page: notifications allowed, nothing ever subscribed, and a service worker still
installing. The remembered answer is put in place too, which is what every open after the first
has. Needs the local stack and the demo data. Makes one course of its own and removes it.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

COURSE = "Т-проверка напоминания"

PHONE_THAT_HASNT_SUBSCRIBED = """
(() => {
  // Watch the page from its first frame: a shift that happens before a protocol call could
  // register it has already happened by then.
  window.__shifts = [];
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      if (e.hadRecentInput) continue;
      window.__shifts.push({
        t: Math.round(e.startTime),
        value: e.value,
        sources: (e.sources || []).map((s) => {
          const el = (s.node && s.node.nodeType === 1) ? s.node : s.node && s.node.parentElement;
          return el ? (el.className || '').toString().trim().split(/\\s+/).slice(0, 2).join('.') : '?';
        }),
      });
    }
  }).observe({ type: 'layout-shift', buffered: true });

  // Notifications are allowed on this phone and nothing was ever subscribed to.
  Object.defineProperty(Notification, 'permission', { get: () => 'granted', configurable: true });
  const worker = navigator.serviceWorker;
  const reallyReady = worker.ready;
  Object.defineProperty(worker, 'ready', {
    configurable: true,
    get: () => new Promise((resolve) => setTimeout(async () => {
      const registration = await reallyReady;
      Object.defineProperty(registration, 'pushManager', {
        configurable: true,
        value: { getSubscription: async () => null },
      });
      resolve(registration);
    }, 2500)),
  });

  // What this browser answered last time: every open after the first has it.
  try { localStorage.setItem('petzy:push-state', 'off'); } catch (e) { /* private mode */ }
})();
"""

READ_SHIFTS = "() => { const out = window.__shifts || []; window.__shifts = []; return out; }"

BANNER = """
() => {
  const found = Array.from(document.querySelectorAll('[role=note]'))
    .find((el) => /напоминан/i.test(el.textContent || ''));
  if (!found) return null;
  const box = found.getBoundingClientRect();
  const first = document.querySelector('.swipeable-row');
  return {
    top: Math.round(box.top),
    bottom: Math.round(box.bottom),
    firstCardTop: first ? Math.round(first.getBoundingClientRect().top) : null,
    text: (found.textContent || '').trim(),
  };
}
"""


async def main() -> int:
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        # The service worker stays on: the point of the check is what happens while it installs.
        ctx, pg = await new_page(b, init=PHONE_THAT_HASNT_SUBSCRIBED)
        med_id = None
        try:
            rex = await login(pg, "demo", "Рекс")
            made = await api(
                pg,
                "POST",
                "/medications",
                {
                    "pet_id": rex,
                    "name": COURSE,
                    "type": "Таблетка",
                    "default_dose": 1,
                    "dose_unit": "таб",
                    "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["09:00", "21:00"]},
                    "is_active": True,
                },
            )
            med_id = made["json"].get("id")
            check("a course to show the notice under was created", bool(med_id), f"status {made['status']}")

            await pg.goto(BASE + "/medications")
            await pg.wait_for_selector(".swipeable-row", timeout=20000)

            # While the worker is still not ready. Before the fix nothing was drawn yet, and the
            # notice arrived seconds later, under the list.
            early = await pg.evaluate(BANNER)
            check(
                "the notice is on screen before the browser has answered",
                early is not None,
                "" if early else "nothing drawn while the worker is still installing",
            )

            # And it stays where it is: nothing may move under the person reading.
            await pg.wait_for_timeout(5000)
            shifts = await pg.evaluate(READ_SHIFTS)
            worst = max((s["value"] for s in shifts), default=0.0)
            movers = sorted({node for s in shifts for node in s["sources"]})
            check(
                "nothing on the page moved while the notice settled",
                worst < 0.0005,
                f"worst {worst:.4f} at {[s['t'] for s in shifts if s['value'] == worst][:3]}ms, moved: {', '.join(movers) or '—'}",
            )

            banner = await pg.evaluate(BANNER)
            check(
                "the notice says the dose will not remind of itself, not just that something is wrong",
                bool(banner) and "не напомнит о себе" in banner["text"],
                (banner["text"][:70] if banner else "no notice"),
            )
            check(
                "it took its own place above the list, not any of the list's",
                bool(banner) and banner["firstCardTop"] is not None and banner["firstCardTop"] >= banner["bottom"],
                f"notice y {banner['top']}..{banner['bottom']}, first card y {banner['firstCardTop']}"
                if banner
                else "no notice",
            )
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        finally:
            if med_id:
                await api(pg, "DELETE", f"/medications/{med_id}")
        await b.close()
    summary("the medicines list that does not slide")


asyncio.run(main())
