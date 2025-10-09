"""
Service for importing Zoho MRR reports to create accurate historical snapshots
"""
import pandas as pd
from typing import List, Dict
from datetime import datetime


class ZohoReportImporter:
    """Import Zoho MRR Excel reports"""

    @staticmethod
    def import_monthly_mrr_report(file_path: str) -> List[Dict]:
        """
        Import Zoho's Monthly MRR report from Excel

        Args:
            file_path: Path to the Excel file

        Returns:
            List of monthly MRR data dictionaries
        """
        try:
            # Read Excel file, skip the header row
            df = pd.read_excel(file_path, skiprows=1)

            # The columns should be something like:
            # date, col2, col3, col4, col5, col6, col7, col8, net_mrr
            # We need to identify the date and MRR columns

            # Try to find date column
            date_col = None
            mrr_col = None

            for col in df.columns:
                col_lower = str(col).lower()
                if 'date' in col_lower or df[col].dtype == 'datetime64[ns]':
                    date_col = col
                elif 'mrr' in col_lower or 'net_mrr' in col_lower:
                    mrr_col = col

            if date_col is None:
                # First column is likely the date
                date_col = df.columns[0]

            if mrr_col is None:
                # Last column is likely the MRR
                mrr_col = df.columns[-1]

            # Clean the data
            df = df[[date_col, mrr_col]].copy()
            df.columns = ['date', 'mrr']

            # Convert to proper types
            df['date'] = pd.to_datetime(df['date'])
            df['mrr'] = pd.to_numeric(df['mrr'], errors='coerce')

            # Remove rows with NaN
            df = df.dropna()

            # Convert to list of dictionaries
            result = []
            for _, row in df.iterrows():
                result.append({
                    'month': row['date'].strftime('%Y-%m'),
                    'month_name': row['date'].strftime('%B %Y'),
                    'mrr': float(row['mrr']),
                    'date': row['date'],
                })

            return result

        except Exception as e:
            raise Exception(f"Failed to import Zoho MRR report: {str(e)}")

    @staticmethod
    def import_mrr_details_report(file_path: str, month: str = None) -> Dict:
        """
        Import Zoho's MRR Details report (subscription-level data) from Excel
        This is the most accurate source - it shows exactly what Zoho counts as MRR for that month

        Args:
            file_path: Path to the Excel file
            month: Optional month string (YYYY-MM), if not provided will extract from file

        Returns:
            Dictionary with month and subscription details matching Zoho exactly
        """
        try:
            # Read Excel file, skip the header row
            df = pd.read_excel(file_path, skiprows=1)

            print(f"Imported {len(df)} rows from Zoho MRR Details report")

            # Get the month from the first date or use provided month
            if month is None:
                if 'date' in df.columns:
                    first_date = pd.to_datetime(df['date'].iloc[0])
                    month = first_date.strftime('%Y-%m')
                else:
                    # Try first column
                    first_date = pd.to_datetime(df[df.columns[0]].iloc[0])
                    month = first_date.strftime('%Y-%m')

            # Calculate total MRR (this is already excluding VAT from Zoho)
            mrr_col = None
            for col in df.columns:
                if 'mrr' in str(col).lower() and 'customer' not in str(col).lower():
                    mrr_col = col
                    break

            if mrr_col is None:
                # Last column is likely MRR
                mrr_col = df.columns[-1]

            df['mrr'] = pd.to_numeric(df[mrr_col], errors='coerce')
            total_mrr = df['mrr'].sum()

            # Count subscriptions
            subscription_count = len(df)

            # Count unique customers
            customer_col = None
            for col in df.columns:
                if 'customer' in str(col).lower() and 'id' in str(col).lower():
                    customer_col = col
                    break

            if customer_col:
                customer_count = df[customer_col].nunique()
            else:
                # Estimate based on subscription count
                customer_count = int(subscription_count * 0.85)

            # Calculate ARPU
            arpu = total_mrr / customer_count if customer_count > 0 else 0

            print(f"Month: {month}")
            print(f"Total MRR: {total_mrr:,.2f} NOK")
            print(f"Subscriptions: {subscription_count}")
            print(f"Customers: {customer_count}")
            print(f"ARPU: {arpu:,.2f} NOK")

            return {
                'month': month,
                'mrr': float(total_mrr),
                'subscription_count': subscription_count,
                'customer_count': customer_count,
                'arpu': float(arpu),
            }

        except Exception as e:
            raise Exception(f"Failed to import Zoho MRR Details report: {str(e)}")

    @staticmethod
    def calculate_new_mrr(current_file_path: str, previous_file_path: str) -> Dict:
        """
        Calculate New MRR by comparing two MRR Details files
        New MRR = MRR from subscriptions that exist in current month but NOT in previous month

        Args:
            current_file_path: Path to current month's MRR Details Excel file
            previous_file_path: Path to previous month's MRR Details Excel file

        Returns:
            Dictionary with month, new_mrr, and new subscription details
        """
        try:
            # Read both files
            current_df = pd.read_excel(current_file_path, skiprows=1)
            previous_df = pd.read_excel(previous_file_path, skiprows=1)

            # Get month from current file
            current_date = pd.to_datetime(current_df['date'].iloc[0])
            month = current_date.strftime('%Y-%m')

            # Find subscriptions in current that are NOT in previous
            previous_subs = set(previous_df['subscription_id'].tolist())
            current_subs = set(current_df['subscription_id'].tolist())
            new_subs = current_subs - previous_subs

            # Calculate New MRR from new subscriptions
            new_mrr_df = current_df[current_df['subscription_id'].isin(new_subs)]
            new_mrr = new_mrr_df['mrr'].sum()

            # Get details of new subscriptions
            new_subscription_details = []
            for _, row in new_mrr_df.iterrows():
                new_subscription_details.append({
                    'subscription_id': str(row['subscription_id']),
                    'customer_name': str(row['customer_name']) if pd.notna(row['customer_name']) else None,
                    'plan_name': str(row['plan_name']) if pd.notna(row['plan_name']) else None,
                    'mrr': float(row['mrr']) if pd.notna(row['mrr']) else 0.0,
                })

            print(f"Month: {month}")
            print(f"New Subscriptions: {len(new_subs)}")
            print(f"New MRR: {new_mrr:,.2f} NOK")

            return {
                'month': month,
                'new_subscriptions': len(new_subs),
                'new_mrr': float(new_mrr),
                'new_subscription_details': new_subscription_details,
            }

        except Exception as e:
            raise Exception(f"Failed to calculate New MRR: {str(e)}")

    @staticmethod
    def import_churn_report(file_path: str, month: str = None) -> Dict:
        """
        Import Zoho's Churn report from Excel

        Args:
            file_path: Path to the Excel file
            month: Optional month string (YYYY-MM), if not provided will extract from file

        Returns:
            Dictionary with month, churned customers count, and churned MRR
        """
        try:
            # Read Excel file, skip the header row
            df = pd.read_excel(file_path, skiprows=1)

            print(f"Imported {len(df)} churned records from Zoho Churn report")

            # Handle empty file (no churn for this month)
            if len(df) == 0:
                print("Empty churn report - no churned customers for this month")
                # Try to extract month from filename if not provided
                if month is None:
                    import re
                    import os
                    filename = os.path.basename(file_path)
                    # Try to find month pattern like "Sept25", "March25", "ChurnMarch25", etc
                    # Match full month names or abbreviations followed by 2-digit year
                    month_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(\d{2})', filename.lower())
                    if month_match:
                        month_name = month_match.group(1)
                        year = f"20{month_match.group(2)}"

                        # Map month names to numbers
                        month_map = {
                            'january': '01', 'jan': '01',
                            'february': '02', 'feb': '02',
                            'march': '03', 'mar': '03',
                            'april': '04', 'apr': '04',
                            'may': '05',
                            'june': '06', 'jun': '06',
                            'july': '07', 'jul': '07',
                            'august': '08', 'aug': '08',
                            'september': '09', 'sep': '09', 'sept': '09',
                            'october': '10', 'oct': '10',
                            'november': '11', 'nov': '11',
                            'december': '12', 'dec': '12'
                        }
                        month = f"{year}-{month_map[month_name]}"
                    else:
                        raise Exception(f"Cannot determine month from empty file '{filename}'. Filename should contain month and year (e.g., 'ChurnMarch25.xlsx')")

                return {
                    'month': month,
                    'churned_customers': 0,
                    'churned_mrr': 0.0,
                    'churn_details': [],
                }

            # Get the month from the first date or use provided month
            # First, find the date column (needed for both month extraction and detail records)
            date_col = None
            for col in df.columns:
                col_lower = str(col).lower()
                if 'date' in col_lower or 'cancelled' in col_lower or df[col].dtype == 'datetime64[ns]':
                    date_col = col
                    break

            if month is None:
                if date_col is None:
                    # Try first column
                    date_col = df.columns[0]

                first_date = pd.to_datetime(df[date_col].iloc[0])
                month = first_date.strftime('%Y-%m')

            # Count churned customers (unique customer IDs)
            customer_col = None
            for col in df.columns:
                if 'customer' in str(col).lower() and 'id' in str(col).lower():
                    customer_col = col
                    break

            if customer_col:
                churned_customers = df[customer_col].nunique()
            else:
                # If no customer ID, count rows (assuming one row per customer)
                churned_customers = len(df)

            # Calculate churned MRR
            # Look for MRR or amount column
            mrr_col = None
            for col in df.columns:
                col_lower = str(col).lower()
                if 'mrr' in col_lower or 'amount' in col_lower:
                    mrr_col = col
                    break

            if mrr_col:
                df['churned_amount'] = pd.to_numeric(df[mrr_col], errors='coerce')
                # Sum the amounts - this is the total MRR lost from churned customers
                churned_mrr = df['churned_amount'].sum()
            else:
                # If no MRR/amount column, set to 0
                churned_mrr = 0.0

            print(f"Month: {month}")
            print(f"Churned Customers: {churned_customers}")
            print(f"Churned MRR: {churned_mrr:,.2f} NOK")

            # Extract detailed churn records
            churn_details = []

            # date_col is already found above
            for _, row in df.iterrows():
                # Find columns
                cust_id_col = next((col for col in df.columns if 'customer' in str(col).lower() and 'id' in str(col).lower()), None)
                cust_name_col = next((col for col in df.columns if 'customer' in str(col).lower() and 'name' in str(col).lower()), None)
                cust_email_col = next((col for col in df.columns if 'email' in str(col).lower()), None)
                sub_id_col = next((col for col in df.columns if 'subscription' in str(col).lower() and 'id' in str(col).lower()), None)
                plan_col = next((col for col in df.columns if 'plan' in str(col).lower()), None)
                reason_col = next((col for col in df.columns if 'reason' in str(col).lower()), None)
                ltv_col = next((col for col in df.columns if 'ltv' in str(col).lower()), None)
                ltd_col = next((col for col in df.columns if 'ltd' in str(col).lower()), None)

                # Get raw amount and plan name
                raw_amount = float(row[mrr_col]) if mrr_col and pd.notna(row[mrr_col]) else 0.0
                plan_name = str(row[plan_col]) if plan_col and pd.notna(row[plan_col]) else None

                # Normalize to MRR - if plan name contains "(år)" or "(year)", divide by 12
                mrr_amount = raw_amount
                if plan_name and ('(år)' in plan_name.lower() or '(year)' in plan_name.lower()):
                    mrr_amount = raw_amount / 12

                churn_details.append({
                    'customer_id': str(row[cust_id_col]) if cust_id_col and pd.notna(row[cust_id_col]) else None,
                    'customer_name': str(row[cust_name_col]) if cust_name_col and pd.notna(row[cust_name_col]) else None,
                    'customer_email': str(row[cust_email_col]) if cust_email_col and pd.notna(row[cust_email_col]) else None,
                    'subscription_id': str(row[sub_id_col]) if sub_id_col and pd.notna(row[sub_id_col]) else None,
                    'plan_name': plan_name,
                    'amount': mrr_amount,  # Now properly normalized to MRR
                    'cancellation_reason': str(row[reason_col]) if reason_col and pd.notna(row[reason_col]) else None,
                    'cancelled_date': pd.to_datetime(row[date_col]) if date_col and pd.notna(row[date_col]) else None,
                    'ltv': float(row[ltv_col]) if ltv_col and pd.notna(row[ltv_col]) else None,
                    'ltd': int(row[ltd_col]) if ltd_col and pd.notna(row[ltd_col]) else None,
                })

            # Recalculate churned_mrr from the normalized amounts
            churned_mrr = sum(detail['amount'] for detail in churn_details)

            return {
                'month': month,
                'churned_customers': int(churned_customers),
                'churned_mrr': float(churned_mrr),
                'churn_details': churn_details,
            }

        except Exception as e:
            raise Exception(f"Failed to import Zoho Churn report: {str(e)}")
