"""Test Zoho MRR import"""
import pandas as pd

# Import directly without going through services/__init__.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the class directly from the file
import importlib.util
spec = importlib.util.spec_from_file_location("zoho_import", "services/zoho_import.py")
zoho_import = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zoho_import)

ZohoReportImporter = zoho_import.ZohoReportImporter

importer = ZohoReportImporter()
data = importer.import_monthly_mrr_report(r'c:\Users\nikolai\Downloads\Monthly Recurring Revenue (MRR).xlsx')

print(f"OK Importert {len(data)} maneder fra Zoho")
print("\nSiste 5 maneder:")
for d in data[:5]:
    print(f"  {d['month_name']}: {d['mrr']:,.0f} kr")
