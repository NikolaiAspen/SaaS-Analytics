# Pre-Commit Checklist for Claude

## VIKTIG: Husk alltid før du committer!

### 1. Oppdater Versjonsnummer
Oppdater `version.py` med nytt versjonsnummer og dato:
```python
__version__ = "2.X.X"  # Oppdater dette!
__version_date__ = "DD. måned YYYY"
__version_name__ = "Kort beskrivelse"
```

**Versjonering:**
- Major (X.0.0): Store arkitekturelle endringer, breaking changes
- Minor (2.X.0): Nye features, forbedringer
- Patch (2.3.X): Bugfixes, små justeringer

### 2. Oppdater CHANGELOG.md
Legg til en ny seksjon øverst i `CHANGELOG.md`:
```markdown
## Versjon 2.X.X - DD. måned YYYY

### 🎯 [Kategori]
- **Feature navn**: Beskrivelse
- **Forbedring**: Beskrivelse

### 🐛 Feilrettinger
- **Bug navn**: Hva ble fikset

### 🔧 Tekniske Endringer
- Hva ble endret teknisk
```

**Kategorier:**
- 🎯 Nye Funksjoner
- 🤖 AI Forbedringer
- 📊 UI Forbedringer
- 🐛 Feilrettinger
- 🔧 Tekniske Endringer
- 🔒 Sikkerhet
- 📈 Ytelse

### 3. Commit Message Format
```
Version 2.X.X - [Kort tittel]

- Add/Update/Fix: [Hva ble gjort]
- [Flere punkter...]

Version 2.X.X Highlights:
- [Viktigste endringer]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 4. Test Lokalt
- [ ] Kjør appen lokalt og verifiser at alt fungerer
- [ ] Sjekk at endringsloggen vises riktig på /changelog
- [ ] Verifiser at nye features fungerer som forventet

### 5. Push til Railway
```bash
git add [files]
git commit -m "[message]"
git push origin master
```

Railway vil automatisk deploye de nye endringene.

---

## Når skal du oppdatere versjon?

**JA - Oppdater versjon når:**
- Du legger til nye features
- Du fikser viktige bugs
- Du gjør UI/UX forbedringer
- Du forbedrer AI-funksjonalitet
- Du gjør tekniske forbedringer som påvirker brukeren

**NEI - Ikke oppdater versjon når:**
- Du bare rydder opp i kode (refactoring uten endringer)
- Du legger til kommentarer eller dokumentasjon
- Du gjør små testfiler eller debug-scripts
- Det er work-in-progress som ikke er ferdig

---

## Eksempel på god versjonering:

✅ **GOD:**
```
Version 2.3.0 - MRR Gap Analysis & Invoice Fix

- Add comprehensive MRR gap analysis Excel report
- Fix invoice MRR display showing 0.00 kr
- Improve AI explanations for subscription vs invoice MRR

Version 2.3.0 Highlights:
- 100% subscription matching rate achieved
- Gap reduced to 0.1% (1,612 NOK)
- Enhanced changelog design with green accents
```

❌ **DÅRLIG:**
```
update stuff

fixed things
```

---

## Quick Reference: Version.py Template

```python
"""
Version information for SaaS Analytics
"""

__version__ = "2.3.0"
__version_date__ = "15. oktober 2025"
__version_name__ = "Gap Analysis & Invoice Display Fix"
```

**HUSK:** Dette er din commit-checklist - følg den!
