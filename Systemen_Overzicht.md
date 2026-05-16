# SLN Meta Ads Analyzer — Systeemoverzicht

> **Versie:** Mei 2026  
> **Doel:** Alle gebruikte systemen, diensten, bibliotheken, omgevingsvariabelen en infrastructuur op één plek

---

## Inhoudsopgave

1. [Architectuuroverzicht](#1-architectuuroverzicht)
2. [Hosting & deployment](#2-hosting--deployment)
3. [Externe diensten & API's](#3-externe-diensten--apis)
4. [Database](#4-database)
5. [Python-bibliotheken](#5-python-bibliotheken)
6. [Omgevingsvariabelen](#6-omgevingsvariabelen)
7. [Bestandsstructuur](#7-bestandsstructuur)
8. [Sessie- & authenticatiebeheer](#8-sessie--authenticatiebeheer)
9. [Beveiliging](#9-beveiliging)
10. [Wat werkt lokaal vs. in productie](#10-wat-werkt-lokaal-vs-in-productie)

---

## 1. Architectuuroverzicht

```
[Gebruiker / Rick]
       │
       │  Browser (HTTPS)
       ▼
┌─────────────────────────────┐
│   Flask Web App (Python)    │  ← draait op Render / Gunicorn
│   app.py  (~2000 regels)    │
└────────────┬────────────────┘
             │
     ┌───────┼───────────────┐
     │       │               │
     ▼       ▼               ▼
┌─────────┐ ┌──────────┐ ┌──────────────────┐
│Supabase │ │Anthropic │ │  Lokale uploads  │
│Postgres │ │Claude API│ │  (CSV-bestanden) │
│(database│ │(AI-motor)│ │  /uploads/       │
└─────────┘ └──────────┘ └──────────────────┘
```

**Samenvatting in gewone taal:**

| Laag | Wat het is |
|------|-----------|
| **Frontend** | HTML-pagina's gegenereerd door Flask (geen apart React/Vue framework) |
| **Backend** | Python Flask app, draait als één proces via Gunicorn |
| **Database** | Supabase (PostgreSQL in de cloud) |
| **AI** | Anthropic Claude API — externe dienst, betaald per gebruik |
| **Opslag** | CSV-uploads staan tijdelijk op disk én permanent in de database als tekst |

---

## 2. Hosting & deployment

| Onderdeel | Details |
|-----------|---------|
| **Platform** | Render.com (cloud hosting) |
| **Webserver** | Gunicorn 23.0.0 (WSGI server voor Python) |
| **Framework** | Flask 3.1.0 |
| **Python versie** | 3.x (3.14 actief op de server op basis van cache-bestanden) |
| **Poort** | 5000 (standaard), aanpasbaar via `PORT` omgevingsvariabele |
| **Host** | 0.0.0.0 (luistert op alle interfaces) |
| **Deploy-trigger** | Push naar `main`-branch op GitHub → Render bouwt automatisch opnieuw |
| **Startup-commando** | `gunicorn app:app` |

> **Hoe werkt automatisch deployen?** Elke keer dat er code naar GitHub wordt gepusht op de `main`-branch, pikt Render dat automatisch op en bouwt de app opnieuw. Je hoeft niets handmatig te doen. Dit duurt doorgaans 1-3 minuten.

---

## 3. Externe diensten & API's

### Anthropic Claude API

| Eigenschap | Waarde |
|-----------|--------|
| **Dienst** | Anthropic (anthropic.com) |
| **SDK-versie** | `anthropic==0.52.0` |
| **Model** | `claude-sonnet-4-6` (standaard, aanpasbaar) |
| **Authenticatie** | API-sleutel via `ANTHROPIC_API_KEY` omgevingsvariabele |
| **Kosten** | Betaald per token (input + output) — zie Anthropic-dashboard voor gebruik |
| **Fallback** | Als de API niet bereikbaar is, valt het systeem terug op ingebouwde rekenregels |

**Waarvoor wordt Claude gebruikt:**

| Functie | Aanroep type | Max output tokens |
|---------|-------------|-------------------|
| Inzichten genereren | Tekst | 1200 |
| Creative decoder (winner/loser) | JSON | 800 |
| Shoot brief genereren | JSON | 800 per shoot |
| Testkit / smart generator | JSON | 800 |
| Script generator | JSON | 800 (1800 bij scripts) |
| Static image analyse | JSON + afbeelding (Vision) | 1000 |
| Ad-tag suggesties | JSON | 800 |

**Hoe afbeeldingen worden verstuurd:** afbeeldingen worden base64-gecodeerd en als onderdeel van de API-aanroep meegestuurd (geen aparte upload-URL). Maximaal 5 MB per afbeelding.

---

### Supabase (database)

| Eigenschap | Waarde |
|-----------|--------|
| **Dienst** | Supabase (supabase.com) |
| **Database type** | PostgreSQL |
| **Authenticatie** | Connection string via `DATABASE_URL` omgevingsvariabele |
| **Verbinding** | psycopg2 met een connection pool van minimaal 1 en maximaal 5 verbindingen |
| **SSL** | Verplicht (wordt automatisch toegevoegd aan Supabase-URLs) |
| **Row Level Security** | Ingeschakeld op alle tabellen (directe REST-toegang geblokkeerd) |
| **Kosten** | Afhankelijk van Supabase-plan (gratis tier beschikbaar) |

---

### Meta Ads Manager (als databron)

Meta Ads Manager is geen API-koppeling — de gebruiker exporteert handmatig een CSV-bestand vanuit Meta en uploadt dat naar de app. Er is geen directe API-verbinding met Meta.

| Eigenschap | Details |
|-----------|---------|
| **Integratie** | Handmatige CSV-export uit Meta Ads Manager |
| **Talen** | Zowel Engelse als Nederlandse kolomnamen worden herkend |
| **Kolomvarianten** | Meer dan 50 kolomnaamvarianten worden ondersteund |
| **Max bestandsgrootte** | 50 MB (aanpasbaar via `MAX_UPLOAD_MB`) |
| **Max rijen** | 10.000 (aanpasbaar via `MAX_CSV_ROWS`) |

---

## 4. Database

### Verbinding

```
DATABASE_URL=postgresql://gebruiker:wachtwoord@host:5432/databasenaam?sslmode=require
```

Het systeem gebruikt een connection pool: maximaal 5 gelijktijdige verbindingen. Als de database niet bereikbaar is, werkt de app in "lokale modus" (geen persistentie tussen sessies).

### Tabellen

| Tabel | Doel | Sleutelvelden |
|-------|------|--------------|
| `clients` | Klantprofielen | id, name, industry, campaign_type, cpl_benchmark, roas_benchmark, client_context |
| `uploads` | Geschiedenis van CSV-uploads | id, client_id, filename, uploaded_at, date_from, date_to, total_spend, total_results, avg_cpl, avg_roas, avg_ctr, avg_frequency, num_ads, csv_content |
| `ad_name_mappings` | Handmatige hook/format-toewijzingen per advertentie | id, client_id, ad_name, hook_type, format_type |
| `hook_snapshots` | Historische hookprestaties per upload | id, client_id, upload_id, hook_type, format_type, ads, spend, results, cpl, avg_ctr |
| `shoot_briefs` | Gegenereerde shoot briefs (opgeslagen als JSON) | id, client_id, upload_id, brief_json |
| `insights_history` | Gegenereerde AI-inzichten per upload | id, client_id, upload_id, insights_text |
| `ad_creatives` | Scripts, headlines en copy per advertentie | id, client_id, ad_naam, script, headline, headline_2, headline_3, ad_copy_1, ad_copy_2, ad_copy_3, afbeelding_pad |

### Relaties

```
clients (1)
   ├── uploads (n)           ← elke upload hoort bij één klant
   │      ├── hook_snapshots (n)
   │      ├── shoot_briefs (n)
   │      └── insights_history (n)
   ├── ad_name_mappings (n)  ← handmatige hook-toewijzingen per klant
   └── ad_creatives (n)      ← scripts/copy per advertentienaam per klant
```

---

## 5. Python-bibliotheken

| Bibliotheek | Versie | Waarvoor |
|------------|--------|---------|
| `flask` | 3.1.0 | Webframework — routes, templates, sessies |
| `Werkzeug` | 3.1.3 | Onderdeel van Flask — request handling, bestandsuploads |
| `gunicorn` | 23.0.0 | Productie WSGI-server — draait de Flask-app in productie |
| `psycopg2-binary` | 2.9.10 | PostgreSQL-adapter — verbinding met Supabase database |
| `python-dotenv` | 1.0.1 | Laadt `.env`-bestand — omgevingsvariabelen lokaal beschikbaar maken |
| `anthropic` | 0.52.0 | Anthropic SDK — communicatie met Claude API |
| `plotly` | 5.24.1 | Grafieken — interactieve grafieken in het analyse-dashboard |
| `openpyxl` | 3.1.5 | Excel-bestanden lezen en schrijven — template import/export |
| `fpdf2` | 2.8.2 | PDF-generatie — exporteert het analyserapport als PDF |

**Totaal: 9 externe bibliotheken**

---

## 6. Omgevingsvariabelen

Dit zijn alle variabelen die in de `.env`-file (lokaal) of in het Render-dashboard (productie) moeten staan.

| Variabele | Verplicht | Standaardwaarde | Waarvoor |
|-----------|-----------|----------------|---------|
| `ANTHROPIC_API_KEY` | Ja (voor AI) | — | Authenticatie voor de Claude API. Zonder deze key valt de app terug op fallback-regels |
| `DATABASE_URL` | Ja (voor persistentie) | — | Verbindingsstring naar Supabase PostgreSQL. Zonder deze key werkt de app in tijdelijke modus (data verdwijnt na herstart) |
| `FLASK_SECRET_KEY` | Ja | `change-this-to-a-random-secret` | Versleuteling van sessie-cookies. Gebruik een lange willekeurige string in productie |
| `ANTHROPIC_MODEL` | Nee | `claude-sonnet-4-6` | Welk Claude-model gebruikt wordt. Aanpassen als er een nieuw model beschikbaar is |
| `MAX_UPLOAD_MB` | Nee | `50` | Maximale bestandsgrootte voor CSV-uploads in MB |
| `MAX_CSV_ROWS` | Nee | `10000` | Maximaal aantal rijen dat verwerkt wordt per CSV |
| `PORT` | Nee | `5000` | Poortnummer waarop de app luistert |
| `FLASK_DEBUG` | Nee | `false` | Debugmodus (nooit `true` in productie — toont interne foutmeldingen) |
| `APP_USERS` | Nee | — | Optionele basisauthenticatie. Formaat: `gebruiker1:wachtwoord1,gebruiker2:wachtwoord2` |

### Waar stel je deze in?

**Lokaal (ontwikkeling):** in het bestand `.env` in de hoofdmap van het project. Dit bestand staat in `.gitignore` en wordt nooit naar GitHub gepusht.

**Productie (Render):** via het Render-dashboard → je app → Environment → Environment Variables. Render injecteert deze variabelen automatisch bij elke herstart.

---

## 7. Bestandsstructuur

```
meta_ads_automation/
│
├── app.py                          # Hoofdapplicatie (~2000 regels) — alle routes
│
├── core/                           # Kernlogica (losse modules)
│   ├── ai_client.py                # Communicatie met Anthropic Claude API
│   ├── analysis.py                 # CSV-verwerking & metrics berekenen
│   ├── axes_mapper.py              # Genereer 6 creatieve test-assen
│   ├── creative_decoder.py         # Decodeer winners & losers
│   ├── csv_parser.py               # CSV inlezen & normaliseren (EN/NL kolommen)
│   ├── db.py                       # Database-laag (Supabase / psycopg2)
│   ├── excel_templates.py          # Excel templates genereren & importeren
│   ├── generation.py               # AI-inzichten genereren
│   ├── hook_analyzer.py            # Hook & format detectie uit advertentienamen
│   ├── reporter.py                 # PDF-rapportage genereren
│   ├── script_generator.py         # Videoscripts genereren
│   ├── shoot_brief.py              # Shoot briefs genereren (5 shoots)
│   ├── smart_generator.py          # Testkit genereren (7 varianten + extras)
│   └── static_analyzer.py         # Statische afbeeldingen analyseren (Vision)
│
├── models/
│   └── campaign.py                 # Datamodellen: Campaign, AdSet, Ad
│
├── templates/                      # HTML-templates (Jinja2)
│   └── *.html                      # Alle pagina's van de app
│
├── static/                         # CSS, JavaScript, afbeeldingen
│
├── uploads/                        # Tijdelijke opslag van geüploade CSV-bestanden
│
├── requirements.txt                # Python-bibliotheken (9 packages)
├── .env                            # Lokale omgevingsvariabelen (niet in Git)
├── .env.example                    # Template voor omgevingsvariabelen
├── HANDLEIDING_RICK.md             # Volledige gebruikershandleiding
└── Systemen_Overzicht.md           # Dit bestand
```

---

## 8. Sessie- & authenticatiebeheer

### Sessies

| Eigenschap | Details |
|-----------|---------|
| **Type** | Cookie-gebaseerde Flask-sessies |
| **Levensduur** | 4 uur na inloggen |
| **Maximale grootte** | 4 KB (browserlimiet voor cookies) |
| **Wat er in de sessie staat** | data_source (verwijzing naar upload), samenvatting-metrics, top 5 advertenties |
| **Wat NIET in de sessie staat** | Volledige advertentiedata en AI-inzichten — die staan in de database om de cookie-limiet niet te overschrijden |

### Authenticatie

| Eigenschap | Details |
|-----------|---------|
| **Type** | Basisauthenticatie via sessiebeheer |
| **Instelling** | Via `APP_USERS` omgevingsvariabele (`gebruiker:wachtwoord` paren, kommagescheiden) |
| **Inlogpagina** | `/login` |
| **Uitloggen** | `/logout` |
| **Zonder APP_USERS** | Als de variabele niet is ingesteld, is authenticatie uitgeschakeld (handig lokaal, nooit in productie) |

---

## 9. Beveiliging

| Onderwerp | Status | Details |
|-----------|--------|---------|
| **API-sleutels** | Veilig | Staan in omgevingsvariabelen, nooit in de code of Git |
| **Database** | Veilig | Row Level Security ingeschakeld op alle tabellen — directe publieke toegang geblokkeerd |
| **Sessie-encryptie** | Veilig | Flask versleutelt sessies met `FLASK_SECRET_KEY` |
| **HTTPS** | Veilig | Render regelt dit automatisch (SSL-certificaat inbegrepen) |
| **Debugmodus** | Let op | `FLASK_DEBUG` moet `false` zijn in productie — anders worden interne foutmeldingen zichtbaar voor gebruikers |
| **Bestandsuploads** | Beperkt | Alleen CSV-bestanden geaccepteerd, maximaal 50 MB |
| **CORS** | Niet geconfigureerd | Alleen same-origin requests (geen externe API-aanroepen vanuit de browser) |

---

## 10. Wat werkt lokaal vs. in productie

| Functie | Lokaal (zonder .env) | Productie (Render) |
|---------|---------------------|-------------------|
| CSV uploaden & analyseren | Ja | Ja |
| Inzichten genereren | Fallback (geen AI) | Ja (met API-sleutel) |
| Shoot briefs genereren | Fallback (geen AI) | Ja (met API-sleutel) |
| Scripts genereren | Fallback (geen AI) | Ja (met API-sleutel) |
| Static image analyse | Nee (geen AI) | Ja (met API-sleutel) |
| Klantprofielen opslaan | Nee (geen database) | Ja |
| Historische uploads bewaren | Nee (geen database) | Ja |
| Hook-snapshots opbouwen | Nee (geen database) | Ja |
| Cross-client vergelijking | Nee | Ja |
| PDF exporteren | Ja | Ja |
| Excel templates | Ja | Ja |

> **Samengevat:** zonder `DATABASE_URL` en `ANTHROPIC_API_KEY` werkt de app alleen als een eenmalige CSV-analysetool. Met beide variabelen ingesteld zijn alle functies actief.

---

## Snel overzicht: alle externe afhankelijkheden

```
┌─────────────────────────────────────────────┐
│            EXTERNE DIENSTEN                  │
├───────────────────┬─────────────────────────┤
│ Dienst            │ Doel                    │
├───────────────────┼─────────────────────────┤
│ Render.com        │ Hosting & deployment    │
│ Supabase          │ Database (PostgreSQL)   │
│ Anthropic Claude  │ AI-analyse & generatie  │
│ GitHub            │ Versiebeheer & CI/CD    │
│ Meta Ads Manager  │ Databron (CSV-export)   │
└───────────────────┴─────────────────────────┘

┌─────────────────────────────────────────────┐
│          PYTHON PACKAGES (9 stuks)           │
├───────────────────┬─────────────────────────┤
│ flask             │ Webframework            │
│ Werkzeug          │ Request handling        │
│ gunicorn          │ Productieserver         │
│ psycopg2-binary   │ Database-verbinding     │
│ python-dotenv     │ Omgevingsvariabelen     │
│ anthropic         │ Claude AI SDK           │
│ plotly            │ Grafieken               │
│ openpyxl          │ Excel in/export         │
│ fpdf2             │ PDF-export              │
└───────────────────┴─────────────────────────┘

┌─────────────────────────────────────────────┐
│     OMGEVINGSVARIABELEN (verplicht)          │
├───────────────────┬─────────────────────────┤
│ ANTHROPIC_API_KEY │ Claude API-toegang      │
│ DATABASE_URL      │ Supabase-verbinding     │
│ FLASK_SECRET_KEY  │ Sessie-encryptie        │
└───────────────────┴─────────────────────────┘
```

---

*Laatste update: mei 2026*  
*Systeem: SLN Meta Ads Analyzer*
