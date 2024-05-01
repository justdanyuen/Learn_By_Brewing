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
    """ """

    barrels_json = json.dumps([barrel_to_dict(barrel) for barrel in barrels_delivered])

    potion_data = {
        "red": [0, [], []],  # new_ml, potion_type, barrels_json
        "green": [0, [], []],
        "blue": [0, [], []],
        "dark": [0, [], []]
    }
    cost = 0

    for item in barrels_delivered:
        quantity = item.quantity
        ml_per_barrel = item.ml_per_barrel
        price = item.price
        potion_type_key = "unknown"  # Default case

        if item.potion_type == [1, 0, 0, 0]:
            potion_type_key = "red"
        elif item.potion_type == [0, 1, 0, 0]:
            potion_type_key = "green"
        elif item.potion_type == [0, 0, 1, 0]:
            potion_type_key = "blue"
        elif item.potion_type == [0, 0, 0, 1]:
            potion_type_key = "dark"

        if potion_type_key != "unknown":
            potion_data[potion_type_key][0] += quantity * ml_per_barrel
            potion_data[potion_type_key][1] = item.potion_type
            potion_data[potion_type_key][2].append(barrel_to_dict(item))
        cost -= price * quantity

    with db.engine.begin() as connection:
        try:
            connection.execute(sqlalchemy.text("""
                INSERT INTO gold_ledger (net_change, function, transaction)
                VALUES (:cost, :function, :transaction);
            """), {'cost': cost, 'function': "post_deliver_barrels", 'transaction': barrels_json})

            # insert the ml ledger change selectively for each type of potion
            insert_ml_ledger = sqlalchemy.text("""
                INSERT INTO ml_ledger (net_change, barrel_type, function, transaction)
                VALUES (:ml_in_barrel, :barrel_type, :function, :transaction);
            """)

            for data in potion_data.values():
                new_ml, potion_type, barrels_info = data
                if new_ml > 0:
                    connection.execute(insert_ml_ledger, {
                        'ml_in_barrel': new_ml,
                        'barrel_type': potion_type,
                        'function': "post_deliver_barrels",
                        'transaction': json.dumps(barrels_info)
                    })
        except Exception as e:
            print(f"An error occurred: {e}")
            connection.rollback()  # Rollback in case of any error

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

    """ """
    # print(wholesale_catalog)

    barrels_to_purchase = []

    with db.engine.begin() as connection:
        num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, gold = connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, gold FROM global_inventory")).one()
        print("Global inventory current values:")
        print("Red ml:", num_red_ml)
        print("Green ml:", num_green_ml)
        print("Blue ml:", num_blue_ml)
        print("Dark ml:",num_dark_ml)
        print("Gold:", gold)

        #split up the catalog into potion type
        red_catalog = [x for x in wholesale_catalog if x.potion_type == [1, 0, 0, 0]]
        green_catalog = [x for x in wholesale_catalog if x.potion_type == [0, 1, 0, 0]]
        blue_catalog = [x for x in wholesale_catalog if x.potion_type == [0, 0, 1, 0]]
        dark_catalog = [x for x in wholesale_catalog if x.potion_type == [0, 0, 0, 1]]


        # order from least to greatest in price so that the cheapest is at the front
        red_sorted = sorted(red_catalog, key=lambda x: x.price / x.ml_per_barrel)
        green_sorted = sorted(green_catalog, key=lambda x: x.price / x.ml_per_barrel)
        blue_sorted = sorted(blue_catalog, key=lambda x: x.price / x.ml_per_barrel)
        dark_sorted = sorted(dark_catalog, key=lambda x: x.price / x.ml_per_barrel)


        # Print sorted lists for debugging or analysis
        print("Sorted Red Offers:", red_sorted)
        print("Sorted Green Offers:", green_sorted)
        print("Sorted Blue Offers:", blue_sorted)
        print("Sorted Dark Offers:", dark_sorted)

        # if number_of_potions[potion_type] < 10 AND gold >= filtered_barrels[0].price

        min = find_min_price(wholesale_catalog)
        print("Minimum price: ", min)
        
        print("Red sorted: ", red_sorted)
        wholesale_total = 0
        for item in wholesale_catalog:
            wholesale_total += item.quantity

        while any([num_red_ml < 200, num_green_ml < 200, num_blue_ml < 200, num_dark_ml < 200]) and gold > 0:
            updated = False

            for item in green_sorted:
                if num_green_ml < 200 and gold >= item.price:
                    if try_purchase_barrels(gold, item, barrels_to_purchase):
                        gold -= item.price
                        num_green_ml += item.ml_per_barrel
                        updated = True

            for item in red_sorted:
                    if num_red_ml < 200 and gold >= item.price:
                        if try_purchase_barrels(gold, item, barrels_to_purchase):
                            gold -= item.price
                            num_red_ml += item.ml_per_barrel
                            updated = True

            for item in blue_sorted:
                if num_blue_ml < 200 and gold >= item.price:
                    if try_purchase_barrels(gold, item, barrels_to_purchase):
                        gold -= item.price
                        num_blue_ml += item.ml_per_barrel
                        updated = True

            for item in dark_sorted:
                if num_dark_ml < 200 and gold >= item.price:
                    if try_purchase_barrels(gold, item, barrels_to_purchase):
                        gold -= item.price
                        num_dark_ml += item.ml_per_barrel
                        updated = True

            # If no updates were possible in a full pass, break to avoid infinite loop
            if not updated:
                break

    print(f"barrels plan to buy: {barrels_to_purchase}") #for debugging

    return barrels_to_purchase                

def find_min_price(wholesale_catalog: list[Barrel]):
    min_price = -1
    for item in wholesale_catalog:
        if min_price == -1: # only caught on first time (or never)
            min_price = item.price
        elif item.price < min_price:
            min_price = item.price

    return min_price

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
            barrels_to_purchase[check]["quantity"] = barrels_to_purchase[check]["quantity"] + 1
        barrel.quantity = barrel.quantity - 1
        return True
    
    return False


def check_purchase_plan(sku: str, purchase_plan):
    for i in range(0, len(purchase_plan)):
        if sku == purchase_plan[i]["sku"]:
            return i
        
    return -1