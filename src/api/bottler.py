from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
import json

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    print(f"potions delivered: {potions_delivered} order_id: {order_id}")

    ml_changes = {'red': 0, 'green': 0, 'blue': 0, 'dark': 0}

    with db.engine.begin() as connection:
        for potion in potions_delivered:
            potion_type_info = connection.execute(sqlalchemy.text("""
                SELECT id, sku, price FROM potion_inventory
                WHERE red_ml = :red AND green_ml = :green AND blue_ml = :blue AND dark_ml = :dark LIMIT 1;
                """), {
                'red': potion.potion_type[0],
                'green': potion.potion_type[1],
                'blue': potion.potion_type[2],
                'dark': potion.potion_type[3]
            }).mappings().first()

            if potion_type_info:
                potion_id = potion_type_info['id']
                sku = potion_type_info['sku']
                price_per_unit = potion_type_info['price']

                # Record transaction in potion_ledger
                connection.execute(sqlalchemy.text("""
                    INSERT INTO potion_ledger (potion_id, quantity, transaction, cost, function)
                    VALUES (:potion_id, :quantity, 'delivery', :cost, :function);
                    """), {
                    'potion_id': potion_id,
                    'quantity': potion.quantity,
                    'cost': price_per_unit,
                    'transaction': json.dumps({'order_id': order_id, 'ml_per_type': potion.potion_type}),
                    'function': "post_deliver_bottles"
                })

                # Aggregate ml changes for each color
                ml_changes['red'] -= potion.potion_type[0] * potion.quantity
                ml_changes['green'] -= potion.potion_type[1] * potion.quantity
                ml_changes['blue'] -= potion.potion_type[2] * potion.quantity
                ml_changes['dark'] -= potion.potion_type[3] * potion.quantity
            else:
                print(f"Error: Potion with components {potion.potion_type} not found in inventory.")

        # Record aggregated volume changes in ml_ledger for each potion type
        for color, change in ml_changes.items():
            if change < 0:
                current_time = connection.execute(sqlalchemy.text("""
                            SELECT day, hour FROM time_table ORDER BY created_at DESC LIMIT 1;
                        """)).first()  # Use first() to fetch the first result directly

                if current_time:  # Check if a result was returned
                    connection.execute(sqlalchemy.text("""
                        INSERT INTO ml_ledger (barrel_type, net_change, transaction, function, day, hour)
                        VALUES (:barrel_type, :net_change, 'delivery', :function, :day, :hour);
                        """), {
                        'barrel_type': color,
                        'net_change': change,
                        'transaction': json.dumps({'order_id': order_id}),
                        'function': "post_deliver_bottles",
                        'day': current_time.day,
                        'hour': current_time.hour
                    })   
                else:  
                    connection.execute(sqlalchemy.text("""
                        INSERT INTO ml_ledger (barrel_type, net_change, transaction, function)
                        VALUES (:barrel_type, :net_change, 'delivery', :function);
                        """), {
                        'barrel_type': color,
                        'net_change': change,
                        'transaction': json.dumps({'order_id': order_id}),
                        'function': "post_deliver_bottles"
                    })    
    return "OK"




