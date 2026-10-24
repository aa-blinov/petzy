# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

The application is a Progressive Web App that installs on a phone (React 18, TypeScript, Vite, antd-mobile) over a Flask API and MongoDB. It has an MCP server for assistants, a service that sends the reminders, and a nightly backup of the database into object storage. The interface is Russian, and there is no localisation.

## Users

A family that looks after one pet together: several people record feeding, weight, litter and medicines from a phone, often on the go and with one hand. The owner invites the others, and the pet and its records are shared by everyone who has access.

The second situation: showing the data to a vet at the appointment, from the phone screen or as a PDF.

## Product Purpose

A pet health diary as a PWA that installs on a phone. It replaces the chats and the notes: everything the family records about the pet is in one place and visible to everyone.

Success for the user: nobody forgot and nobody gave a medicine twice, and at the appointment the data the vet needs is found in seconds. Success for the product: the diary stays the one place the family writes in.

## Positioning

One shared place for the family, where the pet's events, the medication courses with their schedule and reminders, and the medical card for the vet come together. The medical card and the PDF are assembled from the records and the pet's profile rather than filled in as a separate questionnaire. The catalogue of built-in events is picked for the kind of animal, the family adds its own event types, and the owner tunes the pet's look to its character.

The medical card is the part a neighbour cannot copy by adding a form. It reads the records, the profile and the catalogue, and it shows the gaps: what is overdue, what the record does not say, how far the card is from being complete.

## Operating Context

A phone with the PWA installed, a dark and a light theme, Web Push for the doses, the documents whose term is ending, the repeat of a vaccination or a parasite treatment, and the unusual values. The data sits on the project's server (Flask, MongoDB), the scans and the archives in object storage. The app is rolled out automatically on a push to `master`.

The interface is Russian. Numbers are written the Russian way, with the unit next to the value. A date and a time are kept as they were typed, with the time zone of the person who typed them, so two phones in two zones agree on what happened.

## Capabilities and Constraints

Confirmed by the code:

- 34 built-in event types in a catalogue, grouped by kind, and 13 kinds of animal, each with its own small starter set. The family adds its own types with their own fields, and only the family that created them sees them.
- A feed, a history with filters, a chart of trends, and notifications about unusual values.
- Export to CSV, TSV, HTML, Markdown, or a ZIP with one file per record type. The file comes back in the answer and is stored nowhere.
- Medication courses with a schedule, start and end dates, the reason and the doctor, the doses, the stock, the nearest dose on the feed, a dose time that can be corrected, and a dose that can be cancelled.
- Documents: photos and PDFs up to 10 MB, scans and archives up to 500 MB, sent straight to object storage. The quota is 2048 MB per pet owner.
- A medical card built from the records, and a PDF for the vet: what is needed at the appointment on the first page, the history after it (`fpdf2`, the DejaVu Sans font in `web/fonts`).
- A read-only link for a vet, for 1, 7 or 30 days, revocable at once. Only the hash of the secret is in the database.
- Personal access tokens for scripts and assistants: four scopes (`pets:read`, `events:write`, `history:read`, `medical:read`), from 1 to 365 days, 90 by default, at most 10 active ones, 120 requests a minute for each.
- An MCP server with five tools: `list_pets`, `list_event_types`, `add_event`, `get_history`, `get_medical_card`.
- Web Push reminders in steps, to everyone with access to the pet: "soon" at 14 and at 3 days for a vaccination, at 7 and at 3 for a parasite treatment, "today", "overdue", and "still overdue" a week later.
- A record removed by a swipe disappears at once and stays undoable for six seconds.
- Personal data under 152-FZ and Law of the Republic of Kazakhstan No. 94-V: the consent and the version of the policy are recorded at registration, and a user deletes their own account.

Deliberately not true, and worth knowing before a change:

- Everything is in Russian. There is no second language.
- The MCP server can add a record but cannot delete or change one.
- The link for a vet is read only. It cannot write anything.
- The medical card and the PDF invent nothing and write "not stated" where the record is silent.
- One fact is entered in one place: weight, the medicines and the documents in their own sections, the vaccinations, the treatments, the visits, the operations and the profile for the vet in the medical card.
- The repeat date («Следующая») of a vaccination or a treatment follows the record's date by the same interval for as long as it is the form's own (the usual interval put in, or an interval button pressed, also when the record is edited): the pressed button stays pressed. A date set by hand, typed or picked, is the person's and never moves. A date typed in that is unfinished or impossible stops the save with a message; it never silently leaves the old date.
- The repository and the CI logs are public, so no secret and no user data is printed.

## Brand Commitments

**Name:** Petzy. **Tone:** calm and direct.

The rules for the interface text, confirmed by the owner: no "·" separator, no long dash (a comma, a full stop, a colon instead), and the notes and the captions follow the humanizer-ru rules.

The visual identity lives in `DESIGN.md`: Material 3 with a copper seed, one accent (ginger copper) on cream paper, a single 12px corner for every rectangle in the app, a warm night theme with a counterpart for every colour, and DynaPuff for the wordmark alone. The screen is a column of sheets on cream paper, and copper is reserved for what means something.

## Evidence on Hand

- `README.md` describes the capabilities, and `screenshots/` holds the real interface.
- The live service at https://petzy.duckdns.org, and a demo account from `scripts/seed_demo.py`.
- `web/builtin_event_types.py` holds the catalogue of the 34 built-in types, `web/vaccines.py` the catalogue of the products, `web/medical_share.py` the read-only link, `web/medical_card_pdf.py` the PDF, `mcp/petzy_mcp/tools.py` the five tools of the MCP server.
- `docs/ux/` holds the audit of the user paths, one file per screen (36 screens, 298 findings), and `docs/qa/` the QA checklist.
- `audit/` holds the audits of the backend, the database and the interface.

Absent, and not to be invented: no reviews, no customers, no usage numbers. The project has none, so none are written here.

## Product Principles

1. **One shared source of truth for the family**, with no duplicates between the screens.
2. **What has to be done on the go is done with one hand and in a couple of taps.**
3. **The medical card is assembled from what has already been recorded**, and it shows the gaps instead of hiding them.
4. **Reminders are precise and do not repeat:** one correct one is better than three extra.
5. **The honest state comes first** ("not stated", "overdue"), the decoration after.

## Accessibility & Inclusion

- **Large touch targets**, from 44px (`--touch-min`), on every control including the small chips and the links.
- **Both themes carry enough contrast.** `e2e/check_accent_contrast.py` measures what lands on a pet's colour against the seven pet colours in both themes, on the rendered pixels, with a bar of 4.5:1.
- **A visible focus ring** for the keyboard, and an open sheet or dialog that keeps the Tab inside it and returns the focus to what opened it (`utils/antdA11y.ts`).
- **A status is a word and an icon**, never only a colour: "overdue", "not stated", "still overdue", with the days counted.
- **The interface reads on a narrow screen** and works as a PWA on a phone.

Not decided, and stated rather than guessed: a formal conformance standard for the interface has not been set, and the interface is in Russian only, so a person who does not read Russian cannot use the app.
