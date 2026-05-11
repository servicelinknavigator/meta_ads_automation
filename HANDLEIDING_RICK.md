# SLN Meta Ads Analyzer — Handleiding voor Rick

**Versie:** mei 2026  
**Gebouwd door:** Anna & Claude  
**Doel:** Analyseer Meta Ads data per klant, ontdek welke hooks en formats werken, en genereer directe shoot briefs voor de volgende videosessie.

---

## Inhoudsopgave

1. [Wat doet deze tool?](#1-wat-doet-deze-tool)
2. [Inloggen](#2-inloggen)
3. [Klanten aanmaken en beheren](#3-klanten-aanmaken-en-beheren)
4. [CSV exporteren uit Meta](#4-csv-exporteren-uit-meta)
5. [Ad naamgeving — de sleutel tot goede analyse](#5-ad-naamgeving--de-sleutel-tot-goede-analyse)
6. [Een analyse uitvoeren](#6-een-analyse-uitvoeren)
7. [Overzichtspagina — wat je ziet](#7-overzichtspagina--wat-je-ziet)
8. [Creative Intelligence — winners en losers](#8-creative-intelligence--winners-en-losers)
9. [Hook Intelligence & Shoot Brief](#9-hook-intelligence--shoot-brief)
10. [Meerdere uploads samenvoegen (merge)](#10-meerdere-uploads-samenvoegen-merge)
11. [Historische data en leereffect](#11-historische-data-en-leereffect)
12. [PDF rapport exporteren](#12-pdf-rapport-exporteren)
13. [Analyseren zonder klant (gastmodus)](#13-analyseren-zonder-klant-gastmodus)
14. [Klantprofiel — alles per klant op één plek](#14-klantprofiel--alles-per-klant-op-één-plek)
15. [Benchmarks instellen](#15-benchmarks-instellen)
16. [Klantcontext invullen voor betere scripts](#16-klantcontext-invullen-voor-betere-scripts)
17. [Onze klanten en hun instellingen](#17-onze-klanten-en-hun-instellingen)
18. [Veelgemaakte fouten](#18-veelgemaakte-fouten)
19. [Technische achtergrond (kort)](#19-technische-achtergrond-kort)

---

## 1. Wat doet deze tool?

De SLN Meta Ads Analyzer zet een ruwe Meta Ads CSV-export om in bruikbare inzichten. Concreet:

- **Metrics in één oogopslag** — totale spend, resultaten, CPL/ROAS, CTR, frequentie, week-over-week vergelijking
- **Brandende budgetten opsporen** — ads met spend maar 0 resultaten worden direct rood gemarkeerd
- **Ad fatigue signaleren** — frequentie > 3.5 = het ad is uitgespeeld, tijd voor iets nieuws
- **Winners en losers decoderen** — welke psychologische drivers zitten achter je beste ad? Wat gaat fout bij je slechtste?
- **Hook en format intelligentie** — welke openingszinnen en videoformaten leveren de laagste CPL op?
- **Shoot brief genereren** — een kant-en-klare opdracht voor de volgende video shoot, met spoken script, shots, locatie, CTA
- **Historisch leren** — elke upload wordt opgeslagen. Het systeem bouwt over tijd een beeld op van welke hooks structureel goed presteren voor elke klant
- **Meerdere periodes samenvoegen** — combineer exports van januari, februari en maart in één analyse zonder dubbele data

---

## 2. Inloggen

Ga naar de URL van de app (Render-domein). Je ziet een inlogscherm.

- **Gebruikersnaam en wachtwoord** zijn ingesteld via de omgevingsvariabelen op Render (`APP_USERS`)
- Na inloggen land je automatisch op de klantenpagina
- Je sessie blijft 4 uur actief. Daarna moet je opnieuw inloggen.

> **Wachtwoord vergeten?** Anna past de `APP_USERS` variabele aan op Render.

---

## 3. Klanten aanmaken en beheren

### Nieuwe klant aanmaken

1. Ga naar **Klanten** (klik op het SLN-logo bovenin)
2. Vul het formulier aan de rechterkant in:
   - **Naam** — bijv. `fit20 Gooise Meren` (verplicht)
   - **Sector** — bijv. `Fitness`, `Recruitment`, `Coaching`
   - **Campagnetype** — kies `Leads`, `Purchases / E-com` of `Awareness`
   - **CPL benchmark** — jouw gewenste kosten per lead in euro, bijv. `45`
   - **ROAS benchmark** — voor e-com klanten, bijv. `3.5`
   - **Notities** — interne opmerkingen, bijzonderheden
   - **Klant context** — uitgebreide beschrijving van de doelgroep (zie sectie 16)
3. Klik **Klant aanmaken**

### Klant bewerken

1. Klik op een klantkaart om naar het profiel te gaan
2. Klik de **Bewerk**-knop (potlood icoon) rechts bovenin
3. Pas aan wat nodig is en sla op

### Klant verwijderen

Onderaan het klantprofiel staat een **Verwijder**-knop. Let op: dit verwijdert ook alle uploads, briefs en historische data van die klant.

---

## 4. CSV exporteren uit Meta

De tool werkt met de standaard Meta Ads Manager export. Zo exporteer je correct:

### Stap-voor-stap

1. Open **Meta Ads Manager**
2. Ga naar het tabblad **Advertenties** (niet Campagnes of Advertentiesets)
3. Selecteer de gewenste datumrange bovenin
4. Klik op **Exporteren** (rechts) → **Exporteer tabelgegevens**
5. Kies formaat **CSV**
6. Klik **Exporteren**

### Verplichte kolommen

De tool werkt automatisch met zowel Engelse als Nederlandse kolomnamen uit Meta. De volgende kolommen moeten aanwezig zijn:

| Wat | Engels | Nederlands |
|-----|--------|------------|
| Campagnenaam | Campaign name | Naam campagne |
| Advertentienaam | Ad name | Naam advertentie |
| Vertoningen | Impressions | Vertoningen |
| Besteed bedrag | Amount spent (EUR) | Besteed bedrag (EUR) |
| Resultaten | Results | Resultaten |
| Dag | Day | Dag |

### Aanbevolen extra kolommen (voor betere analyse)

- Klikken, CTR, CPC, CPM — voor click-data analyse
- Frequentie — voor ad fatigue detectie
- Bereik — voor unieke gebruikersaantallen
- Kosten per resultaat — voor CPL direct uit Meta
- Aankoop-ROAS — voor e-com klanten
- Resultaatindicator — voor automatische detectie campagnetype

> **Tip:** Sla je exportinstelling op in Meta als "SLN Export" zodat je elke keer dezelfde kolommen krijgt.

### Bestandsformaat

- Alleen `.csv` bestanden
- Maximale bestandsgrootte: 50 MB
- Maximaal 10.000 rijen per upload
- UTF-8 of UTF-8 BOM encoding (Meta exporteert altijd correct)

---

## 5. Ad naamgeving — de sleutel tot goede analyse

Dit is **het belangrijkste onderdeel van de workflow**. De tool detecteert hooks en formats puur op basis van de ad naam. Hoe beter de naamgeving, hoe beter de analyse.

### De naamgevingsconventie

```
Format - Hook - V# - Beschrijving
```

**Voorbeelden:**

| Ad naam | Format | Hook | Versie |
|---------|--------|------|--------|
| `UGC - Proof - V1 - Lid testimonial` | ugc | proof | 1 |
| `Talking Head - Recognition - V2 - Drukke mama` | talking_head | recognition | 2 |
| `Static - Promise - V1 - 20 min resultaat` | static | promise | 1 |
| `Reels - Frustration - V3 - Nooit volgehouden` | reels | frustration | 3 |

### Beschikbare hook types

| Hook | Uitleg | Voorbeeldopeningszin |
|------|--------|----------------------|
| `recognition` | Kijker herkent zichzelf | "Herken je dat gevoel dat je iets wil veranderen..." |
| `frustration` | Benoem een concrete pijn | "Je hebt het al zo vaak geprobeerd..." |
| `curiosity` | Verrassend feit of vraag | "Wist je dat je maar 20 minuten nodig hebt..." |
| `proof` | Klantresultaat of testimonial | "Dit zeggen onze leden na een paar maanden..." |
| `promise` | Concreet resultaat in X tijd | "Stel je voor: in 20 minuten per week fitter..." |
| `confrontation` | Directe aanspraak | "Stop met wachten op het perfecte moment..." |
| `urgency` | Beperkte beschikbaarheid | "Er zijn nog maar X plekken beschikbaar..." |
| `problem_solve` | Probleem tonen, dan oplossing | "Dit is het probleem. En zo lossen we het op." |
| `social_proof` | Cijfers en autoriteit | "Honderden mensen gingen je al voor..." |
| `educational` | Waardevolle kennis | "Ik leg je in 30 seconden uit waarom..." |

### Beschikbare format types

| Format | Uitleg |
|--------|--------|
| `talking_head` | Presentator spreekt direct in camera |
| `testimonial` | Klant/lid aan het woord |
| `ugc` | User-generated content stijl, handheld, authentiek |
| `reels` | Short-form verticaal, max 60 seconden |
| `static` | Stilstaand beeld met tekst |
| `carousel` | Meerdere slides of frames |
| `before_after` | Transformatie vergelijking |
| `product_demo` | Product of dienst in gebruik getoond |
| `story` | Begin-midden-eind narratief |
| `animation` | Motion graphics of illustratie |
| `problem_solve` | Probleem visueel tonen, dan oplossing |

### Wat als ads nog niet zo benoemd zijn?

Geen probleem. De tool probeert keywords te herkennen in de naam:
- "Herken" of "Ken jij" → recognition
- "Wist je dat" → curiosity
- "Carousel" in naam → carousel format
- "Static" of "Statisch" → static format
- "?" in naam → curiosity

Ads die niet herkend worden, verschijnen in een **Tagger**-blok onderaan de overzichtspagina. Daar kun je handmatig hook en format invullen. Dit wordt onthouden voor alle toekomstige analyses van die klant.

> **Beste aanpak:** Pas de naamgeving in Meta aan voordat je gaat opschalen. Zo bouw je automatisch historische data op.

---

## 6. Een analyse uitvoeren

### Nieuwe upload

1. Ga naar het **klantprofiel** (klik op de klant in het overzicht)
2. Klik **Nieuwe upload** of gebruik het uploadformulier
3. Selecteer je CSV-bestand
4. Optioneel: kies het **campagnetype** als de automatische detectie fout gaat
5. Klik **Analyseren**

Je land automatisch op de **overzichtspagina** met de resultaten.

### Navigeren na analyse

Bovenaan elke analysepagina zie je een donkere contextbalk met:
- De naam van de actieve klant
- De dataperiode (bijv. "1 apr – 30 apr 2025")
- Drie tabbladen: **Overzicht / Creatief / Hooks & Brief**

Klik op een tabblad om te wisselen. Je data blijft actief zolang de sessie loopt (4 uur).

---

## 7. Overzichtspagina — wat je ziet

### KPI-blokken

Bovenaan staan de totalen voor de geanalyseerde periode:

| Metric | Uitleg |
|--------|--------|
| **Totale spend** | Totaal besteed bedrag in euro |
| **Resultaten** | Leads, aankopen of thrupays (afhankelijk van campagnetype) |
| **CPL / ROAS** | Kosten per lead, of return on ad spend |
| **CTR** | Click-through rate (klikken / vertoningen) |
| **Frequentie** | Gemiddeld hoe vaak iemand een ad heeft gezien |
| **CPM** | Kosten per 1.000 vertoningen |

### Week-over-week vergelijking

De dataperiode wordt automatisch in twee helften gesplitst. Je ziet een pijltje omhoog (groen) of omlaag (rood) met het percentage verandering voor spend, resultaten, CPL en CTR.

> Zo zie je direct of je ads de tweede helft van de periode beter of slechter presteerden.

### Urgente acties (rode kaarten)

Als de tool deze situaties detecteert, verschijnt er een **rode waarschuwingskaart**:

- **Brandend budget** — een ad heeft meer dan €50 uitgegeven maar 0 resultaten behaald. Stop dit ad direct.
- **Ad fatigue** — een ad heeft een frequentie > 3.5. De doelgroep is het ad zat. Vervangen of roteren.

### De grafiek

De top-10 ads op spend worden getoond in een staafgrafiek. Je kunt de grafiek bekijken op:
- **CPL** (leads campagne) of **ROAS** (e-com)
- **Spend**
- **CTR**
- **Resultaten**

Klik op de legenda om metrics aan/uit te zetten.

### AI-inzichten

Onderaan staat een AI-gegenereerd tekstblok met:
- Sterke punten van de account
- Punten om te verbeteren
- Concrete aanbevelingen

Dit wordt gegenereerd op basis van de data, niet willekeurig.

### Onbekende ads taggen

Als er ads zijn zonder herkenbare hook of format in de naam, zie je een **Ads taggen**-blok. Geef elk ad handmatig een hook en format. Dit wordt opgeslagen en geldt voor alle toekomstige analyses van deze klant.

### Datumfilter en heranalyse

Rechts is een paneel waarmee je:
- Een specifieke datumrange kunt analyseren (bijv. alleen de laatste 2 weken)
- Het campagnetype handmatig kunt overriden
- Drempelwaarden voor winner/mid/loser kunt aanpassen

---

## 8. Creative Intelligence — winners en losers

Klik op het tabblad **Creatief** in de contextbalk.

### Winners

De top winnende ads worden getoond met:

- **Psychologische driver** — welke emotionele knop drukt dit ad? (angst, verlangen, sociale bewijskracht, etc.)
- **Hook type** — welke opening gebruikt het ad?
- **Format** — video, static, carousel, etc.
- **Waarom het werkt** — een beschrijving van de structuur
- **Test suggesties** — welke variaties kun je testen om dit ad te schalen?

### Losers

De slechtste ads (0 resultaten, hoge spend) worden geanalyseerd op:
- Waarom het waarschijnlijk niet werkt
- Wat je anders zou kunnen doen

### Patronen

Onderaan staat een patroonblok dat laat zien:
- Welke hook type domineert bij de winners
- Welk format het beste presteert
- Welke formats nog niet getest zijn (kansen!)

---

## 9. Hook Intelligence & Shoot Brief

Klik op het tabblad **Hooks & Brief** in de contextbalk.

### Hook performance tabel

Een tabel met alle hook types gesorteerd op CPL (laagste = beste):

| Kolom | Uitleg |
|-------|--------|
| Hook type | De categorie van de opening |
| Ads | Hoeveel ads vallen in deze hook |
| Spend | Totaal besteed op deze hook |
| Resultaten | Totale leads of aankopen |
| CPL | Kosten per resultaat voor deze hook |
| CTR | Gemiddelde click-through rate |

### Format performance tabel

Dezelfde tabel maar dan voor formats.

### Winning combinaties

De top-3 combinaties van hook + format met de laagste CPL. Dit zijn de bewezen formules voor deze klant.

### Nog niet geteste hooks/formats

Welke hooks of formats zijn nog nooit gebruikt bij deze klant? Dit zijn directe groeikansen.

### Shoot brief

Onderaan staat de **shoot brief** — een kant-en-klare opdracht voor de volgende shoot. De brief bestaat altijd uit precies 3 shoots:

| Type | Doel |
|------|------|
| **Safe** | Bewezen hook + bewezen format. Iteratie op de beste ad. Laag risico, hoge kans op resultaat. |
| **New hook** | Ongeteste hook-type, zelfde format als safe. Risico middelmatig. Kan doorbreken. |
| **Format test** | Beste hook, nieuw format. Test of hetzelfde verhaal beter werkt in een ander format. |

Elke shoot bevat:
- **Concept** — wat het ad laat zien en waarom het zou werken
- **Openingszin** — de exacte eerste zin die de presentator uitspreekt
- **Aspect ratio en duur** — 9:16 voor Reels/Stories, 30–45 seconden
- **Talent** — wie staat er voor de camera?
- **Locatie** — waar wordt er gefilmd?
- **5 shots** — een concreet shot-by-shot plan
- **Key message** — de kern van de boodschap
- **CTA** — de call-to-action tekst
- **Hypothese** — wat je wilt bewijzen met deze shoot
- **Volledig script** — 4 getimede blokken (0-5s, 5-18s, 18-25s, 25-30s) met de exacte spreektekst

Klik op **Script bekijken** om het volledige script uit te klappen.

> **Belangrijk:** De scripts zijn geschreven vanuit het perspectief van de **klant**, niet van SLN. fit20 adverteert aan potentiële leden, niet aan ondernemers die advertentiediensten zoeken.

### Shoot brief opslaan

De brief wordt automatisch opgeslagen bij de klant zodra je de Hooks-pagina bezoekt na een nieuwe upload. Eerdere briefs zijn terug te vinden in het klantprofiel.

---

## 10. Meerdere uploads samenvoegen (merge)

Handig wanneer je data van meerdere maanden wilt combineren in één analyse.

### Hoe werkt het?

1. Ga naar het **klantprofiel**
2. Vink **minimaal 2 uploads** aan (vinkjes links naast elke upload in de tabel)
3. Er verschijnt een groene balk onderaan: **"X uploads geselecteerd — Samenvoegen"**
4. Klik **Samenvoegen & analyseren**

### Deduplicatie

De merge-functie is slim: als dezelfde ad op dezelfde dag in meerdere uploads voorkomt, wordt hij maar één keer meegeteld. Deduplicatie werkt op de combinatie van ad ID + campagne ID + datum.

### Wat wordt er opgeslagen?

Een merged analyse wordt **niet** als nieuw upload opgeslagen in de database. Het is een tijdelijke gecombineerde weergave. De originele uploads blijven intact.

---

## 11. Historische data en leereffect

### Wat onthoudt het systeem?

Per klant wordt het volgende opgeslagen:

| Data | Waar te zien |
|------|--------------|
| Elke CSV upload (inclusief ruwe data) | Klantprofiel → uploadtabel |
| Metrics per upload (spend, CPL, ROAS, CTR, etc.) | Klantprofiel → uploadtabel |
| Hook performance per upload | Klantprofiel → hook trend sectie |
| Format performance per upload | Klantprofiel → hook trend sectie |
| AI-inzichten per analyse | Opgeslagen intern |
| Shoot briefs | Klantprofiel → shoot brief geschiedenis |
| Ad naamtags (hook/format overrides) | Automatisch toegepast op elke analyse |

### Dubbeltelling voorkomen

Het systeem gebruikt een slim algoritme om dubbeltelling te voorkomen wanneer uploads overlappende datumperiodes hebben. De meest recente upload is leidend voor overlappende data; oudere uploads vullen alleen periodes aan die nog niet gedekt zijn.

### Historische analyse herladen

Wil je een eerdere upload opnieuw bekijken?

1. Ga naar het klantprofiel
2. Klik **Laad** naast de gewenste upload in de tabel
3. Of klik **Laatste analyse** voor de meest recente upload

De volledige analyse wordt opnieuw uitgevoerd op de opgeslagen CSV-data.

---

## 12. PDF rapport exporteren

Na een analyse klik je op de **PDF**-knop in de navigatiebalk (rechts bovenin op de Overzicht-pagina).

Het PDF bevat:
- Alle KPI's en totalen
- Week-over-week vergelijking
- Top 10 advertenties
- AI-inzichten als tekst

Het bestand heet `meta_ads_rapport.pdf` en wordt direct gedownload.

---

## 13. Analyseren zonder klant (gastmodus)

Op de klantenpagina staat rechtsboven de knop **"Analyseer zonder klant"**.

In gastmodus kun je:
- Een CSV uploaden en analyseren
- Alle drie de analysepagina's gebruiken
- Een shoot brief genereren

Maar er wordt niets opgeslagen in de database. Gebruik dit voor eenmalige analyses of als je snel iets wilt checken zonder het aan een klant te koppelen.

---

## 14. Klantprofiel — alles per klant op één plek

Het klantprofiel is de hub voor alles rond een klant. Je ziet er:

### Bovenaan
- Naam, sector, campagnetype
- CPL en ROAS benchmarks
- Notities
- **Bewerk**-knop en **Verwijder**-knop

### Upload geschiedenis
Een tabel met alle uploads, gesorteerd op datum (nieuwste bovenaan):

| Kolom | Uitleg |
|-------|--------|
| Datum | Wanneer de upload is gemaakt |
| Bestand | Originele bestandsnaam |
| Periode | Datumrange van de data |
| Spend | Totale spend in die upload |
| Resultaten | Aantal leads/aankopen |
| CPL / ROAS | Gemiddeld voor die periode |
| Acties | Laad opnieuw of verwijder |

### Nieuwe upload
Direct beschikbaar als er nog geen uploads zijn, of klik op de blauwe **+**-knop.

### Shoot brief geschiedenis
De laatste 10 shoot briefs zijn hier terug te vinden, inclusief de periode waarop ze gebaseerd zijn.

### Hook performance over tijd
Een samenvattende tabel die laat zien welke hooks cumulatief het beste presteren voor deze klant, op basis van alle niet-overlappende uploads.

---

## 15. Benchmarks instellen

Benchmarks sturen het **drempelwaarden-systeem** aan. De tool categoriseert ads in:
- **Winner** — CPL onder de benchmark
- **Mid** — CPL tussen benchmark en 1.5× benchmark
- **Loser** — CPL boven 1.5× benchmark

### Automatische drempelwaarden (aanbevolen)

Als je een **CPL benchmark** instelt bij de klant, pakt het systeem die automatisch op:

- Win = benchmark-waarde
- Mid = benchmark × 1.5

Bij fit20 met CPL benchmark €45:
- Winner = CPL < €45
- Mid = €45–€67
- Loser = CPL > €67

### Handmatige drempelwaarden

Op de overzichtspagina kun je ook handmatig drempelwaarden instellen via het paneel rechts. Of kies een preset:
- **fit20** — Winner €40, Mid €60
- **Belladonna** — Winner €30, Mid €50
- **Custom** — zelf invullen

---

## 16. Klantcontext invullen voor betere scripts

De **klantcontext** is een veld in het klantprofiel (via Bewerk) dat de AI gebruikt om shoot scripts te schrijven die écht passen bij de klant.

### Wat moet er in?

Vul in dit veld een beschrijving van:
- Wat de klant doet en voor wie
- De doelgroep — wie zijn ze, wat is hun probleem, wat houden ze tegen?
- Tone of voice — hoe praat de klant met klanten? (warm, professioneel, direct?)
- Unieke propositie — wat maakt dit bedrijf anders?
- Typische CTA — wat wil je dat mensen doen? (proefles plannen, aanvragen, bestellen)

### Voorbeeld (fit20)

```
fit20 biedt EMS-personal training in 20 minuten per week. Doelgroep: 
45-65 jaar, drukke professionals en mensen met lichamelijke klachten of 
een hekel aan de sportschool. Tone of voice: warm, persoonlijk, 
laagdrempelig — geen hype, geen grote beloftes, gewoon eerlijk. 
Uniek: wetenschappelijk bewezen methode, kleine studio, altijd 
persoonlijke begeleiding. CTA: "Plan een gratis proefles via de link."
```

Hoe meer je hier invult, hoe relevanter de shoot briefs en scripts worden.

---

## 17. Onze klanten en hun instellingen

| Klant | Sector | Type | CPL benchmark | ROAS benchmark |
|-------|--------|------|---------------|----------------|
| fit20 Gooise Meren | Fitness | Leads | €45 | — |
| fit20 Rijen | Fitness | Leads | €45 | — |
| fit20 Medemblik | Fitness | Leads | €45 | — |
| fit20 Roermond | Fitness | Leads | €45 | — |
| fit20 Venlo | Fitness | Leads | €45 | — |
| Absolute Fit | Fitness | Leads | nader bepalen | — |
| New Health | Gezondheid | Leads | nader bepalen | — |
| Belladonna | Schoonheid | Leads | €30 | — |

> **Let op:** Voor alle fit20-klanten is de klantcontext hetzelfde (EMS, 20 min/week, 45-65 jaar). Vul dit in bij elke vestiging. De scripten worden dan automatisch geschreven vanuit het perspectief van die specifieke vestiging.

---

## 18. Veelgemaakte fouten

### "Geen data gevonden voor de geselecteerde periode"
Je hebt een datumfilter ingesteld dat buiten de CSV-periode valt. Verwijder het filter of upload een CSV met de juiste periode.

### "CSV bevat meer dan 10.000 rijen"
Exporteer een kortere periode uit Meta, of split het in meerdere exports en gebruik de merge-functie.

### Hook analyse toont alleen "unknown"
De ad namen volgen de naamgevingsconventie niet. Gebruik de **Tagger** op de overzichtspagina om ze handmatig te labelen, of pas de namen aan in Meta.

### Shoot brief script spreekt over "onze advertenties" of "leads genereren"
Dit mag niet meer voorkomen. Als je dit ziet, controleer of de **klantcontext** ingevuld is bij die klant, en meld het aan Anna — dan wordt de prompt aangepast.

### "Sessie verlopen — upload je CSV opnieuw"
De app bewaart de geüploade CSV 4 uur in de sessie. Herlaad de historische upload via het klantprofiel of upload opnieuw.

### Ik zie geen "Samenvoegen"-balk bij meerdere uploads
Je moet **minimaal 2 vinkjes** aanvinken in de uploadtabel. De balk verschijnt pas zodra je 2 of meer aanvinkt.

### De merge-functie zegt "Upload X heeft geen opgeslagen CSV"
Oudere uploads die zijn gemaakt voordat de CSV-opslag werd ingebouwd, kunnen niet worden samengevoegd. Upload die bestanden opnieuw via "Nieuwe upload" in het klantprofiel.

---

## 19. Technische achtergrond (kort)

### Architectuur

```
Meta Ads Manager
      ↓ (CSV export)
SLN Analyzer (Flask, Render)
      ↓
CSV Parser → Analysis Engine → Hooks Analyzer
      ↓                             ↓
  Supabase DB              Shoot Brief Generator
  (PostgreSQL)                  ↓
      ↓                    Claude API (Anthropic)
  Klantprofiel                  ↓
  Upload historie          Shoot scripts + briefs
  Hook snapshots
  Shoot briefs
```

### Wat wordt opgeslagen in de database?

- Klantgegevens (naam, benchmarks, context)
- Elke upload inclusief de ruwe CSV-tekst
- Hook en format performance per upload (als snapshot)
- Ad naamtags (hook/format overrides per klant)
- Shoot briefs (als JSON)
- AI-inzichten (als tekst)

### AI (Anthropic Claude)

Als er een `ANTHROPIC_API_KEY` is ingesteld op Render, worden de shoot briefs gegenereerd met Claude. Zonder API key valt het systeem terug op ingebouwde fallback scripts. De fallback scripts zijn volledig functioneel — ze werken op basis van de fit20 ICP en zijn geschreven per hook type.

### Sessie vs. database

- De **sessie** (4 uur) bevat de actieve analyse: CSV-data, berekende metrics, drempelwaarden
- De **database** (permanent) bevat alle historische uploads, tags, briefs en klantdata
- Als je na 4 uur terugkomt, herlaad dan een historische upload via het klantprofiel

### Drempelwaarden systeem

Winners en losers worden bepaald op basis van CPL-drempelwaarden. Als de CPL benchmark van de klant is ingesteld, worden de drempelwaarden automatisch berekend:

```
Winner < benchmark
Mid    = benchmark × 1.0 tot 1.5
Loser  > benchmark × 1.5
```

---

## Snelreferentie — Dagelijkse workflow

```
1. Open de app → log in
2. Klik op de klant
3. Upload de nieuwste Meta export
4. Check de rode waarschuwingen (brand / fatigue)
5. Bekijk de week-over-week trend
6. Ga naar Creatief → bekijk winners en patronen
7. Ga naar Hooks & Brief → check welke hooks het beste werken
8. Scroll naar de shoot brief → kopieer naar het shoot-briefdocument
9. Tag onbekende ads via de Tagger (als aanwezig)
10. Klaar — de data is opgeslagen en telt mee voor de trend
```

---

*Vragen of iets werkt niet? Stuur een berichtje naar Anna.*
