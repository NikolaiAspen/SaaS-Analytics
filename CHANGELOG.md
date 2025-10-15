# Endringslogg - SaaS Analytics

## Versjon 2.3.0 - 15. oktober 2025

### 🎯 MRR Gap Analyse & Excel Rapport
- **Komplett gap-analyse rapport**: Ny Excel-rapport med 5 detaljerte ark (Sammendrag, Kunde Sammenligning, Subscriptions, Fakturaer, Forklaring)
- **100% matching rate**: Alle 1,933 subscriptions matchet via multi-tier strategi (Subscription ID, Kallesignal, Fartøy)
- **Minimal gap**: Kun 0.1% forskjell (1,612 NOK) mellom subscription og faktura MRR
- **Pedagogisk forklaring**: Excel-arket "Forklaring" forklarer hvorfor subscription-basert og faktura-basert MRR er forskjellige

### 🤖 AI Forbedringer
- **Bedre forklaring av MRR-forskjeller**: Niko kan nå forklare forskjellen mellom subscription-basert og faktura-basert MRR på en pedagogisk måte
- **5 konkrete årsaker til gap**: Tidsforskyving, kreditnotaer, gamle fakturaer, engangsfakturaer, manuelle justeringer
- **Tydeligere kildehenvisning**: Niko spesifiserer alltid om tall er fra subscriptions eller fakturaer
- **Bedre kontekstforståelse**: AI-en vet nå at begge metoder er gyldige men brukes til forskjellige formål

### 🐛 Feilrettinger
- **Faktura MRR display**: Fikset bug hvor fakturaer med kreditnotaer viste 0.00 kr MRR i stedet for korrekt beløp
- **Template separering**: Invoice MRR, Credit Amount og Net MRR vises nå i separate kolonner for klarhet
- **Database connection**: Automatisk tillegg av +asyncpg driver for Railway PostgreSQL-kompatibilitet

### 🔧 Tekniske Endringer
- `/health` endpoint utvidet med test query for å verifisere database-data
- Forbedret matching-logikk for invoice-subscription kobling
- Oppdatert AI-instruksjoner med 1000+ linjer detaljert kontekst

### 📊 Resultater
- Subscription MRR: 2,061,316 NOK
- Faktura MRR: 2,062,928 NOK
- Gap: 1,612 NOK (0.1%)
- Matched: 1,933/1,933 subscriptions (100%)

---

## Versjon 2.1.0 - 10. oktober 2025

### 🎯 Niko AI Forbedringer
- **Komplett churn-analyse**: Niko har nå tilgang til ALL churn-data fra databasen
- **Detaljerte churn-årsaker**: Når du spør om churn, får du nå spesifikke kundenavn, beløp og årsaker
- **Utvidet historikk**: Viser churn-detaljer for siste 12 måneder (opp fra 6 måneder)
- **Flere detaljer per måned**: Viser opptil 20 kunder per måned med fullstendige detaljer

### 📊 UI Forbedringer
- **Sorterbare tabeller**: Klikk på kolonneoverskrifter for å sortere data
- **Ny kundeside**: "Kunder og oppsigelser" med komplett oversikt over aktive og churned kunder
- **Fartøy og kallesignal**: Nye kolonner viser fartøynavn og kallesignal for hver kunde
- **Bedre navigasjon**: Konsistent sidebar-meny på tvers av alle sider
- **BETA-merking**: Faktura-baserte MRR-funksjoner er tydelig merket som under utvikling

### 🔧 Tekniske Endringer
- Optimalisert database-spørringer for churn-data
- Forbedret AI-instruksjoner for mer presise svar
- Økt data-kontekst for bedre AI-analyse

---

## Versjon 2.0.0 - 9. oktober 2025

### ✨ Nye Funksjoner
- **Niko AI Chat**: Still spørsmål om tallene dine og få detaljerte svar
- **Faktura-basert MRR**: Alternativ MRR-beregning basert på fakturaer fra Zoho Billing
- **Komplett kundeanalyse**: Se alle kunder med deres abonnementer, fartøy og churn-status
- **AI-genererte innsikter**: Automatiske analyser av kundeadferd og trender

### 📈 Dashboard Forbedringer
- Interaktivt chat-grensesnitt med Niko
- Quick actions for vanlige spørsmål
- Forbedret visualisering av nøkkeltall
- Klikkbare KPI-kort som leder til detaljsider

### 🔒 Sikkerhet
- Basic Authentication for alle API-endepunkter
- Konfigurerbar tilgangskontroll via miljøvariabler

---

## Hvordan bruke de nye funksjonene?

### Spør Niko
1. Gå til Dashboard
2. Skriv spørsmålet ditt i chat-boksen
3. Få detaljerte svar med faktiske kundenavn og tall

**Eksempler på spørsmål:**
- "Hvilke kunder churnet i september og hvorfor?"
- "Hvorfor endret MRR seg i siste måned?"
- "Hva er den største bekymringen akkurat nå?"

### Sorterbare tabeller
- Klikk på en kolonneoverskrift for å sortere
- Klikk igjen for å reversere sorteringen
- Fungerer på alle tabeller i systemet

### Se komplett kundeoversikt
- Naviger til "Kunder og oppsigelser" i menyen
- Filtrer på aktive eller churned kunder
- Eksporter til CSV for videre analyse
