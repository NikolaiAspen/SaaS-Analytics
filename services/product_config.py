"""
Product Configuration Service

Handles product configuration for categorization and periodization overrides.
"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models.product_config import ProductConfiguration
from models.accounting import AccountingReceivableItem
from services.accounting import AccountingService
from typing import Optional, Dict, List


class ProductConfigService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_products(self) -> List[Dict]:
        """
        Get all unique products from accounting data with their current usage stats

        Returns list of dicts with:
        - product_name
        - total_items (count of invoice items)
        - total_mrr (sum of MRR)
        - avg_period_months (average periodization)
        - has_config (whether manual config exists)
        """
        # Get all unique products with stats
        query = select(
            AccountingReceivableItem.item_name,
            func.count(AccountingReceivableItem.item_id).label('total_items'),
            func.sum(AccountingReceivableItem.mrr_per_month).label('total_mrr'),
            func.avg(AccountingReceivableItem.period_months).label('avg_period_months'),
        ).group_by(AccountingReceivableItem.item_name)

        result = await self.session.execute(query)
        products = []

        for row in result:
            item_name = row.item_name

            # Check if config exists
            config = await self.get_config(item_name)

            # Determine if recurring:
            # 1. If manual config exists, use that
            # 2. Otherwise, use automatic categorization rules
            if config:
                is_recurring = config.is_recurring
                category = config.category
            else:
                # Use automatic categorization
                category = AccountingService.categorize_item(item_name)
                is_recurring = AccountingService.is_recurring_category(category)

                # Debug: Print first 5 products
                if len(products) < 5:
                    print(f"DEBUG: {item_name[:50]} => Category: {category}, Recurring: {is_recurring}")

            products.append({
                'product_name': item_name,
                'total_items': row.total_items,
                'total_mrr': float(row.total_mrr) if row.total_mrr else 0.0,
                'avg_period_months': float(row.avg_period_months) if row.avg_period_months else 1.0,
                'has_config': config is not None,
                'auto_category': category if not config else None,  # Show auto category when no manual config
                'auto_is_recurring': is_recurring,  # Always show effective is_recurring value
                'config': {
                    'category': config.category if config else None,
                    'period_months': config.period_months if config else None,
                    'is_recurring': config.is_recurring if config else None,
                    'notes': config.notes if config else None,
                    'updated_at': config.updated_at.isoformat() if config and config.updated_at else None,
                    'updated_by': config.updated_by if config else None,
                } if config else None
            })

        # Sort by total MRR descending
        products.sort(key=lambda x: abs(x['total_mrr']), reverse=True)

        return products

    async def get_config(self, product_name: str) -> Optional[ProductConfiguration]:
        """Get configuration for a specific product"""
        query = select(ProductConfiguration).where(
            ProductConfiguration.product_name == product_name
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_config(
        self,
        product_name: str,
        category: str,
        period_months: int,
        is_recurring: bool,
        notes: Optional[str] = None
    ) -> ProductConfiguration:
        """
        Create or update product configuration

        Args:
            product_name: Name of the product
            category: Category (e.g., "Fangstdagbok", "VMS", "Hardware")
            period_months: Number of months for periodization
            is_recurring: Whether to include in MRR
            notes: Optional admin notes
        """
        # Check if config exists
        config = await self.get_config(product_name)

        if config:
            # Update existing
            config.category = category
            config.period_months = period_months
            config.is_recurring = is_recurring
            config.notes = notes
        else:
            # Create new
            config = ProductConfiguration(
                product_name=product_name,
                category=category,
                period_months=period_months,
                is_recurring=is_recurring,
                notes=notes
            )
            self.session.add(config)

        await self.session.commit()
        await self.session.refresh(config)

        return config

    async def delete_config(self, product_name: str) -> bool:
        """
        Delete product configuration (revert to automatic rules)

        Returns True if config was deleted, False if it didn't exist
        """
        config = await self.get_config(product_name)

        if config:
            await self.session.delete(config)
            await self.session.commit()
            return True

        return False

    async def get_all_configs(self) -> List[ProductConfiguration]:
        """Get all product configurations"""
        query = select(ProductConfiguration).order_by(ProductConfiguration.product_name)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def recalculate_product_data(self, product_name: str, new_period_months: int) -> Dict:
        """
        Recalculate existing AccountingReceivableItem records for a product

        Updates period_months and mrr_per_month for all items matching this product name.
        Returns count of updated records and list of affected months for snapshot regeneration.

        Args:
            product_name: Name of the product to recalculate
            new_period_months: New periodization in months

        Returns:
            {
                'items_updated': int,
                'affected_months': List[str]  # YYYY-MM format
            }
        """
        from sqlalchemy import update
        from datetime import datetime
        import pandas as pd

        # Find all items for this product
        query = select(AccountingReceivableItem).where(
            AccountingReceivableItem.item_name == product_name
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        if not items:
            return {'items_updated': 0, 'affected_months': []}

        # Track affected months for snapshot regeneration
        affected_months = set()
        items_updated = 0

        for item in items:
            # Recalculate end date based on new period
            if item.period_start_date:
                # Calculate new end date
                new_end_date = item.period_start_date + pd.DateOffset(months=new_period_months, days=-1)
                item.period_end_date = new_end_date

            # Recalculate MRR
            # Remove VAT (25%) first, then divide by new period
            bcy_total_excl_vat = item.bcy_total_with_tax / 1.25 if item.bcy_total_with_tax else 0.0
            new_mrr = bcy_total_excl_vat / new_period_months if new_period_months > 0 else bcy_total_excl_vat

            # For credit notes, MRR should be negative
            if item.transaction_type == 'creditnote':
                new_mrr = -abs(new_mrr)

            item.period_months = new_period_months
            item.mrr_per_month = new_mrr
            items_updated += 1

            # Track source month for snapshot regeneration
            if item.source_month:
                affected_months.add(item.source_month)

        # Commit changes
        await self.session.commit()

        return {
            'items_updated': items_updated,
            'affected_months': sorted(list(affected_months))
        }
