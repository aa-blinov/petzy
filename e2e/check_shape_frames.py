"""A frame cut to a shape stays visible on the card, with or without a photo.

The shape is a mask: without a photo its background used to be the card's own colour, and the shape vanished; with a
photo its edge could merge into a light card. A shape frame now has a tint without a photo and an outline with one, and a
round frame (the story ring) keeps its own gradient. A throwaway pet is made for the check and deleted afterwards.
"""

import asyncio

from common import BASE, api, async_playwright, check, login, new_page, summary

PET = "qa-shape-r8"


async def avatar_state(pg):
    # Only inside this pet's card: other elements of the page may carry a shadow of their own.
    return await pg.evaluate(
        """((name) => {
          const card = [...document.querySelectorAll('.card-soft')].find(c => c.textContent.includes(name));
          const wrap = card ? card.querySelector('[style*="drop-shadow"]') : null;
          const avatar = wrap ? wrap.firstElementChild : null;
          return {
            outlined: Boolean(wrap),
            background: avatar ? getComputedStyle(avatar).backgroundColor : null,
          };
        })(%s)"""
        % repr(PET)
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx, pg = await new_page(browser)
        await login(pg)
        made = await api(pg, "POST", "/pets", {"name": PET, "species": "cat", "gender": "female"})
        pid = made["json"]["pet"]["_id"]
        try:
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, PET],
            )
            await api(pg, "PUT", f"/pets/{pid}/look", {"frame": "heart", "accent": "rose"})
            await pg.goto(BASE + "/")
            await pg.wait_for_timeout(1500)
            heart = await avatar_state(pg)
            check("a heart frame without a photo is outlined", heart["outlined"], str(heart))
            check(
                "and its shape has a tint of the pet's colour, not the card's own",
                heart["background"] not in (None, "rgba(0, 0, 0, 0)"),
                str(heart["background"]),
            )

            await api(pg, "PUT", f"/pets/{pid}/look", {"frame": "story", "accent": "rose"})
            await pg.goto(BASE + "/")
            await pg.wait_for_timeout(1500)
            story = await avatar_state(pg)
            check("a round frame (story) is not cut by the shape rule", story["outlined"] is False, str(story))
        finally:
            await api(pg, "DELETE", f"/pets/{pid}")
            await ctx.close()
        await browser.close()
    summary("shape frames")


asyncio.run(main())
