"""
Migration script to add 'source' column to monthly_mrr_snapshots table
"""
import sqlite3
import sys

def migrate():
    try:
        # Connect to database
        conn = sqlite3.connect('data/app.db')
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_mrr_snapshots'")
        if not cursor.fetchone():
            print("Table monthly_mrr_snapshots does not exist yet. Will be created on first app startup.")
            conn.close()
            return

        # Check if column already exists
        cursor.execute("PRAGMA table_info(monthly_mrr_snapshots)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'source' in columns:
            print("Column 'source' already exists")
            conn.close()
            return

        # Add source column with default value 'calculated'
        print("Adding 'source' column to monthly_mrr_snapshots table...")
        cursor.execute("""
            ALTER TABLE monthly_mrr_snapshots
            ADD COLUMN source TEXT DEFAULT 'calculated'
        """)

        conn.commit()
        print("Successfully added 'source' column")

        # Show current data
        cursor.execute("SELECT month, source FROM monthly_mrr_snapshots ORDER BY month")
        snapshots = cursor.fetchall()
        print(f"\nCurrent snapshots ({len(snapshots)} total):")
        for month, source in snapshots:
            print(f"  {month}: {source or 'calculated'}")

        conn.close()
        print("\nMigration complete!")

    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    migrate()
