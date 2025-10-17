# 📊 Guide: Importere Månedlige Accounting Rapporter

## 📥 Når du mottar en ny Receivable Details rapport fra regnskapet

### Metode 1: Bruk Python-scriptet (anbefalt)

1. **Plasser Excel-filen** i `excel/RD/` mappen
   ```
   excel/RD/Receivable Details oct 25.xlsx
   ```

2. **Kjør import-scriptet**:
   ```bash
   python import_monthly_accounting.py "excel/RD/Receivable Details oct 25.xlsx"
   ```

3. **Ferdig!** Scriptet vil automatisk:
   - Importere data fra Excel-filen
   - Slette eksisterende data for den måneden (hvis det finnes)
   - Beregne MRR med korrekt periodisering
   - Generere snapshot for måneden

### Metode 2: Bruk Batch-filen (Windows)

1. **Dra og slipp** Excel-filen på `import_accounting.bat`
2. **Ferdig!** Batch-filen kjører scriptet automatisk

---

## 📋 Krav til Excel-filen

### Filnavn:
Filnavnet MÅ inneholde:
- **Månedsnavn** (jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec)
- **År** (24, 25, 2024, 2025)

**Eksempler på gyldige filnavn:**
- ✅ `Receivable Details oct 25.xlsx`
- ✅ `Receivable Details Jan 2024.xlsx`
- ✅ `RD sept 25 (2).xlsx`
- ❌ `October Report.xlsx` (mangler standard månedsnavn)

### Format:
Excel-filen må ha samme format som Zoho Billing eksporterer:
- Første rad inneholder kolonnenavn
- Kolonnene må inkludere: `transaction_type`, `item_name`, `description`, `customer_name`, `bcy_total_with_tax`, etc.

---

## 🔍 Se resultatene

Etter import kan du se dataene på:

1. **Dashboard**: http://localhost:8000/api/accounting/dashboard
2. **Trender**: http://localhost:8000/api/accounting/trends
3. **Drilldown for måneden**: http://localhost:8000/api/accounting/month-drilldown?month=2025-10

---

## ⚙️ Periodisering-regler

Scriptet bruker **automatisk korrekt periodisering**:

### Produkter som er 12 måneder (UTEN "(mnd)" i navnet):
- Alle "oppgradering" produkter
- Sporingstrafikk VMS GPRS (årlig)
- 30 dager ERS (årlig abonnement)

### Produkter som er månedlige (MED "(mnd)" i navnet):
- Sporingstrafikk VMS GPRS (mnd)
- Fangstdagbok inkl. sporing (mnd)
- 30 dager ERS (mnd)

### Produkter som IKKE inkluderes i MRR:
- Hardware (Rockfleet LTE, Fangstr VMS, etc.)
- Frakt
- Renter og gebyr inkasso
- Andre engangs-kostnader

---

## 🔧 Feilsøking

### "Filen finnes ikke"
- Sjekk at stien er korrekt
- Bruk anførselstegn rundt stien hvis den inneholder mellomrom

### "Could not infer source_month"
- Sjekk at filnavnet inneholder månedsnavn (jan, feb, mar, etc.)
- Sjekk at filnavnet inneholder år (24, 25, 2024, 2025)

### "transaction_type column not found"
- Excel-filen har feil format
- Sjekk at du eksporterer "Receivable Details" fra Zoho Billing
- Første rad må inneholde kolonnenavn

### Data ser feil ut
- Sjekk at Excel-filen er fra riktig måned
- Se i dashboardet om tallene ser riktige ut
- Hvis noe er galt, kan du kjøre import-scriptet på nytt (det sletter og re-importerer)

---

## 📅 Månedlig rutine (anbefalt)

1. **Første dag i ny måned**: Be regnskapet om Receivable Details for forrige måned
2. **Motta Excel-fil** fra regnskapet
3. **Lagre filen** i `excel/RD/` med riktig navn (f.eks. "Receivable Details oct 25.xlsx")
4. **Kjør import**: `python import_monthly_accounting.py "excel/RD/Receivable Details oct 25.xlsx"`
5. **Verifiser** at tallene ser riktige ut på dashboardet
6. **Ferdig!** MRR-trendene oppdateres automatisk

---

## 💡 Tips

- **Behold alle Excel-filene** i `excel/RD/` mappen for historisk referanse
- **Sjekk dashboardet** etter hver import for å verifisere at tallene ser riktige ut
- **Sammenlign** Accounting MRR med Subscription MRR (2-5% gap er normalt)
- Hvis du må **re-importere samme måned**, bare kjør scriptet på nytt (det sletter og erstatter automatisk)

---

## 🆘 Hjelp

Hvis du har problemer:
1. Sjekk denne guiden først
2. Se i terminalvinduet for feilmeldinger
3. Verifiser at Excel-filen har riktig format
4. Kontakt utvikler hvis problemet vedvarer
