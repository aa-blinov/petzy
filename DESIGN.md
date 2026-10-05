---
name: Petzy
description: A pet health diary on warm cream paper, written in ginger-cat copper.
colors:
  ginger-cat: "#C46A3F"
  ginger-deep: "#AD5830"
  copper-ink: "#9F4F2A"
  peach-fur: "#E8946A"
  apricot-wash: "#FBEFE5"
  cream-paper: "#FAF6EF"
  milk-card: "#FEFCF6"
  oat-line: "#EFE9DD"
  oat-divider: "#E5DFD0"
  espresso-ink: "#1F1B16"
  driftwood: "#6F675D"
  pebble: "#786E62"
  on-fill: "#FFFFFF"
  alarm-red: "#B3261E"
  amber-note: "#9A5800"
  meadow-green: "#1E7A3C"
  sky-note: "#0062C4"
  night-hearth: "#1A1714"
  night-card: "#252220"
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
    backgroundColor: "#FF7A70"
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

# Design System: Petzy

## Overview

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
- **Copper Ink** (copper-ink): copper for small text and icons on the apricot tint: chips, settings-row icons, the expiry badge's accents.
- **Peach Fur** (peach-fur): the light end of the brand gradient (peach-fur to ginger-cat, 135°) for the wordmark and the cat and default photo placeholders; also the accent itself in the dark theme.
- **Apricot Wash** (apricot-wash): the soft copper tint behind icons, the pet card's «Кормление» and «Вес» tiles, the active rail item and empty-state icons.

### Neutral
- **Cream Paper** (cream-paper): the page ground.
- **Milk Card** (milk-card): sheets, the top bar, the tab bar, dialogs.
- **Oat Line** (oat-line): card borders and input strokes. **Oat Divider** (oat-divider): row separators and the rail's hover.
- **Espresso Ink** (espresso-ink): primary text. **Driftwood** (driftwood): secondary text and form labels (5.2:1). **Pebble** (pebble): tertiary text and placeholders (4.6:1).

