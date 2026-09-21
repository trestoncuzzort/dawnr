# Design brief

Written 2026-09-21 from six sourced research passes plus ten pages fetched and read
again while writing this file. It exists because the window's look was decided by one
person's taste and by contrast arithmetic, and the operator asked for the other thing:
evidence about what people actually want, worldwide, before the design is called
finished.

**This brief overrules taste where the evidence is stronger than taste, and it says so
out loud each time.** It reverses one decision the operator made by hand on 2026-09-21,
the dark fallback, and it puts a ceiling on a second, the warmth of the ground. Both are
named in section 1 rather than buried, with the sources that outrank them.

## How to read it

Every claim carries a source as a bare host and path, and a rank:

| Rank | What it means | What it can settle |
| --- | --- | --- |
| **STUDY** | Controlled measurement with a stated method and sample | What happens to human beings |
| **SURVEY** | Asked people, stated method | What people say they want |
| **GUIDELINE** | A platform owner's own text | What is idiomatic **on that platform**, nothing about human beings |
| **OPINION** | A blog, a wiki, a preference | Nothing on its own. Allowed, if labelled |
| **MEASURED HERE** | Computed or read out of this repository while writing this file | Our own state |

Provenance is marked too. `[read here]` means the page was fetched and read while this
file was written. `[research pass]` means a researcher fetched it and this file did not
re-verify it. A number with no instrument beside it is a bug in this document.

---

## 1. What the evidence says we got wrong

### C1. Opening dark when the system setting cannot be read is wrong on every ground we could find

Two of the three platform owners publish a default and both say light.
GNOME: "Most apps should use the standard light UI style by default. However, apps can
alternatively choose to use the dark style by default instead. This is primarily
recommended for apps which display rich visual content like images or video."
(developer.gnome.org/hig/guidelines/ui-styling.html, GUIDELINE, [read here]). locallm
displays no images or video, so the stated exception does not reach it.
Microsoft: "Windows uses Light mode by default, but users can choose Dark mode."
(learn.microsoft.com/en-us/windows/apps/desktop/modernize/apply-windows-themes,
GUIDELINE, [read here]). Apple publishes no default either way.

The usability review the industry reads says the same in plain words: "we don't
recommend switching to dark mode by default if your target audience includes the
general population" (nngroup.com/articles/dark-mode, GUIDELINE summarising STUDY,
[read here]).

The measurement that matters most is about the exact case the fallback covers. The
fallback fires when no desktop service answers, which is most likely on a bare or
minimal Linux install, which is also the machine most likely to be in a dim room at
night. Dobres, Chahine and Reimer, Applied Ergonomics 60 (2017), 34 participants in the
analysis sample of 50 recruited, ages 20 to 65, lexical decision with an adaptive
staircase: in a near-dark room at 0 lux, 3 mm text needed a presentation time of
122.3 ms (SD 50.0) in dark mode against 84.1 ms (SD 43.7) in light, F(1,33) = 49.60,
p < 0.001, while in a bright room at 4750 lux the polarity difference was not
significant (jdobr.es/pdf/Dobres-etal-2017-Ambient.pdf, STUDY, [research pass];
nngroup.com/articles/dark-mode summarises the same study and was [read here]). So the
fallback currently chooses the one combination with a measured legibility penalty, in
the one situation where it applies.

**And the file already knew.** `locallm/look.py` carries this in its own palette
header at line 64: "LIGHT IS THE DEFAULT AND DARK FOLLOWS THE SYSTEM, which is what
the platform this runs on asks for", quoting that exact GNOME sentence. At line 153 sits
`_DARK_WHEN_UNKNOWN = True`, with the comment "When nothing can be read, open dark. The
operator's decision, 2026-09-21." The module states a rule and then breaks it in the
same file (MEASURED HERE, `locallm/look.py`).

### C2. The reason usually given for dark mode is not supported, including by the page that gives it

The Microsoft page above says users "might prefer this setting because it's easier on
the eyes in lower-light environments", and cites nothing. Measured work does not find
it. Piepenbrock and colleagues collected pre and post eyestrain, headache, muscle
strain and back pain and "concluded that there was no significant difference of
contrast polarity on any of them" (nngroup.com/articles/dark-mode, STUDY via review,
[read here]). Sengsoon and Intaruk, IJERPH 22(4):609, 2025, crossover, 30 female
participants, mean age 21.20 (SD 1.16), one hour per mode: visual fatigue 18.37
(SD 6.96) light against 18.87 (SD 7.01) dark, p = 0.305 (pmc.ncbi.nlm.nih.gov/articles/
PMC12027292, STUDY, [research pass]). The nearest family of claims, blue-light
filtering, has a null result from 17 randomised trials and 619 participants
(cochrane.org/evidence/CD013244, STUDY, [research pass]).

So: dark mode stays, and the sentence "easier on the eyes" never appears in locallm's
copy, README or store text. A vendor asserting it is not evidence, and this is the
clearest case in the whole brief of a GUIDELINE being used for something a guideline
cannot settle.

### C3. The warming direction that produced the cream ground is the direction one study measured as worst, but the cream is nowhere near the tested worst point

Xie, Yu and Chen, International Journal of Human-Computer Interaction 41(2), 2024,
2x2x3 design, 36 participants, eye tracking for blink rate and pupil diameter plus the
Richter scale: "Whether at daytime or night, the 2800 K color temperature resulted in
the highest visual fatigue", and the paper reports a significant negative correlation
between text-background luminance contrast and visual fatigue, with participants
preferring higher contrast (api.semanticscholar.org, DOI 10.1080/10447318.2024.2305982,
STUDY, [read here, abstract]).

The research pass read that as an argument against the cream. Recomputing it here says
something narrower and more useful. By McCamy's cubic approximation applied to the sRGB
to XYZ (D65) conversion, computed while writing this file: `#E8DCC8` sits at about
5389 K, the previous `#F2EDE1` at about 5899 K, and pure white at 6507 K, which is the
method's sanity check against D65's 6504 K (MEASURED HERE). The study's worst condition,
2800 K, is a whole-screen colour temperature far warmer than any of these. The study
also manipulated the **display's** colour temperature, not one application's background
under a neutral system white point, which is a different and stronger intervention than
ours.

