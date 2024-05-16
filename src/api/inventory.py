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

        connection.execute(sqlalchemy.text("""
            CREATE OR REPLACE VIEW capacity_view AS
            SELECT SUM(ml_capacity) AS ml_cap, SUM(potion_capacity) AS pot_cap
            FROM capacity_ledger
        """))

        connection.execute(sqlalchemy.text("""
            CREATE OR REPLACE VIEW potion_quantities_sold AS
            SELECT item_sku, SUM(quantity) AS total_quantity
            FROM cart_items
            GROUP BY item_sku
            ORDER BY SUM(quantity) ASC;
        """))

        connection.execute(sqlalchemy.text("""
            CREATE OR REPLACE VIEW total_ml_view AS
            SELECT SUM(net_change) AS total_ml
            FROM ml_ledger
        """))

        connection.execute(sqlalchemy.text("""
            CREATE OR REPLACE VIEW total_potions_view AS
            SELECT SUM(quantity) AS total_potions
            FROM potion_ledger
        """))

# def update_preferences():
#     with db.engine.begin() as connection:
#         connection.execute(sqlalchemy.text("""
#             WITH SoldQuantities AS (
#                 SELECT 
#                     item_sku, 
#                     SUM(quantity) AS total_quantity
#                 FROM 
#                     cart_items
#                 GROUP BY 
#                     item_sku
#             ),
#             RankedItems AS (
#                 SELECT 
#                     item_sku, 
#                     total_quantity,
#                     RANK() OVER (ORDER BY total_quantity DESC) AS preference
#                 FROM 
#                     SoldQuantities
#             )
#             UPDATE 
#                 preference_table
#             SET 
#                 quantity = RankedItems.total_quantity,
#                 preference = RankedItems.preference
#             FROM 
#                 RankedItems
#             WHERE 
#                 preference_table.item_sku = RankedItems.item_sku;
#     """))

@router.get("/audit")
def get_inventory():
    """ Computes inventory and financial state from ledger tables. """
    create_views()  # Ensure views are created or updated
    # update_preferences()
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

# Gets called once a day at 1pm tick (check this before it happens!!)
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    with db.engine.begin() as connection:
        # Fetch ml_capacity and potion_capacity from the first row of capacity_ledger
        # capacities = connection.execute(sqlalchemy.text(
        #     "SELECT ml_capacity, potion_capacity FROM capacity_ledger LIMIT 1"
        # )).fetchone()
        # ml_capacity = capacities.ml_capacity
        # potion_capacity = capacities.potion_capacity

        # # Fetch the total number of potions
        # current_potions = connection.execute(sqlalchemy.text(
        #     "SELECT COALESCE(SUM(quantity), 0) FROM potion_ledger"
        # )).scalar()

        # # Fetch the total amount of ml in the ml_ledger
        # current_ml = connection.execute(sqlalchemy.text(
        #     "SELECT COALESCE(SUM(net_change), 0) FROM ml_ledger"
        # )).scalar()

        # Fetch the total amount of gold
        gold = connection.execute(sqlalchemy.text(
            "SELECT SUM(net_change) FROM gold_ledger"
        )).scalar()

        print(f"this is the current gold I got for capacity: {gold}")

        add_to_pot = 0
        add_to_ml = 0

        total_cost = 0
        if gold >= 2000:
            total_cost -= 2000
            add_to_pot += 1
            add_to_ml += 1
            
        elif gold >= 1000:
            total_cost -= 1000
            add_to_ml += 1

    add_to_pot = 1
    add_to_ml = 1

    # passively purchase 2 capacities every day
    print(f"Adding {add_to_pot} capacities to potions, {add_to_ml} capacities to ml")
    return {
        "potion_capacity": add_to_pot,
        "ml_capacity": add_to_ml
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
    # HARD CODED LOGIC RIGHT NOW TO PURCHASE IT IF I HAVE ENOUGH GOLD, BUT I NEED TO CHANGE THIS LOGIC

    modified_ml = capacity_purchase.ml_capacity * 10000
    modified_potion = capacity_purchase.potion_capacity * 50
    modified_gold = (capacity_purchase.ml_capacity + capacity_purchase.potion_capacity) * 1000

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("""INSERT INTO capacity_ledger 
                                                (ml_capacity, potion_capacity) VALUES
                                                (:mls, :potions)"""),
                                                [{
                                                    'mls': modified_ml,
                                                    'potions': modified_potion
                                                }])

        connection.execute(sqlalchemy.text("""
                INSERT INTO gold_ledger (net_change, function, transaction)
                VALUES (:cost, 'capacity plan', 'capacity purchase delivery');
            """), {'cost': -modified_gold})
    return "OK"
