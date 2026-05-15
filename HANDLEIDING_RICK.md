# SLN Meta Ads Analyzer — Volledige Handleiding voor Rick

> **Versie:** Mei 2026  
> **Voor:** Rick — volledig overzicht van alle functies, AI-logica en redenering achter elke analyse

---

## Inhoudsopgave

1. [Wat doet het systeem?](#1-wat-doet-het-systeem)
2. [Inloggen & navigatie](#2-inloggen--navigatie)
3. [Klantbeheer](#3-klantbeheer)
4. [CSV uploaden & analyseren](#4-csv-uploaden--analyseren)
5. [Analyse-dashboard](#5-analyse-dashboard)
6. [Creative-analyse & winners/losers](#6-creative-analyse--winnerslosers)
7. [Hook-analyse](#7-hook-analyse)
8. [Static image analyse](#8-static-image-analyse)
9. [Shoot brief generator](#9-shoot-brief-generator)
10. [Script generator](#10-script-generator)
11. [Testkit & smart generator](#11-testkit--smart-generator)
12. [Axes mapper](#12-axes-mapper)
13. [Excel templates: video's & statics](#13-excel-templates-videos--statics)
14. [Creatieve content per advertentie](#14-creatieve-content-per-advertentie)
15. [PDF-export](#15-pdf-export)
16. [Historische data & meerdere CSV's samenvoegen](#16-historische-data--meerdere-csvs-samenvoegen)
17. [Ad-tagging (handmatig hook toewijzen)](#17-ad-tagging-handmatig-hook-toewijzen)
18. [Hoe AI beslissingen neemt — de volledige redenering](#18-hoe-ai-beslissingen-neemt--de-volledige-redenering)
19. [Fallback: wat gebeurt er zonder AI?](#19-fallback-wat-gebeurt-er-zonder-ai)
20. [Naamgevingsconventie advertenties](#20-naamgevingsconventie-advertenties)
21. [Veelgestelde vragen & tips](#21-veelgestelde-vragen--tips)

---

## 1. Wat doet het systeem?

De SLN Meta Ads Analyzer is een intern webplatform dat Meta Ads Manager exports (CSV) omzet in bruikbare creatieve aanbevelingen. Het systeem:

- **Analyseert prestaties** van alle campagnes, ad sets en advertenties
- **Herkent hooks en formats** uit advertentienamen
- **Identificeert winners en losers** op basis van CPL of ROAS
- **Genereert shoots, scripts en copy** op basis van wat al werkt
- **Leert van klanthistorie** — hoe meer uploads, hoe slimmer de suggesties
- **Werkt cross-client** — patronen van andere klanten in dezelfde branche worden meegenomen

Het systeem gebruikt Claude (Anthropic) als AI-engine. Als er geen internetverbinding of API-sleutel is, valt het terug op ingebouwde rekenregels — de functies blijven dan gewoon werkend, maar de output is minder genuanceerd.

---

## 2. Inloggen & navigatie

**Inloggen:** Ga naar de URL van de app en log in met de gebruikersnaam en het wachtwoord die in de omgevingsvariabelen staan ingesteld. De sessie blijft 4 uur actief, daarna moet je opnieuw inloggen.

**Hoofdnavigatie:**
- **Klanten** — overzicht van alle klantprofielen
- **Nieuw klantprofiel** — klant aanmaken
- **Per klantpagina** — alle acties voor die klant (uploaden, analyseren, scripts, briefs, etc.)

---

## 3. Klantbeheer

### Klant aanmaken / bewerken

Elk klantprofiel bevat:

| Veld | Wat het doet |
|------|-------------|
| **Naam** | Naam van de klant, zichtbaar in alle analyses |
| **Branche** | Wordt gebruikt voor cross-client vergelijking (bijv. "fitness", "coaching") |
| **Campagnetype** | `leads` of `purchases` — bepaalt of CPL of ROAS de hoofdmaatstaf is |
| **CPL-benchmark** | Drempelwaarde voor leads. Onder deze waarde = winnaar |
| **ROAS-benchmark** | Drempelwaarde voor aankopen. Boven deze waarde = winnaar |
| **Klantcontext / ICP** | Vrije tekst over de klant: doelgroep, aanbod, toon. Dit wordt meegestuurd naar de AI |

**Tip:** Hoe meer context je invult in het "klantcontext"-veld, hoe relevanter de scripts en copy-suggesties worden. Beschrijf het aanbod, de doelgroep, de pijnpunten en de tone of voice. De AI gebruikt dit letterlijk bij het schrijven van scripts en copy.

---

## 4. CSV uploaden & analyseren

### Wat voor CSV?

Een export uit Meta Ads Manager. Zowel **Engelse** als **Nederlandse** kolomnamen worden herkend. Het systeem heeft mappings voor meer dan 50 kolomvarianten — het maakt niet uit hoe Meta de kolommen ook noemt.

**Minimale vereiste kolommen:**
- Advertentienaam (of campagne / ad set naam)
- Besteed bedrag
- Resultaten (leads, aankopen, of weergaven)
- Impressies

**Optioneel maar nuttig:**
- Klikken, CTR, CPC, CPM, frequentie, leveringsstatus, CPL, ROAS

### Uploadproces

1. Ga naar het klantprofiel → **"Upload CSV"**
2. Kies een bestand
3. Kies de drempelwaarde:

| Optie | Wat het betekent |
|-------|-----------------|
| **Auto** | Gebruikt de CPL-benchmark uit het klantprofiel |
| **Fit20** | Vaste drempelwaarde specifiek voor Fit20-klanten |
| **Belladonna** | Vaste drempelwaarde specifiek voor Belladonna-klanten |
| **Custom** | Zelf een getal invoeren |

4. Optioneel: filter op datumbereik (begin- en einddatum invullen)
5. Klik op **"Analyseren"**

### Wat gebeurt er na de upload — stap voor stap?

**Stap 1 — Normaliseren**
Alle komma's, procenttekens en valutasymbolen worden verwijderd uit de getallen. "€1.234,56" wordt "1234.56". Dit is nodig omdat Meta soms komma's gebruikt als duizendtalscheider.

**Stap 2 — Verwijder aggregate rijen**
Rijen die optelsommen zijn (bijv. een "Totaal"-rij die Meta onderaan exporteert) worden gedetecteerd en verwijderd. Als je ze erin laat, klopt het budget dubbel.

**Stap 3 — Filter €0 spend**
Advertenties die helemaal geen budget hebben gekregen worden volledig buiten de analyse gelaten. Ze zijn inactief en vervuilen de gemiddelden.

**Stap 4 — Multi-conversie deduplicatie**
Meta exporteert soms dezelfde advertentie meerdere keren op dezelfde dag — één rij per conversie-event. Voorbeeld: "Lead via formulier" staat als aparte rij van "Lead via bericht", maar het zijn dezelfde advertentie op dezelfde dag. Het systeem herkent dit (zelfde advertentienaam + zelfde datum) en voegt ze samen: de resultaten worden opgeteld, het budget wordt maar één keer meegeteld. Zonder deze stap zouden budgetten verdubbeld worden meegeteld.

**Stap 5 — Hiërarchie opbouwen**
Advertenties worden gegroepeerd per ad set, en ad sets per campagne. Metrics worden op elk niveau geaggregeerd zodat je ook campagne- en ad set-niveau kunt analyseren.

**Stap 6 — Campagnetype detecteren**
Het systeem kijkt naar de naam van de resultaatkolom om te bepalen wat voor campagne het is:

| Resultaatkolom bevat | Campagnetype |
|----------------------|-------------|
| "lead", "message", "contact", "form", "custom" | leads |
| "purchase", "sale" | purchases |
| "thruplay", "view" | awareness |

Als er meerdere types voorkomen (bijv. een export met zowel lead- als aankoopscampagnes), wint leads boven aankopen boven awareness.

**Stap 7 — Opslaan in database**
De volledige CSV-inhoud + geaggregeerde metrics worden opgeslagen. Je kunt later altijd terugkeren naar deze upload zonder het bestand opnieuw te hoeven uploaden.

---

## 5. Analyse-dashboard

Na het uploaden land je op het analyse-dashboard. Dit bevat:

### KPI-overzicht (bovenste rij)

- **Budget:** totaal besteed in de geselecteerde periode
- **CPL of ROAS:** gemiddelde over alle advertenties (gewogen naar spend)
- **CTR:** gemiddelde doorklikratio
- **Resultaten:** totaal aantal leads of aankopen

**Tweede rij:** Impressies, CPM, CPC, Frequentie

### Campagnetabel

Elke campagne met: naam, budget, CPL/ROAS, CTR, resultaten, frequentie.

### Top advertenties (grafiek)

De 10 advertenties met het hoogste budget worden getoond met hun metrics. Dit is de basis voor verdere analyse.

### Urgente acties

Het systeem markeert automatisch twee situaties zonder AI:

**Burning (stop direct):**
- De advertentie heeft €50+ uitgegeven
- Er zijn 0 resultaten
- De advertentie heeft een actieve leveringsstatus

**Fatigue (ververs creative):**
- Frequentie is hoger dan 3.5
- De advertentie heeft een actieve leveringsstatus
- Er zijn wél resultaten (de advertentie werkt, maar raakt versleten)

> **Waarom €50 als grens voor "burning"?** Dat is genoeg budget om statistisch een eerste resultaat te verwachten bij een normale campagne. Onder €30 is er te weinig data voor een conclusie — die advertenties krijgen het label "Te weinig data" maar worden niet geflagd als urgent.

> **Waarom 3.5 als frequetiegrens?** Boven 3.5 ziet de gemiddelde Meta-gebruiker dezelfde advertentie meer dan 3 keer. Dat leidt structureel tot dalende CTR en stijgende CPL. Beneden die grens is de kans op fatigue klein genoeg om te negeren.

### AI-inzichten

Onder de grafieken verschijnt een tekstblok met AI-gegenereerde analyse opgebouwd uit vier secties:

1. **Sterke Advertenties — SCHALEN** — welke ads budget verdienen
2. **Underperformers — STOPPEN** — welke ads te pauseren of aanpassen
3. **Hook & Creative Aanbevelingen** — concrete test-ideeën op basis van wat werkt
4. **Budget Reallocatie** — hoe budget te herverdelen tussen advertenties

De AI ontvangt voor deze analyse: alle metrics van de top 15 advertenties op spend, de samenvatting van de account, creatieve context (opgeslagen scripts en copy), en eventuele patronen van andere klanten in dezelfde branche.

---

## 6. Creative-analyse & winners/losers

### Navigeer naar: Klantprofiel → "Creative analyse"

Dit scherm toont alle advertenties gesplitst in winners, middenmoters en losers.

### Hoe worden winners en losers bepaald?

Dit doet het systeem zelf — zonder AI — puur op basis van rekenwiskundige drempelwaarden.

**Voor leadcampagnes (CPL):**

| Categorie | Criterium |
|-----------|-----------|
| **Winner** | CPL < gemiddelde CPL × 0.85 |
| **Loser** | €50+ spend + 0 resultaten, OF CPL > gemiddelde CPL × 1.5 |
| **Middenmoter** | Alles daartussenin |

**Voor aankoopscampagnes (ROAS):**

| Categorie | Criterium |
|-----------|-----------|
| **Winner** | ROAS > gemiddelde ROAS × 1.2 |
| **Loser** | ROAS < gemiddelde ROAS × 0.5 + minimaal €50 spend |

> **Waarom ×0.85 en ×1.5?** Dit zijn bewuste marges. Een advertentie die 15% beter presteert dan het gemiddelde is statistisch relevant genoeg om als winner te behandelen. De ×1.5-grens voor losers voorkomt dat kleine schommelingen meteen als "slecht" worden gemarkeerd — je wilt iets dat echt significant underperformt voordat je er actie op neemt.

> **Waarom ×1.2 voor ROAS-winners?** Bij aankoopscampagnes is 20% boven gemiddeld een duidelijk signaal dat de advertentie beter converteert dan de rest van het account.

### Creative decoder — wat analyseert de AI per advertentie?

Voor elke winner en loser roept het systeem Claude aan met een gestructureerde prompt. Hieronder staat exact wat de AI ontvangt en wat het teruggeeft.

#### Voor een winner:

De AI ontvangt:
- De advertentienaam
- Het campagnetype (leads / purchases)
- De metrics: CPL/ROAS, CTR, spend, resultaten, frequentie
- De gemiddelde accountprestaties (als referentie)
- Eventueel het opgeslagen script en copy voor deze advertentie

De AI geeft terug:

| Veld | Wat het is |
|------|-----------|
| **hook_type** | Welk type hook de AI herkent (proof, promise, frustration, etc.) |
| **hook_explanation** | Waarom de AI dit hook-type herkent — gebaseerd op de naam en eventueel de copy |
| **promise** | De kernbelofte van de advertentie in 1 zin |
| **audience_pain** | Welk specifiek pijnpunt er wordt aangesproken |
| **format** | Formaat (reels, static, testimonial, etc.) |
| **cta_intent** | Welke actie de kijker moet nemen + waarom die laagdrempelig is |
| **psychological_driver** | FOMO, zekerheid, identiteit, sociaal bewijs, status, angst, of aspiratie |
| **why_wins** | 2-3 concrete redenen waarom deze advertentie het beter doet dan het accountgemiddelde, gebaseerd op de aangeleverde metrics |
| **test_hypothesis** | 1 concrete hypothese om te testen op basis van wat werkt |

> **Wat de AI NIET doet bij winner-analyse:** de AI telt geen woorden in de advertentietekst en kijkt niet naar de lengte van de copy. Het kijkt naar de naam, het formaat, de metrics in relatie tot het accountgemiddelde, en eventueel de opgeslagen copy — en redeneert vanuit die combinatie waarom de advertentie het goed doet.

#### Voor een loser:

De AI ontvangt dezelfde data maar analyseert vanuit faalredenen.

| Veld | Wat het is |
|------|-----------|
| **failure_reason** | Een van zeven categorieën (zie hieronder) |
| **failure_explanation** | 2-3 zinnen concrete uitleg van het probleem |
| **fix_direction** | Welke hook of welk format te proberen als alternatief |
| **should_kill** | true of false — moet deze advertentie gestopt worden? |
| **test_hypothesis** | 1 specifieke test om te zien of het concept gered kan worden |

**De zeven faalcategorieën:**

| Categorie | Wanneer van toepassing |
|-----------|----------------------|
| `hook_generic` | De opening is te algemeen, trekt niet aan |
| `wrong_audience` | Het pijnpunt/de belofte past niet bij de doelgroep |
| `format_mismatch` | Het format past niet bij de boodschap |
| `weak_cta` | De call-to-action is te zwak of onduidelijk |
| `ad_fatigue` | De advertentie heeft te lang gedraaid voor dezelfde doelgroep |
| `budget_insufficient` | Te weinig spend om te beoordelen |
| `creative_mismatch` | Visuele stijl sluit niet aan bij de propositie |

---

## 7. Hook-analyse

### Navigeer naar: Klantprofiel → "Hook analyse"

Dit scherm toont welke hooks en formats presteren in het account, gebaseerd op alle uploads die zijn opgeslagen.

### Hoe detecteert het systeem hooks?

Het systeem kijkt naar de **advertentienaam** en werkt in twee stappen:

**Stap 1 — Gestructureerde parsing (voorkeur)**
Als de advertentienaam het standaardformat volgt (`Format - Hook - V# - Omschrijving`), parseert het systeem de onderdelen direct via opsplitsing op " - ".

Voorbeeld: `Reels - Proof - V2 - Klantresultaat fitness`
→ Format: `reels`, Hook: `proof`, Versie: `V2`

**Stap 2 — Keyword matching (fallback)**
Als de naam niet gestructureerd is, zoekt het systeem naar trefwoorden. Er zijn 90+ keyword-mappings, waaronder:

| Keyword in naam | → Hook |
|----------------|--------|
| "resultaat", "bewijs", "voor/na", "klant laat zien" | → proof |
| "frustrer", "moe van", "klaar met", "zat van" | → frustration |
| "geheim", "ontdek", "wist je dat", "niemand vertelt je" | → curiosity |
| "belofte", "garantie", "binnen X weken", "zeker van" | → promise |
| "jij ook", "herken je", "is dit jou", "ken je dat" | → recognition |
| "nu", "beperkt", "laatste kans", "alleen vandaag" | → urgency |
| "hoe je", "stappenplan", "methode", "systeem" | → educational |
| "klanten zeggen", "review", "testimonial", "dit zegt" | → social_proof |
| "stop met", "doe dit niet", "waarom je faalt" | → confrontation |
| "oplossing voor", "fix voor", "zo los je op" | → problem_solve |

Als er geen keyword matcht, krijgt de advertentie de hook `unknown` en verschijnt die in de "onbekende advertenties"-sectie voor handmatige tagging.

**Versienummer detectie:**
Het systeem herkent: V1, V2, V3, version 1, hook 3, variant 2 — in alle gangbare notaties.

### Wat toont de hook-analyse?

- **Per hook:** gemiddelde CPL, gemiddelde CTR, aantal advertenties, totale spend
- **Per format:** dezelfde metrics
- **Winnende combinaties:** top 3 hook+format combinaties op laagste CPL
- **Ongeteste hooks:** hooks die nog niet zijn geprobeerd in dit account
- **Onbekende advertenties:** namen die niet herkend konden worden

> **Hoe berekent het systeem "beste hook"?** Het neemt het gewogen gemiddelde CPL per hook-type. Advertenties met minder dan €30 spend tellen niet mee — ze hebben te weinig data om het gemiddelde te beïnvloeden zonder toeval te introduceren.

### Hoe wordt historische hookdata opgebouwd?

Bij elke upload slaat het systeem een "hook snapshot" op in de database: per hook-type en format de spend, resultaten, CPL en CTR van die upload. Bij de hook-analyse worden alle snapshots van alle uploads van die klant gecombineerd. Dit geeft een betrouwbaarder beeld dan één upload alleen.

> **Dubbeltelling voorkomen:** het systeem aggregeert op upload-niveau, niet op rij-niveau. Zo wordt een advertentie die in drie uploads voorkomt niet drie keer meegeteld.

### Cross-client vergelijking

Als een klant een branche heeft ingesteld (bijv. "fitness"), haalt het systeem anonieme hookdata op van andere klanten in dezelfde branche. Dit wordt als extra context getoond: welke hooks in die branche gemiddeld het beste presteren. De daadwerkelijke scripts, copy of namen van andere klanten worden nooit gedeeld — alleen de geaggregeerde metrics.

---

## 8. Static image analyse

### Navigeer naar: Klantprofiel → "Static analyseren"

Hier upload je een statische advertentie-afbeelding (JPEG, PNG, WebP, of GIF — maximaal 5 MB) voor AI-analyse.

### Wat analyseert de AI?

De AI ontvangt vijf dingen tegelijk:

1. **De afbeelding zelf** — via Claude Vision (de AI "ziet" de afbeelding letterlijk)
2. **Hookprestaties van het account** — welke hooks de laagste CPL hebben
3. **Copy-woordlengteanalyse** — het systeem berekent vóór de AI-aanroep de woordlengte van alle opgeslagen advertentieteksten en deelt ze in drie categorieën:
   - Kort: ≤ 20 woorden
   - Middel: 21–40 woorden
   - Lang: > 40 woorden
4. **Gemiddelde CPL per woordlengtecat egorie** — welke lengte historisch het beste converteert voor deze klant
5. **Naam en context van de klant** — uit het klantprofiel

> **Telt de AI woorden?** Nee — het systeem telt de woorden. Vóór de AI-aanroep berekent de code de woordtelling van alle opgeslagen advertentieteksten, berekent de gemiddelde CPL per lengtecat, en geeft dit als kwantitatieve input mee aan Claude. De AI hoeft dus geen woorden te tellen — het krijgt de uitkomst al aangeleverd en gebruikt die om te beslissen welke lengte voor variant 1 (bewezen) en variant 2 (test) gebruikt wordt.

### Wat geeft de analyse terug?

| Veld | Inhoud |
|------|--------|
| **hook_type** | Welk type hook de AI herkent in de afbeelding |
| **visual_samenvatting** | 1-2 zinnen: wat communiceert de afbeelding visueel? |
| **copy_1** | Advertentietekst variant 1: bewezen aanpak |
| **copy_1_aanpak** | Uitleg: welke hook is gebruikt, waarom deze woordlengte, op basis van welke data |
| **copy_2** | Advertentietekst variant 2: testoptie |
| **copy_2_aanpak** | Uitleg van de testredenering |
| **headline** | Koptekst van maximaal 8 woorden |
| **verbeterpunt** | 1 concrete tip om dit type static te verbeteren |

**Hoe kiest de AI voor copy_1 vs copy_2:**

- **Variant 1:** gebruikt de hook met de laagste CPL in het account + de woordlengte die historisch het beste converteert. Dit is de bewezen, veilige keuze.
- **Variant 2:** probeert een ongeteste hook OF de tegenovergestelde woordlengte als test. De twee varianten zijn altijd inhoudelijk anders — de AI heeft expliciet de instructie geen repetitie te gebruiken.

---

## 9. Shoot brief generator

### Navigeer naar: Klantprofiel → "Shoot briefs"

De shoot brief generator maakt altijd **precies 5 shoots** — niet meer, niet minder. Elke shoot heeft een andere strategische reden en vult de andere aan.

### De 5 shoot-types en hun logica

| # | Type | Strategie | Risico |
|---|------|-----------|--------|
| 1 | **Safe** | Bewezen hook + bewezen format. Iteratie op de beste performer. | Laag |
| 2 | **New hook** | Ongeteste of op-één-na-beste hook in het bewezen format. | Middel |
| 3 | **Format test** | Bewezen hook in een nieuw format (bijv. van reels naar carousel). | Middel |
| 4 | **Winner iterate** | ZELFDE hook + format als shoot 1, maar ander concept en copy. | Laag |
| 5 | **Winner scale** | Op-één-na-beste hook + op-één-na-beste format combinatie. | Middel-hoog |

> **Waarom altijd 5?** Dit is een bewuste testmatrix. Shoot 1 en 4 borgen continuïteit — wat werkt blijft draaien en wordt verfijnd. Shoot 2 en 3 zijn gecontroleerde experimenten met één variabele tegelijk (pas één ding aan zodat je weet wat het effect veroorzaakte). Shoot 5 test schaalbaarheid. Samen dekken ze alle kritische variabelen zonder het account te overladen met te veel simultane tests.

### Wat bevat elke shoot brief?

Elke shoot bevat een volledig productiepakket:

| Veld | Inhoud |
|------|--------|
| **Naam suggestie** | Conform de naamgevingsconventie, bijv. `Proof-Reels-V1` |
| **Concept** | 1-2 zinnen: wat laat de advertentie zien? |
| **Redenering** | 3-5 zinnen met concrete cijfers uit het account (CPL, CTR, spend) die de keuze onderbouwen |
| **Hook type** | Welk hook-type |
| **Format** | reels, static, testimonial, ugc, carousel, story, etc. |
| **Openingszin** | De exacte eerste zin of openingsscène van de advertentie |
| **Aspect ratio** | 9:16 (reels/stories), 1:1 (feed), 16:9 (landscape) |
| **Duur** | 30 of 45 seconden |
| **Talent** | Wie filmt: lid / klant / trainer — altijd warm en authentiek, geen acteur |
| **Locatie** | Studio of locatie van de klant |
| **Copy** | 3-5 zinnen advertentietekst (vanuit klantperspectief) |
| **Headline** | Maximaal 8 woorden, punchige CTA |
| **Key message** | 1 zin kernvoordeel |
| **CTA** | Call-to-action tekst |
| **Hypothese** | Wat je test met deze shoot en wat je wilt leren |
| **Script** | Tijdgestuurde scènes voor video (bijv. "0-5s: openingszin", "5-18s: probleembeschrijving") of visual beschrijving voor statics |

### Hoe kiest de AI de inhoud?

De AI ontvangt:
- Alle hookprestaties gesorteerd op CPL (laagste eerst)
- Gemiddelde CTR per format
- Ongeteste hooks voor dit account
- De top 3 winnende hook+format combinaties
- Naam en context van de klant

Op basis hiervan redeneert de AI:
- Shoot 1: "Hook X heeft CPL €Y — dit is de best presterende hook. Format Z heeft de hoogste CTR. Dit is de veilige keuze."
- Shoot 2: "Hook A is nog nooit getest in dit account. Het werkt in dezelfde branche. Test in format Z want dat heeft de hoogste CTR."
- Shoot 3: "Hook X werkt bewezen. Format W is nog niet getest — test of dezelfde boodschap in een ander format beter converteert."
- Shoot 4: "Frequentie van de winnende advertentie stijgt. Maak hetzelfde hook+format maar ander concept om ad fatigue te voorkomen."
- Shoot 5: "Hook B (op-één-na-best) + Format V (op-één-na-best CTR) — test de tweede keuze op schaalbaarheid."

De redenering staat altijd expliciet in het `redenering`-veld van elke shoot, inclusief de cijfers waarop het gebaseerd is.

---

## 10. Script generator

### Navigeer naar: Klantprofiel → "Scripts genereren"

Genereert **2 videoscripts** op basis van de prestaties van het account en de stijl van bestaande scripts.

### Hoe leert de AI van bestaande scripts?

Dit is een van de slimmere functies van het systeem. Voordat de AI een nieuw script schrijft, analyseert de code alle bestaande scripts die in de database zijn opgeslagen:

**Woordtelling per hook:** voor elk opgeslagen script telt het systeem het aantal woorden. Per hook-type berekent het de gemiddelde scriptlengte.

Voorbeeld:
- "Proof-scripts zijn gemiddeld 85 woorden"
- "Frustration-scripts zijn gemiddeld 110 woorden"

**Dit wordt als kwantitatieve context meegestuurd naar de AI**, samen met de scripts zelf (voor stijlherkenning). De AI schrijft dan een nieuw script dat:
- Dezelfde woordlengte heeft als bewezen scripts voor die hook
- Dezelfde stijl volgt (klantperspectief, conversationele toon, geen em-dashes)
- Een nieuwe invalshoek kiest zodat er geen overlap is met bestaande content

> **Telt de AI woorden voor scripts?** Nee — de code telt de woorden van bestaande scripts vóór de AI-aanroep, berekent het gemiddelde per hook-type, en geeft dat als instructie mee. Claude wordt gevraagd een script te schrijven dat past binnen de bewezen woordlengte van die hook. De AI hoeft zelf niet te tellen.

### Wat levert de generator op?

**Diagnose:** 2-3 zinnen analyse van wat voor deze klant werkt — welke hooks, welke CPL-cijfers, wat de trend is.

**Script 1 — Bewezen aanpak:**
- Hook-type: de hook met de laagste CPL in het account
- Naam suggestie conform naamgevingsconventie
- Aanpak: waarom dit de bewezen keuze is (met cijfers)
- Script met tijdcodes:
  - **0-5s:** Hook — de openingszin die de aandacht pakt
  - **5-18s:** Body — het probleem, het bewijs, of het verhaal
  - **18-25s:** Oplossing / USP — het concrete voordeel
  - **25-30s:** CTA — een laagdrempelige vervolgstap

**Script 2 — Testoptie:**
- Ongeteste of underperformende hook
- Andere invalshoek dan script 1
- Zelfde structuur, andere energie en boodschap

---

## 11. Testkit & smart generator

### Navigeer naar: Klantprofiel → Creative analyse → "Testkit genereren" (bij een winnende advertentie)

De testkit genereert een volledig test-universum op basis van één winnende advertentie.

### Input

De testkit combineert twee eerdere analyses:
- De **gedecodeerde winner** (hook, belofte, pijnpunt, format, psychologische driver)
- De **assen** van de axes mapper (6 richtingen om in te variëren)

### Output: 7 varianten + extras

**3 safe variants** (lage-risico tests)
Elk bevat: openingszin, volledige advertentietekst (3-4 zinnen), headline (max 40 tekens), uitleg waarom het werkt, en productiespec (format, duur, aspect ratio, talent, locatie).

**3 fresh variants** (nieuwe hooks of formats)
Testen een andere hook OF een ander format maar behouden de kern van de winnende propositie.

**1 risky variant**
Contrair concept — gaat in tegen de verwachting. Bijv. negatieve hook, anti-sell ("dit is niet voor iedereen"), of een radicaal andere invalshoek.

**Testimonial brief:**
- Welk verhaal de klant moet vertellen
- 3 interview-vragen om dat verhaal op te halen
- Gewenst gevoel na het bekijken van de testimonial

**Static concept:**
- Visual beschrijving (wat staat er op de afbeelding)
- Headline max 35 tekens
- Ondersteunende tekst
- CTA-tekst

**Shootlist:**
- 6 concrete opnames die je nodig hebt voor de safe variants

**Test prioriteit:**
- Welke 3 varianten je het eerst moet testen
- Redenering: wat je leert van elke test en waarom deze volgorde logisch is

---

## 12. Axes mapper

De axes mapper wordt automatisch uitgevoerd als onderdeel van de testkit. Het genereert 6 "assen" van creatieve variatie op basis van de winnende advertentie en de ongeteste hooks van het account.

### De 6 assen

| As | Wat het test | Voorbeelden |
|----|-------------|------------|
| **A — Angle variation** | Andere invalshoek op hetzelfde concept | Resultaatgericht, procesgericht, community-gericht |
| **B — Pain variation** | Ander pijnpunt aanspreken | Tijdsdruk, onzekerheid, FOMO op een gemiste kans |
| **C — Promise variation** | Andere formulering van de belofte | Sneller resultaat, simpeler aanpak, garantie |
| **D — Format variation** | Ander formaat testen | Testimonial video, before/after carousel |
| **E — Opposite angle** | Negatieve hook: wat verlies je als je dit niet doet? | Anti-sell: "Dit is niet voor iedereen" |
| **F — New segment** | Andere doelgroep | Andere leeftijdsgroep, warme vs. koude doelgroep |

Elke as bevat 2-3 concrete, specifieke ideeën. Geen vage richtingen als "test een andere tone of voice" — maar echte uitwerkingen die je direct kunt produceren.

---

## 13. Excel templates: video's & statics

### Navigeer naar: Klantprofiel → "Excel templates"

Je kunt creatieve content in bulk importeren en exporteren via Excel.

### Video-template kolommen

| Kolom | Inhoud |
|-------|--------|
| Ad naam | Advertentienaam (moet exact overeenkomen met de naam in Meta) |
| Script | Volledig videoscript |
| Ad copy 1 | Advertentietekst variant 1 |
| Ad copy 2 | Advertentietekst variant 2 |
| Ad copy 3 | Advertentietekst variant 3 |

### Static-template kolommen

| Kolom | Inhoud |
|-------|--------|
| Ad naam | Advertentienaam |
| Headline 1 | Koptekst variant 1 |
| Headline 2 | Koptekst variant 2 |
| Headline 3 | Koptekst variant 3 |
| Ad copy 1 | Advertentietekst variant 1 |
| Ad copy 2 | Advertentietekst variant 2 |
| Ad copy 3 | Advertentietekst variant 3 |

### Template opmaak

- **Rij 1:** Klantnaam (blauwe achtergrond)
- **Rij 3:** Kolomkoppen (donkere achtergrond, witte tekst)
- **Rij 4:** Voorbeeldrij (grijs, cursief — wordt automatisch genegeerd bij import)
- **Rij 5+:** Jouw data

Kolombreedte en rijhoogte zijn geoptimaliseerd voor leesbaarheid. Tekst wordt automatisch gewrapped zodat lange scripts leesbaar blijven.

### Importeren

1. Download het sjabloon voor de klant
2. Vul de advertentienamen en content in
3. Advertentienamen moeten **exact** overeenkomen met de namen in Meta Ads Manager
4. Upload het ingevulde bestand via het klantprofiel
5. Het systeem slaat alles op per advertentienaam

Bij het importeren worden **alleen niet-lege velden** overschreven. Als er al een script staat en je importeert alleen copy, blijft het script behouden.

---

## 14. Creatieve content per advertentie

### Navigeer naar: Klantprofiel → "Creatieve content"

Dit is het overzicht van alle advertenties met hun opgeslagen scripts, headlines en copy.

### Wat kun je hier doen?

- Bekijken welke advertenties nog geen creatieve content hebben (handig om te zien wat ontbreekt)
- Handmatig content toevoegen of aanpassen
- Scripts, headlines en 3 copy-varianten per advertentie opslaan
- Afbeeldingen koppelen aan advertenties (voor static analyse later)

> **Waarom is dit belangrijk?** Deze opgeslagen content is de basis voor alle AI-functies. De script generator leert van opgeslagen scripts. De static analyse vergelijkt nieuwe copy met bestaande copy-patronen. De inzichten-generator gebruikt opgeslagen copy als context. Hoe meer content er is opgeslagen, hoe beter de AI leert van de stijl en structuur die voor deze klant werkt.

---

## 15. PDF-export

### Navigeer naar: Analyse-dashboard → "Exporteer PDF"

Genereert een PDF-rapport met de volledige analyse. Geschikt om te delen met klanten.

**Inhoud van de PDF:**

1. **Header** — "Meta Ads Rapport — SLN Solutions" + datum
2. **Periode** — het datumbereik van de geanalyseerde data
3. **KPI-blokken (rij 1)** — Budget, CPL/ROAS, CTR, Resultaten
4. **KPI-blokken (rij 2)** — Impressies, CPM, CPC, Frequentie
5. **Campagnetabel** — naam, budget, CPL/ROAS, CTR, resultaten, frequentie per campagne
6. **Top advertenties tabel** — top ads op spend met alle metrics
7. **AI-inzichten** — de volledige gegenereerde analyse, opgemaakt voor PDF

> Speciale tekens (accenten, em-dashes, aanhalingstekens) worden automatisch omgezet naar PDF-veilige equivalenten om opmaakproblemen te voorkomen.

---

## 16. Historische data & meerdere CSV's samenvoegen

### Meerdere uploads per klant

Elke upload wordt permanent opgeslagen in de database. Je kunt op elk moment terugkeren naar een eerdere upload via het klantprofiel — je hoeft het CSV-bestand dus niet te bewaren.

### CSV's samenvoegen

**Navigeer naar: Klantprofiel → "Samenvoegen"**

Als je meerdere CSV's hebt (bijv. per maand of per periode), kun je ze samenvoegen tot één gecombineerde analyse.

**Hoe werkt de merge?**
Het systeem combineert alle rijen en past dezelfde deduplicatie toe als bij een normale upload: dezelfde advertentie op dezelfde dag wordt maar één keer meegeteld, ook als die rij in twee bestanden voorkomt. Zo wordt overlap automatisch afgehandeld.

**Wanneer gebruik je dit?**
- Je wilt een kwartaalanalyse maken maar hebt drie maandelijkse exports
- Je wilt de prestaties van twee campagneperiodes vergelijken in één overzicht
- Je hebt data van meerdere ad accounts die je wilt combineren

### Historische data laden

Via het klantprofiel selecteer je een eerdere upload uit de lijst. Het systeem haalt de data op uit de database (niet van schijf). Als de database-opslag om een reden niet beschikbaar is, wordt een fallback naar het lokale bestand geprobeerd.

---

## 17. Ad-tagging (handmatig hook toewijzen)

### Navigeer naar: "Ad tagging" in de navigatie

Als een advertentienaam niet voldoet aan de naamgevingsconventie en het systeem geen hook kan detecteren, verschijnen die advertenties in de "onbekende advertenties"-lijst.

### Wat kun je hier doen?

- Per advertentie handmatig een hook-type en format toewijzen
- De toewijzing wordt opgeslagen in de database per klant
- Bij alle toekomstige analyses wordt de opgeslagen toewijzing automatisch gebruikt — je hoeft dit maar één keer te doen

### AI-suggesties voor onbekende advertenties

De AI kan suggesties doen voor de hook- en formattoewijzing. Dit werkt als volgt: alle onbekende advertentienamen worden in één API-aanroep naar Claude gestuurd. De AI analyseert elke naam en stelt een hook + format voor op basis van de naamstructuur en de campagnecontext. Jij bevestigt of past aan vóór opslaan.

---

## 18. Hoe AI beslissingen neemt — de volledige redenering

Dit is de sectie die de meeste context geeft over hoe het systeem denkt. Lees dit als je wilt begrijpen waarom de AI een bepaalde aanbeveling doet.

### Wat gaat er naar de AI bij elke aanroep?

| Element | Inhoud |
|---------|--------|
| **Systeemrol** | "Je bent een Meta Ads specialist voor SLN Solutions. Je schrijft in het Nederlands. Je bent data-gedreven en concreet." |
| **Klantnaam + context** | Zoals ingevuld in het klantprofiel (ICP, doelgroep, toon) |
| **Campagnetype** | Leads of aankopen |
| **CPL/ROAS-benchmark** | De drempelwaarde voor deze klant |
| **Performance data** | Top 15 advertenties op spend, gesorteerd. Per ad: naam, spend, resultaten, CPL/ROAS, CTR, frequentie |
| **Accountgemiddelden** | CPL/ROAS, CTR, totaal spend als referentie |
| **Creatieve context** | Opgeslagen scripts, headlines, copy per advertentie (max 400 tekens per veld) |
| **Hook context** | CPL + CTR per hook-type, ongeteste hooks, winnende combinaties |
| **Cross-client data** | Anonieme hook + format prestaties van andere klanten in dezelfde branche (indien beschikbaar) |

### Wat de AI NIET doet

- De AI analyseert geen landingspagina's, comments, of data buiten de aangeleverde CSV
- De AI telt geen woorden in advertentieteksten bij winner/loser analyse — dat doet de code vóór de aanroep bij specifieke functies (scripts, static analyse)
- De AI maakt geen beslissingen op basis van algemene kennis over de klant of de branche — alles is gebaseerd op de data die in het systeem is aangeleverd
- De AI verdeelt geen budgetten daadwerkelijk — het doet altijd aanbevelingen die jij beoordeelt

### Hoe scoort het systeem — en wanneer doet de AI dat?

**Het systeem scoort** (zonder AI):
- Winner / loser / middenmoter classificatie
- Burning / fatigue detectie
- Hook-rankings op CPL en CTR
- Woordlengte-categorisering van copy

**De AI interpreteert** (na de scoring):
- Waarom werkt een winner? Welk mechanisme zit erachter?
- Welke faalreden heeft een loser, en is het te redden?
- Welke hooks zijn het meest kansrijk om te testen?
- Hoe moet een nieuw script klinken dat past bij de stijl van het account?

### Taalgebruik en stijlregels voor de AI

De AI heeft de volgende expliciete instructies:
- Schrijf altijd in het Nederlands
- Schrijf scripts en copy vanuit **klantperspectief** ("ik", niet "jij")
- Conversationele toon — geen marketingclichés
- Geen em-dashes in de output
- Data-gedreven: noem altijd concrete cijfers in de redenering

### Maximale output per aanroep

| Functie | Max tokens output |
|---------|------------------|
| Inzichten | 1200 |
| Creative decoder (winner/loser) | 800 |
| Shoot brief (per shoot) | 800 |
| Testkit / smart generator | 800 |
| Script generator | 800 |
| Static analyse | 800 |
| Ad tag suggesties | 800 |

> Als de AI-output wordt afgekapt door de tokenlimiet, kan dit resulteren in onvolledige JSON. Het systeem probeert dit automatisch te herstellen. Als dat niet lukt, verschijnt een foutmelding.

---

## 19. Fallback: wat gebeurt er zonder AI?

Als de API niet beschikbaar is (geen sleutel, geen verbinding, of een API-fout), valt het systeem terug op ingebouwde rekenregels. De functies blijven werkend maar de output is minder genuanceerd.

### Fallback inzichten

Het systeem genereert regelbased inzichten:
- Identificeert de top 3 advertenties op CPL
- Identificeert de 3 slechtste advertenties op CPL
- Detecteert fatigue (frequentie > 3.0)
- Beoordeelt CTR: < 0.5% = zwakke hook, 0.5–1.5% = gemiddeld, > 1.5% = sterk
- Schrijft standaard aanbevelingen op basis van deze regels

### Fallback creative decoder

- Hook wordt afgeleid uit de advertentienaam (zelfde keyword-matching als hook-detectie)
- Format wordt geparset uit de naam
- Faalredenen worden bepaald op basis van regels:
  - CTR < 0.5% → `weak_hook`
  - 0 resultaten bij €50+ spend → `weak_cta` of landingspaginaprobleem
  - Hoge CPL + lage CTR → `format_mismatch`
- Suggereert standaard een V2-test of nieuw format als hersteloptie

### Fallback shoot brief

Het systeem bouwt briefs op basis van vooraf geschreven scriptstructuren per hook-type. Elke hook (recognition, frustration, proof, etc.) heeft een template dat wordt ingevuld met de beschikbare data. De productiespecificaties zijn standaard (9:16, 30 seconden).

---

## 20. Naamgevingsconventie advertenties

Voor optimale werking van het systeem is het sterk aanbevolen deze naamgevingsconventie te volgen:

```
Format - Hook - Versie - Korte omschrijving
```

**Voorbeelden:**
```
Reels - Proof - V1 - Klantresultaat gewichtsverlies
Static - Promise - V2 - 12 weken resultaat garantie
Testimonial - Social_proof - V1 - Klant over haar transformatie
UGC - Frustration - V1 - Moe van crash diëten
Carousel - Educational - V1 - 3 fouten bij afvallen
```

### Geldige formats

| Format | Omschrijving |
|--------|-------------|
| `Reels` | Verticale video ≤ 60s, inclusief talking head |
| `Testimonial` | Klantgetuigenis video |
| `UGC` | User-generated content stijl |
| `Story` | Instagram / Facebook Story |
| `Carousel` | Meerdere afbeeldingen of kaarten |
| `Static` | Enkelvoudige afbeelding |
| `Product_demo` | Product demonstratie |
| `Before_after` | Voor/na vergelijking |
| `Animation` | Geanimeerde video |

### Geldige hook-types

| Hook | Omschrijving |
|------|-------------|
| `Recognition` | Herkenning: "Is dit jou?" |
| `Frustration` | Frustratie aanspreken: "Moe van..." |
| `Curiosity` | Nieuwsgierigheid: "Dit wist je niet over..." |
| `Proof` | Bewijs: resultaten, voor/na, klantcase |
| `Promise` | Belofte: "Binnen X weken..." |
| `Confrontation` | Confrontatie: "Stop met..." |
| `Urgency` | Urgentie: "Alleen dit weekend..." |
| `Problem_solve` | Oplossing: "Zo fix je..." |
| `Social_proof` | Sociaal bewijs: klanten aan het woord |
| `Educational` | Educatief: uitleg, stappenplan, methode |

**Versienummering:** Gebruik altijd V1, V2, V3. Begin bij V1 voor elke nieuwe combinatie van format + hook.

---

## 21. Veelgestelde vragen & tips

**Hoe weet het systeem of een campagne leads of aankopen meet?**
Het kijkt naar de naam van de resultaatkolom in de CSV. Meta gebruikt namen zoals "Leads", "Purchases", "Thruplay" etc. Als het campagnetype niet uit de CSV af te leiden is, kun je het handmatig instellen in het klantprofiel.

**Waarom worden sommige advertenties genegeerd?**
Advertenties met €0 spend worden automatisch gefilterd — ze zijn inactief en verstoren de gemiddelden. Advertenties met minder dan €30 spend worden wel getoond maar krijgen het label "Te weinig data" en tellen niet mee in hook-gemiddelden.

**Wat als ik twee verschillende conversie-events in één campagne meet?**
Het systeem detecteert dit (zelfde advertentienaam + zelfde datum met verschillende resultaattypen) en voegt ze samen. Resultaten worden opgeteld, spend wordt maar één keer meegeteld.

**Hoe nauwkeurig is de hook-detectie?**
Bij een correcte naamgevingsconventie is de detectie 100% nauwkeurig. Bij vrije namen is de keyword-matching goed voor gangbare formuleringen maar mist het subtiele varianten. Gebruik ad-tagging voor advertenties die niet herkend worden.

**Wat als de AI een onjuiste hook detecteert?**
De AI-output is een redeneeradvies, geen automatische actie. Als de AI een onjuiste hook herkent (bijv. omdat de naam misleidend is), kun je dit corrigeren via ad-tagging. De gecorrigeerde toewijzing wordt opgeslagen en voortaan automatisch gebruikt.

**Hoe snel veroudert de data?**
Het systeem slaat alle uploads op maar weet niet of een advertentie inmiddels is gepauzeerd of gewijzigd in Meta. Upload altijd een recente CSV voor actuele aanbevelingen. Historische data is nuttig voor trend-analyse maar niet voor acutionele beslissingen.

**Kan ik de app in het Engels gebruiken?**
De interface en AI-output zijn in het Nederlands. De CSV kan zowel Engels als Nederlands zijn — beide worden herkend. De AI-output is altijd Nederlands.

**Hoe werkt cross-client leren?**
Als je bij een klant de branche hebt ingesteld (bijv. "fitness"), haalt het systeem anonieme hookdata op van andere klanten in dezelfde branche. Alleen hook-type + format + gemiddelde CPL/CTR worden gedeeld — nooit namen, scripts, of copy van andere klanten.

**Waarom schrijft de AI copy vanuit klantperspectief?**
Dit is een expliciete instructie in het systeem. Advertenties die klinken alsof een klant zijn eigen resultaat deelt converteren structureel beter dan copy geschreven vanuit het bureau. De AI heeft de instructie altijd "ik" te schrijven vanuit de klant, niet "jij" vanuit het bureau.

**Wat is de maximale bestandsgrootte voor een CSV?**
Er is geen harde limiet, maar exports met meer dan 10.000 rijen kunnen langzamer verwerkt worden. Filter de export in Meta op een specifieke periode als de CSV erg groot is.

**Kan ik meerdere klanten tegelijk analyseren?**
Nee — het systeem werkt per klantprofiel. Cross-client vergelijking is beschikbaar via de branche-instelling, maar de analyse-interface werkt altijd per klant.

**Wat als een shoot brief niet klopt met de realiteit van de klant?**
De AI heeft geen kennis van de specifieke situatie van de klant buiten wat je hebt ingevoerd in het klantprofiel. Hoe meer context je invult (doelgroep, aanbod, tone of voice, beperkingen), hoe relevanter de briefs worden. Gebruik het klantcontext-veld uitgebreid.

---

*Laatste update: mei 2026*  
*Systeem: SLN Meta Ads Analyzer — gebouwd op Claude (Anthropic)*