The honest conclusion is therefore not "the cream is wrong". It is: **the cream is as
warm as this ground is ever allowed to get, and the next request for warmer has to be
refused with this citation.** The luminance part of the operator's request survives
intact and is the part with a mechanism: by the WCAG relative luminance formula
(w3.org/WAI/GL/wiki/Relative_luminance), `#E8DCC8` measures Y = 0.7251 against 0.8488
for `#F2EDE1` and 1.0000 for white, so on a panel whose white measures 250 cd/m2 the
three grounds emit roughly 181, 212 and 250 cd/m2 (MEASURED HERE, arithmetic from
luminance, not a photometer).

### C4. No platform has a cream, and the only vendor who answers the native-versus-branded question says native

GNOME's palette page scopes itself: "The GNOME color palette is intended for use in app
icons and illustrations", and its light neutrals are `#ffffff`, `#f6f5f4`, `#deddda`
(developer.gnome.org/hig/reference/palette.html, GUIDELINE, [research pass]).
Microsoft, twice on one page: "If you can't use WinUI, consider emulating the styles
demonstrated in our design toolkits and WinUI 3 Gallery"
(learn.microsoft.com/en-us/windows/apps/get-started/best-practices, GUIDELINE,
[research pass]). Apple frames native as a benefit rather than a rule, and its App
Review Guidelines section 4 never names the Human Interface Guidelines as a requirement
(developer.apple.com/app-store/review/guidelines, GUIDELINE, [research pass]).

So keeping a branded ground is off-guideline on Windows, permitted on macOS and
tolerated on GNOME. That is a choice we are allowed to make and have not yet made
deliberately. Section 2 makes it.

### C5. The body text is smaller than we thought, and smaller is where dark hurts most

The research pass assumed locallm's body sits at each platform's minimum, 13 pt or
14 px. The source is worse than that. `locallm/studio.py` sets `font=SANS(8)` at lines
662, 666, 669, 680 and 701 and `font=SANS(9)` at 698, for chart axis labels and legend
text (MEASURED HERE). Tk reads a positive size as points
(tcl-lang.org/man/tcl8.6/TkCmd/font.htm, [read here]), so 8 points is about 10.7 px at
96 dpi. Microsoft's floor is "14px Semibold, 12px Regular" with the reason "Text
smaller than these sizes and weights are illegible in some languages"
(learn.microsoft.com/en-us/windows/apps/design/style/typography, GUIDELINE,
[research pass]). Our smallest text is below the only floor that was justified by
non-Latin legibility rather than by taste.

That compounds C1: the positive-polarity advantage "increased linearly as the font size
was decreased" (nngroup.com/articles/dark-mode on Piepenbrock in Human Factors, STUDY
via review, [read here]). Smallest type in the worst polarity is the combination the
current fallback produces.

### C6. Two tab labels are verbs, the labels run from 2 to 12 characters, and the window has eight pages behind five tabs

GNOME: "Label views with header capitalization, and use nouns rather than verbs... Try
to give view labels a similar length", with three to five views and a sidebar beyond
that (developer.gnome.org/hig/patterns/nav/view-switchers.html, GUIDELINE,
[research pass]). Apple asks for nouns or short noun phrases and at most six tabs
(developer.apple.com/design/human-interface-guidelines/tab-views, GUIDELINE,
[research pass]).

Current: `Home`, `Train`, `Proof`, `Collect data`, `AI` at `t/lab.py` line 946, and
`self.pages` also holds `Live checks`, `Test a model` and `Results`, reachable only
through the View menu (MEASURED HERE). Five visible views is inside both limits; eight
pages with three hidden in a menu is a structure no guideline we found describes and no
evidence we found measures.

### C7. On Windows the app is system DPI aware and the comment says otherwise

Microsoft: Win32 and its relatives "don't automatically handle per-monitor DPI
scaling... applications might appear blurry or incorrectly sized"
(learn.microsoft.com/en-us/windows/apps/get-started/best-practices, GUIDELINE,
[research pass]). `t/lab.py` line 2875 and `locallm/studio.py` line 2065 both call
`SetProcessDpiAwareness(1)`, and studio's comment labels it "per-monitor aware". The
enumeration says otherwise: `PROCESS_SYSTEM_DPI_AWARE = 1`, "This app does not scale
for DPI changes. It will query for the DPI once and use that value for the lifetime of
the app", while per-monitor is 2
(learn.microsoft.com/en-us/windows/win32/api/shellscalingapi/ne-shellscalingapi-process_dpi_awareness,
GUIDELINE, [read here]). The code is correct for what it does and the comment is false
(MEASURED HERE).

Separately, nothing in the repository calls `DwmSetWindowAttribute` (MEASURED HERE,
grep across `t/` and `locallm/`), so on Windows the dark theme ships a light title bar
over a dark body, which is the defect the Microsoft theming page exists to warn about.

### C8. The window cannot be promised at 1024x600 on the path that matters most

GNOME: "The smallest recommended display size for GNOME on desktop is currently
1024x600px, and this size should be supported by all apps"
(developer.gnome.org/hig/guidelines/adaptive.html, GUIDELINE, [read here]).
`locallm/look.py` `fit_to_screen` clamps the minimum to 760x560 scaled, which fits. But
`t/lab.py` lines 2858 to 2861 hold a fallback used when `look` cannot be imported, and
line 2861 sets `minsize(1000, 700)`: 700 does not fit in 600 (MEASURED HERE). That fallback
path is exactly the no-torch, no-locallm, portable case the project cares about most.

Worldwide resolution share corroborates that this is not hypothetical, with the caveat
that the measurement is page-view weighted and browser-based:
gs.statcounter.com/screen-resolution-stats/desktop/worldwide for August 2026 gives
1920x1080 at 22.22%, 1366x768 at 5.2% and 1280x720 at 3.52%, with no dominant
resolution (SURVEY-grade measurement, [research pass]).

### C9. Restoring where the user was is half built, and the half that exists can open the window off-screen

Apple: "Restore the previous state when your app restarts so people can continue where
they left off... display windows in the same state and location in which people left
them" (developer.apple.com/design/human-interface-guidelines/launching, GUIDELINE,
[research pass]). GNOME asks for the previous window size too.

