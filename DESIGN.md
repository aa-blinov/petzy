---
name: Petzy
description: A pet health diary on warm cream paper, written in ginger-cat copper.
colors:
  ginger-cat: "#C46A3F"
  ginger-deep: "#AD5830"
  copper-ink: "#9C4D28"
  peach-fur: "#E8946A"
  apricot-wash: "rgba(196, 106, 63, 0.12)"
  cream-paper: "#FFF8F3"
  milk-card: "#FFFBF7"
  oat-line: "#EFE9DD"
  oat-divider: "#E5DFD0"
  espresso-ink: "#1F1B16"
  driftwood: "#6A6258"
  pebble: "#665E53"
  on-fill: "#FFFFFF"
  alarm-red: "#B3261E"
  amber-note: "#9A5800"
  meadow-green: "#1E7A3C"
  sky-note: "#0062C4"
  night-hearth: "#151210"
  night-card: "#221E1B"
  night-ink: "#F5EFE3"
typography:
  wordmark:
    fontFamily: "DynaPuff, system-ui, sans-serif"
    fontSize: "56px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.02em"
  display:
    fontFamily: "Outfit, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Outfit, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Outfit, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Outfit, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  secondary:
    fontFamily: "Outfit, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Outfit, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.4px"
rounded:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  round: "50%"
spacing:
  2xs: "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ginger-deep}"
    textColor: "{colors.on-fill}"
    typography: "{typography.title}"
    rounded: "{rounded.md}"
    height: "48px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ginger-deep}"
    rounded: "{rounded.md}"
    padding: "3px 12px"
  button-danger-dark:
    backgroundColor: "#FF8B82"
    textColor: "{colors.espresso-ink}"
    rounded: "{rounded.md}"
    height: "48px"
  card:
    backgroundColor: "{colors.milk-card}"
    rounded: "{rounded.lg}"
    padding: "16px"
  chip-selected:
    backgroundColor: "{colors.ginger-deep}"
    textColor: "{colors.on-fill}"
    typography: "{typography.secondary}"
    rounded: "{rounded.sm}"
    padding: "8px 4px"
  chip-idle:
    backgroundColor: "transparent"
    textColor: "{colors.driftwood}"
    rounded: "{rounded.sm}"
    padding: "8px 4px"
  settings-row-icon:
    backgroundColor: "{colors.apricot-wash}"
    textColor: "{colors.copper-ink}"
    rounded: "{rounded.sm}"
    size: "32px"
  record-pill:
    textColor: "{colors.espresso-ink}"
    rounded: "14px"
    size: "44px"
  tab-active:
    textColor: "{colors.ginger-deep}"
    typography: "{typography.label}"
  add-button:
    backgroundColor: "{colors.ginger-deep}"
    textColor: "{colors.on-fill}"
    rounded: "{rounded.round}"
    size: "56px"
---

# Design system: Petzy

## Overview

**Material 3, with the copper seed.** The app follows Material 3 (M3) in its tokens, shapes, elevation, navigation and
states. The brand stays: ginger copper seeds the primary tonal palette (`--app-primary-text`, `--app-primary-fill`,
`--app-accent-soft` as primary-container), and the wordmark is the one display face. The sections below that still
describe the earlier «Warm Notebook» (flat sheets, 12px buttons) are superseded where they conflict with this paragraph.

### Material 3: what follows the specification, and what does not

Checked against the specification's own files, and every value below is taken from them: the system tokens (`material-foundation/material-tokens`: `css/typography.css`, `css/elevation.css`, `css/shape.css`, `css/state.css`, `css/motion.css`) and the component tokens (`material-components/material-web`, `tokens/versions/v0_192/`). The names are the specification's own (`md.sys.*`, `md.comp.*`).

**Follows the specification**

