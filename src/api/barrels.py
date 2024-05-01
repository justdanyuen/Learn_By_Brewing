from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
import json

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

# Assuming you've defined a method in Barrel class to convert it to a dictionary
def barrel_to_dict(barrel):
    return {
        "sku": barrel.sku,
        "ml_per_barrel": barrel.ml_per_barrel,
        "potion_type": barrel.potion_type,
        "price": barrel.price,
        "quantity": barrel.quantity
    }


def filter_and_format_barrels(barrels, potion_type):
    filtered_barrels = [
        {
            'quantity': barrel.quantity,
            'ml_per_barrel': barrel.ml_per_barrel,
            'price': barrel.price
        }
        for barrel in barrels if barrel.potion_type == potion_type
    ]
    return json.dumps(filtered_barrels)


@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ Process delivery of barrels and update financial and stock ledgers. """
    barrels_json = json.dumps([barrel_to_dict(barrel) for barrel in barrels_delivered])

    potion_data = {
        "red": [0, []],
        "green": [0, []],
        "blue": [0, []],
        "dark": [0, []]
    }
    total_cost = 0

    for barrel in barrels_delivered:
        quantity = barrel.quantity
        ml_per_barrel = barrel.ml_per_barrel
        price = barrel.price
        potion_type_key = None  # Initialize with None to check for valid assignment

        # Determine the color key based on potion_type
        if barrel.potion_type == [1, 0, 0, 0]:
            potion_type_key = "red"
        elif barrel.potion_type == [0, 1, 0, 0]:
            potion_type_key = "green"
        elif barrel.potion_type == [0, 0, 1, 0]:
            potion_type_key = "blue"
        elif barrel.potion_type == [0, 0, 0, 1]:
            potion_type_key = "dark"

        if potion_type_key:  # If a valid key is found
            ml_increase = quantity * ml_per_barrel
            potion_data[potion_type_key][0] += ml_increase
            potion_data[potion_type_key][1].append(barrel_to_dict(barrel))
            total_cost += price * quantity

    with db.engine.begin() as connection:
        try:
            # Update the gold ledger
            connection.execute(sqlalchemy.text("""
                INSERT INTO gold_ledger (net_change, function, transaction)
                VALUES (:cost, 'deliver_barrels', :transaction);
            """), {'cost': -total_cost, 'transaction': barrels_json})

            # Insert changes into the ml_ledger
            for color, (ml_change, barrels_info) in potion_data.items():
                if ml_change > 0:
                    connection.execute(sqlalchemy.text("""
                        INSERT INTO ml_ledger (net_change, barrel_type, function, transaction)
                        VALUES (:ml_change, :barrel_type, 'deliver_barrels', :transaction);
                    """), {
                        'ml_change': ml_change,
                        'barrel_type': color,
                        'transaction': json.dumps(barrels_info)
                    })
        except Exception as e:
            print(f"An error occurred: {e}")
            connection.rollback()

    return "OK"


#def calculate_barrel_to_purchase(catalog, max_to_spend, potion_type, ml_available)
#   (barrel for barrel in bareel_etnries if barel.price <= max_to_spend and barrel.ml_per_barrel <= ml_available):
#   key = lambda barrel: barrel.ml_per_barrel
#   default = none
#)



# if gold > 300 else gold, potion_type, MAX_ML - current_ml)
# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ Determine the optimal barrels to purchase based on current ml and gold statuses in ledgers. """
    barrels_to_purchase = []

    with db.engine.begin() as connection:
        # Retrieve current ml amounts and total gold from ledgers
        ml_totals = connection.execute(sqlalchemy.text(
            """
            SELECT barrel_type, SUM(net_change) AS total_ml
            FROM ml_ledger
            GROUP BY barrel_type
            """
        )).fetchall()

        gold_total = connection.execute(sqlalchemy.text(
            "SELECT SUM(net_change) FROM gold_ledger"
        )).scalar() or 0

        # Initialize ml counts from the fetched data
        ml_counts = {'red': 0, 'green': 0, 'blue': 0, 'dark': 0}
        for ml in ml_totals:
            if ml['barrel_type'] in ml_counts:
                ml_counts[ml['barrel_type']] = ml['total_ml']

        print(f"Current ml values - {ml_counts}")
        print(f"Current gold: {gold_total}")

        # Split the catalog into potion types
        potion_type_catalogs = {
            'red': [],
            'green': [],
            'blue': [],
            'dark': []
        }
        for barrel in wholesale_catalog:
            if barrel.potion_type == [1, 0, 0, 0]:
                potion_type_catalogs['red'].append(barrel)
            elif barrel.potion_type == [0, 1, 0, 0]:
                potion_type_catalogs['green'].append(barrel)
            elif barrel.potion_type == [0, 0, 1, 0]:
                potion_type_catalogs['blue'].append(barrel)
            elif barrel.potion_type == [0, 0, 0, 1]:
                potion_type_catalogs['dark'].append(barrel)

        # Sort each type by cost-effectiveness
        for color in potion_type_catalogs:
            potion_type_catalogs[color].sort(key=lambda x: x.price / x.ml_per_barrel)

        # Purchase decision logic
        while any(ml_counts[color] < 200 for color in ml_counts) and gold_total > 0:
            updated = False
            for color, catalog in potion_type_catalogs.items():
                for barrel in catalog:
                    if ml_counts[color] < 200 and gold_total >= barrel.price:
                        if try_purchase_barrels(gold_total, barrel, barrels_to_purchase):
                            gold_total -= barrel.price
                            ml_counts[color] += barrel.ml_per_barrel
                            updated = True

            if not updated:
                break

        print(f"Barrels to purchase: {barrels_to_purchase}")
    return barrels_to_purchase             

def try_purchase_barrels(gold, barrel, barrels_to_purchase):
    if barrel.price <= gold and barrel.quantity > 0:
        check = check_purchase_plan(barrel.sku, barrels_to_purchase)
        if check == -1:
            barrels_to_purchase.append({
                "sku": barrel.sku,
                "quantity": 1,
                "ml_per_barrel": barrel.ml_per_barrel,
                "potion_type": barrel.potion_type,
                "price": barrel.price
            })
        else:
            barrels_to_purchase[check]["quantity"] += 1
        barrel.quantity -= 1
        return True
    return False

def check_purchase_plan(sku: str, purchase_plan):
    for i, plan in enumerate(purchase_plan):
        if plan['sku'] == sku:
            return i
    return -1
