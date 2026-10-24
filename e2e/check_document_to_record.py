"""A document uploaded in «Документы» is attached to a visit afterwards, and let go of again, without touching the file.

The record's PUT is a full replace, so the check also reads the visit before and after: every field it had stays. Attached from
the «Действия» menu of the row; the form of the document then says which record holds it, and «Открепить» lets it go.

Needs the local stand and the demo data. Makes a scratch pet «Тест-М» (a visit and a document by the API) and removes it.
"""

import asyncio
from datetime import date, timedelta

from common import BASE, api, async_playwright, check, login, new_page, settle, summary, wait_until
from scratch import drop_pet, make_pet, make_record, ru

PDF = bytes([37, 80, 68, 70, 45, 49, 46, 52, 32, 120])  # %PDF-1.4 x


async def make_document(pg, pid, title):
    await pg.evaluate(
        """async ([pid, title, bytes]) => {
            const fd = new FormData();
            fd.append('pet_id', pid);
            fd.append('category', 'lab_result');
            fd.append('title', title);
            fd.append('file', new File([new Uint8Array(bytes)], 'анализ.pdf', {type: 'application/pdf'}));
            await fetch('/api/documents', {method: 'POST', body: fd, credentials: 'include'});
        }""",
        [pid, title, list(PDF)],
    )
    docs = (await api(pg, "GET", f"/documents?pet_id={pid}"))["json"]["documents"]
    return next(d["_id"] for d in docs if d["title"] == title)


async def record_of(pg, rid):
    return (await api(pg, "GET", f"/medical-records/{rid}"))["json"]["record"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await new_page(b, width=390, height=844, sw=False)
        await login(pg, "demo", "Рекс")
        pid = None
        try:
            pid = await make_pet(pg)
            await pg.evaluate(
                "([id, n]) => { localStorage.setItem('selectedPetId', JSON.stringify(id)); localStorage.setItem('selectedPetName', JSON.stringify(n)); }",
                [pid, "Тест-М"],
            )
            day = date.today() - timedelta(days=3)
            rid = await make_record(
                pg,
                pid,
                "visit",
                "Осмотр",
                day.isoformat(),
                clinic="Ортовет",
                vet="Иванова",
                note="Заметка визита",
                complaint="Вялость",
                diagnosis="Ничего страшного",
                recommendations="Покой",
            )
            doc_id = await make_document(pg, pid, "Анализ крови")
            before = await record_of(pg, rid)
            check("the visit starts with no documents", before["documents"] == [])

            # attach from the «Действия» menu of the row
            await pg.goto(BASE + "/documents")
            await settle(pg)
            await pg.get_by_role("button", name="Действия: Анализ крови").click()
            await pg.locator(".adm-action-sheet-button-item", has_text="Прикрепить к записи").click()
            label = f"Визит к врачу, {ru(day)}: Осмотр"
            row = pg.get_by_role("button", name=label)
            await row.wait_for(state="visible", timeout=10000)
            check("the sheet lists the pet's records, named by kind, day and reason", await row.count() == 1)
            await row.click()
            await wait_until(pg, lambda t: "Документ прикреплён к записи" in t)
            await settle(pg, 150)
            after = await record_of(pg, rid)
            check(
                "the document is among the record's documents",
                [d["id"] for d in after["documents"]] == [doc_id],
                str(after["documents"]),
            )
            kept = ("date", "title", "clinic", "vet", "note", "complaint", "diagnosis", "recommendations", "next_due")
            check(
                "the full replace kept every other field of the visit",
                all(before[k] == after[k] for k in kept),
                str({k: (before[k], after[k]) for k in kept if before[k] != after[k]}),
            )

            # the form says which record holds the file
            await pg.goto(BASE + f"/documents/{doc_id}/edit")
            await settle(pg)
            body = await wait_until(pg, lambda t: "Прикреплён к записи" in t)
            check(
                "the form of the document names the record that holds it",
                f"Прикреплён к записи: {label}" in body,
                body[:300].replace(chr(10), " | "),
            )
            check(
                "the file has one label on the form, not a header and a row both",
                len([line for line in body.split("\n") if line.strip() == "Файл"]) <= 1,
                body[:120].replace(chr(10), " | "),
            )
            await pg.get_by_role("button", name="Открепить").click()
            await wait_until(pg, lambda t: "Документ откреплён от записи" in t)
            await settle(pg, 150)
            gone = await record_of(pg, rid)
            check("detached: the record let go of the document", gone["documents"] == [], str(gone["documents"]))
            check(
                "detached: the visit's other fields are as they were",
                all(before[k] == gone[k] for k in kept),
            )
            check(
                "the file itself is still there",
                any(
                    d["_id"] == doc_id for d in (await api(pg, "GET", f"/documents?pet_id={pid}"))["json"]["documents"]
                ),
            )
            check(
                "the form then says it is attached to nothing",
                "Не прикреплён ни к одной записи" in await wait_until(pg, lambda t: "Не прикреплён ни к одной" in t),
            )

            # and attached again from the form itself
            await pg.get_by_role("button", name="Прикрепить к записи").click()
            await pg.get_by_role("button", name=label).click()
            await wait_until(pg, lambda t: "Документ прикреплён к записи" in t)
            await settle(pg, 150)
            again = await record_of(pg, rid)
            check("attached from the form too", [d["id"] for d in again["documents"]] == [doc_id])
            check("no horizontal scroll", not await pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        finally:
            if pid:
                await drop_pet(pg, pid)
        await b.close()
    return summary("документ прикрепляется к записи и открепляется")


asyncio.run(main())
