# Video Storyboard — LogX AI

Shooting script: one screen capture per page, narration to read while
filming/clicking. Each block = [what's on screen] + [what the voice-over
says]. Durations are indicative (~11-13 min total following everything,
~6-7 min if you cut the sections marked "optional").

Filming tips:
- Record at 1080p minimum, browser full screen, NIGHT theme (more
  photogenic on video than the day theme).
- One page = one separate clip, edit afterward — avoids reshooting
  everything if a single take fails.
- Zoom in / highlight on click (enlarged cursor or a highlighting tool)
  so the elements mentioned in the narration are visible on screen.
- Prepare the log BEFORE filming: a few QSOs already entered, a contest
  selected, the config filled in — an empty screen sells nothing.

---

## 0. Hook (0:00 – 0:25)

**Screen**: fast montage (3-4 shots of 1-2s) — LOGBOOK in full traffic, the
AI map spinning, a spot turning into a QSO on click, the score climbing.
No detailed narration here, just the tone.

**Voice-over**:
"One piece of software for everyday logging. Another for contests. A
website for propagation. A spreadsheet for your portable activations. And
a pile of open tabs for the cluster, the maps, the QSL confirmations.
LogX AI brings all of that into a single application — that runs on your
own computer, for free, no account, no subscription."

**On-screen title**: LogX AI — the next-generation operating companion.

---

## 1. CONFIGURATION (about 1:00)

**Screen**: `logx_configuration.html`. Show the category hub (card grid),
then open 2-3 popups by clicking.

**Narration**:
"It all starts here, in CONFIG. A hub of categories rather than one long
form: station identity, operators, contest selection, radio, propagation...
each card opens a dedicated popup, with contextual help on every field —
the little **?** next to each setting."

*(Open popup 3 — Contest selection)*
"41 contests built in — REF, IARU, CQ WW, CQ WPX, ARRL DX, WAE... — plus
the complete WA7BNM world calendar, ready in one click. And if a contest
isn't in there? The AI reads the rules, PDF or web page, French or
English, and proposes bands, dates, exchange and scoring — always subject
to your review before it's activated."

*(Open popup 6 — Radio CAT)*
"Radio control: native CAT for Icom, Yaesu, Kenwood, Elecraft, Xiegu over
serial cable, TCI for SDRs, rigctld for everything else. Auto-detected on
plug-in — plug-and-play, no manual port configuration."

---

## 2. LOGBOOK — the central page (about 2:30)

**Screen**: `logx_logbook.html`. This is the page that deserves the most
time — show each area in order: entry (left), band map (middle), log
table (right), bottom bar.

### 2a. QSO entry (left column)

"Entry, designed to be fast. Band and mode in one click — a button, a
menu, instead of a row of seventeen unreadable buttons. You type the
callsign..."

*(Type a callsign into the field)*

"...and the correspondent's card appears on its own: country, flag,
history of your contacts with them, a gold alert if it's a new country
ever worked. Distance, bearing and points are calculated as soon as the
grid locator is entered. And ESM mode — the Enter key chains CQ,
exchange, then logging the QSO, without ever leaving the keyboard."

### 2b. Band map (middle column)

"In the center, the band map: spots from the cluster, RBN and PSK
Reporter placed by frequency. Clicking one tunes the radio AND
pre-fills the callsign — zero retyping. Red: never worked. The filter
lets you keep only new countries or LoTW-confirmed stations."

*(Click the panadapter icon in the band map toolbar)*

"And recently, a built-in panadapter: spectrum and waterfall from the
receive audio, the native scope of recent Icoms, or the IQ stream from a
TCI server — no extra hardware for the audio version."

### 2c. Log table (right column)

"On the right, the live log — search, band filters, one-click export.
The MAP button switches to a map of all your QSOs for the session."

*(Optional: click the magnifying glass in the nav bar, type a keyword)*

"And if you can't remember where a specific setting lives — a single
word typed into the nav's search finds the right page and the right
passage, without having to know the software by heart."

### 2d. Bottom bar — keyer

*(Switch to CW mode if possible, otherwise show the voice keyer in SSB)*

"At the bottom, the keyer — voice in phone, F1-to-F8 macros in CW, with a
built-in CW decoder that listens to the receive audio and displays the
decoded Morse. The voice keyer spells out the callsign and report on the
fly in the ICAO phonetic alphabet, and automatically keys up for the
duration of the message."

### 2e. Top bar (score, propagation, alerts) — optional

"Always in view: the live score, time remaining in the contest, solar
indices, an alert if there's a storm at your QTH — without ever leaving
the entry page."

