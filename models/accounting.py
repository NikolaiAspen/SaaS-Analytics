"""
Accounting Receivable Data Models
Stores data from accounting's "Receivable Details" Excel reports
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Date, Boolean, Index
from datetime import datetime
from .subscription import Base  # Use same Base as other models


class AccountingReceivableItem(Base):
    """
    Accounting receivable item from "Receivable Details" reports

    This is the "ultimate source of truth" - what accounting actually reports as MRR
    """
    __tablename__ = "accounting_receivable_items"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Zoho IDs
    item_id = Column(String(100), nullable=False, index=True)
    transaction_id = Column(String(100), nullable=False, index=True)
    transaction_number = Column(String(50), nullable=False, index=True)  # Invoice/CN number
    customer_id = Column(String(100), index=True)
    product_id = Column(String(100))

    # Transaction details
    transaction_type = Column(String(20), nullable=False, index=True)  # invoice or creditnote
    transaction_date = Column(DateTime, index=True)
    status = Column(String(20))  # paid, unpaid, overdue, etc

    # Item details
    item_name = Column(String(500))
    product_name = Column(String(500))
    description = Column(Text)
    quantity_ordered = Column(Float)

    # Amounts (bcy = base currency = NOK)
    bcy_item_price = Column(Float)  # Price per unit
    bcy_total = Column(Float)  # Total excl tax
    bcy_total_with_tax = Column(Float)  # Total incl tax
    bcy_tax_amount = Column(Float)

    # Customer info
    customer_name = Column(String(500), nullable=False, index=True)
    company_name = Column(String(500))  # Sometimes different from customer_name

    # Custom fields (vessel info)
    vessel_name = Column(String(500), index=True)  # invoice.CF.Fartøy
    call_sign = Column(String(100), index=True)  # invoice.CF.Radiokallesignal
    customer_reference = Column(String(500))  # invoice.CF.Deres ref

    # Calculated fields for MRR
    period_start_date = Column(DateTime, index=True)  # Extracted from description
    period_end_date = Column(DateTime, index=True)  # Extracted from description
    period_months = Column(Integer)  # Number of months in period
    mrr_per_month = Column(Float, index=True)  # Calculated MRR per month

    # Meta
    source_file = Column(String(500))  # Which Excel file this came from
    source_month = Column(String(7), index=True)  # YYYY-MM format
    imported_at = Column(DateTime, default=datetime.utcnow)
    created_time = Column(DateTime)  # When item was created in Zoho
    created_by = Column(String(200))

    # Indexes for fast querying
    __table_args__ = (
        Index('idx_accounting_period', 'period_start_date', 'period_end_date'),
        Index('idx_accounting_customer_period', 'customer_name', 'period_start_date'),
        Index('idx_accounting_month_type', 'source_month', 'transaction_type'),
    )


class AccountingMRRSnapshot(Base):
    """
    Monthly MRR snapshots calculated from accounting receivable data

    This is what accounting reports as the "true" MRR each month
    """
    __tablename__ = "accounting_mrr_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String(7), unique=True, nullable=False, index=True)  # YYYY-MM

    # MRR metrics
    mrr = Column(Float, nullable=False)  # Total MRR (invoices + credit notes)
    arr = Column(Float)  # Annual Recurring Revenue

    # Customer metrics
    total_customers = Column(Integer)

    # Invoice metrics
    total_invoice_items = Column(Integer)  # Number of invoice line items
    total_creditnote_items = Column(Integer)  # Number of credit note line items
    invoice_mrr = Column(Float)  # Positive MRR from invoices
    creditnote_mrr = Column(Float)  # Negative MRR from credit notes

    # Average metrics
    arpu = Column(Float)  # Average Revenue Per User

    # Meta
    source = Column(String(50), default="accounting_report")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