Current: `t/lab.py` writes `GEOMETRY` only inside the self-refresh path at line 1981
and reads it at line 2849, so a normal quit remembers nothing; the start page is always
`Home` unless `--page` is passed; and the saved geometry is applied at line 2866,
**after** `fit_to_screen` at line 2862 has clamped the window to the work area, without
being clamped itself (MEASURED HERE). A geometry remembered from a monitor that is no longer attached
therefore defeats the function written to prevent exactly that.

---

## 2. Decisions

Each one states what we will do, the evidence with its rank, what we give up, and where
it lives. Nothing here is a research summary; the research is section 1 and the
citations.

### Colour scheme

**D1. When the system preference cannot be read, open light.**
Because C1: GNOME and Microsoft both publish light as the platform default (GUIDELINE),
NN/g recommends against a dark default for a general audience (GUIDELINE over STUDY),
and the fallback's own most likely environment is the dim room where dark measured
122.3 ms against 84.1 ms for 3 mm text (STUDY, n = 34).
*We give up* the operator's stated preference for a dark window on a desktop that
answers nothing. That preference is OPINION-rank and it is honest, so it keeps two
routes: `LOCALLM_THEME=dark` already works, and D3 adds a remembered setting.
*Where:* `locallm/look.py`, `_DARK_WHEN_UNKNOWN`. One boolean, plus the comment beside
it, plus the header paragraph that already says light and must stop contradicting the
constant.

**D2. Keep following the operating system's setting when it can be read.**
Because it is the only behaviour all three platforms permit. Apple: "Avoid offering an
app-specific appearance setting... they may think your app is broken because it doesn't
respond to their systemwide appearance choice"
(developer.apple.com/design/human-interface-guidelines/dark-mode, GUIDELINE,
[research pass]).
*We give up* nothing; this is what `system_wants_dark()` already does across the XDG
portal, gsettings, the Windows registry and `defaults`.

**D3. Ship a theme override with three options, on Windows and Linux, and not on macOS.**
The options read Light / Dark / Use system setting, which is Microsoft's prescribed
wording (learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings,
GUIDELINE, [research pass]) and matches GNOME's "three options should typically be
included: light, dark, and follow system preference". GNOME adds the reason this app
qualifies: per-app style preferences are "primarily useful for text editing apps, or
apps which users use for long periods of time"
(developer.gnome.org/hig/guidelines/ui-styling.html, GUIDELINE, [read here]). A training
run is a long period. Apple forbids the control, so on macOS it is not built, and the
environment variable remains for anyone determined.
*We give up* one of the four or five settings every platform tells us to budget, and
strict single-codepath simplicity: one `if` on the platform decides whether the control
exists.
*Where:* `t/lab.py` `show_preferences`, plus a persisted value read by `locallm/look.py`.

**D4. Dark stays a first-class theme, fully maintained.**
NN/g: "we strongly recommend that designers allow users to switch to dark mode if they
want to", for long-term effects, for visually impaired users and for preference
(GUIDELINE, [read here]). The low-vision case is real and small: Legge and colleagues,
1985, 7 participants with cloudy ocular media, all read faster in dark mode, on CRT
displays, a limitation NN/g itself flags as possibly biased against light (STUDY,
[read here]). Xie 2024 found lower visual fatigue in dark mode at both 450 lux and
3 lux (STUDY, n = 36, [read here]). A survey of university students in Nepal reports
79.7% preferring dark on their phones (arxiv.org/abs/2409.10895, SURVEY, sample size
not stated in the abstract, [research pass]).
*We give up* nothing. This is what exists.

**D5. The words "easier on the eyes" are banned from our copy.**
Because C2. The defensible sentences are: it is dimmer, some people find it more
comfortable, and it is what your system asked for.
*Where:* `locallm/README.md`, `t/lab.py` `show_about`, any store text.

### The ground and the palette

**D6. Keep `#E8DCC8` as the one ground, at this luminance, and freeze its warmth.**
This is the choice C4 says must be deliberate: we are knowingly off-guideline on
Windows, where Microsoft asks non-native apps to emulate native styles (GUIDELINE), in
exchange for a ground that is recognisably this application's. The luminance case is
measured (C3). The warmth is now at its ceiling and any future request for warmer is
refused with Xie 2024.
*We give up* looking native on the platform with the most users, and we accept that a
reviewer can cite that sentence against us. If the trade is ever reversed, the
replacement is not white: it is the neutral at the same luminance, which is
`#DDDDDD` at Y = 0.7231 against the cream's 0.7251, the closest neutral there is
(MEASURED HERE, by search over the WCAG luminance formula), and
that swap keeps every contrast pair within a few hundredths.
*We reject* the research pass's suggestion to keep the ground in the content area and
platform neutrals in the chrome. In Tk the chrome is not the platform's either: the tab
strip and header are our own widgets, so a grey strip would not be native, it would
just be a second ground. The one thing above our content that really is the platform's
is the title bar, which is what D14 fixes.

**D7. Every muted tone is chosen by arithmetic against the cream, never against white.**
Measured while writing this file with the WCAG contrast formula: light ink `#241E16` on
`#E8DCC8` is 12.18:1 (and 14.13:1 on the old `#F2EDE1`); dark ink `#EDE7D9` on
`#1B1917` is 14.22:1; muted `#5E5140` is 5.68:1 on the ground and 6.45:1 on the card;
the weakest light text pair is proved `#24603C` at 5.51:1. All clear SC 1.4.3's 4.5:1
and the primaries clear Apple's 7:1 aspiration for custom colours. The trap is
unchanged: a plain `#6E6E6E` grey measures 3.76:1 on this ground and fails, while
`#5A5A5A` measures 5.09:1 and passes (all MEASURED HERE).
*Note two corrections.* The research pass computed the light theme's ink as `#1B1917`,
which is the dark ground, not the light ink; the real pair is 12.18:1, not 12.94:1.
And `locallm/look.py`'s header says muted is 5.08 light, where the current hex measures
5.68: the comment predates the palette and should be restated or deleted, since
`locallm/test_look.py` recomputes every pair from the hex anyway.
*Where:* `locallm/look.py` comments; no colour changes.

**D8. Keep the rule that nothing but ink sits on a selection band.**
Muted on the `#CBB795` band measures 3.94:1 here, below the body bar, and ink measures
8.45:1 (MEASURED HERE). `look.py` already states this; it is now measured twice.

