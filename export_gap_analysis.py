"""
Export gap analysis to Excel file
Generates a detailed Excel report with 3 sheets for easy follow-up
"""

import asyncio
import pandas as pd
from datetime import datetime
from database import AsyncSessionLocal
from services.invoice import InvoiceService
from io import BytesIO


async def export_gap_to_excel(target_month: str) -> BytesIO:
    """
    Generate Excel file with gap analysis details

    Args:
        target_month: Month in YYYY-MM format (e.g., "2025-09")

    Returns:
        BytesIO object containing the Excel file
    """

    async with AsyncSessionLocal() as session:
        invoice_service = InvoiceService(session)
        gap_data = await invoice_service.analyze_mrr_gap(target_month)

        # Create Excel writer
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:

            # Sheet 1: Name Mismatch (fakturaen er under et annet navn, men subscription finnes)
            mismatch_customers = gap_data.get('customers_with_name_mismatch_list', [])
            if mismatch_customers:
                mismatch_data = []
                for customer in mismatch_customers:
                    # Flatten matches for Excel
                    match_info = []
                    for match in customer.get('matches', []):
                        match_info.append(f"{match['subscription_customer']} (via {match['type']}: {match['value']})")

                    mismatch_data.append({
                        'Faktura Kundenavn': customer['customer_name'],
                        'MRR (kr)': customer['mrr'],
                        'Fartøy': ', '.join(customer['vessels']) if customer['vessels'] else '',
                        'Kallesignal': ', '.join(customer['call_signs']) if customer['call_signs'] else '',
                        'Subscription under navnet': '; '.join(match_info) if match_info else ''
                    })

                df_mismatch = pd.DataFrame(mismatch_data)
                df_mismatch.to_excel(writer, sheet_name='Name Mismatch', index=False)

                # Format columns
                worksheet = writer.sheets['Name Mismatch']
                worksheet.column_dimensions['A'].width = 40  # Faktura Kundenavn
                worksheet.column_dimensions['B'].width = 15  # MRR
                worksheet.column_dimensions['C'].width = 20  # Fartøy
                worksheet.column_dimensions['D'].width = 20  # Kallesignal
                worksheet.column_dimensions['E'].width = 60  # Subscription under navnet

            # Sheet 2: Truly Without Subscriptions (faktisk ingen subscription)
            truly_without = gap_data.get('customers_truly_without_subs_list', [])
            # Filter out 0 MRR
            truly_without = [c for c in truly_without if c.get('mrr', 0) > 0]

            if truly_without:
                truly_without_data = []
                for customer in truly_without:
                    truly_without_data.append({
                        'Kundenavn': customer['customer_name'],
                        'MRR (kr)': customer['mrr'],
                        'Fartøy': ', '.join(customer['vessels']) if customer['vessels'] else '',
                        'Kallesignal': ', '.join(customer['call_signs']) if customer['call_signs'] else '',
                        'Status': 'INGEN SUBSCRIPTION FUNNET'
                    })

                df_truly_without = pd.DataFrame(truly_without_data)
                df_truly_without.to_excel(writer, sheet_name='Uten Subscription', index=False)

                # Format columns
                worksheet = writer.sheets['Uten Subscription']
                worksheet.column_dimensions['A'].width = 40  # Kundenavn
                worksheet.column_dimensions['B'].width = 15  # MRR
                worksheet.column_dimensions['C'].width = 20  # Fartøy
                worksheet.column_dimensions['D'].width = 20  # Kallesignal
                worksheet.column_dimensions['E'].width = 30  # Status

            # Sheet 3: Without Invoices (subscription men ingen faktura)
            without_invoices = gap_data.get('customers_without_invoices_list', [])
            if without_invoices:
                without_invoices_data = []
                for customer in without_invoices:
                    without_invoices_data.append({
                        'Kundenavn': customer['customer_name'],
                        'MRR (kr)': customer['mrr'],
                        'Plan': customer.get('plan_name', ''),
                        'Fartøy': customer.get('vessel_name', ''),
                        'Kallesignal': customer.get('call_sign', ''),
                        'Status': 'SUBSCRIPTION FINNES, INGEN FAKTURA'
                    })

                df_without_invoices = pd.DataFrame(without_invoices_data)
                df_without_invoices.to_excel(writer, sheet_name='Uten Faktura', index=False)

                # Format columns
                worksheet = writer.sheets['Uten Faktura']
                worksheet.column_dimensions['A'].width = 40  # Kundenavn
                worksheet.column_dimensions['B'].width = 15  # MRR
                worksheet.column_dimensions['C'].width = 30  # Plan
                worksheet.column_dimensions['D'].width = 20  # Fartøy
                worksheet.column_dimensions['E'].width = 20  # Kallesignal
                worksheet.column_dimensions['F'].width = 40  # Status

            # Sheet 4: Summary
            summary_data = [
                {'Kategori': 'Kunder med kundenavn-mismatch (subscription finnes)', 'Antall': gap_data.get('customers_with_name_mismatch', 0), 'MRR (kr)': gap_data.get('matched_gap_mrr', 0)},
                {'Kategori': 'Kunder faktisk uten subscription', 'Antall': gap_data.get('customers_truly_without_subs', 0), 'MRR (kr)': gap_data.get('unmatched_gap_mrr', 0)},
                {'Kategori': 'Kunder med subscription men ingen faktura', 'Antall': gap_data.get('customers_without_invoices', 0), 'MRR (kr)': '(subscription MRR)'},
                {'Kategori': '', 'Antall': '', 'MRR (kr)': ''},
                {'Kategori': 'Total gap MRR (truly unmatched)', 'Antall': '', 'MRR (kr)': gap_data.get('total_gap_mrr', 0)},
                {'Kategori': 'Matched gap MRR (name mismatch)', 'Antall': '', 'MRR (kr)': gap_data.get('matched_gap_mrr', 0)},
                {'Kategori': '', 'Antall': '', 'MRR (kr)': ''},
                {'Kategori': '⚠️ Kreditterte fakturaer (ekskludert fra analysen)', 'Antall': gap_data.get('credited_invoices_count', 0), 'MRR (kr)': 'Utelatt fra gap'},
            ]

            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='Oversikt', index=False)

            # Format columns
            worksheet = writer.sheets['Oversikt']
            worksheet.column_dimensions['A'].width = 60  # Kategori
            worksheet.column_dimensions['B'].width = 15  # Antall
            worksheet.column_dimensions['C'].width = 20  # MRR

        output.seek(0)
        return output


async def main():
    """Test export for current month"""
    current_month = datetime.utcnow().strftime("%Y-%m")
    print(f"Exporting gap analysis for {current_month}...")

    excel_file = await export_gap_to_excel(current_month)

    # Save to file
    filename = f"gap_analysis_{current_month}.xlsx"
    with open(filename, 'wb') as f:
        f.write(excel_file.read())

    print(f"Exported to {filename}")


if __name__ == "__main__":
    asyncio.run(main())
