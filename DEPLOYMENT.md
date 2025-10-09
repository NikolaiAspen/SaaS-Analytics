# Deployment Guide - SaaS Analytics Dashboard

## 🚀 Quick Deploy med Railway.app (Anbefalt)

### Steg 1: Forbered GitHub Repository
```bash
git add .
git commit -m "Prepare for deployment"
git push origin main
```

### Steg 2: Deploy på Railway
1. Gå til [railway.app](https://railway.app) og logg inn med GitHub
2. Klikk "New Project" → "Deploy from GitHub repo"
3. Velg repository: `NikolaiAspen/SaaS-Analytics`
4. Railway vil automatisk detektere Python-appen

### Steg 3: Legg til PostgreSQL Database
1. I Railway-prosjektet, klikk "+ New" → "Database" → "Add PostgreSQL"
2. Railway genererer automatisk `DATABASE_URL` environment variabel

### Steg 4: Sett Environment Variables
I Railway dashboard, gå til Settings → Variables og legg til:

```
OPENAI_API_KEY=din_openai_api_key
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Auto-generert av Railway
APP_ENV=production
```

### Steg 5: Deploy
- Railway deployer automatisk!
- Få din URL: `https://your-app.railway.app`

---

## 🎯 Alternativ: Render.com

### Steg 1: Opprett Web Service
1. Gå til [render.com](https://render.com) og logg inn
2. Klikk "New +" → "Web Service"
3. Koble til GitHub repo: `NikolaiAspen/SaaS-Analytics`

### Steg 2: Konfigurer Service
- **Name**: saas-analytics
- **Environment**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### Steg 3: Legg til PostgreSQL
1. Klikk "New +" → "PostgreSQL"
2. Koble database til web service

### Steg 4: Environment Variables
```
OPENAI_API_KEY=din_openai_api_key
DATABASE_URL=  # Auto-kobles fra PostgreSQL
APP_ENV=production
```

### Steg 5: Deploy
- Klikk "Create Web Service"
- Render deployer automatisk!

---

## 📝 Viktige Noter

### Database Migration
Første gang appen starter vil den automatisk:
- Opprette alle nødvendige tabeller
- Initialisere databasen

### Viktige miljøvariabler:
- `DATABASE_URL`: Database connection string (auto-satt av Railway/Render)
- `OPENAI_API_KEY`: Nødvendig for "Spør Niko" AI-features
- `APP_ENV`: Sett til `production` for prod-miljø

### Lokal testing før deploy:
```bash
# Installer avhengigheter
pip install -r requirements.txt

# Kjør lokalt
uvicorn app:app --reload
```

### Kostnad:
- **Railway**: $5/måned for hobby plan (inkluderer database)
- **Render**: Gratis tier tilgjengelig, $7/måned for PostgreSQL

### Tilgang for teamet:
Etter deployment, del URL-en med teamet. Alle kan få tilgang via:
- Direkte URL: `https://your-app.railway.app`
- Ingen pålogging nødvendig (kan legges til senere om ønskelig)

### Sikkerhet:
For å legge til autentisering senere, vurder:
- Basic Auth
- OAuth (Google/Microsoft)
- IP whitelist

---

## 🔧 Feilsøking

### Problem: Database connection error
**Løsning**: Sjekk at `DATABASE_URL` er riktig satt i environment variables

### Problem: OpenAI API error
**Løsning**: Verifiser at `OPENAI_API_KEY` er riktig satt

### Problem: App crashes on startup
**Løsning**: Sjekk logs i Railway/Render dashboard for detaljer

---

## 📞 Support
Ved problemer, sjekk:
- Railway docs: https://docs.railway.app
- Render docs: https://render.com/docs
- GitHub repo: https://github.com/NikolaiAspen/SaaS-Analytics