### Type

**D9. Five semantic roles, bound to per-platform values at startup, derived from Tk's own standard named fonts.**
Microsoft's own cross-platform system solved exactly our problem by keeping role names
and swapping numbers: Fluent 2 publishes macOS Caption 1 10pt/13pt, Body 1 13pt/16pt,
Title 3 15pt/20pt, Title 1 22pt/26pt, Large Title 26pt/32pt, and Windows Caption
12px/16px, Body 14px/20px, Body large 18px/24px, Subtitle 20px/28px, Title 28px/36px
(fluent2.microsoft.design/typography, GUIDELINE, [research pass]). GNOME publishes no
numbers and says "Don't hard-code font styles or sizes... express font-sizes as relative
values" (developer.gnome.org/hig/guidelines/typography.html, GUIDELINE, [research pass]).
The mechanism exists in Tk and we are not using it. Tk publishes nine standard named
fonts, including `TkDefaultFont`, `TkTextFont`, `TkHeadingFont`, `TkCaptionFont` and
`TkSmallCaptionFont`, "supported on all systems, and default to values that match
appropriate system defaults", with the instruction "It is not advised to change these
fonts, as they may be modified by Tk itself in response to system changes. Instead,
make a copy of the font and modify that" (tcl-lang.org/man/tcl8.6/TkCmd/font.htm,
GUIDELINE, [read here]). So: read `font actual TkDefaultFont` at startup, take its size
as the base, and derive Caption, Body, Body strong, Subtitle and Title as ratios of it,
never as literals at call sites.
*We give up* the ability to read a size at the call site and know what it is. In
exchange a user who set a larger system font gets a larger application, which is what
GNOME's rule is protecting and what a fixed ladder cannot do.
*One measurement the implementation must take, not assumed here:* on Windows
`TkDefaultFont` is expected to resolve to the platform UI face at 9 points, which is
12 px at 96 dpi, at Microsoft's regular floor and 2 px below Fluent's Body of 14 px.
If that is what it measures, Body takes a floor of 14 px on Windows rather than the raw
base. This brief was written on Linux and did not measure it.
*Where:* `locallm/look.py` `SANS`/`MONO`, and every call site that passes a literal.

**D10. Nothing below 12 px equivalent, anywhere, ever.**
Microsoft's floor is the only one justified by a reason about human beings rather than
convention: "Text smaller than these sizes and weights are illegible in some languages"
(GUIDELINE). That makes it the global floor, above Apple's 10 pt macOS minimum.
*We give up* the current 8 pt chart labels (C5). Chart axis labels move to the Caption
role.
*Where:* `locallm/studio.py` lines 662, 666, 669, 680, 698, 701. This is the one item
in this brief that touches a file two other runs are editing, so it is listed in the
diff and not done here.

**D11. Add a text-size control with three steps, multiplying the one base value.**
Hou, Anicetus and He, Frontiers in Psychology 13:931646, accepted 30 June 2022, a
systematic review across four databases, concludes that font size should be specified
as visual angle in arcminutes and reports recommendations between 42 and 66 arcminutes
at 40 cm for readers over 57, from individual samples of 12 to 40 people
(ncbi.nlm.nih.gov/pmc/articles/PMC9376262, STUDY, [research pass]). At a 50 cm viewing
distance macOS body 13 pt is about 31.5 arcminutes and Windows body 14 px about 25.5
(arithmetic reported by the research pass). The platform floors are floors for young
eyes. A control that multiplies the D9 base by roughly 1.0, 1.25 and 1.5 reaches the
reviewed range at the top step.
*We give up* the second of our four or five settings. This is the last one; after D3 and
D11 the settings budget is spent.

**D12. Regular and Semibold only, no italics, no all-caps, one family per platform, body lines capped near 60 characters.**
Rare three-way agreement. Microsoft: "Use Semibold instead of Bold for emphasis. Italic
is excluded because it can reduce readability and legibility, particularly for people
with dyslexia", and "Keep to 50-60 letters per line for ease of reading" (GUIDELINE).
GNOME: "Avoid the use of italic or oblique faces... Do not capitalize every letter (all
caps)" (GUIDELINE). Apple: "avoid Ultralight, Thin, and Light" and "Minimize the number
of typefaces you use" (GUIDELINE). Microsoft's dyslexia sentence is the only
human-factors reason any of the three offers for a type rule.
*We give up* nothing; the native-first font list already does the family part.
*Where:* the 60-character cap gives `t/lab.py`'s `_rewrap` an actual number instead of a
window-width guess.

### Spacing and targets

**D13. Keep the 4/8/12/16/24/32 scale and make 24 the window gutter.**
Microsoft: "all dimensions, margins, and padding should be in increments of 4 epx", with
"12 epx gutters" below 640 px width and "24 epx gutters" above
(learn.microsoft.com/en-us/windows/apps/design/layout/alignment-margin-padding,
GUIDELINE, [research pass]). Apple's only published spacing numbers are "about 12
points of padding around elements that include a bezel" and "about 24 points" for
unbezeled ones (developer.apple.com/design/human-interface-guidelines/accessibility,
GUIDELINE, [research pass]); Home's cards are unbezeled text blocks, so they are in the
24 bucket. GNOME publishes no scale, and libadwaita's `.toolbar` "ensures 6px margins
and spacing between widgets" (gnome.pages.gitlab.gnome.org/libadwaita, GUIDELINE,
[research pass]).
The existing scale comes from Carbon (carbondesignsystem.com) and already satisfies
Microsoft exactly. The change is which name the outer margin uses: `SPACE.group` (24)
rather than `SPACE.page` (32), so the gutter lands on both Microsoft's recommendation
and Apple's unbezeled number.
*We give up* GNOME's 6 px rhythm at 4, 8, 16 and 32. We meet it at 12, 24 and 48. We
reject switching to 6/12/24/48 wholesale, because that abandons a published scale and a
working test for a de-facto value one stylesheet mentions.

