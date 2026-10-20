# Screenshots

The captures of the interface.

The images live in `screenshots/` at the root of the repository, not in
this folder. This file indexes them: what each one shows and where
it came from. The two are split because the repository already had
`screenshots/` with the captures in it, and the README points at them from
there.

## Where the captures come from

`scripts/screenshot_ui.py` takes them. It drives the app with Playwright
against the local stack on `127.0.0.1:3001`, with the demo data from
`scripts/seed_demo.py`, on an iPhone Pro Max viewport of 430 by 932
pixels. The colour scheme is pinned at the browser context, dark by
default, so a run is the same twice. `PETZY_SHOT_THEME=light` takes the
light set.

The accounts in the captures are the demo accounts, and the data in them is
the demo data. Nothing in them belongs to a real person.

The other two sets come from two other scripts: `scripts/profile_pages.py`
for the set in `screenshots/profile/`, and `scripts/profile_low_end.py` for
the set in `screenshots/low_end/`.

## The captures

| Capture | What it shows |
| --- | --- |
| `00_login.png` | The sign-in screen. |
| `dashboard.png` | The feed: today's records, the nearest dose and the pet card. |
| `pets.png` | The list of the pets. |
| `history.png` | The history with the filters and the charts. |
| `medications.png` | The courses, the doses and the stock. |
| `settings.png` | The settings. |
| `quick_add_sheet.png` | The sheet that asks what to record. |
| `health_form.png` | The form of a record, here a feeding. |
| `pet_form.png` | The form that adds a pet. |
| `pet_events.png` | The events of a pet, in the order the family set. |
| `event_catalog.png` | The catalogue of the event types. |
| `form_defaults.png` | The defaults of the form fields, per pet. |
| `pet_look.png` | The look of a pet: the picture, the colour, the caption and the handwritten name. |
| `admin_panel.png` | The admin panel with the blocked accounts. |
| `user_form.png` | The form that creates a user. |
| `medical_card.png` | The medical card of a pet. |
| `medical_card_vet.png` | The medical card as it is given to a vet. |
| `medical_card_prevention.png` | The vaccinations and the treatments. |
| `medication_form.png` | The form of a course. |
| `navbar_1pet_state.png`, `navbar_2pets.png`, `navbar_2pets_state.png`, `navbar_2pets_popup.png` | The top bar with one pet and with several. |
| `bottomtab_lucide.png` | The bottom bar after the change of the icon set. |
| `swipe_pets.png` | The swipe on a pet in the list. |
| `history_swipe_left.png`, `history_swipe_right.png` | The swipe on a record in the history. |
| `dashboard_fab_fix.png` | The round button after the fix of its place. |
| `dashboard_new_petcard.png`, `dashboard_new_petcard_only.png` | The new pet card in the feed. |
| `dashboard_nextdose_after.png` | The feed with the nearest dose. |

The names with a fix in them are the passes. The README shows the current
set, and the older passes are kept beside it.

## The two other sets

`screenshots/profile/` holds the pages of the performance profile: the
sign-in, the feed, the pets, the history as a chart and as a list, the
medicines, the forms, the settings and the tiles, with `report.json`
beside them.

`screenshots/low_end/` holds the same pages on a slow device, twice: cold,
before the data is in the cache, and warm, after it. The pairs are the
admin panel, the feed, the history, the medicines and the pets.

## Putting a picture here

This folder is part of the standard, and the images the README shows are
referenced by a relative path, so they have to live somewhere the checker
can resolve. A new capture that the README is going to show can go into
`screenshots/` beside the others, and this index is the place to describe
it.
