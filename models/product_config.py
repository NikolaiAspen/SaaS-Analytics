"""
Product Configuration Model

Stores configuration for how products should be categorized and periodized.
This allows manual override of automatic categorization and periodization rules.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from models.subscription import Base


class ProductConfiguration(Base):
    """
    Product configuration for categorization and periodization

    This table stores manual overrides for product handling:
    - How many months a product should be periodized
    - Which category it belongs to (Fangstdagbok, VMS, Hardware, etc.)
    - Whether it should be included in MRR calculations
    """
    __tablename__ = "product_configurations"

    product_name = Column(String(500), primary_key=True, index=True)
    category = Column(String(100), nullable=False)  # e.g., "Fangstdagbok", "VMS", "Hardware"
    period_months = Column(Integer, nullable=False, default=1)  # Number of months for periodization
    is_recurring = Column(Boolean, nullable=False, default=True)  # Include in MRR calculations
    notes = Column(String(1000), nullable=True)  # Admin notes
    updated_by = Column(String(100), nullable=True, default="admin")  # Who last updated
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ProductConfiguration(product_name='{self.product_name}', category='{self.category}', period_months={self.period_months}, is_recurring={self.is_recurring})>"