**D14. 24x24 px is the floor for anything clickable, 40x40 for primary buttons, 28x28 for secondary controls.**
WCAG 2.2 SC 2.5.8 Target Size (Minimum), Level AA, a W3C Recommendation dated
12 December 2024: "The size of the target for pointer inputs is at least 24 by 24 CSS
pixels", with a spacing exception, and it applies to mouse and pen users because it
"reduces the chances of erroneous activation due to either a tremor or reduced
precision" (w3.org/WAI/WCAG22/Understanding/target-size-minimum.html, GUIDELINE,
[research pass]). Microsoft asks for 40x40 px at 135 PPI (GUIDELINE). Apple's
accessibility table says 28x28 pt default and 20x20 pt minimum on macOS while Apple's
buttons page says 44x44 pt as a general rule, so Apple contradicts Apple and there is no
single authority to defer to. 24 is the number an audit will cite.
*Where:* the tab strip is `tk.Label` with `padx=16, pady=8` (`t/lab.py` line 947), which
should clear it comfortably, and the primary buttons need measuring. This is a test to
write, not a redesign: assert requested height at `tk scaling` 1.0 and again at 2.0.

### Structure, naming and first run

**D15. Rename the five tabs to single-word nouns of similar length.**
Proposed: `Home`, `Training`, `Proof`, `Data`, `Autopilot`, at 4, 8, 5, 4 and 9
characters against today's 4, 5, 5, 12 and 2.
Because C6, and because single words dissolve a conflict the research pass called
irreconcilable. Microsoft wants sentence case for all UI text including titles; Apple
and GNOME want title or header capitalization on tab labels. A one-word label is
spelled identically under all three, so the conflict only exists for multi-word labels
and the fix is to not have any. That is better than branching casing on the platform at
startup, which was the alternative.
*We give up* "Collect data", which says what the page does, for "Data", which says what
it is about; and "AI", which is short, for "Autopilot", which is what the page actually
holds ("the orchestrator (a fixed plan) and the autopilot", `t/lab.py` line 2211).
*Cost:* the literals appear about ten times in `t/lab.py`, including the `--page`
argument at line 1985 and the View menu built by walking `self.pages`, plus the
screenshot filenames in `docs/img/` and their references.
*Unresolved, and flagged rather than guessed:* whether "Data" reads as jargon to the
audience `home.py` is written for, "someone who has never heard of a transformer". No
evidence was found either way. The alternative is "Text", matching Home's first card.

**D16. Home's four numbered cards stay, and collapse once a model exists.**
GNOME blesses the current design almost exactly: a placeholder page with an illustration
in the main view "when it is empty... a good way to provide guidance, set a positive
note, and establish a relationship with the user", with a heading, a description and
"controls for relevant actions... This is one place where the suggested button style can
be appropriate" (developer.gnome.org/hig/patterns/feedback/placeholders.html, GUIDELINE,
[research pass]). Microsoft makes it a store rule: "The value proposition of your
product must be clear during the first run experience" (policy 10.1.1, Microsoft Store
Policies 7.20, effective 22 October 2026,
learn.microsoft.com/en-us/windows/apps/publish/store-policies, GUIDELINE,
[research pass]). Apple wants onboarding "fast, fun, and optional" and not shown again
after it has been used (GUIDELINE, [research pass]).
The reconciliation is GNOME's own caveat: placeholders are for the initial view "when
the initial empty state is unavoidable". Once there is a corpus and a trained model the
state is no longer empty, so each card collapses to one line naming what it holds, with
the primary button becoming train again or talk to it.
*We give up* a constant teaching surface for returning users, and we keep it for the
first run, which is the run the only hard rule covers.

**D17. Restore the last page, the last window geometry and the last corpus path on relaunch, and clamp the restored geometry.**
Because C9, and because a training run is long and people quit and come back, which
makes this worth more here than in most applications. Apple and GNOME both ask for it
(GUIDELINE). Apple also asks for no launch screen and no branding at launch, which we
already satisfy by not having one.
*Where:* `t/lab.py`, write `GEOMETRY` on `WM_DELETE_WINDOW` as well as on refresh, store
the page name and corpus path beside it, and run the restored geometry through the same
work-area clamp `fit_to_screen` applies. The clamp is the bug fix; the rest is new.
*This is the cheapest high-value item in the brief.*

**D18. Detect at launch, and say at launch, when this machine cannot train.**
Microsoft policy 10.4.1: a product on an incompatible device "must detect that at launch
and display a message to the customer detailing the requirements" (GUIDELINE,
[research pass]). `home.py` already says in words which cards cannot work and
`check_my_computer.py` exists, so this is mostly wiring: the statement must name the
requirement (torch, a usable device, free RAM) at launch rather than at the moment a
button fails.

**D19. Settings stay few and stay in a separate window, and no sixth tab is ever added for them.**
All three agree on keeping settings few. Apple: "Aim to provide default settings that
give the best experience to the largest number of people... Minimize the number of
settings you offer." Microsoft: "Try to keep the total number of settings to a maximum
of four or five." GNOME: "If something can be done automatically, do it automatically."
(GUIDELINE, all [research pass].) They disagree structurally about where settings live:
Apple wants a separate window from the App menu at Command-comma with minimize and
maximize dimmed, GNOME wants a secondary window that closes with its parent, Microsoft
wants a full-window page pinned to the navigation pane.
We already have most of the compromise: `t/lab.py` `show_preferences` opens a
`Toplevel`, `transient` to the root, wired to `::tk::mac::ShowPreferences` on macOS and
to a `Settings...` menu item elsewhere (MEASURED HERE, `t/lab.py` lines 1214 to 1282,
`show_preferences` at 1269). That is
exactly right on macOS and GNOME and merely unidiomatic on Windows.
*What changes:* bind Ctrl-comma on Windows and Linux, let the window resize, and add
the two controls from D3 and D11 to the read-only rows already there. Total interactive
settings after this: two.

### The three platforms' own debts

**D20. Ask Windows for the dark title bar when the dark palette is live.**
Because C7. `DwmSetWindowAttribute` on the toplevel's HWND, through `ctypes`, which is
standard library and costs no dependency.
*Not verified here:* the attribute number differs between Windows 10 builds (one value
before a certain build, another after), and this brief did not fetch the exact numbers.
Read them off learn.microsoft.com at implementation time and try both, failing silently.

