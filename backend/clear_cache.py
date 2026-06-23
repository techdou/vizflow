"""
Clear cached chart specs from database.
Run this when you want to force regeneration with the new prompt.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from src.core.config import settings

def clear_chart_cache():
    """Clear all cached chart specs."""
    engine = create_engine(settings.DB_URL)
    
    with engine.connect() as conn:
        # Count before deletion
        result = conn.execute(text("SELECT COUNT(*) FROM chart_specs"))
        count = result.scalar()
        
        print(f"Found {count} cached chart specs")
        
        if count > 0:
            # Delete all chart specs
            conn.execute(text("DELETE FROM chart_specs"))
            conn.commit()
            print(f"✅ Deleted {count} chart specs")
        else:
            print("✅ No cache to clear")

if __name__ == "__main__":
    print("Clearing chart spec cache...")
    clear_chart_cache()
    print("\nCache cleared! Now restart the backend and try generating charts again.")
