from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

def create_views():
    with db.engine.begin() as connection:
        # Create or replace view for ml_ledger totals
        connection.execute(sqlalchemy.text("""
            CREATE OR REPLACE VIEW ml_totals_view AS
            SELECT barrel_type, SUM(net_change) AS total_ml
            FROM ml_ledger
            GROUP BY barrel_type
        """))

        # Create or replace view for the total gold change
        connection.execute(sqlalchemy.text("""
            CREATE OR REPLACE VIEW total_gold_view AS
            SELECT SUM(net_change) AS total_gold
            FROM gold_ledger
        """))

        # Create or replace view for the total number of potions, now including potion_id
        connection.execute(sqlalchemy.text("""
            CREATE OR REPLACE VIEW potion_view AS
            SELECT potion_id, SUM(quantity) AS total_potions
            FROM potion_ledger
            GROUP BY potion_id
        """))

# You might call this function to ensure all views are created or updated
create_views()

@router.get("/audit")
def get_inventory():
    """ Computes inventory and financial state from ledger tables. """
    create_views()  # Ensure views are created or updated
    with db.engine.begin() as connection:
        # Aggregate changes in ml_ledger for each barrel type
        ml_totals = connection.execute(sqlalchemy.text("""
            SELECT barrel_type, SUM(net_change) as total_ml
            FROM ml_ledger
            GROUP BY barrel_type
        """)).fetchall()
        
        # Create a dictionary to track ml totals
        ml_counts = {'red': 0, 'green': 0, 'blue': 0, 'dark': 0}
        for record in ml_totals:
            ml_counts[record.barrel_type] = record.total_ml

        total_ml = sum(ml_counts.values())  # Total ml from all barrels

        # Aggregate changes in gold from gold_ledger
        total_gold = connection.execute(sqlalchemy.text("""
            SELECT SUM(net_change)
            FROM gold_ledger
        """)).scalar() or 0  # Default to 0 if None

        # Count total potions from potion_ledger
        total_potions = connection.execute(sqlalchemy.text("""
            SELECT SUM(quantity)
            FROM potion_ledger
        """)).scalar() or 0  # Default to 0 if None

    return {
        "number_of_potions": total_potions,
        "ml_in_barrels": total_ml,
        "gold": total_gold
    }

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return {
        "potion_capacity": 0,
        "ml_capacity": 0
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return "OK"
