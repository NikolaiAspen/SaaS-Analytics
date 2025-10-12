from openai import AsyncOpenAI
from typing import Dict


class AnalysisService:
    """Service for generating natural language insights using OpenAI GPT-5"""

    def __init__(self, api_key: str, model: str = "gpt-5-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_analysis(self, metrics: Dict, trends: list = None) -> str:
        """
        Generate natural language analysis of metrics in Norwegian using GPT-5-mini

        Args:
            metrics: Dictionary of calculated metrics
            trends: Optional list of monthly trend data

        Returns:
            Analysis text in Norwegian
        """
        prompt = self._build_prompt(metrics, trends)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du er en erfaren SaaS-analytiker som skriver innsiktsfulle rapporter på norsk. "
                        "Fokuser på endringer i siste måned og viktige trender. "
                        "Strukturer analysen med klare seksjoner og linjeskift for lesbarhet. "
                        "Skriv konsist og profesjonelt, med konkrete forretningsinnsikter."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
        )

        return response.choices[0].message.content.strip()

    async def ask_question(self, question: str, metrics: Dict, trends: list = None) -> str:
        """
        Answer a specific question about the metrics data using GPT-5-mini

        Args:
            question: User's question in Norwegian
            metrics: Dictionary of current metrics
            trends: Optional list of monthly trend data

        Returns:
            Answer in Norwegian
        """
        context = self._build_context(metrics, trends)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du er en SaaS-analytiker som svarer på spørsmål om metrics på norsk. "
                        "Svar direkte og konkret basert på tallene du har tilgjengelig. "
                        "Hvis du ikke har nok data til å svare, si det tydelig."
                    )
                },
                {"role": "user", "content": f"Her er dataene:\n\n{context}\n\nSpørsmål: {question}"}
            ],
            max_tokens=600,
        )

        return response.choices[0].message.content.strip()

    async def ask_comprehensive(
        self,
        question: str,
        subscription_metrics: Dict = None,
        subscription_trends: list = None,
        invoice_metrics: Dict = None,
        invoice_trends: list = None,
        churn_details: list = None,
        new_customer_details: list = None,
        all_subscriptions: list = None,
        customer_summary: list = None,
        gap_analysis: Dict = None,
        conversation_history: list = None
    ) -> str:
        """
        Answer comprehensive questions with full context from all data sources

        Args:
            question: User's question in Norwegian
            subscription_metrics: Subscription-based metrics
            subscription_trends: Subscription trends data (12 months)
            invoice_metrics: Invoice-based metrics
            invoice_trends: Invoice trends data (12 months)
            churn_details: Detailed churn information with reasons
            new_customer_details: New customers details (12 months)
            all_subscriptions: Complete list of all active subscriptions
            customer_summary: Aggregated customer data grouped by company
            gap_analysis: MRR gap analysis with specific customers and vessels
            conversation_history: Previous Q&A pairs for context

        Returns:
            Detailed answer with markdown formatting
        """
        from datetime import datetime

        # Build comprehensive context
        today = datetime.utcnow()
        current_month = today.strftime("%B %Y")  # e.g., "Oktober 2025"

        context = f"# TILGJENGELIG DATA\n\n"
        context += f"**DAGENS DATO: {today.strftime('%d.%m.%Y')} ({current_month})**\n\n"

        # Subscription data
        if subscription_metrics:
            context += "## Subscription-baserte Tall (fra Zoho Subscriptions)\n"
            context += f"- MRR: {subscription_metrics.get('mrr', 0):,.0f} NOK\n"
            context += f"- ARR: {subscription_metrics.get('arr', 0):,.0f} NOK\n"
            context += f"- ARPU: {subscription_metrics.get('arpu', 0):,.0f} NOK\n"
            context += f"- Aktive kunder: {subscription_metrics.get('total_customers', 0)}\n"
            context += f"- Aktive subscriptions: {subscription_metrics.get('active_subscriptions', 0)}\n"
            context += f"- Customer churn: {subscription_metrics.get('customer_churn_rate', 0):.1f}%\n"
            context += f"- Revenue churn: {subscription_metrics.get('revenue_churn_rate', 0):.1f}%\n"
            context += f"- Ny MRR (siste 30d): {subscription_metrics.get('new_mrr', 0):,.0f} NOK\n\n"

        # Invoice data
        if invoice_metrics:
            context += "## Faktura-baserte Tall (fra Zoho Billing)\n"
            context += f"- MRR: {invoice_metrics.get('mrr', 0):,.0f} NOK\n"
            context += f"- ARR: {invoice_metrics.get('arr', 0):,.0f} NOK\n"
            context += f"- ARPU: {invoice_metrics.get('arpu', 0):,.0f} NOK\n"
            context += f"- Kunder med fakturaer: {invoice_metrics.get('total_customers', 0)}\n"
            context += f"- Aktive fakturaer: {invoice_metrics.get('active_invoices', 0)}\n\n"

        # Subscription trends (siste 12 måneder, nyeste først)
        if subscription_trends and len(subscription_trends) > 0:
            context += "## Subscription Trender (siste 12 måneder)\n"
            # Reverser for å få nyeste først
            recent_trends = list(reversed(subscription_trends))[:12]
            for i, trend in enumerate(recent_trends):
                context += f"**{trend.get('month_name')}:** "
                context += f"MRR {trend.get('mrr', 0):,.0f} kr"
                if trend.get('mrr_change'):
                    context += f" ({trend.get('mrr_change', 0):+,.0f} kr, {trend.get('mrr_change_pct', 0):+.1f}%)"
                context += f", {trend.get('customers', 0)} kunder"
                if trend.get('customer_change'):
                    context += f" ({trend.get('customer_change', 0):+d})"
                context += f"\n  - Ny MRR: {trend.get('new_mrr', 0):,.0f} kr"
                context += f"\n  - Churned MRR: {trend.get('churned_mrr', 0):,.0f} kr"
                context += f"\n  - Churned kunder: {trend.get('churned_customers', 0)} stk\n"
            context += "\n"

        # Invoice trends (siste 12 måneder, nyeste først)
        if invoice_trends and len(invoice_trends) > 0:
            context += "## Faktura Trender (siste 12 måneder)\n"
            # invoice_trends er allerede sortert desc i app.py
            recent_invoice_trends = invoice_trends[:12]  # Allerede sortert desc
            for i, trend in enumerate(recent_invoice_trends):
                context += f"**{trend.get('month_name')}:** "
                context += f"MRR {trend.get('mrr', 0):,.0f} kr"
                if trend.get('mrr_change'):
                    context += f" ({trend.get('mrr_change', 0):+,.0f} kr, {trend.get('mrr_change_pct', 0):+.1f}%)"
                context += f", {trend.get('customers', 0)} kunder\n"
            context += "\n"

        # Churn details (ALLE churned kunder med datoer og årsaker)
        if churn_details and len(churn_details) > 0:
            context += "## Churned Kunder (KOMPLETT OVERSIKT)\n"
            context += "**VIKTIG:** Disse dataene inneholder ALLE churned kunder med kundenavn, beløp, datoer og churn-årsaker.\n"
            context += f"**Totalt {len(churn_details)} churned kunder i databasen.**\n\n"

            # Grupper churn etter måned for oversikt
            from datetime import datetime
            from collections import defaultdict
            churn_by_month = defaultdict(list)

            for churn in churn_details:
                if churn.get('churned_at'):
                    try:
                        churn_date = datetime.strptime(churn.get('churned_at'), '%Y-%m-%d')
                        month_key = churn_date.strftime('%Y-%m')
                        churn_by_month[month_key].append(churn)
                    except:
                        pass

            # Vis siste 12 måneder med churn-detaljer
            sorted_months = sorted(churn_by_month.keys(), reverse=True)[:12]

            for month_key in sorted_months:
                month_churns = churn_by_month[month_key]
                month_date = datetime.strptime(month_key, '%Y-%m')
                month_name = month_date.strftime('%B %Y')
                total_mrr = sum(c.get('amount', 0) for c in month_churns)

                context += f"### {month_name} ({len(month_churns)} kunder, {total_mrr:,.0f} kr MRR)\n"

                for churn in month_churns[:20]:  # Vis maks 20 per måned
                    context += f"- **{churn.get('customer_name')}**: {churn.get('amount', 0):,.0f} kr"
                    if churn.get('plan_name'):
                        context += f" ({churn.get('plan_name')})"
                    if churn.get('reason'):
                        context += f" - *{churn.get('reason')}*"
                    context += "\n"

                if len(month_churns) > 20:
                    context += f"  ... og {len(month_churns) - 20} flere\n"
                context += "\n"

        # New customer details (siste 12 måneder)
        if new_customer_details and len(new_customer_details) > 0:
            context += f"## Nye Kunder (siste 12 måneder - {len(new_customer_details)} totalt)\n"
            # Vis bare de siste 20 for å ikke overbelaste context
            for customer in new_customer_details[:20]:
                context += f"- **{customer.get('customer_name')}**: {customer.get('amount', 0):,.0f} kr"
                if customer.get('plan_name'):
                    context += f" ({customer.get('plan_name')})"
                if customer.get('activated_at'):
                    context += f" - Aktivert: {customer.get('activated_at')}"
                context += "\n"
            if len(new_customer_details) > 20:
                context += f"  ... og {len(new_customer_details) - 20} flere\n"
            context += "\n"

        # Customer summary (sorted by MRR, top customers)
        if customer_summary and len(customer_summary) > 0:
            context += f"## Kundeoversikt (Alle kunder sortert etter MRR)\n"
            context += f"**Totalt {len(customer_summary)} kunder i databasen.**\n\n"
            context += "**Top 30 kunder etter MRR:**\n"
            for i, customer in enumerate(customer_summary[:30], 1):
                context += f"{i}. **{customer.get('customer_name')}**: {customer.get('total_mrr', 0):,.0f} kr/mnd"
                context += f" ({customer.get('subscription_count', 0)} subscriptions"
                if customer.get('vessels'):
                    vessel_count = len(customer.get('vessels', []))
                    context += f", {vessel_count} fartøy"
                context += ")\n"
                # Vis planer
                if customer.get('plans'):
                    plans = customer.get('plans', [])
                    context += f"   Planer: {', '.join(plans[:3])}"
                    if len(plans) > 3:
                        context += f" (+{len(plans)-3} flere)"
                    context += "\n"
            if len(customer_summary) > 30:
                remaining_mrr = sum(c.get('total_mrr', 0) for c in customer_summary[30:])
                context += f"\n... og {len(customer_summary) - 30} flere kunder (totalt {remaining_mrr:,.0f} kr MRR)\n"
            context += "\n"

        # All subscriptions overview
        if all_subscriptions and len(all_subscriptions) > 0:
            context += f"## Fullstendig Subscription Database\n"
            context += f"**Totalt {len(all_subscriptions)} aktive subscriptions i databasen.**\n"
            context += "**VIKTIG:** Du har tilgang til ALLE subscriptions med fullstendige detaljer (kunde, plan, beløp, status, fartøy, datoer).\n\n"

            # Grupper subscriptions etter status
            live_count = sum(1 for s in all_subscriptions if s.get('status') == 'live')
            non_renewing_count = sum(1 for s in all_subscriptions if s.get('status') == 'non_renewing')
            context += f"**Status fordeling:**\n"
            context += f"- Live: {live_count} subscriptions\n"
            context += f"- Non-renewing: {non_renewing_count} subscriptions\n\n"

            # Grupper etter plan type
            from collections import defaultdict
            plans_summary = defaultdict(lambda: {'count': 0, 'total_mrr': 0})
            for sub in all_subscriptions:
                plan_name = sub.get('plan_name', 'Unknown')
                interval_months = sub.get('interval', 1) if sub.get('interval_unit') == 'months' else (12 if sub.get('interval_unit') == 'years' else 1)
                mrr = (sub.get('amount', 0) / 1.25) / interval_months if sub.get('amount') else 0
                plans_summary[plan_name]['count'] += 1
                plans_summary[plan_name]['total_mrr'] += mrr

            context += "**Fordeling per plan:**\n"
            sorted_plans = sorted(plans_summary.items(), key=lambda x: x[1]['total_mrr'], reverse=True)[:10]
            for plan_name, data in sorted_plans:
                context += f"- **{plan_name}**: {data['count']} subscriptions, {data['total_mrr']:,.0f} kr MRR\n"
            context += "\n"

        # Gap Analysis (specific customers and vessels causing MRR gap)
        if gap_analysis:
            context += "## MRR Gap Analyse (Forskjell mellom Subscription og Faktura MRR)\n"
            context += "**VIKTIG:** Denne seksjonen viser SPESIFIKKE kunder og fartøy som forårsaker forskjellen mellom subscription-basert og faktura-basert MRR.\n\n"

            context += f"**Gap Oversikt:**\n"
            context += f"- Total gap MRR: {gap_analysis.get('total_gap_mrr', 0):,.0f} kr\n"
            context += f"- Kunder med fakturaer men ingen subscriptions: {gap_analysis.get('customers_without_subscriptions', 0)}\n"
            context += f"- Kunder med subscriptions men ingen fakturaer: {gap_analysis.get('customers_without_invoices', 0)}\n\n"

            context += f"**Matching Statistikk:**\n"
            context += f"- Matched by call sign: {gap_analysis.get('matched_by_call_sign', 0)} kunder ({gap_analysis.get('matched_gap_mrr', 0):,.0f} kr)\n"
            context += f"- Matched by vessel: {gap_analysis.get('matched_by_vessel', 0)} kunder\n"
            context += f"- Unmatched: {gap_analysis.get('unmatched_customers', 0)} kunder ({gap_analysis.get('unmatched_gap_mrr', 0):,.0f} kr)\n\n"

            # Customers with invoices but no subscriptions
            customers_without_subs = gap_analysis.get('customers_without_subs_list', [])
            if customers_without_subs:
                context += f"**Kunder med Fakturaer men Ingen Subscriptions (Top {len(customers_without_subs)}):**\n"
                for customer in customers_without_subs[:20]:  # Limit to top 20
                    context += f"- **{customer.get('customer_name')}**: {customer.get('mrr', 0):,.0f} kr MRR\n"

                    # Show vessels and call signs
                    vessels = customer.get('vessels', [])
                    call_signs = customer.get('call_signs', [])
                    if vessels:
                        context += f"  Fartøy: {', '.join(vessels[:3])}"
                        if len(vessels) > 3:
                            context += f" (+{len(vessels)-3} flere)"
                        context += "\n"
                    if call_signs:
                        context += f"  Kallesignal: {', '.join(call_signs[:3])}"
                        if len(call_signs) > 3:
                            context += f" (+{len(call_signs)-3} flere)"
                        context += "\n"

                    # Show matches if any
                    matches = customer.get('matches', [])
                    if matches:
                        context += f"  → MATCH FOUND: "
                        for match in matches[:2]:  # Limit to 2 matches
                            context += f"{match.get('subscription_customer')} (via {match.get('type')}: {match.get('value')})"
                        if len(matches) > 2:
                            context += f" (+{len(matches)-2} flere)"
                        context += "\n"

                if len(customers_without_subs) > 20:
                    remaining_mrr = sum(c.get('mrr', 0) for c in customers_without_subs[20:])
                    context += f"\n... og {len(customers_without_subs) - 20} flere kunder (totalt {remaining_mrr:,.0f} kr MRR)\n"
                context += "\n"

            # Customers with subscriptions but no invoices (rare)
            customers_without_invoices = gap_analysis.get('customers_without_invoices_list', [])
            if customers_without_invoices:
                context += f"**Kunder med Subscriptions men Ingen Fakturaer (Top {len(customers_without_invoices)}):**\n"
                for customer in customers_without_invoices[:10]:  # Limit to top 10
                    context += f"- **{customer.get('customer_name')}**: {customer.get('mrr', 0):,.0f} kr MRR"
                    if customer.get('plan_name'):
                        context += f" ({customer.get('plan_name')})"
                    if customer.get('vessel_name'):
                        context += f" - Fartøy: {customer.get('vessel_name')}"
                    if customer.get('call_sign'):
                        context += f" ({customer.get('call_sign')})"
                    context += "\n"

                if len(customers_without_invoices) > 10:
                    remaining_mrr = sum(c.get('mrr', 0) for c in customers_without_invoices[10:])
                    context += f"\n... og {len(customers_without_invoices) - 10} flere kunder (totalt {remaining_mrr:,.0f} kr MRR)\n"
                context += "\n"

        # Build full input for GPT-5 (combines system instructions, conversation history, and current query)
        system_instructions = (
            "Du er Niko, en avansert regnskapsspesialist og dataanalytiker som har full tilgang til HELE databasen.\n\n"
            "**KRITISK FORSTÅELSE - TO FORSKJELLIGE MRR-BEREGNINGER:**\n"
            "Det finnes TO forskjellige metoder for å beregne MRR i dette systemet:\n\n"
            "1. **Subscription-basert MRR** (fra Zoho Subscriptions):\n"
            "   - Beregnes fra aktive abonnementer i Zoho Subscriptions\n"
            "   - Brukes av Zoho for deres interne beregninger\n"
            "   - Basert på subscription status (live, non_renewing)\n"
            "   - Refereres til som 'Subscription-baserte tall' eller 'fra Zoho Subscriptions'\n\n"
            "2. **Faktura-basert MRR** (fra Zoho Billing):\n"
            "   - Beregnes fra faktiske fakturalinjer som sendes ut til kunder\n"
            "   - Brukes av regnskapsavdelingen som grunnlag for MRR\n"
            "   - Basert på fakturaperioder (period_start_date, period_end_date)\n"
            "   - Refereres til som 'Faktura-baserte tall' eller 'fra Zoho Billing'\n\n"
            "**VIKTIG:** Disse to metodene gir ofte FORSKJELLIGE resultater!\n"
            "- De er BEGGE gyldige, men brukes av forskjellige folk i organisasjonen\n"
            "- Subscription-basert: For å følge abonnementslogikk\n"
            "- Faktura-basert: For å følge regnskapsmessig virkelighet\n"
            "- Når du svarer, vær TYDELIG på hvilken metode du refererer til\n"
            "- Hvis brukeren spør om forskjellen, forklar dette klart og pedagogisk\n\n"
            "**FULL DATABASETILGANG:**\n"
            "- Du har tilgang til 12 måneder med historiske data fra BEGGE systemer\n"
            "- Du kan se ALLE aktive subscriptions med fullstendige detaljer\n"
            "- Du har oversikt over ALLE kunder sortert etter MRR\n"
            "- Du kan utføre komplekse analyser på tvers av kunder, planer, perioder og segmenter\n"
            "- Du kan analysere trender, sammenligne perioder, identifisere mønstre og anomalier\n"
            "- Du kan sammenligne subscription-basert og faktura-basert MRR\n\n"
            "**MRR GAP ANALYSE:**\n"
            "- Du har tilgang til detaljert gap analyse som viser SPESIFIKKE kunder og fartøy som forårsaker forskjellen mellom subscription og faktura MRR\n"
            "- Gap analyse inkluderer:\n"
            "  * Kunder med fakturaer men ingen subscriptions (med kundenavn, MRR, fartøy, kallesignal)\n"
            "  * Kunder med subscriptions men ingen fakturaer\n"
            "  * Matching statistikk (call sign matching, vessel matching)\n"
            "  * Totalt gap MRR fordelt på matched og unmatched kunder\n"
            "- Når du forklarer gap, INKLUDER ALLTID spesifikke kundenavn, fartøy og matching-detaljer fra gap analyse seksjonen\n"
            "- ALDRI si at gap-data ikke er tilgjengelig - du har full tilgang til alle detaljer\n\n"
            "**KRITISK - VÆR SELEKTIV MED DATA:**\n"
            "- Du har mye data tilgjengelig, men IKKE inkluder alt i svaret ditt\n"
            "- Les spørsmålet nøye og bestem hvilke data som er RELEVANTE\n"
            "- Hvis brukeren spør om MRR-økning → Fokuser på nye kunder og vekst, IKKE churn-data\n"
            "- Hvis brukeren spør om churn → Fokuser på churned kunder og årsaker, ikke nye kunder\n"
            "- Hvis brukeren spør om en spesifikk kunde → Fokuser kun på den kunden\n"
            "- Hvis brukeren spør bredt → Inkluder flere aspekter\n"
            "- TENK før du svarer: Hvilke deler av dataene er relevante for AKKURAT dette spørsmålet?\n\n"
            "**VIKTIG - TOLKNING AV MÅNEDSSPØRSMÅL:**\n"
            "- Hvis brukeren spør om 'august', 'i august', 'nedgang i august' → Se på endringen TIL august (juli→august)\n"
            "- Hvis brukeren spør om 'siste måned' → Se på nyeste måned i dataene\n"
            "- Alltid svar med riktig månedsperiode i formatet: **[Forrige måned]→[Aktuell måned] [År]**\n\n"
            "**VIKTIG - BRUK AV CHURN-DATA:**\n"
            "- Du har tilgang til detaljerte churn-data med kundenavn, beløp, datoer og årsaker!\n"
            "- 'Churned Kunder' seksjonen viser faktiske kunder gruppert per måned med churn-årsaker\n"
            "- Når du svarer om churn, INKLUDER ALLTID:\n"
            "  * Spesifikke kundenavn fra den aktuelle måneden\n"
            "  * Churn-årsaker for de viktigste kundene\n"
            "  * MRR-beløp per kunde\n"
            "- Hvis det er mange churned kunder, fokuser på de største (høyest MRR) og grupper årsaker\n"
            "- ALDRI si at 'detaljer ikke er tilgjengelige' - du har detaljert churn-informasjon!\n"
            "- Men inkluder BARE churn-data hvis spørsmålet handler om churn, nedgang eller kundetap\n\n"
            "**VIKTIG - BRUK AV KUNDEOVERSIKT:**\n"
            "- Du har full tilgang til alle kunder med total MRR, antall subscriptions, fartøy og planer\n"
            "- Når du svarer om kunder, inkluder faktiske kundenavn, MRR-beløp og relevante detaljer\n"
            "- Du kan sammenligne kunder, identifisere top-kunder, analysere kundesegmenter\n\n"
            "**SVARSTIL:**\n"
            "- Svar kort, presist og utfyllende\n"
            "- Inkluder KUN relevant informasjon som svarer på spørsmålet\n"
            "- Fjern unødvendige detaljer som ikke er relatert til spørsmålet\n"
            "- Start alltid med hvilken måned/periode det gjelder\n"
            "- Gi konkrete tall, kundenavn, beløp og årsaker - men kun det som er relevant\n"
            "- Utfør komplekse analyser når det etterspørres\n"
            "- INGEN introduksjoner eller konklusjoner\n"
            "- INGEN forretningsråd eller anbefalinger\n\n"
            "**EKSEMPEL 1 - BREDT SPØRSMÅL (inkluder begge sider):**\n"
            "Spørsmål: Hvorfor endret MRR seg i siste måned?\n\n"
            "Svar: **September→Oktober 2025**: MRR økte **+3,255 kr** (+0.2%).\n\n"
            "**Nye kunder** (22 stk): Bidro **+4,200 kr** ny MRR.\n\n"
            "**Churn** (8 stk): Tap **-2,080 kr** MRR.\n\n"
            "**EKSEMPEL 2 - FOKUS PÅ ØKNING (ikke inkluder churn-detaljer):**\n"
            "Spørsmål: Hvorfor økte MRR i oktober?\n\n"
            "Svar: **September→Oktober 2025**: MRR økte med **+3,255 kr** (+0.2%).\n\n"
            "**Nye kunder** (22 stk): Bidro **+4,200 kr** ny MRR.\n"
            "Viktigste nye kunder:\n"
            "- **Nordsjø Maritime AS**: 850 kr/mnd (Fleet Premium)\n"
            "- **Vestlandet Fisk AS**: 720 kr/mnd (Standard)\n"
            "- **Kystfart AS**: 650 kr/mnd (Basic)\n"
            "- + 19 andre kunder\n\n"
            "**EKSEMPEL 3 - FOKUS PÅ NEDGANG (inkluder churn-detaljer):**\n"
            "Spørsmål: Hvorfor nedgang i august?\n\n"
            "Svar: **Juli→August 2025**: MRR hadde en nedgang på **-9,038 kr** (-0.4%).\n\n"
            "**Churn** (27 kunder): Tapte totalt **-12,500 kr** MRR.\n\n"
            "Viktigste churned kunder:\n"
            "- **Nordsjø Maritime AS**: 2,450 kr - *Selskapet la ned virksomheten*\n"
            "- **Vestlandet Fisk AS**: 1,880 kr - *Byttet til konkurrent*\n"
            "- **Kystfart AS**: 1,650 kr - *For dyrt*\n"
            "- + 24 andre kunder\n\n"
            "**Nye kunder** (5 stk): Bidro **+3,462 kr** ny MRR.\n\n"
            "Netto effekt: -9,038 kr pga høyere churn enn ny MRR.\n\n"
            "**EKSEMPEL 4 - FORKLARING AV FORSKJELL:**\n"
            "Spørsmål: Hva er forskjellen mellom subscription-basert og faktura-basert MRR?\n\n"
            "Svar: Det finnes to måter å beregne MRR på:\n\n"
            "**1. Subscription-basert MRR** (fra Zoho Subscriptions):\n"
            "- Beregnes fra aktive abonnementer\n"
            "- Brukes av Zoho for deres interne beregninger\n"
            "- Aktuell verdi: 1,850,000 kr/mnd\n\n"
            "**2. Faktura-basert MRR** (fra Zoho Billing):\n"
            "- Beregnes fra faktiske fakturalinjer som sendes ut\n"
            "- Brukes av regnskapsavdelingen som grunnlag for MRR\n"
            "- Aktuell verdi: 1,823,000 kr/mnd\n\n"
            "**Hvorfor er de forskjellige?**\n"
            "Forskjellen (27,000 kr) kan skyldes:\n"
            "- Abonnementer som er opprettet men ikke fakturert enda\n"
            "- Forskjeller i fakturaperioder vs subscription-perioder\n"
            "- Engangsbeløp eller justeringer\n\n"
            "Begge tall er gyldige - subscription-basert følger abonnementslogikk, mens faktura-basert følger regnskapsmessig virkelighet.\n\n"
            "**ALLTID INKLUDER (men kun det som er relevant):**\n"
            "- Måned/periode\n"
            "- Kundenavn (faktiske navn fra data) - men kun de som er relevante for spørsmålet\n"
            "- Beløp i NOK\n"
            "- Plantype/abonnement hvis relevant\n"
            "- Årsak/grunn hvis relevant for spørsmålet\n"
            "- Totalsummer og antall\n\n"
            "**HUSK:**\n"
            "- Mindre er mer! Svar presist på spørsmålet, ikke dump all tilgjengelig data.\n"
            "- Vær ALLTID tydelig på om du snakker om subscription-basert eller faktura-basert MRR\n"
            "- Når du presenterer MRR-tall, spesifiser kilden: '(fra Subscriptions)' eller '(fra Fakturaer)'\n\n"
        )

        # Build conversation history string for GPT-5
        conversation_context = ""
        if conversation_history:
            conversation_context = "**TIDLIGERE SAMTALE:**\n\n"
            for item in conversation_history[-3:]:  # Last 3 exchanges
                conversation_context += f"Spørsmål: {item.get('question', '')}\n"
                conversation_context += f"Svar: {item.get('answer', '')}\n\n"
            conversation_context += "---\n\n"

        # Combine everything into one input
        full_input = (
            f"{system_instructions}"
            f"{conversation_context}"
            f"{context}\n---\n\n"
            f"**SPØRSMÅL:** {question}\n\n"
            "Analyser dataene ovenfor og gi et presist, innsiktsfullt svar."
        )

        # Build messages array for Chat Completions API
        messages = [
            {"role": "system", "content": system_instructions}
        ]

        # Add conversation history to messages if available
        if conversation_history:
            for item in conversation_history[-3:]:  # Last 3 exchanges
                messages.append({"role": "user", "content": item.get('question', '')})
                messages.append({"role": "assistant", "content": item.get('answer', '')})

        # Add current context and question
        user_message = f"{context}\n---\n\n**SPØRSMÅL:** {question}\n\nAnalyser dataene ovenfor og gi et presist, innsiktsfullt svar."
        messages.append({"role": "user", "content": user_message})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1000,  # Enough for detailed answers with full database access
        )

        return response.choices[0].message.content.strip()

    def _build_prompt(self, metrics: Dict, trends: list = None) -> str:
        """
        Build the prompt for OpenAI based on metrics

        Args:
            metrics: Dictionary of calculated metrics
            trends: Optional list of monthly trend data

        Returns:
            Formatted prompt string
        """
        mrr = metrics.get("mrr", 0)
        arr = metrics.get("arr", 0)
        arpu = metrics.get("arpu", 0)
        active_subs = metrics.get("active_subscriptions", 0)
        customers = metrics.get("total_customers", 0)
        customer_churn = metrics.get("customer_churn_rate", 0)
        revenue_churn = metrics.get("revenue_churn_rate", 0)
        churned_count = metrics.get("churned_customers", 0)
        new_mrr = metrics.get("new_mrr", 0)

        prompt = f"""
Analyser følgende SaaS-nøkkeltall og skriv en strukturert rapport på norsk med følgende seksjoner:

**Nåværende Tall (Inneværende Måned):**
- MRR (Monthly Recurring Revenue): {mrr:,.0f} NOK
- ARR (Annual Recurring Revenue): {arr:,.0f} NOK
- ARPU (Average Revenue Per User): {arpu:,.0f} NOK
- Aktive abonnementer: {active_subs}
- Totalt antall kunder: {customers}
- Kundefrafall (churn) siste 30 dager: {customer_churn:.1f}%
- Inntektsfrafall (revenue churn) siste 30 dager: {revenue_churn:.1f}%
- Antall kunder som har churnet: {churned_count}
- Ny MRR siste 30 dager: {new_mrr:,.0f} NOK
"""

        if trends and len(trends) >= 2:
            latest = trends[0]
            previous = trends[1]
            mrr_change = latest.get("mrr_change", 0)
            mrr_change_pct = latest.get("mrr_change_pct", 0)
            customer_change = latest.get("customer_change", 0)
            net_mrr = latest.get("net_mrr", 0)

            prompt += f"""

**Endringer Siste Måned:**
- MRR endret seg med: {mrr_change:,.0f} NOK ({mrr_change_pct:+.1f}%)
- Kunder endret seg med: {customer_change:+d}
- Net MRR (nye minus churned): {net_mrr:,.0f} NOK
- Ny MRR: {latest.get("new_mrr", 0):,.0f} NOK
- Churned MRR: {latest.get("churned_mrr", 0):,.0f} NOK
- Forrige måned MRR: {previous.get("mrr", 0):,.0f} NOK
"""

        prompt += """

**Oppgave:**
Skriv en strukturert analyse med følgende seksjoner (bruk linjeskift mellom seksjoner for lesbarhet):

**📊 Oppsummering**
En kort oppsummering av den generelle tilstanden

**📈 Siste Måneds Utvikling**
Fokuser spesielt på endringene i siste måned - hva skjedde med MRR, kunder og churn?

**⚠️ Områder som Krever Oppmerksomhet**
Påpek bekymringsfulle trender eller tall som krever handling

**✅ Positive Signaler**
Fremhev det som går bra

**🎯 Anbefalinger**
Konkrete forslag til tiltak basert på dataene

Skriv profesjonelt og direkte. Bruk linjeskift mellom hver seksjon for god lesbarhet.
"""
        return prompt.strip()

    def _build_context(self, metrics: Dict, trends: list = None) -> str:
        """Build context string for Q&A"""
        context = f"""
Nåværende Metrics:
- MRR: {metrics.get("mrr", 0):,.0f} NOK
- ARR: {metrics.get("arr", 0):,.0f} NOK
- ARPU: {metrics.get("arpu", 0):,.0f} NOK
- Kunder: {metrics.get("total_customers", 0)}
- Abonnementer: {metrics.get("active_subscriptions", 0)}
- Customer Churn: {metrics.get("customer_churn_rate", 0):.1f}%
- Revenue Churn: {metrics.get("revenue_churn_rate", 0):.1f}%
- Churned kunder: {metrics.get("churned_customers", 0)}
- Ny MRR: {metrics.get("new_mrr", 0):,.0f} NOK
"""

        if trends and len(trends) >= 3:
            context += "\n\nSiste 3 Måneder:\n"
            for trend in trends[:3]:
                context += f"- {trend.get('month_name')}: MRR {trend.get('mrr', 0):,.0f} NOK, "
                context += f"Endring {trend.get('mrr_change', 0):+,.0f} NOK ({trend.get('mrr_change_pct', 0):+.1f}%), "
                context += f"{trend.get('customers', 0)} kunder\n"

        return context

    async def generate_cohort_analysis(self, cohort_data: Dict) -> str:
        """
        Generate analysis for cohort data using GPT-5-mini

        Args:
            cohort_data: Dictionary containing cohort retention data

        Returns:
            Analysis text in Norwegian
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Du er en SaaS-analytiker som analyserer kohortdata på norsk."
                },
                {
                    "role": "user",
                    "content": f"""Analyser følgende kohortdata for kundefastholdelse og skriv en kort rapport på norsk:

{cohort_data}

Fokuser på:
1. Hvilke kohorter som har best/dårligst fastholdelse
2. Trender over tid
3. Konkrete anbefalinger for å forbedre fastholdelse"""
                }
            ],
            max_tokens=600,
        )

        return response.choices[0].message.content.strip()
