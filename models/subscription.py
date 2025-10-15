from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Subscription(Base):
    """Model for storing subscription data from Zoho Billing"""
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True)  # Zoho subscription_id
    customer_id = Column(String, nullable=False, index=True)
    customer_name = Column(String)
    plan_code = Column(String, index=True)
    plan_name = Column(String)
    status = Column(String, index=True)  # live, cancelled, expired, etc.
    amount = Column(Float, nullable=False)  # MRR amount
    currency_code = Column(String, default="NOK")
    interval = Column(String)  # months, years
    interval_unit = Column(Integer, default=1)

    # Custom fields from Zoho
    vessel_name = Column(String, nullable=True)  # Fartøy
    call_sign = Column(String, nullable=True)  # Kallesignal

    created_time = Column(DateTime)
    activated_at = Column(DateTime, index=True)
    cancelled_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Metadata
    last_synced = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MetricsSnapshot(Base):
    """Model for storing calculated metrics snapshots"""
    __tablename__ = "metrics_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(DateTime, nullable=False, index=True)

    # Core metrics
    mrr = Column(Float, nullable=False)  # Monthly Recurring Revenue
    arr = Column(Float)  # Annual Recurring Revenue
    total_customers = Column(Integer)
    active_subscriptions = Column(Integer)

    # Churn metrics
    churned_customers = Column(Integer, default=0)
    churned_mrr = Column(Float, default=0.0)
    customer_churn_rate = Column(Float)  # Percentage
    revenue_churn_rate = Column(Float)  # Percentage

    # Growth metrics
    new_mrr = Column(Float, default=0.0)
    expansion_mrr = Column(Float, default=0.0)
    contraction_mrr = Column(Float, default=0.0)

    # Average metrics
    arpu = Column(Float)  # Average Revenue Per User

    # AI Analysis
    analysis_text = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class SyncStatus(Base):
    """Model for tracking sync status"""
    __tablename__ = "sync_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_sync_time = Column(DateTime, nullable=False)
    sync_type = Column(String, default="incremental")  # "full" or "incremental"
    subscriptions_synced = Column(Integer, default=0)
    invoices_synced = Column(Integer, default=0)
    creditnotes_synced = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MonthlyMRRSnapshot(Base):
    """Model for storing monthly MRR snapshots based on actual subscription data at that time"""
    __tablename__ = "monthly_mrr_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String, nullable=False, unique=True, index=True)  # Format: "YYYY-MM"
    mrr = Column(Float, nullable=False)
    arr = Column(Float)
    total_customers = Column(Integer)
    active_subscriptions = Column(Integer)
    new_mrr = Column(Float, default=0.0)
    churned_mrr = Column(Float, default=0.0)
    churned_customers = Column(Integer, default=0)  # Number of customers who churned
    net_mrr = Column(Float, default=0.0)
    arpu = Column(Float)
    source = Column(String, default="calculated")  # "excel_import" or "calculated"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChurnedCustomer(Base):
    """Model for storing individual churned customer details with cancellation reasons"""
    __tablename__ = "churned_customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String, nullable=False, index=True)  # Format: "YYYY-MM"
    customer_id = Column(String, nullable=False)
    customer_name = Column(String)
    customer_email = Column(String)
    subscription_id = Column(String)
    plan_name = Column(String)
    amount = Column(Float, nullable=False)  # MRR lost
    cancellation_reason = Column(String)
    cancelled_date = Column(DateTime)
    ltv = Column(Float)  # Lifetime value
    ltd = Column(Integer)  # Lifetime days
    created_at = Column(DateTime, default=datetime.utcnow)