| What | The specification | The app |
|---|---|---|
| The three easings | `md.sys.motion.easing.standard` (0.2, 0, 0, 1), `…standard-decelerate` (0, 0, 0, 1), `…emphasized-decelerate` (0.05, 0.7, 0.1, 1) | the same three, to the digit (`--motion-ease-standard`, `--motion-ease-decelerate`, `--motion-ease-emphasized`) |
| The state layer of a control | `md.sys.state.pressed-state-layer-opacity` = 12% over the surface | the same 12%: antd's buttons (the `.adm-button:active` rule) and the app's own controls (`--app-accent-wash`: the card's doors, its «+», its chip, its bottom bar) |
| The FAB | `md.comp.fab.primary.container.height` and `.width` = 56px, `icon-size` 24px | 56×56, icon 24px (`components/Fab.tsx`) |
| The elevation | six levels, `md.sys.elevation.level0…level5` = 0, 1, 3, 6, 8, 12; cards at 1, floating layers at 3 | cards at 1 (`--app-shadow`), floating at 3 (`--app-shadow-strong`) |
| The filled text field | the highest surface container as its fill | `--app-field-fill`, with the app's 12px corner all round |
| The type sizes that are left | `md.sys.typescale.body-small.size` 12, `title-small.size` 14, `body-large.size` 16, `title-large.size` 22, `headline-small.size` 24, `headline-medium.size` 28 | `--text-xs` 12, `--text-sm` 14, `--text-md` 16, `--text-lg` 22, `--text-xl` 24, `--text-display` 28 |

**Deviates, and why**

| What | The specification | The app | Why |
|---|---|---|---|
| The type scale | 15 roles, `md.sys.typescale.display-large.size` 57 down to `label-small.size` 11 | seven sizes | A phone of records wants fewer sizes than a spec that also describes a TV; every size that is left is one of the spec's own |
| The corner radii | `md.sys.shape.corner.extra-small` 4, `small` 8, `medium` 12, `large` 16, `extra-large` 28 | one curve, 12px, everywhere | The house is a notebook: one curve, and the children nest inside it. The spec's scale is for a system with many component families; the app has one family of surfaces |
| The button's height | `md.comp.filled-button.container.height` = 40px | 48px (`--btn-height`), and the smallest target is 44px | The app's targets are bigger than the spec's: a finger on a phone is wider than a spec written for a stylus |
| The navigation bar | `md.comp.navigation-bar.container.height` = 80px, the active indicator 64×32 of `secondary-container` | 50px plus the safe area, the indicator a full-round pill of `--app-accent-soft` behind the icon | A denser bar for a denser app; the app has no secondary accent, so the indicator takes the primary one |
| The pressed thing moves | the specification keeps it still | the controls scale to 98% and dim to 85%, the round «+» to 94% | The house's micro-feedback: a card never moves, but a control under the finger answers at once. The layer itself is the specification's 12% |
| The hover | `md.sys.state.hover-state-layer-opacity` = 8% | a border and a fill change | The same answer, one step louder: the thing the finger is over says so by its edge |
| The rows of the record | a list item has no state layer of its own | the card's records open a record and do not answer the touch | The record is the card's text; the doors under it are what answer |
| The filled field's shape | the filled text field keeps its square bottom corners and a 1px indicator line along the bottom edge (`md.comp.filled-text-field`) | a fill, the app's 12px corner all four sides, and the copper ring when focused | The flat bottom and the line were read as a field that had been cut off, with a stray line under the label: the app's own surfaces are rounded on every side, and a field is one of them |
| The motion durations | 50–600 in steps of 50 | 80 / 160 / 240 / 320 | The app's ladder is one line of its own; the spec's has twelve steps, of which the app would use three |
| The colour roles | `md.sys.color.primary`, `secondary`, `tertiary` and their containers, `surface` and its five containers, `inverse-surface`, `outline-variant` | one accent (copper) and its soft and deep, the page, the card, the field, the lines, three steps of text, the danger, the success, the info, the violet | The app has no second and no third accent: the secondary and tertiary roles would have nothing to say. The pet's colour is the one thing that may tint a surface, and it does so on the pet's own card, never on the app's buttons |
| The components | M3's buttons, cards, chips, lists | antd-mobile's parts, restyled | The look follows M3; the parts are Ant's. Every token they read is overwritten with the app's own |

Two of the easings used to be Material 2's and are now the specification's own. The rest of the table is a decision, not an oversight.

**The medical card** is a surface of the app, so it holds the same rules: its sheets are the app's sheets (12px, a hairline, no shadow, the level 0 of a record that lies on the page), its gaps come from the app's ladder (2/4/8/12/16/24/32), its type from the app's scale, and the only thing of its own is that it does not lie on the pet's scene while it is open.

**Creative North Star: "The Warm Notebook"**

Petzy is a diary someone keeps for the animal they live with: feedings, weight, medicines, the vet's papers. The system reads like that diary kept well. Cream paper (cream-paper) holds milk-white sheets (milk-card). Everything important is written in one ginger copper ink, the colour of a ginger cat (ginger-cat), and nothing on the page competes with it. People open the app on an ordinary morning to tick off a dose, and on a bad night when the pet is ill; the mood holds for both: calm and caring, never loud.

Density is moderate and scannable. A screen is one column of sheets (at most 800px wide), each answering one question: what the pet is, what is due now, what happened today. Records carry a small pastel pill with an icon so a feed of weights, meals and pills can be read by colour at a glance, while copper stays reserved for action and state.

Personality lives in two places only: the bubbly DynaPuff wordmark «Petzy» and the per-species photo placeholders. Everything else is quiet, rounded, and precise.

**Key Characteristics:**
- One accent: ginger copper, deepened wherever it carries text or white type.
- Warm neutrals throughout: no pure grey, no pure black text, no pure white page.
- Sheets lie flat on the paper; only floating layers cast a real shadow.
- One ladder of radii and spacing (spacing 2/4/8/12/16/24/32), used concentrically, with one rule for each gap (see Spacing rules).
- Russian first: Cyrillic runs in the system face, Outfit sets digits and Latin.
- Light and dark are one system: every colour has a dark counterpart by role.

## Colors

A warm, single-accent palette: ginger copper on cream, with espresso-brown ink and oat-coloured lines.

### Primary
- **Ginger Cat** (ginger-cat): the brand accent for icons, the active tab, the add-button's glow and focus rings. Never used for text on cream or under white type; it is too light for either (3.7:1 and 3.8:1).
- **Ginger Deep** (ginger-deep): the working copper. Solid buttons, selected chips and copper text (the active tab label, «Добавить», outline buttons). White on it reads at 5:1.
- **Copper Ink** (copper-ink): copper for small text and icons on the apricot tint: chips, settings-row icons, the expiry badge's accents. It reads on the apricot tint itself, not only on the page: the card's soft accent may be any of the seven pet colours, and every token that lands on it has to clear 4.5:1 against all of them, not against the default alone.
- **Peach Fur** (peach-fur): the light end of the brand gradient (peach-fur to ginger-cat, 135°) for the wordmark and the cat and default photo placeholders; also the accent itself in the dark theme.
- **Apricot Wash** (apricot-wash): the soft copper tint behind icons, the pet card's «Кормление» and «Вес» tiles, the active rail item and empty-state icons.

### Neutral
- **Cream Paper** (cream-paper): the page ground.
- **Milk Card** (milk-card): sheets, the top bar, the tab bar, dialogs.
- **Oat Line** (oat-line): card borders and input strokes. **Oat Divider** (oat-divider): row separators and the rail's hover.
- **Espresso Ink** (espresso-ink): primary text. **Driftwood** (driftwood): secondary text and form labels (5.2:1). **Pebble** (pebble): tertiary text and placeholders (4.6:1).

### Status
- **Alarm Red** (alarm-red), **Amber Note** (amber-note), **Meadow Green** (meadow-green), **Sky Note** (sky-note): status as text; each also has a soft tint (the same hue at 12-20% opacity) for badges and banners. The bright iOS fills (#FF453A, #FF9F0A, #34C759) are for fills and icons only; as small text on cream they fail contrast. A tint is a badge or a banner, and the two are not the same: a badge lives inside a sheet, a banner that stands on the paper is a sheet of its own with the tint laid over an opaque ground. The pet's pattern never shows through a banner.

### Dark theme
The same roles on a warm night: night-hearth page, night-card sheets, night-ink text; the accent lifts to peach-fur, copper text becomes #F5C9A8 on a #3A2A1F apricot wash, and fills that are light in the dark theme (the accent, the #FF8B82 red) carry espresso-ink text instead of white.

### Named rules
**The One Ink Rule.** Copper is the only accent. A new screen gets its emphasis from copper, weight and size, never from a second brand colour. Record pastels identify a record type; they never mark an action.

**The Deep-for-Text Rule.** Wherever copper carries type or sits under white type, use ginger-deep or copper-ink, never ginger-cat.

## Typography

**Display Font:** Outfit (with -apple-system, BlinkMacSystemFont, system-ui)
**Body Font:** Outfit, the same stack
**Wordmark:** DynaPuff 700, for «Petzy» only

**Character:** Outfit's round geometry for numbers and Latin next to the platform's own Cyrillic keeps the diary friendly without costuming it; DynaPuff's bubbly letters are the brand's single playful note. Both are self-hosted (Latin subsets, the weights in use).

### Hierarchy
- **Wordmark** (DynaPuff 700, 56px on sign-in, smaller in the top bar, -0.02em): the name, filled with the brand gradient. Nowhere else.
- **Display** (600, 1.5rem, one 2rem line, -0.02em): the page title («Лекарства», «Удаление аккаунта»). One per screen. The title of a top-level screen of the tab bar (the pets, the medicines, the documents, the settings) is one step larger, `--text-display` (1.75rem, 700).

Sizes are written in rem tokens (`--text-xs` to `--text-display`), never in px: a pixel size does not follow the size the person set for their phone. The exceptions are the wordmark and the sizes of icons.
- **Headline** (700, 1.25rem, 1.2, -0.01em): section headers inside a page («Сегодня», «Вчера», «Удалятся»).
- **Title** (600, 1rem): a record's time, a medicine's name, a pet's name in lists.
- **Body** (400, 1rem, 1.5): record values, form inputs (16px, so iOS never zooms a focused field), policy text (38rem measure).
- **Secondary** (400, 0.875rem): hints under fields, meta lines, chips.
- **Label** (600, 0.75rem, +0.4px, uppercase): the tiny tile captions on the pet card («КОРМЛЕНИЕ», «ВЕС»). Uppercase is used there and nowhere else.

### Named rules
**The Units-Beside-Values Rule.** Numbers are Russian-formatted («29,1 кг», «4,8»), with the unit next to the value, in charts, tooltips and chips alike.

**The Whole-Letter Rule.** A pet's name may be set in a hand-written face (Caveat, Marck Script, Bad Script, Pacifico, Neucha, Amatic SC), and these run far past the usual line: a tail of «Щ», the loop of «Д», the dots of «Ё». Each face carries its own `line` (line-height) and `scale` in `PET_FONTS`, measured so that the tallest and the lowest letters of a name sit inside the line box, because the card clamps the name to two lines and cuts anything outside the box. The picker tiles are one height for every face (`3.25rem`, scaling with the text size) with the name in the middle. A new face is added only with its measured `line`.

## Layout

One centred column, 800px at most, with a 16px side gutter that grows to the safe-area inset on notched phones. Spacing comes from one scale (2, 4, 8, 12, 16, 24, 32px, the `--spacing-*` tokens); cards sit 12px apart and pad 16px; sections are separated by 24px with the header closer to its content than to the section above. Each kind of gap has one value, listed under Spacing rules. The page reserves room for the fixed top bar (64px) and the bottom bar.

Each screen's title is one line, 32px high (`2rem`), on every screen, so every title starts at the same height under the top bar. A button on the title's row is centred on that line.

A form row that holds one field is one height (`--form-row-height`, 51px) whatever control is in it, a switch, a text input or a picker, so the hairlines between the fields of a card keep one rhythm; a row with a note, a textarea or a group of choices is as tall as its content asks for. Blocks are separated by those hairlines rather than by space alone (see Dividers).

Responsive behaviour is contextual rather than stretched:
- **Phone, portrait** (the design's home): top bar, one column, bottom tab bar of five sections; below 360px the tab labels tighten to 10px. The «Медкарта» tab carries a red dot, ringed in the bar's ground and read aloud as «есть просроченное», while a vaccination or a treatment of the chosen pet is overdue: the one signal that reaches every screen. With several pets the pet switcher carries the same dot when a pet that is not chosen has something overdue, and the picker says which one and what, in words, under its name. Red stays for overdue only.
- **Phone, landscape** (height 500px or less): a 48px top bar and a 40px tab bar with labels beside their icons; content and tabs keep clear of the notch.
- **1024px and wider** (a computer, a tablet held sideways): the same five sections move to a 96px rail on the left; the column stays 800px; the add button drops to the corner.

### Spacing rules

One value per kind of gap, taken from the `--spacing-*` tokens, never a raw pixel count between blocks. A new screen reuses these; an unlisted gap is a sign to reuse one that is.

| Between | Gap |
|---|---|
| Two full-width buttons, one under another | 12px (`md`), also under a sticky main button (`.form-sticky-action` pads 8px itself, so `.form-actions` after it adds 4px) |
| A button and a text-only button under it («Готово», «Вернуть набор») | 8px (`sm`); the text button's 44px target gives it the rest |
| Cards, rows or tiles in a list | 12px (`md`) |
| Chips, tiles or an icon and its label in a row | 8px (`sm`) |
| A row of choice buttons and the field under it | 8px (`sm`): the chip's own border lands on the row's divider without it |
| A section header and its content | 8px (`sm`) |
| One section and the next | 24px (`xl`) |
| A block and the block above it | a hairline (see Dividers), then 12px (`md`) of air under it |
| The last field and the button that closes the form | 24px (`xl`): `.form-sticky-action`, `.form-actions` |
| A title and the one-line caption under it | 2px (`2xs`) |
| A screen's title and the pet or the line it is about | 4px (`xs`) |
| The pieces at the top of a screen (an alert, a status line, the main buttons) | 16px (`lg`), as one group |
| A part of a screen (a section, a block of the card) and what is above it | 24px (`xl`) |
| The groups of a bottom sheet | 24px (`xl`); a group's title to its tiles 8px (`sm`) |
| A card's inner padding | 16px (`lg`); a centred message or empty state 24px (`xl`) |

Allowed to stay off the ladder, because the label or a fixed neighbour sets them: the padding inside a control (a chip, a badge, a button is sized by its label and its 44px target); the room kept clear for the fixed bars (`calc(env(safe-area-inset-*) + 80px)` and its like); an optical nudge of an icon to the first line of its text; a negative margin that widens a tap target; the miniature product screens on the intro slides.

### Named rules
**The Concentric Rule.** A rounded element inset in a rounded parent takes the radius one rung down the ladder for the spacing between them (a 24px card padded 12px holds 12px children).

## Elevation & Depth

Material 3 levels, in the warm shadow colour. Cards sit at level 1 (a hairline oat border and `--app-shadow`); they do not lift
on press. Floating layers take level 3 (`--app-shadow-strong`): pickers, dialogs and sheets. The round add button keeps its
copper glow. In the dark theme the shadows become black at higher opacity, as before.

### Shadow vocabulary
- **Sheet** (`box-shadow: 0 2px 8px rgba(60, 40, 20, 0.06)`): cards and the top bar.
- **Hairline** (`box-shadow: 0 1px 3px rgba(60, 40, 20, 0.04)`): small raised pieces inside a sheet.
- **Float** (`box-shadow: 0 6px 24px rgba(60, 40, 20, 0.10)`): popups, sheets, dialogs.
- **Copper glow** (`box-shadow: 0 4px 16px rgba(173, 88, 48, 0.45)`): the add button only.

### Named rules
**The State Layer Rule (M3).** A pressed control takes a 12% wash of its content colour (buttons) and a 0.98 scale; a card
never animates its elevation on press. Feedback is a state layer, never a lift.

## Shapes

One rectangle for the whole app: every control, card, tile, chip, segment, field, dialog and sheet has the same 12px corner
(`--radius-md`; the tokens `--radius-xs` … `--radius-xl` and `--radius-pill` all hold it, so one value sets the app). The only round
shapes are the ones that are circles by nature: the round add button, avatars, colour swatches and the swipe row's menu
(`--radius-round`). Nothing is a capsule. Borders are 1px oat hairlines; there are no coloured side borders. Photos are cropped to their frame with the face kept high (object position centre 20%).

## Components

### Buttons
M3 buttons: one primary per screen.
- **Shape:** the common 12px corner (`--radius-md`), the same as every other rectangle; the add button is round.
- **Outline:** every button has a 1px border. A filled button's border is its fill; an outlined one takes its colour; a text-only one (fill none) takes the oat hairline, copper for the primary.
- **Label:** weight 500 (medium), not 600.
- **Press:** a 12% state layer and a 0.98 scale.
- **Size:** two, picked by `size`, never by hand. **Large** (`size="large"`, 48px, the `--btn-height` token) is the main action of a screen or a sheet and the button stacked with it («Создать» and «Отмена», «Записать» and «Оформить карточку»). The **usual** size (44px, `--touch-min`) is for a button inside a card or a row («Дали сейчас», «Загрузить ещё»). The small and mini ones keep their look and get an invisible 44px area to touch. Plain `<button>`s that stand in for a large one (`SpinnerButton`, the sheet buttons) use the same `--btn-height`.
- **Label:** body size (16px), weight 600, on every size but the small and mini ones, which keep their own size.
- **Primary:** ginger-deep fill, white text, full width at 48px for the main action of a form or screen («Создать», «Принять сейчас»). The sign-in and sign-up buttons use the deepened brand gradient instead.
- **Outline:** a copper outline with ginger-deep text for secondary actions in a card («Отметить приём», «Пополнить»).
- **Neutral outline:** an oat outline with ink text for the way out («Отмена», «Отклонить»): it takes no colour, so a copper outline always means a step forward.
- **Text:** a navigation link on the sign-in screens only (plain ginger-deep text). Every action, header or row, is an outlined button (see Outline).
- **Danger:** every destructive button is a solid red button, the same as «Удалить аккаунт» (dark text on it in the dark theme), at whatever size its place asks for: the foot of a form, a card, a row or a sheet («Удалить запись», «Убрать», «Отозвать»). Red text or a red outline is never an action: on a pet's patterned backdrop it does not read.
- **Press:** 0.98 scale and the 12% state layer; no hover lift. A visible focus ring for the keyboard.

### The round «+»
One way to add on the screens that fill a diary: the round copper button bottom right, above the tab bar (`.app-fab`, 56px, in a portal). What its sheet holds depends on the screen: the feed's sheet lists the diary of events («Добавить запись»), the medical card's, in the mode that edits, is «Что записать?» (a vaccination, a treatment, a visit, an allergy, a medicine, a weight, a document). The reading mode of the card has none, because nothing is added there.

**One door per screen.** The card's tiles only open their part, and nothing on the card records a thing: the overdue strip says what is due and where it is recorded, and the action sits in that part ("Записать повторную прививку" in «Прививки и обработки», «Записать вес» in «Вес», «Изменить» in the allergies). A screen carries the round «+» only where its blocks carry no door of their own: a block with its own «Добавить», «Записать вес» or «Указать» next to what it adds does not get one as well. A part of the card that asks between two kinds keeps the «+» (it is the only way in) and its blocks carry no door, so a person reads one way to add rather than guessing between two. The card itself keeps its «+» because it is the only way from there to an allergy, a medicine, a weight or a document.

### Dialogs and sheets
Dialogs and sheets: the common 12px corner, the floating shadow (level 3), the title in the large size.

### Fields
Filled text fields, rounded on all four corners. Every form row (`.adm-form-item`) holds a fill (`--app-field-fill`,
surface-container-highest) and the app's 12px corner (`--radius-md`), like every other filled surface here: a field is a
box, not a sheet of paper. The focused row takes the 2px copper ring (`--app-accent`) all round and its label the
deeper copper. Rows are told apart by the gap of their fills, and the hairline between them is gone. The label sits
above the value, as before. A field that stands outside a form row (the event type's name, `input-row`) is the same box:
the fill, the app's corner, the copper ring when focused, and no underline of its own.

### Chips
- **Style:** transparent with an oat border and driftwood text; selected fills ginger-deep with white 600 text (weekday chips, choices in forms). Plain selectors mark the choice with copper-ink on the apricot wash.
- **Target:** at least 44px (the `--touch-min` token) to press even when the chip is drawn smaller.
- **In code:** `ChoiceChips` (a labelled group) and `ChoiceChip` (a choice with `pressed`) in `components/ChoiceChips.tsx`; the stylesheet comes with the component. The record form, the profile and «К приёму» use them: a choice row is not drawn by hand again. They are pills (a choice is a shape-is-the-meaning case), selected on the apricot wash.

### Tabs
A screen's own tabs (here the six parts of a pet's look) sit in one grid of equal columns, so every row is full and a label that is too long for its column wraps inside it. A tab is never cut off at the edge or scrolled out of sight, and the tabs never leave a short last row. The chosen tab has a 3px copper underline and `aria-selected`; each tab keeps the 44px touch height.

### Cards / Containers
- **Corner Style:** 12px, as every rectangle.
- **Background:** milk-card on cream-paper.
- **Shadow Strategy:** the Sheet shadow and an oat hairline (see Elevation).
- **Internal Padding:** 16px; 12px between cards.

### Inputs / Fields
- **Style:** antd-mobile form rows inside a sheet: driftwood label on the left, the value in espresso-ink at 16px, an oat divider above each row, hints below in secondary type.
- **Pickers:** a row that opens a picker (date, time, form, category) shows its value as text with a chevron; the whole row is one button.
- **Error:** a red message under the field, announced to screen readers; the field keeps what was typed.

### Dividers
- **Separation (M3).** A field is separated by its fill, not by a hairline. Sections keep one hairline between their header and content. A row of choice buttons and the «Запоминать значения» switch are not fields and stay plain, with a hairline above them when they follow a field.
- **One length per screen.** Every divider is as long as every other one, drawn across the content column. A line that starts at a label is a second length of the same rule on one screen, and the eye reads the screen as lines being here and there.
- **No line where there is nothing to separate.** The first block of a group, and the row right under a section header, whose card already has a line above it.
- **Below the line:** 12px (`md`) before the first text of the block, the same distance a field has.
- **Colour:** `--app-divider-color`, the oat hairline, which reads as one line in either theme.

### Navigation
- **Top bar:** milk-card, 64px: the wordmark or a back arrow on the left, the pet picker on the right.
- **Tab bar (M3 navigation bar):** the current item sits on an active indicator, a pill of primary-container (`--app-accent-soft`) behind its icon. Five sections (Лента, Лекарства, Медкарта, Документы, Настройки; the medical card tab follows the pet chosen in the top bar, and the card's own page has the wordmark, not a back arrow), icon over an 11px label, driftwood at rest, ginger-deep and a slightly larger icon when current. On wide screens the same items stand in the left rail, the current one on an apricot wash.
- **The keyboard:** the keys cover the bottom of the page and only the visual viewport shrinks, so the bars fixed to the bottom step aside while the keys are up (the tab bar and the round «+» cannot be pressed under them), the page gets the room the keys cover, and a button that closes a long form rides on the top edge of the keys instead of hiding behind them.

### Record pill
The signature of the feed: a 44px tile with the common 12px corner in the record type's pastel (tile-orange for weight, tile-brown for feeding, tile-purple for medicines…) with the type's icon in espresso-ink, left of the record's time and values. The pastel names the type; it never signals state.

### Pet card
The top of the feed: the pet's photo (or a species gradient with its outline icon), the name as a title, age, breed and sex as one wrapped meta line, a copper weight chip, and one bordered row into the medical card (the title «Медкарта» and a line under it that turns red when something is overdue). The last feeding and weight are not on the card: the feed under it says them. The facts of a pet are said in one case everywhere: the breed and the sex are not proper nouns in Russian, so they are in small letters («5 лет, лабрадор, мальчик» on the card of the feed, «Собака, лабрадор» and under it «5 лет, мальчик» in the medical card, one line in the PDF), and the species keeps its capital where it opens the line. The order follows the job: the feed leads with the age (a glance), the document with the species (a record). The passport of the medical card says who the pet is in two lines: the kind and the breed speak at the size the sheet speaks at, the rest of the facts below them. It has no photo at all: the portrait belongs to the feed, and the record says facts.

### Medical card
One page of one pet, one document under the title «Медкарта» (the pet is named in the bar above), read from top to bottom. It answers three questions in this order: what the record says about this pet (the passport: the kind, the breed, the age, the sex, the day the pet was born on a line of its own right after the age («Дата рождения: 01.08.2021»), the weight in ink with the day it was taken in brackets, the way the PDF says it, because a bare date beside a number reads as another date (the block of the weight says it the same way, and the sheets of the measurements put the day on its own line under the number), the chip number and the blood type, the number copied by a tap; no photo, the portrait belongs to the feed), what asks to be done now (the red block «Требует внимания»: every overdue record with its own days and its own action, «Записать повторную прививку» for a vaccine, «Записать повторную обработку» for a parasite treatment, «Оформить как запись» for an expired certificate), and how far the card is from being complete («Готовность к приёму»: N of 5, the five dots, what is missing and the first step). The five dots are a meter and not a checklist: whatever is filled lights them from the first one, so «1 из 5» always means the first dot and never the dot of the item that happens to be done. The step under the readiness stands in a row of its own, held off the hint by the same hairline the app draws between the rows of a card; the day of a weighing keeps a gap of its own before the brackets («29,3 кг (04.10.2026)»), given by layout and not by a space in the text, which an inline-flex container trims. Below that the record itself, in the order a vet asks in: «Здоровье и аллергии», «К приёму», «Лекарства», «Вес», «Прививки и обработки», «Визиты и операции», «Анализы и заключения», «Клиника и врачи», «Питание и условия». A block carries the round «+» in its head (what that block is about is added there) and the quiet doors of the owner under it («Заполнить» or «Изменить», «Все лекарства», «Все документы», «Показать все N»): one block, one door to add, never two. While nothing is written into the card yet, one line under the passport says what the card is and how it is filled in («Это то, что врач спросит на приёме... Чтобы записать своё, нажмите «+» в нужном блоке»); it goes away with the first record, and the copy a guest opens stops after the first sentence. The two ways to hand the card over stand in the document itself, on one row right under the passport, with the quiet line «Скачать заранее: на приёме может не быть связи» under them: «Скачать PDF» and «Ссылка для врача», the same place they take on the copy a vet opens by a link. They were a bar pinned over the card, and it cost a tenth of the screen for the whole reading and made a document look like a tool; the moment they are wanted is the one the card opens on, and the file is taken beforehand, not from the middle of a record. A card that is still nearly empty offers neither, and the line at its foot says what is missing instead. The address of a part of the card (`/medical-card/<part>`) opens the card itself and scrolls to that part. A course on the medicines list carries one button, the dose that is due («Дали сейчас (2,5 мл)»); the two rare doors under it, «Другое время или доза» and «Завершить курс», stand as quiet text on one line behind a hairline, not as two more full-width blocks. Three equally loud buttons to a course turned the list into a panel of buttons and pushed the second course off the screen: the record is what the eye should land on, and the rare door is still one tap away. Every screen of the five tabs answers the same pull: the feed, the medications, the card, the documents and the settings all take the gesture, empty screens too, because a screen opened to write something down is exactly the one whose data may be stale. One piece does it (`AppPullToRefresh`): the same 48px of head, the same medium tap, the same quiet 'обновление' line. A tab that has nothing to refresh is the one to leave out, not the one to forget.

The card is stricter than the feed, and this is what makes it a document and not another screen of the app: it keeps the pet's scene under it like every other screen, its sheets lie flat and are held by a line and not by a shadow, and the colour is kept for what means something: the overdue (red), the call and the action (copper), the ready (green), the rest is ink and grey. The feed stays warm: the pet's photo in its frame, its name in its own hand, its pattern under it. The lines inside a sheet stand close together, as the lines of a record stand (4px between them, 2px inside a line): a sheet says facts one after another, and not in islands. A line that is also a control keeps its 44px tap target without growing the line, the way the house's `touch-target` class does it everywhere else.

The pet's name is written once on any one screen: in the app the switcher in the top bar names it, on a copy opened by a link the title of the page names it, and on paper the head of the PDF names it. The passport says what the record says about the pet, and the name is not written a second time in it. The copy opened by a link says what the page is as well, over the name: «Медкарта» above «Рекс». The page a vet opens by a link says how old the data is and until when the link lives, then the file, then the same document with nothing to change: the overdue block names once, under the list, who can put it right instead of offering a door, and the blocks carry no «+». The red is for overdue only; the allergy block is a neutral apricot with a red icon. A row says its lines in tiers: what is acted on (ink, 600), the facts (ink, bold label), the context (grey), the rest (quiet). A status is always a word and an icon; days are counted («Просрочено на 35 дней»). A block is named once, by its own heading; the copy of the card for a vet keeps the same names.

Three things inside the document are decided there and not everywhere. The heading of the red block is in the alarm's colour, so that the block reads as one alarm and not as a quiet title over a coloured box. The red block is a sheet of its own: the tint is laid over an opaque ground, and the pet's pattern does not show through it. The line of the weight is drawn to the scale of the pet and not to the spread of the series: a change of less than a kilogram on a dog of thirty is a gentle slope and not a cliff, the exact range is written under the line, and the change since the last change of it is said once, in the block of the weight, and not in the passport. The phone of a clinic is an action like any other and not a slab of colour in the middle of a document: it is a copper door «Позвонить», while the door that changes the clinic stays quiet. A sheet over the card names itself («Что добавить?», «Замеры веса», «Все прививки и обработки»), and the card while it loads has the shape of the card: the passport of the pet and the blocks of the document, in the sheets they come in.

### Loading

**The Loading Rule.** Waiting shows one indicator, chosen by what the wait stands in for, and a screen never shows two at once. The words are always «Загружаем…».

| What is loading | What the person sees | Code |
|---|---|---|
| A list of records or cards (the feed, the history, the pets, the documents, the medicines, the medical card, the shared links, the event types) | Placeholder rows of the shape that is coming, shown only after 300 ms | `SkeletonList`, `PetCardSkeleton`, `DashboardSkeleton`, `MedicalCardSkeleton` |
| A screen of one thing (a form, a profile, an account page, a text on its own), or what the screen is about before it is known (its pet, the session, the page's code) | One spinner with its words, centred on the screen | `LoadingSpinner` |
| A block inside a screen (a chart, a sheet, a picker) | One spinner inside the block, the screen around it stays | `LoadingSpinner fullscreen={false}` |
| The next part of a list, or a button that loads or retries | The words «Загружаем…» where the button's words were | the button |
| A button that saves, sends or uploads | Its spinner in place of its words, the button disabled | `SpinnerButton` |
| A value or a hint in a row | The words «Загружаем…» in its place | the row |

A skeleton stands for the list it replaces: the same rows and the same gaps, and it never sits under a spinner.

## Do's and Don'ts

### Do:
- **Do** keep copper as the only accent; use ginger-deep (#AD5830) for copper text and fills under white type.
- **Do** build screens as one column of milk-card sheets on cream-paper, 12px corners, 16px padding.
- **Do** take radii and spacing from the one ladder (radii 4/8/12/16/24, spacing 2/4/8/12/16/24/32), give each kind of gap its one value from Spacing rules, and nest radii concentrically.
- **Do** give every colour a dark-theme counterpart by role, with dark text on the dark theme's light fills.
- **Do** write numbers the Russian way with the unit beside them («29,1 кг»).
- **Do** keep touch targets at 44px, even for small chips, grips and links.
- **Do** let `size` pick a button's height, radius and label: a `Button` carries no radius, height or weight of its own.
- **Do** show a list's placeholder rows, one spinner for a screen of one thing, and the words «Загружаем…» for more items.

### Don't:
- **Don't** put ginger-cat (#C46A3F) under white text or use it as text on cream.
- **Don't** add a second brand colour or use a record pastel to mark an action or state.
- **Don't** lift, move or re-shadow a card on press; use the state layer.
- **Don't** use DynaPuff for anything but the «Petzy» wordmark, or gradient text anywhere else.
- **Don't** join facts with a middle dot («·»); separate them with layout or a comma.
- **Don't** use pure grey neutrals, pure black text or a pure white page.
- **Don't** stack a spinner on a skeleton, or show two indicators on one screen.
