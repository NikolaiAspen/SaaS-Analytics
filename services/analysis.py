from openai import AsyncOpenAI
from typing import Dict


class AnalysisService:
    """Service for generating natural language insights using OpenAI"""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_analysis(self, metrics: Dict, trends: list = None) -> str:
        """
        Generate natural language analysis of metrics in Norwegian

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
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        return response.choices[0].message.content.strip()

    async def ask_question(self, question: str, metrics: Dict, trends: list = None) -> str:
        """
        Answer a specific question about the metrics data

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
                    ),
                },
                {
                    "role": "user",
                    "content": f"Her er dataene:\n\n{context}\n\nSpørsmål: {question}"
                },
            ],
            temperature=0.7,
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

        # Build messages with conversation history
        messages = [
            {
                "role": "system",
                "content": (
                    "Du er Niko, en avansert regnskapsspesialist og dataanalytiker som har full tilgang til HELE databasen.\n\n"
                    "**FULL DATABASETILGANG:**\n"
                    "- Du har tilgang til 12 måneder med historiske data\n"
                    "- Du kan se ALLE aktive subscriptions med fullstendige detaljer\n"
                    "- Du har oversikt over ALLE kunder sortert etter MRR\n"
                    "- Du kan utføre komplekse analyser på tvers av kunder, planer, perioder og segmenter\n"
                    "- Du kan analysere trender, sammenligne perioder, identifisere mønstre og anomalier\n\n"
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
                    "- ALDRI si at 'detaljer ikke er tilgjengelige' - du har detaljert churn-informasjon!\n\n"
                    "**VIKTIG - BRUK AV KUNDEOVERSIKT:**\n"
                    "- Du har full tilgang til alle kunder med total MRR, antall subscriptions, fartøy og planer\n"
                    "- Når du svarer om kunder, inkluder faktiske kundenavn, MRR-beløp og relevante detaljer\n"
                    "- Du kan sammenligne kunder, identifisere top-kunder, analysere kundesegmenter\n\n"
                    "**SVARSTIL:**\n"
                    "- Svar kort, presist og utfyllende\n"
                    "- Inkluder detaljert informasjon om kunder og endringer\n"
                    "- Start alltid med hvilken måned/periode det gjelder\n"
                    "- Gi konkrete tall, kundenavn, beløp og årsaker\n"
                    "- Utfør komplekse analyser når det etterspørres\n"
                    "- INGEN introduksjoner eller konklusjoner\n"
                    "- INGEN forretningsråd eller anbefalinger\n\n"
                    "**EKSEMPEL 1:**\n"
                    "Spørsmål: Hvorfor endret MRR seg i siste måned?\n\n"
                    "Svar: **September→Oktober 2025**: MRR økte **+3,255 kr** (+0.2%).\n\n"
                    "**Nye kunder** (22 stk): Bidro **+4,200 kr** ny MRR.\n\n"
                    "**Churn** (8 stk): Tap **-2,080 kr** MRR.\n\n"
                    "**EKSEMPEL 2:**\n"
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
                    "**ALLTID INKLUDER:**\n"
                    "- Måned/periode\n"
                    "- Kundenavn (faktiske navn fra data)\n"
                    "- Beløp i NOK\n"
                    "- Plantype/abonnement hvis tilgjengelig\n"
                    "- Årsak/grunn hvis tilgjengelig\n"
                    "- Totalsummer og antall"
                )
            }
        ]

        # Add conversation history for context
        if conversation_history:
            for item in conversation_history[-3:]:  # Last 3 exchanges
                messages.append({"role": "user", "content": item.get("question", "")})
                messages.append({"role": "assistant", "content": item.get("answer", "")})

        # Add current question with full context
        messages.append({
            "role": "user",
            "content": f"{context}\n---\n\n**SPØRSMÅL:** {question}\n\nAnalyser dataene ovenfor og gi et presist, innsiktsfullt svar."
        })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1000,  # Økt kapasitet for komplekse analyser med full database
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
        Generate analysis for cohort data

        Args:
            cohort_data: Dictionary containing cohort retention data

        Returns:
            Analysis text in Norwegian
        """
        prompt = f"""
Analyser følgende kohortdata for kundefastholdelse og skriv en kort rapport på norsk:

{cohort_data}

Fokuser på:
1. Hvilke kohorter som har best/dårligst fastholdelse
2. Trender over tid
3. Konkrete anbefalinger for å forbedre fastholdelse
"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Du er en SaaS-analytiker som analyserer kohortdata på norsk.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=600,
        )

        return response.choices[0].message.content.strip()
