"""Фон страницы не мигает при переходе между экранами.

У питомца выбран свой фон (сцена). Он лежит в переменной --pet-scene-bg на <body>, и
красит им себя <main>: то, что стоит вне .route-transition. Экран же лежит внутри этой
обёртки, а она проявляется при каждом переходе с opacity: 0. Пока проявляется, из-под
её фона виден обычный цвет страницы, и выбранный цвет питомца мигает.

Проверка смотрит в двух местах. Первое: красит ли фон тот, кто вне проявления, а не тот,
кто внутри. Второе: каким цветом нарисован край страницы в каждом кадре перехода. Если в
кадре проступает обычный цвет, мигание есть.

Свой питомец со сценой делает проверка сама и убирает за собой.
"""

import asyncio
import io

from common import BASE, api, async_playwright, check, login, new_page, summary

SCENE = {"accent": "teal", "scene": "dots", "backdrop": "fill"}
# Край страницы: слева от карточек, где нарисован сам фон, а не содержимое.
POINT = {"x": 8, "y": 420, "width": 1, "height": 1}


def _rgb(image_bytes):
    from PIL import Image

    return Image.open(io.BytesIO(image_bytes)).convert("RGB").getpixel((0, 0))


def _distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


async def _colour(pg, css: str):
    """The rgb a CSS colour paints as, whatever form it was written in."""
    return await pg.evaluate(
        """(c) => {
            const el = document.createElement('div');
            el.style.color = c;
            document.body.appendChild(el);
            const m = getComputedStyle(el).color.match(/[\\d.]+/g).map(Number);
            el.remove();
            return [Math.round(m[0]), Math.round(m[1]), Math.round(m[2])];
        }""",
        css,
    )


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        made = None
        try:
            await login(pg, "demo", "Рекс")
            made = (await api(pg, "POST", "/pets", {"name": "Тест-М", "species": "собака"}))["json"]["pet"]["_id"]
            await api(pg, "PUT", f"/pets/{made}/look", SCENE)
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [made, "Тест-М"],
            )
            await pg.goto(BASE + "/")
            await pg.wait_for_timeout(2500)

            # Кто красит сцену: тот, кто вне проявления, или тот, кто внутри него.
            where = await pg.evaluate(
                """() => {
                    const painted = el => {
                        const cs = getComputedStyle(el);
                        return cs.backgroundImage !== 'none' || !/rgba\\(0, 0, 0, 0\\)|transparent/.test(cs.backgroundColor);
                    };
                    return {
                        main: painted(document.getElementById('main-content')),
                        page: painted(document.querySelector('.page-container')),
                    };
                }"""
            )
            check("фон сцены красит тот, кто вне проявления", where["main"], str(where))
            check("экран внутри проявления фон сцены не красит", not where["page"], str(where))

            # Цвет, на котором фон успокаивается, и обычный цвет страницы, которым он быть не должен.
            on_feed = _rgb(await pg.screenshot(clip=POINT))
            await pg.get_by_role("link", name="Документы").click()
            await pg.wait_for_timeout(1500)
            on_documents = _rgb(await pg.screenshot(clip=POINT))
            plain = await _colour(pg, await pg.evaluate("() => getComputedStyle(document.body).backgroundColor"))

            check(
                "фон экрана одинаков на обоих экранах",
                _distance(on_feed, on_documents) <= 2,
                f"{on_feed} и {on_documents}",
            )
            check(
                "фон экрана это цвет питомца, а не обычный цвет страницы",
                _distance(on_feed, plain) > 8,
                f"{on_feed} против {plain}",
            )

            # Кадры обратного перехода: цвет по дороге не должен сходить с цвета питомца.
            await pg.get_by_role("link", name="Лента").click()
            frames = [_rgb(await pg.screenshot(clip=POINT)) for _ in range(14)]
            await pg.wait_for_timeout(700)
            worst = max(_distance(c, on_feed) for c in frames)
            check(
                "ни один кадр перехода не проступает обычным цветом страницы",
                worst <= 2,
                f"дальше всего от фона питомца на {worst:.1f}, кадры {frames[1:4]}, обычный {plain}",
            )
        finally:
            if made:
                await api(pg, "DELETE", f"/pets/{made}")
        await b.close()
    return summary("фон сцены не мигает")


asyncio.run(main())
