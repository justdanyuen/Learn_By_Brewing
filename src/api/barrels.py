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

            current_time = connection.execute(sqlalchemy.text("""
                            SELECT day, hour FROM time_table ORDER BY created_at DESC LIMIT 1;
                        """)).first()  # Use first() to fetch the first result directly
            
            # Update the gold ledger
            if current_time:
                connection.execute(sqlalchemy.text("""
                    INSERT INTO gold_ledger (net_change, function, transaction, day, hour)
                    VALUES (:cost, 'deliver_barrels', :transaction, :day, :hour);
                """), {'cost': -total_cost, 
                       'transaction': barrels_json, 
                       'day': current_time.day, 
                       'hour': current_time.hour})
            else:
                connection.execute(sqlalchemy.text("""
                    INSERT INTO gold_ledger (net_change, function, transaction)
                    VALUES (:cost, 'deliver_barrels', :transaction);
                """), {'cost': -total_cost, 'transaction': barrels_json})

            # Insert changes into the ml_ledger
            for color, (ml_change, barrels_info) in potion_data.items():
                if ml_change > 0:
                    

                    if current_time:  # Check if a result was returned
                        connection.execute(sqlalchemy.text("""
                            INSERT INTO ml_ledger (net_change, barrel_type, function, transaction, day, hour)
                            VALUES (:ml_change, :barrel_type, 'deliver_barrels', :transaction, :day, :hour);
                        """), {
                            'ml_change': ml_change,
                            'barrel_type': color,
                            'transaction': json.dumps(barrels_info),
                            'day': current_time.day,
                            'hour': current_time.hour
                        })
                    else:
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

    print("Wholesale Catalog:")
    for barrel in wholesale_catalog:
        print(f"SKU: {barrel.sku}, ML per Barrel: {barrel.ml_per_barrel}, "
              f"Potion Type: {barrel.potion_type}, Price: {barrel.price}, Quantity: {barrel.quantity}")
        
    print("\n\n")


    barrels_to_purchase = []

    with db.engine.begin() as connection:
        # Retrieve current ml amounts and total gold from ledgers
        ml_totals = connection.execute(sqlalchemy.text(
            """
            SELECT barrel_type, COALESCE(SUM(net_change), 0) AS total_ml
            FROM ml_ledger
            GROUP BY barrel_type
            """
        )).mappings().all()

        # Initialize ml counts from the fetched data
        ml_counts = {'red': 0, 'green': 0, 'blue': 0, 'dark': 0}
        for ml in ml_totals:
            if ml['barrel_type'] in ml_counts:
                ml_counts[ml['barrel_type']] = ml['total_ml']

        total_ml = sum(ml_counts.values())

        gold_total = connection.execute(sqlalchemy.text(
            "SELECT SUM(net_change) FROM gold_ledger"
        )).scalar()

        ml_capacity = connection.execute(sqlalchemy.text(
            "SELECT ml_capacity FROM capacity_ledger LIMIT 1"
        )).scalar()


        print(f"Current ml Values - {ml_counts}")
        print(f"Current Gold: {gold_total}")
        # print(f"Current ml Capacity: {ml_capacity}")


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
            print(f"Sorted {color.capitalize()} Offers:", potion_type_catalogs[color])

        if potion_type_catalogs['dark']:

            # Execute query and fetch the first result
            current_time = connection.execute(sqlalchemy.text("""
                SELECT day, hour FROM time_table ORDER BY created_at DESC LIMIT 1;
            """)).first()  # Use first() to fetch the first result directly

            if current_time:  # Check if a result was returned
                day = current_time.day  # Access columns directly via the result
                hour = current_time.hour

                # Execute the insertion with the fetched day and hour
                connection.execute(sqlalchemy.text("""
                    INSERT INTO dark_order_tracker (day, hour)
                    VALUES (:day, :hour);
                """), {'day': day, 'hour': hour})


        # Purchase decision logic - Prioritize larger barrels first
        for color in ['dark', 'red', 'green', 'blue']:
            catalog = potion_type_catalogs[color]
            
            # Sort the catalog by ml_per_barrel in descending order
            catalog.sort(key=lambda x: x.ml_per_barrel, reverse=True)
            
            for barrel in catalog:
                if ml_counts[color] >= 500:
                    continue #if I have 500ml, for now that's good 

                if gold_total < barrel.price:
                    continue

                quantity = min(barrel.quantity, (gold_total // barrel.price), (ml_capacity - total_ml) // barrel.ml_per_barrel)

                if quantity == 0:
                    continue

                success, gold_total = try_purchase_barrels(gold_total, barrel, barrels_to_purchase, quantity)
                if success:
                    ml_counts[color] += barrel.ml_per_barrel * quantity
                    total_ml += barrel.ml_per_barrel * quantity
                else:
                    print(f"Not enough gold, has {gold_total} but requires {barrel.price * quantity}")

                print(f"Barrels to purchase: {barrels_to_purchase}")   
    return barrels_to_purchase  

def try_purchase_barrels(gold, barrel, barrels_to_purchase, quantity):
    """
    Try to purchase the given barrel.

    Returns:
        success (bool): Whether the purchase was successful.
        remaining_gold (int): The remaining amount of gold after the purchase.
    """
    cost = barrel.price * quantity
    if cost <= gold and barrel.quantity >= quantity:
        check = check_purchase_plan(barrel.sku, barrels_to_purchase)
        if check == -1:
            barrels_to_purchase.append({
                "sku": barrel.sku,
                "quantity": quantity,
                "ml_per_barrel": barrel.ml_per_barrel,
                "potion_type": barrel.potion_type,
                "price": barrel.price
            })
        else:
            barrels_to_purchase[check]["quantity"] += quantity
        barrel.quantity -= quantity
        return True, gold - cost
    return False, gold

def check_purchase_plan(sku: str, purchase_plan):
    for i, plan in enumerate(purchase_plan):
        if plan['sku'] == sku:
            return i
    return -1
