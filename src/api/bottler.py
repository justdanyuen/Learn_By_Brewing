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
    total_cost = 0

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
                transaction_cost = potion.quantity * price_per_unit
                total_cost += transaction_cost

                # Record transaction in potion_ledger
                connection.execute(sqlalchemy.text("""
                    INSERT INTO potion_ledger (potion_id, quantity, transaction, cost, function)
                    VALUES (:potion_id, :quantity, 'delivery', :cost, :function);
                    """), {
                    'potion_id': potion_id,
                    'quantity': potion.quantity,
                    'cost': transaction_cost,
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
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into red potions.

    
    bottle_plan = []

    with db.engine.begin() as connection:
        num_red_ml, num_green_ml, num_blue_ml, num_dark_ml = connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory")).one()

        potion_inventory = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory ORDER BY quantity ASC;")).fetchall()

        bottle_plan = make_potions(num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, potion_inventory)
    
    print(bottle_plan) # for debugging
    return bottle_plan

def make_potions(red_ml, green_ml, blue_ml, dark_ml, potion_inventory):
    print(f"red_ml: {red_ml} green_ml: {green_ml} blue_ml: {blue_ml} dark_ml: {dark_ml}")
    for row in potion_inventory:
        print(f"id: {row.id} sku: {row.sku} name: {row.name} r: {row.red_ml} g: {row.green_ml} b: {row.blue_ml} d: {row.dark_ml} quantity: {row.quantity} price: {row.price}")
    bottle_plan = []

    total_ml = red_ml + green_ml + blue_ml + dark_ml

    print(f"total ml: {total_ml}")
    for recipe in potion_inventory:
        # print(f"total ml: {total_ml}")
        # print(f"recipe id: {recipe.id} sku: {recipe.sku}: quantity: {recipe.quantity}")
        if recipe.quantity >= 1:
            continue  # Skip to the next recipe if there is at least one potion
        if total_ml > 100:
            quantity = 0
            # Loop will execute only if there's enough stock and required materials are available
            # print(f"Checking availability - red: {red_ml}/{recipe.red_ml}, green: {green_ml}/{recipe.green_ml}, blue: {blue_ml}/{recipe.blue_ml}, dark: {dark_ml}/{recipe.dark_ml}")
            while (red_ml >= recipe.red_ml and green_ml >= recipe.green_ml and
                blue_ml >= recipe.blue_ml and dark_ml >= recipe.dark_ml and quantity < 3):
                quantity += 1
                red_ml -= recipe.red_ml
                green_ml -= recipe.green_ml
                blue_ml -= recipe.blue_ml
                dark_ml -= recipe.dark_ml
            if quantity > 0:
                bottle_plan.append({
                "potion_type": [recipe.red_ml, recipe.green_ml, recipe.blue_ml, recipe.dark_ml],
                "quantity": quantity
                })
    print(bottle_plan)
    return bottle_plan
            
if __name__ == "__main__":
    print(get_bottle_plan())