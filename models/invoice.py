from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
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
    vessel_name = Column(String, index=True, nullable=True)  # CF.Fartøy from XLSX
    call_sign = Column(String, index=True, nullable=True)  # CF.Radiokallesignal from XLSX

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

    # Line item counts
    active_lines = Column(Integer, default=0)  # Total active lines (invoices + credit notes)
    invoice_lines = Column(Integer, default=0)  # Number of invoice lines
    creditnote_lines = Column(Integer, default=0)  # Number of credit note lines

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


class CreditNote(Base):
    """
    Credit Note model - stores credit notes from Zoho Billing
    Used to identify credited invoices (e.g., due to ownership changes)
    """
    __tablename__ = "credit_notes"

    id = Column(String, primary_key=True)  # creditnote_id from Zoho
    creditnote_number = Column(String, nullable=False, index=True, unique=True)
    creditnote_date = Column(DateTime, nullable=False, index=True)

    # Reference to original invoice
    invoice_id = Column(String, index=True)  # Zoho invoice_id
    invoice_number = Column(String, index=True)  # Invoice number that was credited
    reference_number = Column(String)

    # Customer info
    customer_id = Column(String, nullable=False, index=True)
    customer_name = Column(String, nullable=False)

    # Vessel info (for matching)
    vessel_name = Column(String, index=True, nullable=True)  # creditnote.CF.Fartøy
    call_sign = Column(String, index=True, nullable=True)  # creditnote.CF.RKAL

    # Financial
    currency_code = Column(String, default="NOK")
    total = Column(Float, default=0.0)  # Total credit amount
    balance = Column(Float, default=0.0)  # Remaining balance

    # Status
    status = Column(String, index=True)  # open, closed, void

    # Metadata
    created_time = Column(DateTime)
    last_synced = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CreditNote {self.creditnote_number} - {self.customer_name} - {self.total} {self.currency_code}>"


class CreditNoteLineItem(Base):
    """
    Credit Note line item - individual line items on a credit note
    Links credit notes to specific invoice line items
    """
    __tablename__ = "credit_note_line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creditnote_id = Column(String, ForeignKey("credit_notes.id"), nullable=False, index=True)

    # Line item details
    item_id = Column(String)  # Zoho item_id
    product_id = Column(String, index=True)

    # Product info
    name = Column(String, nullable=False)
    description = Column(Text)
    code = Column(String)

    # Vessel info
    vessel_name = Column(String, index=True, nullable=True)
    call_sign = Column(String, index=True, nullable=True)

    # Pricing (negative values)
    price = Column(Float, nullable=False)  # Negative amount
    quantity = Column(Integer, default=1)
    item_total = Column(Float, nullable=False)

    # Tax
    tax_percentage = Column(Float, default=0.0)
    tax_name = Column(String)

    # MRR impact (calculated from period)
    period_start_date = Column(DateTime, index=True)
    period_end_date = Column(DateTime, index=True)
    period_months = Column(Integer)
    mrr_per_month = Column(Float)  # Negative value

    # Metadata
    created_time = Column(DateTime, default=datetime.utcnow)

    # Relationships
    credit_note = relationship("CreditNote", backref="line_items")

    def __repr__(self):
        return f"<CreditNoteLineItem {self.name} - {self.price}>"


class InvoiceSyncStatus(Base):
    """
    Track last sync time for invoices and credit notes
    Used for incremental sync (only fetch changes since last sync)
    """
    __tablename__ = "invoice_sync_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_sync_time = Column(DateTime, nullable=False)
    invoices_synced = Column(Integer, default=0)
    creditnotes_synced = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<InvoiceSyncStatus {self.last_sync_time} - {self.invoices_synced} invoices, {self.creditnotes_synced} credit notes>"
