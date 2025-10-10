from openai import AsyncOpenAI
from typing import Dict


class AnalysisService:
    """Service for generating natural language insights using OpenAI"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
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
        conversation_history: list = None
    ) -> str:
        """
        Answer comprehensive questions with full context from all data sources

        Args:
            question: User's question in Norwegian
            subscription_metrics: Subscription-based metrics
            subscription_trends: Subscription trends data
            invoice_metrics: Invoice-based metrics
            invoice_trends: Invoice trends data
            churn_details: Detailed churn information with reasons
            new_customer_details: New customers details
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

        # Subscription trends (siste 4 måneder, nyeste først)
        if subscription_trends and len(subscription_trends) > 0:
            context += "## Subscription Trender (siste 4 måneder)\n"
            # Reverser for å få nyeste først
            recent_trends = list(reversed(subscription_trends))[:4]
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

        # Invoice trends (kun siste 2 måneder, nyeste først)
        if invoice_trends and len(invoice_trends) > 0:
            context += "## Faktura Trender\n"
            # Reverser for å få nyeste først (invoice_trends er allerede sortert desc i app.py)
            recent_invoice_trends = invoice_trends[:2]  # Allerede sortert desc
            for i, trend in enumerate(recent_invoice_trends):
                context += f"**{trend.get('month_name')}:** "
                context += f"MRR {trend.get('mrr', 0):,.0f} kr"
                if trend.get('mrr_change'):
                    context += f" ({trend.get('mrr_change', 0):+,.0f} kr, {trend.get('mrr_change_pct', 0):+.1f}%)"
                context += f", {trend.get('customers', 0)} kunder\n"
            context += "\n"

        # Churn details (kun eksempler på siste churned kunder - IKKE filtrert på måned)
        if churn_details and len(churn_details) > 0:
            context += "## Eksempler på Churned Kunder (siste 5 totalt, IKKE per måned)\n"
            context += "**OBS:** For total churn per måned, bruk tallene fra Subscription Trender ovenfor.\n\n"
            for churn in churn_details[:3]:
                context += f"- **{churn.get('customer_name')}**: {churn.get('amount', 0):,.0f} kr"
                if churn.get('plan_name'):
                    context += f" ({churn.get('plan_name')})"
                if churn.get('reason'):
                    context += f" - {churn.get('reason')}"
                context += "\n"
            context += "\n"

        # New customer details
        if new_customer_details and len(new_customer_details) > 0:
            context += "## Nye Kunder (siste 30d)\n"
            for customer in new_customer_details[:3]:
                context += f"- **{customer.get('customer_name')}**: {customer.get('amount', 0):,.0f} kr"
                if customer.get('plan_name'):
                    context += f" ({customer.get('plan_name')})"
                context += "\n"
            context += "\n"

        # Build messages with conversation history
        messages = [
            {
                "role": "system",
                "content": (
                    "Du er Niko, en regnskapsspesialist som svarer på alle spørsmål om dataene i systemet.\n\n"
                    "**VIKTIG - TOLKNING AV MÅNEDSSPØRSMÅL:**\n"
                    "- Hvis brukeren spør om 'august', 'i august', 'nedgang i august' → Se på endringen TIL august (juli→august)\n"
                    "- Hvis brukeren spør om 'siste måned' → Se på nyeste måned i dataene\n"
                    "- Alltid svar med riktig månedsperiode i formatet: **[Forrige måned]→[Aktuell måned] [År]**\n\n"
                    "**VIKTIG - BRUK AV CHURN-DATA:**\n"
                    "- For totalt antall churned kunder per måned: Bruk 'Churned kunder' fra Subscription Trender\n"
                    "- For total churned MRR per måned: Bruk 'Churned MRR' fra Subscription Trender\n"
                    "- Eksempelkundene under 'Eksempler på Churned Kunder' er KUN illustrasjoner, IKKE komplette tall per måned\n"
                    "- Når du oppgir antall churned kunder, bruk ALLTID tallet fra Subscription Trender\n\n"
                    "**SVARSTIL:**\n"
                    "- Svar kort, presist og utfyllende\n"
                    "- Inkluder detaljert informasjon om kunder og endringer\n"
                    "- Start alltid med hvilken måned/periode det gjelder\n"
                    "- Gi konkrete tall, kundenavn, beløp og årsaker\n"
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
            max_tokens=400,  # Nok rom for detaljer med kundenavn
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
