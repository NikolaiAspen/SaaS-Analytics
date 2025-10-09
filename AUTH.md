# Authentication Guide - SaaS Analytics Dashboard

## 🔐 Basic Authentication

Appen bruker **Basic Authentication** for å beskytte tilgang til dashboardet. Dette er enkelt, sikkert nok for interne dashboards, og fungerer på alle plattformer.

## Hvordan det fungerer

Når noen prøver å åpne dashboardet, vil nettleseren vise en innloggingsdialog som ber om brukernavn og passord.

## Sette opp autentisering

### For lokal utvikling:

1. Kopier `.env.example` til `.env`:
   ```bash
   cp .env.example .env
   ```

2. Rediger `.env` og sett brukernavn og passord:
   ```env
   AUTH_USERNAME=admin
   AUTH_PASSWORD=ditt_sikre_passord_her
   ```

3. Start appen - nå vil den kreve innlogging!

### For Railway/Render deployment:

1. Gå til din project dashboard (Railway eller Render)

2. Finn "Environment Variables" eller "Variables" seksjonen

3. Legg til disse variablene:
   ```
   AUTH_USERNAME=admin
   AUTH_PASSWORD=ditt_sikre_passord_her
   ```

4. Redeploy appen om nødvendig

## Deaktivere autentisering

Hvis du ikke vil ha pålogging (f.eks. for testing):

- La `AUTH_USERNAME` og `AUTH_PASSWORD` være tomme eller slett dem
- Appen vil da ikke kreve innlogging

## Brukere og tilganger

### Legge til flere brukere

Basic Auth støtter kun én bruker/passord-kombinasjon. For flere brukere har du disse alternativene:

#### 1. Delt brukernavn/passord (Enklest)
- Del samme brukernavn og passord med alle i teamet
- Eksempel: `team / teampassord123`

#### 2. Oppgrader til avansert auth (Fremtidig funksjonalitet)
Hvis du trenger:
- Flere individuelle brukere
- Ulike tilgangsnivåer
- Innloggingshistorikk

Kontakt utvikler for å oppgradere til en av:
- **Token-based auth** (JWT)
- **OAuth** (Google/Microsoft)
- **Database-backed auth** med brukeradministrasjon

## Sikkerhetstips

### ✅ Gjør dette:
- Bruk et sterkt passord (minst 16 tegn)
- Bruk passordgenerator
- Del passord sikkert (f.eks. via 1Password, LastPass, eller direkte)
- Bytt passord regelmessig

### ❌ Ikke gjør dette:
- Bruk ikke enkle passord som "password123"
- Ikke del passord over usikrede kanaler (SMS, Slack, etc.)
- Ikke hardcode passord i koden
- Ikke commit `.env` filen til git

## Eksempel på sikkert passord

Generer et sterkt passord:
```
M7#kP9$vL2@nQ5&wR8!xT3
```

Eller bruk passordgenerator som 1Password, LastPass, eller Bitwarden.

## Feilsøking

### "Authentication required" vises, men jeg har lagt til credentials
- Sjekk at environment variablene er riktig skrevet (`AUTH_USERNAME` og `AUTH_PASSWORD`)
- Restart appen etter å ha endret environment variables
- Sjekk at det ikke er mellomrom før/etter brukernavn eller passord

### Nettleseren husker ikke innlogging
- Basic Auth sessions lagres av nettleseren
- Lukk alle browserfaner og åpne på nytt for å logge ut
- Bruk "private/incognito" mode for testing

### Jeg har glemt passordet
- Endre `AUTH_PASSWORD` i Railway/Render environment variables
- Redeploy appen
- Bruk det nye passordet

## Support

Ved problemer:
- Sjekk environment variables i Railway/Render dashboard
- Se DEPLOYMENT.md for mer info
- Kontakt admin/utvikler
