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

@router.get("/audit")
def get_inventory():
    """ Computes inventory and financial state from ledger tables. """
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

    # """ """
    # with db.engine.begin() as connection:
    #     potions = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory WHERE quantity > 0")).fetchall()
    #     red_ml, green_ml, blue_ml, dark_ml = connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory")).one()
    #     gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()
    #     total_ml = red_ml + green_ml + blue_ml + dark_ml
    #     total_potions = 0
    #     for potion in potions:
    #         total_potions += potion.quantity
    # print({"number_of_potions": total_potions, "ml_in_barrels": total_ml, "gold": gold})
    # return {"number_of_potions": total_potions, "ml_in_barrels": total_ml, "gold": gold}

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