### Status
- **Alarm Red** (alarm-red), **Amber Note** (amber-note), **Meadow Green** (meadow-green), **Sky Note** (sky-note): status as text; each also has a soft tint (the same hue at 12-20% opacity) for badges and banners. The bright iOS fills (#FF453A, #FF9F0A, #34C759) are for fills and icons only; as small text on cream they fail contrast.

### Dark theme
The same roles on a warm night: night-hearth page, night-card sheets, night-ink text; the accent lifts to peach-fur, copper text becomes #F5C9A8 on a #3A2A1F apricot wash, and fills that are light in the dark theme (the accent, the #FF7A70 red) carry espresso-ink text instead of white.

### Named Rules
**The One Ink Rule.** Copper is the only accent. A new screen gets its emphasis from copper, weight and size, never from a second brand colour. Record pastels identify a record type; they never mark an action.

**The Deep-for-Text Rule.** Wherever copper carries type or sits under white type, use ginger-deep or copper-ink, never ginger-cat.

## Typography

**Display Font:** Outfit (with -apple-system, BlinkMacSystemFont, system-ui)
**Body Font:** Outfit, the same stack
**Wordmark:** DynaPuff 700, for «Petzy» only

**Character:** Outfit's round geometry for numbers and Latin next to the platform's own Cyrillic keeps the diary friendly without costuming it; DynaPuff's bubbly letters are the brand's single playful note. Both are self-hosted (Latin subsets, the weights in use).

### Hierarchy
- **Wordmark** (DynaPuff 700, 56px on sign-in, smaller in the top bar, -0.02em): the name, filled with the brand gradient. Nowhere else.
- **Display** (600, 1.5rem, 1.2, -0.02em): the page title («Лекарства», «Удаление аккаунта»). One per screen.
- **Headline** (700, 1.25rem, 1.2, -0.01em): section headers inside a page («Сегодня», «Вчера», «Удалятся»).
- **Title** (600, 1rem): a record's time, a medicine's name, a pet's name in lists.
- **Body** (400, 1rem, 1.5): record values, form inputs (16px, so iOS never zooms a focused field), policy text (38rem measure).
- **Secondary** (400, 0.875rem): hints under fields, meta lines, chips.
- **Label** (600, 0.75rem, +0.4px, uppercase): the tiny tile captions on the pet card («КОРМЛЕНИЕ», «ВЕС»). Uppercase is used there and nowhere else.

### Named Rules
**The Units-Beside-Values Rule.** Numbers are Russian-formatted («29,1 кг», «4,8»), with the unit next to the value, in charts, tooltips and chips alike.

**The Whole-Letter Rule.** A pet's name may be set in a hand-written face (Caveat, Marck Script, Bad Script, Pacifico, Neucha, Amatic SC), and these run far past the usual line: a tail of «Щ», the loop of «Д», the dots of «Ё». Each face carries its own `line` (line-height) and `scale` in `PET_FONTS`, measured so that the tallest and the lowest letters of a name sit inside the line box, because the card clamps the name to two lines and cuts anything outside the box. The picker tiles are one height for every face (`3.25rem`, scaling with the text size) with the name in the middle. A new face is added only with its measured `line`.

## Layout

One centred column, 800px at most, with a 16px side gutter that grows to the safe-area inset on notched phones. Spacing comes from one scale (2, 4, 8, 12, 16, 24, 32px, the `--spacing-*` tokens); cards sit 12px apart and pad 16px; sections are separated by 24px with the header closer to its content than to the section above. Each kind of gap has one value, listed under Spacing rules. The page reserves room for the fixed top bar (64px) and the bottom bar.

Responsive behaviour is contextual rather than stretched:
- **Phone, portrait** (the design's home): top bar, one column, bottom tab bar of five sections; below 360px the tab labels tighten to 10px. The «Медкарта» tab carries a red dot, ringed in the bar's ground and read aloud as «есть просроченное», while a vaccination or a treatment of the chosen pet is overdue: the one signal that reaches every screen. With several pets the pet switcher carries the same dot when a pet that is not chosen has something overdue, and the picker says which one and what, in words, under its name. Red stays for overdue only.
- **Phone, landscape** (height 500px or less): a 48px top bar and a 40px tab bar with labels beside their icons; content and tabs keep clear of the notch.
- **1024px and wider** (a computer, a tablet held sideways): the same five sections move to a 96px rail on the left; the column stays 800px; the add button drops to the corner.

### Spacing rules

One value per kind of gap, taken from the `--spacing-*` tokens, never a raw pixel count between blocks. A new screen reuses these; an unlisted gap is a sign to reuse one that is.

| Between | Gap |
|---|---|
| Two full-width buttons, one under another | 12px (`md`) |
| A button and a text-only button under it («Готово», «Вернуть набор») | 8px (`sm`); the text button's 44px target gives it the rest |
| Cards, rows or tiles in a list | 12px (`md`) |
| Chips, tiles or an icon and its label in a row | 8px (`sm`) |
| A section header and its content | 8px (`sm`) |
| One section and the next | 24px (`xl`) |
| The last field and the button that closes the form | 24px (`xl`): `.form-sticky-action`, `.form-actions` |
| A title and the one-line caption under it | 2px (`2xs`) |
| A screen's title and the pet or the line it is about | 4px (`xs`) |
| The pieces at the top of a screen (an alert, a status line, the main buttons) | 16px (`lg`), as one group |
| A part of a screen (a section, a block of the card) and what is above it | 24px (`xl`) |
| The groups of a bottom sheet | 24px (`xl`); a group's title to its tiles 8px (`sm`) |
| A card's inner padding | 16px (`lg`); a centred message or empty state 24px (`xl`) |

Allowed to stay off the ladder, because the label or a fixed neighbour sets them: the padding inside a control (a chip, a badge, a button is sized by its label and its 44px target); the room kept clear for the fixed bars (`calc(env(safe-area-inset-*) + 80px)` and its like); an optical nudge of an icon to the first line of its text; a negative margin that widens a tap target; the miniature product screens on the intro slides.

### Named Rules
**The Concentric Rule.** A rounded element inset in a rounded parent takes the radius one rung down the ladder for the spacing between them (a 24px card padded 12px holds 12px children).

## Elevation & Depth

Paper on a table. Sheets lie flat: a hairline oat border plus a barely-there warm shadow (0 2px 8px at 6% brown), and they never lift, move or change shadow on press; pressing dims instead. Real elevation is reserved for what floats above the page: the add button (a copper glow, 0 4px 16px at 45%), pickers, dialogs and sheets (0 6px 24px at 10%). In the dark theme the brown shadows would vanish on charcoal, so they become black at higher opacity.

### Shadow Vocabulary
- **Sheet** (`box-shadow: 0 2px 8px rgba(60, 40, 20, 0.06)`): cards and the top bar.
- **Hairline** (`box-shadow: 0 1px 3px rgba(60, 40, 20, 0.04)`): small raised pieces inside a sheet.
- **Float** (`box-shadow: 0 6px 24px rgba(60, 40, 20, 0.10)`): popups, sheets, dialogs.
- **Copper glow** (`box-shadow: 0 4px 16px rgba(173, 88, 48, 0.45)`): the add button only.

### Named Rules
**The Flat Sheet Rule.** A card never animates its elevation. Feedback on press is a dim or a 0.98 scale, never a lift.

## Shapes

Softly rounded, never pill-shaped except where the shape is the meaning. The ladder is 4, 8, 12, 16, 24px: sheets 16px, buttons and inputs 12px, chips and small icon tiles 8px, record pills 14px, the add button and avatars round. Borders are 1px oat hairlines; there are no coloured side borders. Photos are cropped to their frame with the face kept high (object position centre 20%).

## Components

### Buttons
Soft and composed: one primary per screen.
- **Shape:** gently rounded (12px), on every button; a chip is a pill and the add button is round, because there the shape is the meaning.
- **Size:** two, picked by `size`, never by hand. **Large** (`size="large"`, 48px, the `--btn-height` token) is the main action of a screen or a sheet and the button stacked with it («Создать» and «Отмена», «Записать» and «Оформить карточку»). The **usual** size (44px, `--touch-min`) is for a button inside a card or a row («Дали сейчас», «Загрузить ещё»). The small and mini ones keep their look and get an invisible 44px area to touch. Plain `<button>`s that stand in for a large one (`SpinnerButton`, the sheet buttons) use the same `--btn-height`.
- **Label:** body size (16px), weight 600, on every size but the small and mini ones, which keep their own size.
- **Primary:** ginger-deep fill, white text, full width at 48px for the main action of a form or screen («Создать», «Принять сейчас»). The sign-in and sign-up buttons use the deepened brand gradient instead.
- **Outline:** a copper outline with ginger-deep text for secondary actions in a card («Отметить приём», «Пополнить»).
- **Neutral outline:** an oat outline with ink text for the way out («Отмена», «Отклонить»): it takes no colour, so a copper outline always means a step forward.
- **Text:** plain ginger-deep text for header actions («+ Добавить»).
- **Danger:** red text for destructive actions at the foot of a form; a solid red button only where deletion is the screen's purpose (dark text on it in the dark theme).
- **Press:** 0.98 scale and a slight dim; no hover lift. A visible focus ring for the keyboard.

### The round «+»
One way to add on the screens that fill a diary: the round copper button bottom right, above the tab bar (`.app-fab`, 56px, in a portal). What its sheet offers depends on the screen: the feed's is the diary of events («Добавить запись»), the medical card's, in the mode that edits, is «Что записать?» (a vaccination, a treatment, a visit, an allergy, a medicine, a weight, a document). The reading mode of the card has none, because nothing is added there.

### Chips
- **Style:** transparent with an oat border and driftwood text; selected fills ginger-deep with white 600 text (weekday chips, choices in forms). Plain selectors mark the choice with copper-ink on the apricot wash.
- **Target:** at least 44px (the `--touch-min` token) to press even when the chip is drawn smaller.
- **In code:** `ChoiceChips` (a labelled group) and `ChoiceChip` (a choice with `pressed`) in `components/ChoiceChips.tsx`; the stylesheet comes with the component. The record form, the profile and «К приёму» use them: a choice row is not drawn by hand again. They are pills (a choice is a shape-is-the-meaning case), selected on the apricot wash.

### Cards / Containers
- **Corner Style:** 16px.
- **Background:** milk-card on cream-paper.
- **Shadow Strategy:** the Sheet shadow and an oat hairline (see Elevation).
- **Internal Padding:** 16px; 12px between cards.

### Inputs / Fields
- **Style:** antd-mobile form rows inside a sheet: driftwood label on the left, the value in espresso-ink at 16px, oat dividers between rows, hints below in secondary type.
- **Pickers:** a row that opens a picker (date, time, form, category) shows its value as text with a chevron; the whole row is one button.
- **Error:** a red message under the field, announced to screen readers; the field keeps what was typed.

### Navigation
- **Top bar:** milk-card, 64px: the wordmark or a back arrow on the left, the pet picker on the right.
- **Tab bar:** five sections (Лента, Лекарства, Медкарта, Документы, Настройки; the medical card is the tab of the pet chosen in the top bar, and the card's own page has the wordmark, not a back arrow), icon over an 11px label, driftwood at rest, ginger-deep and a slightly larger icon when current. On wide screens the same items stand in the left rail, the current one on an apricot wash.

### Record pill
The signature of the feed: a 44px tile with a 14px radius in the record type's pastel (tile-orange for weight, tile-brown for feeding, tile-purple for medicines…) with the type's icon in espresso-ink, left of the record's time and values. The pastel names the type; it never signals state.

### Pet card
The top of the feed: the pet's photo (or a species gradient with its outline icon), the name as a title, age, breed and sex as one wrapped meta line, a copper weight chip, and one bordered row into the medical card (the title «Медкарта» and a line under it that turns red when something is overdue). The last feeding and weight are not on the card: the feed under it says them.

### Medical card
One page of one pet, in two modes under the title «Медкарта» (the pet is named in the bar above), a segmented switch with «Записи» first and «Врачу» second. «Записи» is the working mode and opens every time, so that whoever comes back to record a visit finds the «+»: progress and the one next step, eight tiles (a tile opens its part on its own screen; «Документы» goes straight to the documents), «К приёму», and at the bottom «Для врача» with two different buttons, the file and the link. «Врачу» is read at the counter and is entered on purpose, never remembered between visits: the red overdue strip, one line naming the patient (name, species, breed, age) and one with the weight and the day it was taken, the file and the link side by side, then allergies, medicines, «На приём», what is due, clinics, life, the last visits and operations, past courses; no editing. The page a vet opens by a link has the pet's name as its title, says how old the data is and until when the link lives, then the overdue strip, then the same, with its one «Скачать PDF» after what there is to read. The chosen segment is lit: accent tint, accent text and ring, never the darker of the two. The red is for overdue only; the allergy block is a neutral apricot with a red icon. A row says its lines in tiers: what is acted on (ink, 600), the facts (ink, bold label), the context (grey), the rest (quiet). A status is always a word and an icon; days are counted («Просрочено на 35 дней»). A screen whose title already names a block does not name it again: the heading stays for a screen reader only.

## Do's and Don'ts

### Do:
- **Do** keep copper as the only accent; use ginger-deep (#AD5830) for copper text and fills under white type.
- **Do** build screens as one column of milk-card sheets on cream-paper, 16px radius, 16px padding.
- **Do** take radii and spacing from the one ladder (radii 4/8/12/16/24, spacing 2/4/8/12/16/24/32), give each kind of gap its one value from Spacing rules, and nest radii concentrically.
- **Do** give every colour a dark-theme counterpart by role, with dark text on the dark theme's light fills.
- **Do** write numbers the Russian way with the unit beside them («29,1 кг»).
- **Do** keep touch targets at 44px, even for small chips, grips and links.
- **Do** let `size` pick a button's height, radius and label: a `Button` carries no radius, height or weight of its own.

### Don't:
- **Don't** put ginger-cat (#C46A3F) under white text or use it as text on cream.
- **Don't** add a second brand colour or use a record pastel to mark an action or state.
- **Don't** lift, move or re-shadow a card on press.
- **Don't** use DynaPuff for anything but the «Petzy» wordmark, or gradient text anywhere else.
- **Don't** join facts with a middle dot («·»); separate them with layout or a comma.
- **Don't** use pure grey neutrals, pure black text or a pure white page.