---

## 3. AI MAP (0:45)

**Screen**: `logx_carte.html`.

"The AI map: every live spot, positioned on the globe, with the best
targets ranked by REAL point value — not an estimate, the actual scoring
of the active contest. The copilot explains why one station is worth
more than another: new country, new multiplier, distance."

---

## 4. PROPAGATION (0:45)

**Screen**: `logx_propagation.html`.

"Propagation without leaving the software: solar indices, real MUF
measured by ionosondes, band openings by world region, sporadic-E, NCDXF
beacons. And a complete EME panel — Moon position, common window with the
correspondent, Doppler and link budget, from just two grid locators."

---

## 5. HUNT (0:45)

**Screen**: `logx_chasse.html`.

"For POTA, SOTA, WWFF, IOTA and WCA castle activators and hunters: over
415,000 references stored locally, live spots, automatic validation, and
real-time tracking of your own activation — including park-to-park
detection."

---

## 6. Maps / Departments (0:30) — optional

**Screen**: `logx_departements.html`.

"For hunting French departments: the map colors in as you progress,
department by department."

---

## 7. CALENDAR (0:30)

**Screen**: `logx_calendrier.html`.

"The world contest calendar — nearly 360 events for the year, ready to
prepare in one click straight from this page."

---

## 8. WEBSDR (0:30) — optional

**Screen**: `logx_websdr.html`.

"A directory of WebSDR receivers around the world — to listen to your
own signal before a call, or to hear a DX station from a receiver close
to them."

---

## 9. BAND FOCUS (0:30) — optional

**Screen**: `logx_focus.html`.

"The BAND FOCUS page: everything the software knows about a band on a
single screen — cluster filtered by band and mode, openings, active
contests, and every band ranked with the reason spelled out in plain
language."

---

## 10. CW School (0:30) — optional

**Screen**: `logx_cw.html`.

"For practice: ten minutes of CW generated from YOUR own index — your
log, your archives — with the exchange from your next contest. Nothing
goes out over the air, it all stays in the headphones."

---

## 11. Multi-op & wall display (0:45)

**Screen**: ideally two windows/devices side by side, or `logx_wall.html`
alone if only one station is available.

"Multiple stations in the shack — PC, tablet, phone — join the same log
by opening a simple WiFi address, nothing to install. Up to forty
operators in radio-club mode. For a radio club with its own servers,
syncing can also go through a shared MySQL database, near real-time. And
a wall display to project: the live stream of QSOs, visible from the
room while friends watch."

---

## 12. After the contact — QSL & awards (0:30)

**Screen**: CONFIG or LOGBOOK Awards/QSL popup.

"After the contact: lifetime awards, a Worked Matrix by band and mode,
and five QSL services synced in one click — eQSL, LoTW without installing
TQSL, ClubLog, QRZCQ, HRDLog."

---

## 13. Closing / call to action (0:30)

**Screen**: GitHub download page, or the README.

"A single file to download, no installation, no account. Your data stays
on your machine. LogX AI is free, under the free GPLv3 license — the code
stays open and will remain so. Coming from N1MM+, Win-Test, DXLog or
Log4OM? Your history imports in one click, nothing to retype. Built by a
ham radio operator for the community — and your feedback shapes the
software."

**On-screen text (end)**:
- Download: GitHub link / latest release
- Wiki / user guide: link
- Free software — GPLv3
- 73!

---

## Numbers to overlay (optional)

Taken from `docs/LogX_AI_Promotion.md` — update if the figures have
changed since:

| | |
|---|---|
| Built-in references | 415,000+ (SOTA, POTA, WWFF, IOTA, WCA castles) |
| Contests with exact scoring | 41 + world calendar + AI analysis |
| Bands | 17, from 1.8 MHz to 47 GHz |
| Interface languages | 8 |
| Required subscription / account / cloud | 0 |
| License | GPLv3 — open source |

---

## Editing notes

- Section 0 (hook) and section 13 (closing) are the only two that do NOT
  follow the "one capture = one page" rule — plan a slightly more crafted
  edit for these two (music, on-screen text).
- Sections marked "optional" can be cut for a short version (~6-7 min)
  centered on CONFIG → LOGBOOK → AI MAP → PROPAGATION → HUNT → closing.
- If something mentioned in the narration isn't visible on screen at the
  right moment (e.g. no spots on the band map while filming), either
  prepare the data in advance (a log with a few QSOs, an active contest
  with simulated traffic), or adjust the narration to match what's
  actually visible rather than describing an empty screen.
