from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship, deferred
from datetime import datetime
from models.subscription import Base


class Invoice(Base):
    """
    Invoice model - stores invoices from Zoho Billing
    Used for invoice-based MRR calculation (separate from subscriptions)
    """
    __tablename__ = "invoices"

    id = Column(String, primary_key=True)  # invoice_id from Zoho
    invoice_number = Column(String, nullable=False, index=True)
    invoice_date = Column(DateTime, nullable=False, index=True)  # Key for MRR calculation
    due_date = Column(DateTime)

    # Customer info
    customer_id = Column(String, nullable=False, index=True)
    customer_name = Column(String, nullable=False)
    customer_email = Column(String)

    # Financial
    currency_code = Column(String, default="NOK")
    sub_total = Column(Float, default=0.0)  # Excluding tax
    tax_total = Column(Float, default=0.0)
    total = Column(Float, default=0.0)  # Including tax
    balance = Column(Float, default=0.0)

    # Status
    status = Column(String, index=True)  # sent, paid, overdue, void
    transaction_type = Column(String)  # renewal, renewal_upgrade, new

    # Metadata
    created_time = Column(DateTime)
    updated_time = Column(DateTime)
    last_synced = Column(DateTime, default=datetime.utcnow)

    # Relationships
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Invoice {self.invoice_number} - {self.customer_name} - {self.total} {self.currency_code}>"


class InvoiceLineItem(Base):
    """
    Invoice line item - individual products/services on an invoice
    This is where we calculate MRR based on the billing period in the description
    """
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False, index=True)

    # Line item details
    item_id = Column(String)  # Zoho item_id
    product_id = Column(String, index=True)
    subscription_id = Column(String, index=True)

    # Product info
    name = Column(String, nullable=False)
    description = Column(Text)  # Contains period: "Gjelder perioden 10 Oct 2025 til 09 Oct 2026"
    code = Column(String)  # Plan code (e.g., "ERSO15PM", "VMS14")
    unit = Column(String)  # "mnd", "år", "6mnd" - NOT reliable for period calculation

    # Vessel info (for matching with subscriptions)
    # These columns may not exist in older Railway PostgreSQL databases
    # Use deferred() to avoid loading them automatically (causes error if columns don't exist)
    vessel_name = deferred(Column(String, index=True, nullable=True))  # CF.Fartøy from XLSX
    call_sign = deferred(Column(String, index=True, nullable=True))  # CF.Radiokallesignal from XLSX

    # Pricing
    price = Column(Float, nullable=False)  # Excluding tax
    quantity = Column(Integer, default=1)
    item_total = Column(Float, nullable=False)  # price * quantity

    # Tax
    tax_percentage = Column(Float, default=0.0)
    tax_name = Column(String)

    # MRR calculation (calculated from description period)
    period_start_date = Column(DateTime, index=True)  # Parsed from description
    period_end_date = Column(DateTime, index=True)  # Parsed from description
    period_months = Column(Integer)  # Number of months in period
    mrr_per_month = Column(Float)  # price / period_months

    # Metadata
    created_time = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")

    def __repr__(self):
        return f"<InvoiceLineItem {self.name} - {self.price} {self.invoice.currency_code if self.invoice else 'NOK'}>"


class InvoiceMRRSnapshot(Base):
    """
    Monthly MRR snapshots calculated from invoices
    Separate table from subscription-based MRR snapshots
    """
    __tablename__ = "invoice_mrr_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String, nullable=False, unique=True, index=True)  # Format: YYYY-MM

    # MRR metrics
    mrr = Column(Float, nullable=False)  # Total MRR for this month from all invoice line items
    arr = Column(Float, nullable=False)  # ARR = MRR * 12

    # Line item counts (deferred to avoid loading if columns don't exist in Railway)
    active_lines = deferred(Column(Integer, default=0))  # Total active lines (invoices + credit notes)
    invoice_lines = deferred(Column(Integer, default=0))  # Number of invoice lines
    creditnote_lines = deferred(Column(Integer, default=0))  # Number of credit note lines

    # Customer metrics
    total_customers = Column(Integer, default=0)  # Unique customers with active MRR this month
    active_invoices = Column(Integer, default=0)  # Number of invoices contributing to MRR

    # Growth metrics
    new_mrr = Column(Float, default=0.0)  # New MRR this month
    churned_mrr = Column(Float, default=0.0)  # Lost MRR this month
    net_mrr = Column(Float, default=0.0)  # new_mrr - churned_mrr

    # ARPU
    arpu = Column(Float, default=0.0)  # Average Revenue Per User (MRR / customers)

    # Metadata
    source = Column(String, default="invoice_calculation")  # Source of data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<InvoiceMRRSnapshot {self.month} - MRR: {self.mrr} NOK>"
