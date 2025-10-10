# Endringslogg - SaaS Analytics

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