**D21. Fix the DPI comment now; change the awareness level only with a way to observe a change.**
The comment at `locallm/studio.py` line 2065 is false and can be corrected in one line.
The awareness level is not as simple as the research pass assumed. Declaring per-monitor
awareness tells Windows to stop bitmap-scaling the window, so if we then fail to notice
a DPI change the window is sharp and the wrong size, which is worse than blurry and the
right size. Tk 8.6 gives Python no `WM_DPICHANGED` event.
*So:* keep system awareness until a scale change can be observed, and the Tk-shaped way
to observe it is to re-read `winfo_fpixels("1i")` on `<Configure>` and re-run
`tk scaling` plus the D9 font rebuild when it moves. With that in place, raise awareness
to per-monitor v2. Without it, do not.
*This is the one decision in the brief that declines what a platform owner asks for, on
the grounds that half-doing it is worse than not doing it.*

**D22. On macOS, dim the ground and the accent when the window is not focused.**
Apple: "Make sure custom windows use the system-defined appearances. People rely on the
visual differences between windows to help them identify the foreground window... if you
use custom implementations, you need to do this work yourself"
(developer.apple.com/design/human-interface-guidelines/windows, GUIDELINE,
[research pass]). Our grounds are custom, so nothing will do it for us.
*Constraint:* `look.py`'s rule is eight roles and no ninth colour. The inactive ground
must therefore be computed from the active one, not added to the palette, and the result
must be re-checked against the same contrast test.
*Where:* `locallm/look.py` plus one `<FocusIn>`/`<FocusOut>` binding in `t/lab.py`.

### Meaning, colour and language

**D23. Never encode a state in colour alone. Already true; keep it true.**
Apple: "Consider how the colors you use might be perceived in other countries and
cultures. For example, red communicates danger in some cultures, but has positive
connotations in other cultures." Microsoft, with the only population statistic any of
the three guidelines cites: "About 8 percent of men and 0.5 percent of women are
red-green colorblind, so avoid using these color combinations as the sole
differentiator." GNOME lists colour-only distinction as an accessibility defect (all
GUIDELINE, [research pass]).
`look.py` already pairs every verdict with a mark and a sentence through `Say`, and the
marks were chosen by checking glyph coverage rather than by taste. This is the one place
where the current build is ahead of the evidence. Extend it to the Train tab's
running and stopped states.

**D24. State the script ceiling in `LIMITS.md`, and measure it before stating it.**
The community source says "Tk has no bidi facilities yet, so Unicodes even if from r2l
systems must come naively left-to-right if they are to appear correct on screen", with a
2011 note that on Linux Arabic renders left to right and disconnected, "Both of which
render the text unreadable", and a separate note that Devanagari conjuncts render wrong
(wiki.tcl-lang.org/page/bidi+rendering, OPINION, a community wiki, [read here]).
*Two things the research pass did not say, and they matter.* The Linux claim is dated
2011, a 2013 contributor on the same page claims a third-party renderer solved "80% of
the problem", and none of it has been re-verified against Tcl/Tk 9.0. And the same page
that reports the problem hands us the instrument: `font actual -displayof w <font> -- <char>`
returns "those of the specific font used to render that character, which will be
different from the base font if the base font does not contain the given character",
and `font metrics -linespace` returns the line height of whichever face wins
(tcl-lang.org/man/tcl8.6/TkCmd/font.htm, GUIDELINE, [read here]).
*So:* before publishing the limit, render one Arabic word, one Hebrew word and one
Devanagari conjunct in a Tk label on each of the three platforms and capture the result.
Then publish what was measured, on which Tk version, with the date. A repository that
measures everything else should not publish a 2011 wiki note as a fact about itself.
*We stop claiming*, in the meantime, that the application can be localised into any
language. The honest published claim is English now, and a named list of scripts that
were tested and worked.
*Not repeated here:* the research pass's "about 6% of the world's population for Arabic
script" carries no source, so this brief does not use the number.

**D25. Size every container from its content, allow two lines everywhere, and set no fixed widths on translatable strings.**
English source strings expand most when they are shortest: up to 10 characters, 200 to
300%; 11 to 20 characters, 180 to 200%, per IBM's guidelines as cited by
w3.org/International/articles/article-text-size (GUIDELINE, [research pass]), whose
measured example is Flickr's "views" at 5 characters becoming 2.6x in Portuguese and
French, 2.8x in German and 3x in Italian. Home's card labels are "Your text" (9
characters), "How big, how long" (17), "Train" (5) and "Try it" (6), all inside the
widest band (MEASURED HERE, `locallm/home.py` lines 15 to 18). Tk widget widths are set
in characters or pixels and do not reflow.
*The Tk instrument again:* `font measure` "measures the amount of space the string text
would use in the given font", returning pixels (tcl-lang.org/man/tcl8.6/TkCmd/font.htm,
[read here]), so a container can be sized from the actual string at run time rather than
from a guess, in the standard library. `locallm/studio.py` already does this for its
settings column width, which is the pattern to copy rather than invent.
*Add* at least 40% vertical slack for Thai and Devanagari line height, and prefer
measuring `-linespace` over assuming it.

### Distribution

**D26. Three icon assets from one metaphor, and none exists today.**
GNOME wants a 128x128 geometric drawing with no shadow outside the silhouette plus a
monochrome symbolic variant; Apple wants layered square artwork assembled in Icon
Composer; Flathub wants SVG or at least 256x256 square PNG with no baked-in shadows
because the website and native stores add their own (all GUIDELINE, [research pass];
Flathub [read here]). The repository contains no `.svg`, `.ico` or `.icns` and no
application `.png` outside `docs/img/` screenshots (MEASURED HERE).
*This is new work, not a change.*

**D27. Adopt Flathub's quality guidelines, and describe them accurately.**
One correction to the research pass, from reading the page: it opens with "The following
guidelines are not required for submission to Flathub, but are best practices we
recommend and consider for curation and promotion"
(docs.flathub.org/docs/for-app-authors/metainfo-guidelines/quality-guidelines,
GUIDELINE, [read here]). They are a curation bar, not a submission bar, and the reward
is visibility. We adopt them anyway.
Concretely: two brand colours are required, light and dark, both "colorful", explicitly
avoiding "white (or very light grays) and black (or very dark grays)", with the dark
one "a darker, more muted version of the light brand color". That rules out `#E8DCC8`
and `#1B1917`, the two UI grounds. The palette already contains a pair that fits
without inventing a ninth colour: light `#CBB795`, the quadrille hairline, and dark
`#6F4E0C`, the unsettled amber.
The summary must be 10 to 35 characters, not technical, and must not name the toolkit or
the language. "Train a small AI on your own text" is 33 characters (MEASURED HERE) and
says nothing about Python or Tk. The dependency claim stays in `README.md`, where it is
a promise, not a product description.
*Not verified here:* the research pass reports that all-lowercase names are on Flathub's
bad-examples list. The section fetched here covered name length and "just the name" and
did not show that rule, so whether "locallm" should be capitalised in the listing is
open.