@router.post("/plan")
def get_bottle_plan():
    """
    Dynamically computes the plan to bottle potions from barrels based on the transaction records in ml_ledger and potion_ledger.
    """
    with db.engine.begin() as connection:

        # Calculate total number of potions already bottled
        total_existing_potions = connection.execute(sqlalchemy.text(
            "SELECT COALESCE(SUM(quantity), 0) AS total_potions FROM potion_ledger;"
        )).scalar()

        potion_capacity = connection.execute(sqlalchemy.text(
            "SELECT potion_capacity FROM capacity_ledger LIMIT 1"
        )).scalar()

        # Determine the maximum number of potions that can be added
        max_potions_to_bottle = max(0, potion_capacity - total_existing_potions)

        # Retrieve all records from ml_ledger
        ml_ledger_entries = connection.execute(sqlalchemy.text(
            "SELECT barrel_type, net_change FROM ml_ledger;"
        )).mappings().all()

        # Initialize ml counts for each color
        ml_totals = {'red': 0, 'green': 0, 'blue': 0, 'dark': 0}
        for entry in ml_ledger_entries:
            color = entry['barrel_type']
            if color in ml_totals:
                ml_totals[color] += entry['net_change']

        # print(f"{ml_totals}\n\n")

        # Fetch potion inventory without relying on quantity column
        potion_inventory = connection.execute(
            sqlalchemy.text("SELECT id, sku, name, price, red_ml, green_ml, blue_ml, dark_ml FROM potion_inventory ORDER BY id;")
        ).mappings().all()

        # Calculate available quantities from potion_ledger
        potion_quantities = {recipe['id']: 0 for recipe in potion_inventory}  # Initialize quantities to 0
        potion_ledger_entries = connection.execute(sqlalchemy.text(
            "SELECT potion_id, SUM(quantity) AS total_quantity FROM potion_ledger GROUP BY potion_id;"
        )).mappings().all()

        print(f"Potion Ledger Entries: {potion_ledger_entries}\n\n")

        for entry in potion_ledger_entries:
            potion_quantities[entry['potion_id']] = entry['total_quantity']

        merged_potion_inventory = [{
            **potion,
            'quantity': potion_quantities.get(potion['id'], 0)
        } for potion in potion_inventory]

        # Sort potion inventory by quantity
        sorted_potion_inventory = sorted(merged_potion_inventory, key=lambda x: x['quantity'])

        print(f"sorted potion inventory: {sorted_potion_inventory}")

        # Calculate how many potions can be made from the current ml totals
        bottle_plan = make_potions(ml_totals['red'], ml_totals['green'], ml_totals['blue'], ml_totals['dark'], potion_inventory, potion_quantities,max_potions_to_bottle)

    return bottle_plan

def make_potions(red_ml, green_ml, blue_ml, dark_ml, potion_inventory, potion_quantities,max_potions):
    print(f"The max number of potions I can make is {max_potions}")
    # print(f"red_ml: {red_ml} green_ml: {green_ml} blue_ml: {blue_ml} dark_ml: {dark_ml}")
    for recipe in potion_inventory:
        current_quantity = potion_quantities.get(recipe['id'], 0)  # Default to 0 if no entry exists
        print(f"id: {recipe['id']} sku: {recipe['sku']} name: {recipe['name']} r: {recipe['red_ml']} g: {recipe['green_ml']} b: {recipe['blue_ml']} d: {recipe['dark_ml']} quantity: {current_quantity} price: {recipe['price']}")

    bottle_plan = []
    total_potions = 0  # Track the total number of potions created
    # print(f"total ml: {total_ml}")

    for recipe in potion_inventory:
        if total_potions >= max_potions:
            break  # Stop processing if max potion limit is reached

        current_quantity = potion_quantities.get(recipe['id'], 0)
        quantity = 0
        while (red_ml >= recipe['red_ml'] and green_ml >= recipe['green_ml'] and
               blue_ml >= recipe['blue_ml'] and dark_ml >= recipe['dark_ml'] and
               quantity < (max_potions - total_potions)):

            quantity += 1
            red_ml -= recipe['red_ml']
            green_ml -= recipe['green_ml']
            blue_ml -= recipe['blue_ml']
            dark_ml -= recipe['dark_ml']

        if quantity > 0:
            bottle_plan.append({
                "potion_type": [recipe['red_ml'], recipe['green_ml'], recipe['blue_ml'], recipe['dark_ml']],
                "quantity": quantity
            })
            total_potions += quantity

    print("Bottle Plan:", bottle_plan, "\n\n")

    if not bottle_plan:
        with db.engine.begin() as connection:
            current_time = connection.execute(sqlalchemy.text("""
                SELECT hour FROM time_table ORDER BY created_at DESC LIMIT 1;
                """)).first()  # Use first() to fetch the first result directly
            if current_time:
                hour = current_time[0]  # Extract the hour from the tuple
                if hour in {2, 6, 10, 14, 18, 22}:
                    bottle_plan.append({
                                        "potion_type": [100, 0, 0, 0],
                                        "quantity": 10
                                    })
                    print("It's a Barrel Order Tick! Trying to predict making some potions...")                
            else:
                print("No time data was retrieved.")
    
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())