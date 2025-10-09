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