---

## 3. What Tk cannot do, and what we say about it

| What the evidence asks for | Tk's answer | What we do |
| --- | --- | --- |
| Arabic, Hebrew, Persian, Urdu rendering | "Tk has no bidi facilities yet" (wiki.tcl-lang.org, OPINION, 2011 to 2014 notes) | Measure it on all three platforms with `font actual`, then publish the measured result in `LIMITS.md`. Stop implying the app is localisable into any language. A fix needs a third-party package and would break the two-dependency claim, so we do not take it |
| Mirroring layout for right-to-left locales | Not available | Out of reach; state it beside the above |
| Apple's "increase the RTL font size by about 2 points" | Meaningless while shaping is broken | Record as the reason the type system must eventually be per-locale, not only per-platform |
| Relative font units, per GNOME | No CSS, no relative units; positive size is points, negative is pixels (tcl-lang.org/man/tcl8.6/TkCmd/font.htm) | Approximate the intent: derive one ladder from `TkDefaultFont`'s actual size, which does follow a user's larger system font. Say publicly that this is an approximation, not compliance |
| A view switcher that moves to the bottom edge when the window narrows (GNOME) | Nothing in Tk does this | Not met. Keep five views and make them fit at 1024 wide instead |
| Native widget appearance on Windows (Microsoft) | ttk's native themes ignore configured colours, which is why `studio.py` forces `clam` | Not met by design. D6 makes it a choice |
| Per-monitor DPI response | No `WM_DPICHANGED` reaches Python in Tk 8.6 | Poll `winfo_fpixels` on `<Configure>`; raise the awareness level only once that works (D21) |
| Rounded corners, shadows, blur | No border-radius; `home.py` draws its own 12 px corners on a canvas | Already solved by drawing. No change |
| Telling us the ambient light level, which is what the polarity studies actually condition on | Not available on any platform through Tk | This is why the theme follows the system and offers an override, rather than trying to be clever |

## 4. The constraints that do not move

**PyTorch and Tk only** (`locallm/README.md`: "Dependencies: PyTorch and Tk. That's
it."). Every decision above is standard-library Tk plus `ctypes`, which ships with
Python. The only item that would need a dependency is Arabic shaping, and that is why
D24 publishes a limit instead of a fix.

**Nothing is uploaded.** No decision here fetches anything at run time: fonts are
resolved from installed families, the icon work is local files, and the theme probes are
local reads of a portal, gsettings, the registry or `defaults`. The research behind this
brief was network work; the product of it is not.

**The window opens and is useful with no torch.** `look.py` must stay importable in a
bare process, which its own docstring requires. That constrains D3, D9 and D11: the
palette, the type ladder and the two new settings live in `look.py` or in a small state
file read at startup, never behind `studio.py`, which imports torch at module scope.

**It runs from a USB stick.** This is the constraint the research missed entirely, and
it bites two decisions. D17's state restoration and D3's remembered theme both need
somewhere writable. On a read-only stick there is none. So: write to the state path
`t/paths.py` already resolves, fall back to keeping the preference in memory for the
session, and never let an unwritable path raise. A window that refuses to open because
it could not save where it was would fail the one scenario the project is proudest of.

**The licence is research and education only.** Microsoft's store policies (10.1.1,
10.4.1) therefore bind nothing we are obliged to do; we adopt 10.1.1 because clear first
runs are good and 10.4.1 because telling someone their machine cannot train is honest.
Apple's guideline 2.4.5 sandboxing and single-bundle rules apply only to the Mac App
Store, which a PyTorch-sized bundle makes unlikely; direct download needs notarization
and nothing else. Nothing in any listing may imply a warranty.

## 5. The diff against what exists today

Ordered by value per unit of work. "Size" is judged against the file as it stands.

