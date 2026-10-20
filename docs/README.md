# Documentation

The documents of Petzy. The product itself is described at the root of the
repository; this folder holds the documents that were written for the
interface and for the checks.

| Document | What it covers |
| --- | --- |
| [architecture.md](architecture.md) | The app, the API, the database, the object storage and the boundaries between them. |
| [screenshots/README.md](screenshots/README.md) | The captures of the interface, which live in `screenshots/` at the root of the repository. |
| [../README.md](../README.md) | The front door: what the app does and how to run it. |
| [../AGENTS.md](../AGENTS.md) | The commands, the traps and the rules of the project. |
| [../PRODUCT.md](../PRODUCT.md) | The product truth: the users, the purpose, the constraints. |
| [../DESIGN.md](../DESIGN.md) | The palette, the type, the spacing and the components of the interface. |

## The audits

| Document | What it covers |
| --- | --- |
| [ux/README.md](ux/README.md) | The audit of the user paths: one file per screen, with the routes, the findings and the questions for the owner. |
| [ux/_paths.md](ux/_paths.md) | The path as a whole, from the first sign-in to the deletion of the account. |
| [ux/_decisions.md](ux/_decisions.md) | What the owner decided about the findings, and what was deliberately left as it is. |
| [ux/_existing-audit.md](ux/_existing-audit.md) | The older audit of 2 October 2026, matched to the screen that describes each story now. |
| [ux/_template.md](ux/_template.md) | The shape of a screen document. |
| [qa/README.md](qa/README.md) | The QA checklist before a release, with the legend of the marks and the stand it was run on. |
| [ios-checklist.md](ios-checklist.md) | What cannot be checked in a browser and needs a real phone. |
| [ux-audit.docx](ux-audit.docx) | The audit of 2 October 2026: 125 stories over four areas, each with a verdict. |

## The QA checklist

The checklist is ten documents, one per area, each with the cases and the
result of each case rather than the case alone.

| Document | What it covers |
| --- | --- |
| [qa/01-вход-и-аккаунт.md](qa/01-вход-и-аккаунт.md) | The sign-in and the account. |
| [qa/02-питомцы-и-доступ.md](qa/02-питомцы-и-доступ.md) | The pets and the access to them. |
| [qa/03-записи-и-лента.md](qa/03-записи-и-лента.md) | The records and the feed. |
| [qa/04-лекарства.md](qa/04-лекарства.md) | The medicines. |
| [qa/05-документы.md](qa/05-документы.md) | The documents. |
| [qa/06-медкарта.md](qa/06-медкарта.md) | The medical card. |
| [qa/07-настройки-и-справка.md](qa/07-настройки-и-справка.md) | The settings and the help. |
| [qa/08-навигация-и-экран.md](qa/08-навигация-и-экран.md) | The navigation and the screen. |
| [qa/09-уведомления-и-без-сети.md](qa/09-уведомления-и-без-сети.md) | The notifications and the work without a network. |
| [qa/10-администрирование.md](qa/10-администрирование.md) | The administration. |

## A note on the language

Everything in this folder is in Russian, apart from the three documents
written for the house standard: this index, [architecture.md](architecture.md)
and [screenshots/README.md](screenshots/README.md).

## Reading order

New here: [../README.md](../README.md), then [architecture.md](architecture.md)
for the code and the data flow.

Checking the interface: [ux/README.md](ux/README.md) for the audit of the
paths, then the file of the screen you are working on, and
[../AGENTS.md](../AGENTS.md) for the rules the interface holds to.

Before a release: [qa/README.md](qa/README.md) for the checklist and the
stand it was run on.
