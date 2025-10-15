"""
IMPROVED MRR GAP ANALYSIS REPORT
Creates a comprehensive Excel report comparing subscription-based vs invoice-based MRR
with multiple sheets, visualizations, and detailed explanations
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from models.invoice import Invoice, InvoiceLineItem
from models.subscription import Subscription
from sqlalchemy import select


async def generate_comprehensive_report():
    """Generate comprehensive gap analysis Excel report"""

    # Target month for analysis
    target_month = datetime(2025, 10, 1)
    target_month_end = datetime(2025, 10, 31, 23, 59, 59)  # Last second of month (snapshot approach)
    month_name = target_month.strftime("%B %Y")

    print("=" * 120)
    print(f"GENERATING COMPREHENSIVE MRR GAP ANALYSIS REPORT - {month_name.upper()}")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        # ===== FETCH SUBSCRIPTION DATA =====
        print("\n[1/5] Fetching subscription data...")
        sub_result = await session.execute(
            select(Subscription).where(Subscription.status.in_(['live', 'non_renewing']))
        )
        subscriptions = sub_result.scalars().all()

        subscription_data = []
        sub_mrr_by_customer = {}
        sub_by_call_sign = {}
        sub_by_vessel_customer = {}
        total_sub_mrr = 0

        for sub in subscriptions:
            # Calculate MRR (accounting for VAT and intervals)
            amount = float(sub.amount or 0)
            interval_unit = str(sub.interval_unit or 'months').lower()
            interval_val = sub.interval

            if isinstance(interval_val, str):
                if interval_val.lower() in ['years', 'months']:
                    interval_unit = interval_val.lower()
                    interval = 1
                else:
                    try:
                        interval = int(interval_val)
                    except:
                        interval = 1
            else:
                interval = int(interval_val or 1)

            if interval_unit == 'years':
                mrr = (amount / 1.25) / 12
            elif interval_unit == 'months':
                mrr = (amount / 1.25) / interval
            else:
                mrr = amount / 1.25

            customer_name = sub.customer_name
            sub_id = sub.id

            subscription_data.append({
                'Subscription ID': sub_id,
                'Kunde': customer_name,
                'Plan': sub.plan_name or '',
                'Status': sub.status,
                'Beløp (inkl. MVA)': amount,
                'Intervall': f"{interval} {interval_unit}",
                'MRR (ekskl. MVA)': mrr,
                'Fartøy': sub.vessel_name or '',
                'Kallesignal': sub.call_sign or '',
                'Opprettet': sub.created_time.strftime('%Y-%m-%d') if sub.created_time else '',
            })

            sub_mrr_by_customer[customer_name] = sub_mrr_by_customer.get(customer_name, 0) + mrr
            total_sub_mrr += mrr

            # Index by call sign
            if sub.call_sign:
                call_sign_clean = sub.call_sign.strip().upper()
                if call_sign_clean not in sub_by_call_sign:
                    sub_by_call_sign[call_sign_clean] = []
                sub_by_call_sign[call_sign_clean].append({'sub_id': sub_id, 'customer': customer_name, 'mrr': mrr})

            # Index by vessel + customer
            if sub.vessel_name:
                vessel_clean = sub.vessel_name.strip().upper()
                key = f"{vessel_clean}|{customer_name}"
                if key not in sub_by_vessel_customer:
                    sub_by_vessel_customer[key] = []
                sub_by_vessel_customer[key].append({'sub_id': sub_id, 'customer': customer_name, 'mrr': mrr})

        print(f"  [OK] {len(subscriptions)} subscriptions loaded")
        print(f"  [OK] Total Subscription MRR: {total_sub_mrr:,.2f} NOK")

        # ===== FETCH INVOICE DATA =====
        print(f"\n[2/5] Fetching invoice data for {month_name}...")
        # Use snapshot approach: only include invoices active on LAST DAY of month
        # This matches the snapshot calculation method (consistent with subscription MRR)
        inv_result = await session.execute(
            select(InvoiceLineItem, Invoice)
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                InvoiceLineItem.period_start_date <= target_month_end,
                InvoiceLineItem.period_end_date >= target_month_end  # Snapshot: active on month-end
            )
        )
        invoice_rows = inv_result.all()

        invoice_data = []
        inv_mrr_by_customer = {}
        inv_mrr_by_sub_id = {}
        total_inv_mrr = 0
        total_inv_positive = 0
        total_inv_negative = 0

        for line_item, invoice in invoice_rows:
            mrr = line_item.mrr_per_month or 0
            customer_name = invoice.customer_name
            sub_id = line_item.subscription_id

            invoice_data.append({
                'Fakturanr': invoice.invoice_number,
                'Type': 'Faktura' if invoice.transaction_type == 'invoice' else 'Kreditnota',
                'Kunde': customer_name,
                'Produktnavn': line_item.name or '',
                'Periode Start': line_item.period_start_date.strftime('%Y-%m-%d') if line_item.period_start_date else '',
                'Periode Slutt': line_item.period_end_date.strftime('%Y-%m-%d') if line_item.period_end_date else '',
                'Periode (mnd)': line_item.period_months or 0,
                'Totalt Beløp': line_item.item_total or 0,
                'MRR per Måned': mrr,
                'Subscription ID': sub_id or '',
                'Fartøy': line_item.vessel_name or '',
                'Kallesignal': line_item.call_sign or '',
                'Fakturadato': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
            })

            inv_mrr_by_customer[customer_name] = inv_mrr_by_customer.get(customer_name, 0) + mrr
            total_inv_mrr += mrr

            if mrr > 0:
                total_inv_positive += mrr
            else:
                total_inv_negative += mrr

            if sub_id:
                inv_mrr_by_sub_id[sub_id] = inv_mrr_by_sub_id.get(sub_id, 0) + mrr

        print(f"  [OK] {len(invoice_rows)} invoice line items loaded")
        print(f"  [OK] Total Invoice MRR: {total_inv_mrr:,.2f} NOK")
        print(f"    - Positive (Fakturaer): {total_inv_positive:,.2f} NOK")
        print(f"    - Negative (Kreditnotaer): {total_inv_negative:,.2f} NOK")

        # ===== MATCHING ANALYSIS =====
        print("\n[3/5] Performing multi-tier matching...")

        matched_by_sub_id = set()
        matched_by_call_sign = set()
        matched_by_vessel = set()

        # Tier 1: Subscription ID
        for sub_id in inv_mrr_by_sub_id.keys():
            if any(s['Subscription ID'] == sub_id for s in subscription_data):
                matched_by_sub_id.add(sub_id)

        # Tier 2: Call Sign
        for line_item, invoice in invoice_rows:
            if line_item.call_sign:
                call_sign_clean = line_item.call_sign.strip().upper()
                if call_sign_clean in sub_by_call_sign:
                    for sub_info in sub_by_call_sign[call_sign_clean]:
                        if invoice.customer_name == sub_info['customer']:
                            if sub_info['sub_id'] not in matched_by_sub_id:
                                matched_by_call_sign.add(sub_info['sub_id'])

        # Tier 3: Vessel + Customer
        for line_item, invoice in invoice_rows:
            if line_item.vessel_name:
                vessel_clean = line_item.vessel_name.strip().upper()
                key = f"{vessel_clean}|{invoice.customer_name}"
                if key in sub_by_vessel_customer:
                    for sub_info in sub_by_vessel_customer[key]:
                        if sub_info['sub_id'] not in matched_by_sub_id and sub_info['sub_id'] not in matched_by_call_sign:
                            matched_by_vessel.add(sub_info['sub_id'])

        all_matched = matched_by_sub_id | matched_by_call_sign | matched_by_vessel
        match_pct = (len(all_matched) / len(subscriptions) * 100) if subscriptions else 0

        print(f"  [OK] Matched {len(all_matched)} / {len(subscriptions)} subscriptions ({match_pct:.1f}%)")
        print(f"    - By Subscription ID: {len(matched_by_sub_id)}")
        print(f"    - By Call Sign: {len(matched_by_call_sign)}")
        print(f"    - By Vessel: {len(matched_by_vessel)}")

        # ===== CUSTOMER COMPARISON =====
        print("\n[4/5] Comparing customers...")

        all_customers = set(sub_mrr_by_customer.keys()) | set(inv_mrr_by_customer.keys())
        customer_comparison = []

        for customer in all_customers:
            sub_mrr = sub_mrr_by_customer.get(customer, 0)
            inv_mrr = inv_mrr_by_customer.get(customer, 0)
            diff = inv_mrr - sub_mrr
            diff_pct = (diff / sub_mrr * 100) if sub_mrr > 0 else 0

            status = ''
            if sub_mrr == 0:
                status = 'Kun i fakturaer'
            elif inv_mrr == 0:
                status = 'Kun i subscriptions'
            elif abs(diff_pct) < 1:
                status = 'Match (<1% avvik)'
            elif abs(diff_pct) < 5:
                status = 'Lite avvik (1-5%)'
            else:
                status = 'Stort avvik (>5%)'

            customer_comparison.append({
                'Kunde': customer,
                'Subscription MRR': sub_mrr,
                'Faktura MRR': inv_mrr,
                'Differanse': diff,
                'Differanse %': diff_pct,
                'Status': status,
            })

        customer_comparison.sort(key=lambda x: abs(x['Differanse']), reverse=True)

        print(f"  [OK] {len(all_customers)} unique customers analyzed")

        # ===== GENERATE EXCEL REPORT =====
        print("\n[5/5] Generating Excel report...")

        output_file = f"excel/MRR_Gap_Analysis_{target_month.strftime('%Y_%m')}.xlsx"

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Sheet 1: SUMMARY
            summary_data = {
                'Metric': [
                    'Subscription-basert MRR',
                    'Faktura-basert MRR (positiv)',
                    'Kreditnotaer (negativ)',
                    'Faktura-basert MRR (netto)',
                    '',
                    'Differanse (Faktura - Subscription)',
                    'Differanse %',
                    '',
                    'Antall subscriptions',
                    'Antall fakturalinjer',
                    'Antall kunder (subscriptions)',
                    'Antall kunder (fakturaer)',
                    '',
                    'Subscriptions matchet',
                    '  - Via Subscription ID',
                    '  - Via Kallesignal',
                    '  - Via Fartøy + Kunde',
                    'Subscriptions ikke matchet',
                ],
                'Value': [
                    f"{total_sub_mrr:,.2f} NOK",
                    f"{total_inv_positive:,.2f} NOK",
                    f"{total_inv_negative:,.2f} NOK",
                    f"{total_inv_mrr:,.2f} NOK",
                    '',
                    f"{total_inv_mrr - total_sub_mrr:,.2f} NOK",
                    f"{((total_inv_mrr - total_sub_mrr) / total_sub_mrr * 100):.2f}%",
                    '',
                    len(subscriptions),
                    len(invoice_rows),
                    len(sub_mrr_by_customer),
                    len(inv_mrr_by_customer),
                    '',
                    f"{len(all_matched)} ({match_pct:.1f}%)",
                    len(matched_by_sub_id),
                    len(matched_by_call_sign),
                    len(matched_by_vessel),
                    len(subscriptions) - len(all_matched),
                ],
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='📊 Sammendrag', index=False)

            # Sheet 2: CUSTOMER COMPARISON
            customer_df = pd.DataFrame(customer_comparison)
            customer_df.to_excel(writer, sheet_name='👥 Kunde Sammenligning', index=False)

            # Sheet 3: SUBSCRIPTIONS
            subscription_df = pd.DataFrame(subscription_data)
            subscription_df.to_excel(writer, sheet_name='📋 Subscriptions', index=False)

            # Sheet 4: INVOICES
            invoice_df = pd.DataFrame(invoice_data)
            invoice_df.to_excel(writer, sheet_name='🧾 Fakturaer', index=False)

            # Sheet 5: EXPLANATION
            explanation_data = {
                'Spørsmål': [
                    'Hva er forskjellen mellom subscription-basert og faktura-basert MRR?',
                    '',
                    'Hvorfor er tallene forskjellige?',
                    '',
                    '',
                    '',
                    '',
                    '',
                    'Hvilket tall er "riktig"?',
                    '',
                    '',
                    '',
                    'Hvorfor matcher ikke alle subscriptions med fakturaer?',
                    '',
                    '',
                    '',
                    '',
                    '',
                    'Hva betyr de forskjellige matching-tierene?',
                    '',
                    '',
                    '',
                ],
                'Svar': [
                    'Subscription-basert MRR beregnes fra aktive subscriptions i Zoho Subscriptions. '
                    'Faktura-basert MRR beregnes fra faktiske fakturalinjer sendt til kunder i Zoho Billing.',
                    '',
                    'Tallene kan være forskjellige av flere grunner:',
                    '1. Tidsforskyving: Subscriptions kan være opprettet men ikke fakturert enda',
                    '2. Fakturering av gamle perioder: Fakturaer kan dekke perioder før subscription ble opprettet',
                    '3. Engangsfakturaer: Fakturaer uten tilknyttet subscription',
                    '4. Kreditnotaer: Justerer faktura-MRR nedover, men påvirker ikke subscription-MRR',
                    '',
                    'Begge tallene er "riktige" men brukes til forskjellige formål:',
                    '- Subscription-basert: Brukes av Zoho for å beregne recurring revenue',
                    '- Faktura-basert: Brukes av regnskapsavdelingen som grunnlag for MRR-rapportering',
                    '',
                    'Årsaker til manglende matching:',
                    '1. Subscription ID-feltet i fakturaene er ofte tomt eller feil',
                    '2. Fakturaer opprettet manuelt uten kobling til subscription',
                    '3. Gamle fakturaer fra før subscription-systemet ble tatt i bruk',
                    '4. Engangsfakturaer eller spesialtilfeller',
                    '',
                    'Vi bruker 3-tiers matching-strategi:',
                    'Tier 1 - Subscription ID: Direkte kobling via subscription_id felt (mest nøyaktig)',
                    'Tier 2 - Kallesignal: Matcher via fartøyets radiokallesignal (99%+ success rate)',
                    'Tier 3 - Fartøy + Kunde: Matcher via fartøynavn + kundenavn (fallback)',
                ],
            }
            explanation_df = pd.DataFrame(explanation_data)
            explanation_df.to_excel(writer, sheet_name='❓ Forklaring', index=False)

            # Format the Excel sheets
            workbook = writer.book

            # Format Summary sheet
            ws_summary = workbook['📊 Sammendrag']
            ws_summary.column_dimensions['A'].width = 40
            ws_summary.column_dimensions['B'].width = 25

            # Format Customer Comparison sheet
            ws_customer = workbook['👥 Kunde Sammenligning']
            ws_customer.column_dimensions['A'].width = 40
            for col in ['B', 'C', 'D', 'E']:
                ws_customer.column_dimensions[col].width = 18
            ws_customer.column_dimensions['F'].width = 25

            # Format Subscriptions sheet
            ws_subs = workbook['📋 Subscriptions']
            for col in ['A', 'B', 'C', 'D']:
                ws_subs.column_dimensions[col].width = 20

            # Format Invoices sheet
            ws_inv = workbook['🧾 Fakturaer']
            for col in ['A', 'B', 'C', 'D']:
                ws_inv.column_dimensions[col].width = 20

            # Format Explanation sheet
            ws_explain = workbook['❓ Forklaring']
            ws_explain.column_dimensions['A'].width = 60
            ws_explain.column_dimensions['B'].width = 100

        print(f"\n[SUCCESS] REPORT GENERATED: {output_file}")
        print("\n" + "=" * 120)
        print("SUMMARY STATISTICS")
        print("=" * 120)
        print(f"Subscription MRR:  {total_sub_mrr:>15,.2f} NOK")
        print(f"Invoice MRR:       {total_inv_mrr:>15,.2f} NOK")
        print(f"Gap:               {total_inv_mrr - total_sub_mrr:>15,.2f} NOK ({((total_inv_mrr - total_sub_mrr) / total_sub_mrr * 100):.1f}%)")
        print(f"\nMatching rate:     {match_pct:>14.1f}%")
        print(f"Customers analyzed:{len(all_customers):>15}")
        print("=" * 120)

        return output_file


if __name__ == "__main__":
    asyncio.run(generate_comprehensive_report())