| Where | What it does now | What the evidence says | Change | Size |
| --- | --- | --- | --- | --- |
| `locallm/look.py` `_DARK_WHEN_UNKNOWN` | `True`: opens dark when nothing can be read | Light is the published default on two of three platforms (GUIDELINE); dark is measurably worse for small text in a dim room (STUDY, n=34) | Set `False`; rewrite the comment; the header paragraph already says light | One line, plus honesty |
| `t/lab.py` geometry | Written only on self-refresh, restored without a clamp, page always `Home` | Restore state and position on relaunch (Apple, GNOME, GUIDELINE) | Save on close; save the page name and corpus path; run the restored geometry through the work-area clamp | Small |
| `t/lab.py` line 2861 | Fallback `minsize(1000, 700)` | 1024x600 "should be supported by all apps" (GUIDELINE) | `minsize(760, 560)`, matching `fit_to_screen`; then lay the five views out at 1024 wide and keep them there | Small, then a layout pass |
| `locallm/studio.py` line 2065 comment | Calls `SetProcessDpiAwareness(1)` and calls it "per-monitor aware" | `PROCESS_SYSTEM_DPI_AWARE = 1` "does not scale for DPI changes" (GUIDELINE) | Correct the comment. Raise the level only after a DPI change can be observed (D21) | One line now, medium later |
| `t/lab.py` window creation | No `DwmSetWindowAttribute` call anywhere | "Windows gives Win32 apps a light title bar by default" (GUIDELINE) | Ask for the dark title bar through `ctypes` when the dark palette is live | Small |
| `locallm/studio.py` lines 662, 666, 669, 680, 698, 701 | `SANS(8)` and `SANS(9)` for chart labels | 12 px regular is the floor, justified by non-Latin legibility (GUIDELINE) | Move to the Caption role from D9; nothing below 12 px equivalent | Small, but in a file two other runs hold |
| `locallm/look.py` `SANS`/`MONO` | Literal sizes at every call site | Five roles, per-platform values, no hard-coded sizes (GUIDELINE x2) | Derive the ladder from `font actual TkDefaultFont`; name five roles; replace literals | Medium, and it touches many call sites |
| `t/lab.py` `show_preferences` | A read-only note window, `transient`, on the macOS app menu and a `Settings...` item | Separate window is right on two platforms; keep settings to four or five (GUIDELINE x3) | Add Ctrl-comma, make it resizable, add the theme override (not on macOS) and the text-size control | Medium |
| `t/lab.py` line 946 | Tabs `Home, Train, Proof, Collect data, AI` | Nouns, similar lengths, and single words dissolve the casing conflict (GUIDELINE x2) | `Home, Training, Proof, Data, Autopilot`, plus the ten literals, the `--page` default and the screenshot names | Medium, mostly mechanical |
| `locallm/home.py` cards | Four numbered cards, permanent | Blessed for an empty first run (GNOME), not for every run (Apple) | Collapse each card to one line once a corpus and a model exist | Medium |
| `locallm/look.py` palette | Eight roles, two themes | Custom windows must show their own focus state on macOS (GUIDELINE) | Compute an inactive variant arithmetically; bind `<FocusIn>`/`<FocusOut>`; re-run the contrast test | Medium |
| Every label and button holding a translatable string | Fixed widths in places | Short strings expand 200 to 300% (GUIDELINE) | No fixed `width=`; size from `font measure`; two lines allowed everywhere; 40% vertical slack | Medium, spread thin |
| `LIMITS.md` | Says nothing about scripts | Tk's bidi state (OPINION, unverified since 2011) | Measure Arabic, Hebrew and Devanagari rendering on all three platforms, then publish what was measured with the Tk version and date | Small to measure, small to write |
| New files | No icon, no `.metainfo.xml` | Three icon styles are mutually exclusive; Flathub wants two brand colours and a non-technical summary (GUIDELINE) | Three icon assets from one metaphor; brand colours light `#CBB795` and dark `#6F4E0C`; summary "Train a small AI on your own text" (33 characters) | Large, and it is design work, not code |
| `locallm/look.py` comment | "muted itself is 5.08 light" | The current hex measures 5.68:1 (MEASURED HERE) | Restate or delete; the test already recomputes | Trivial |
| Copy everywhere | No claim yet | "Easier on the eyes" is not supported (STUDY x3) | Keep it out of `README.md`, `show_about` and any listing | Trivial, permanent |

## 6. Where the evidence is thin, and where it is absent

**The worldwide claim is the thinnest part of this brief.** Of the studies behind it,
one samples university students in Nepal (arxiv.org/abs/2409.10895, sample size not in
the abstract), one samples 30 Thai women aged 18 to 25 with 20/20 vision
(pmc.ncbi.nlm.nih.gov/articles/PMC12027292), and one claims 173 participants "from
diverse geographic regions worldwide" without publishing the distribution in the
abstract, which is all this brief could read
(api.semanticscholar.org, DOI 10.1080/00140139.2025.2483451, [read here]). Everything
else is German, American or British laboratory work, or a vendor writing about its own
platform. **We have evidence about eyes and almost none about the cultures the product
claims to serve.** Nobody should read section 2 as though the second gap were filled.

**Sample sizes carrying weight here:** Xie 2024 n=36; Gazit 2025 n=173; Dobres 2017
n=34 analysed; Sengsoon 2025 n=30; Aleman 2018 n=7 with a surrogate endpoint (choroid
thickness after one hour); Legge 1985 n=7 on CRT displays. The strongest pro-dark
long-term result in the literature rests on seven people and a proxy measure. It
justifies offering dark. It cannot carry a default.

**Stated preference and measured performance diverge, and we are acting on the
measured one.** Participants whose reading was measurably worse in dark mode "did not
report any difference in their perception of text readability"
(nngroup.com/articles/dark-mode, [read here]). That is the whole reason this brief does
not simply follow the 79.7% figure.

**One source in the input arrived truncated.** The Purdue battery finding was cut off
mid-sentence ("At t"), so this brief does not use it at all, beyond noting that an OLED
battery argument does not reach a desktop application on a backlit panel, which is
itself unverified here.

**Questions nobody in this pass could answer, and we should stop pretending otherwise:**

- Whether a permanent numbered-steps home screen helps or hurts first-time completion.
  Both GNOME and Apple have opinions; neither cites a study. D16 is a judgement call
  between two GUIDELINE-rank texts, and it is labelled as one.
- Whether a warm ground is preferred outside a laboratory. Xie 2024 measured fatigue
  against screen colour temperature, not an application's background colour, and the
  cream is far from its worst condition. D6 rests on measurement of luminance and on
  OPINION about warmth. Labelled.
- Whether "Data" or "Text" reads better to a stranger (D15). No evidence. It is a guess,
  and a cheap one to test with three people.
- Whether Tk 9.0 changed anything about Arabic on Linux. Nobody has looked. D24 says
  look before publishing.
- What people in the markets the project cares about want from a tool that trains a
  model on their own writing. Nothing was found. This is the research that has not been
  done, and it is worth more than anything in section 2.

## 7. What was fetched and read while writing this file

developer.gnome.org/hig/guidelines/ui-styling.html,
developer.gnome.org/hig/guidelines/adaptive.html,
learn.microsoft.com/en-us/windows/apps/desktop/modernize/apply-windows-themes,
learn.microsoft.com/en-us/windows/win32/api/shellscalingapi/ne-shellscalingapi-process_dpi_awareness,
nngroup.com/articles/dark-mode,
wiki.tcl-lang.org/page/bidi+rendering,
docs.flathub.org/docs/for-app-authors/metainfo-guidelines/quality-guidelines,
tcl-lang.org/man/tcl8.6/TkCmd/font.htm,
api.semanticscholar.org for DOI 10.1080/10447318.2024.2305982 and
DOI 10.1080/00140139.2025.2483451.

Everything marked [research pass] came from the six research passes and was not
re-fetched here. Everything marked MEASURED HERE was computed with the WCAG formulas or
read out of `t/lab.py`, `locallm/look.py`, `locallm/home.py` and `locallm/studio.py` at
the versions present on 2026-09-21. Two other runs were editing `locallm/` while this
was written, so line numbers are a pointer, not a promise.
