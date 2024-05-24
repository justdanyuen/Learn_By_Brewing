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

    print("******************************\n******************************\n******************************\nWholesale Catalog:")
    for barrel in wholesale_catalog:
        print(f"SKU: {barrel.sku}, ML per Barrel: {barrel.ml_per_barrel}, "
              f"Potion Type: {barrel.potion_type}, Price: {barrel.price}, Quantity: {barrel.quantity}")
        
    print("\n")


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
            "SELECT SUM(ml_capacity) FROM capacity_ledger"
        )).scalar()


        print(f"Current ml Values - {ml_counts}")
        print(f"Current Gold: {gold_total}")
        print(f"Current ml Capacity: {ml_capacity}")

        available_capacity = ml_capacity - total_ml

        # Determine which colors offer large barrels and are available
        # large_barrels_available = {color: [] for color in ['red', 'green', 'blue', 'dark']}
        # for barrel in wholesale_catalog:
        #     if "LARGE" in barrel.sku:
        #         if barrel.potion_type[0]:
        #             large_barrels_available['red'].append(barrel)
        #         elif barrel.potion_type[1]:
        #             large_barrels_available['green'].append(barrel)
        #         elif barrel.potion_type[2]:
        #             large_barrels_available['blue'].append(barrel)
        #         elif barrel.potion_type[3]:
        #             large_barrels_available['dark'].append(barrel)

        # # Sort barrels within each color by cost-effectiveness
        # for color, barrels in large_barrels_available.items():
        #     barrels.sort(key=lambda x: x.price / x.ml_per_barrel)

        # Purchase logic: try to buy at least one of each color available, prioritize repeats of black and red
        # color_priority = ['dark', 'red', 'green', 'blue']  # Prioritize purchasing dark and red for repeats
        # for color in color_priority:
        #     for barrel in large_barrels_available[color]:
        #         if gold_total >= barrel.price and available_capacity >= barrel.ml_per_barrel:
        #             quantity = 1  # Start with one barrel
        #             if large_barrel_purchases[color] < 2:  # Allow up to two barrels of the same color
        #                 success, gold_total = try_purchase_barrels(gold_total, barrel, barrels_to_purchase, quantity)
        #                 if success:
        #                     large_barrel_purchases[color] += 1
        #                     ml_counts[color] += barrel.ml_per_barrel * quantity
        #                     total_ml += barrel.ml_per_barrel * quantity
        #                     available_capacity -= barrel.ml_per_barrel * quantity
        #                     if large_barrel_purchases[color] == 2:
        #                         break  # Stop if two barrels of this color have been purchased


        # working_capacity = ml_capacity - 10000
        # available_capacity = working_capacity - total_ml

        print(f"The available ml I'm working with is: {available_capacity}\n")

        net_total = 0

        # Split the catalog into potion types
        potion_type_catalogs = {
            'red': [],
            'green': [],
            'blue': [],
            'dark': []
        }
        for barrel in wholesale_catalog:
            if "LARGE" in barrel.sku or "MEDIUM" in barrel.sku:
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
            print("\n")

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

        desired_ml_per_color = 35000  # Example desired ml per potion type

        gold_spent = 0
        # Purchase decision logic - Prioritize larger barrels first
        for color in ['red', 'green', 'blue']:
            catalog = potion_type_catalogs[color]
            print(f"Checking {color} barrels:\n")

            large_barrel = next((barrel for barrel in catalog if "LARGE" in barrel.sku), None)
            if large_barrel:
                if gold_total >= large_barrel.price and available_capacity >= large_barrel.ml_per_barrel:
                    quantity = 1
                    success, gold_total = try_purchase_barrels(gold_total, large_barrel, barrels_to_purchase, quantity)
                    if success:
                        ml_added = large_barrel.ml_per_barrel * quantity
                        ml_counts[color] += ml_added
                        gold_spent += large_barrel.price * quantity
                        total_ml += ml_added
                        available_capacity -= ml_added
                        net_total += large_barrel.ml_per_barrel * quantity
                    continue

            medium_barrels = [barrel for barrel in catalog if "MEDIUM" in barrel.sku]
            if medium_barrels:
                if gold_total >= medium_barrels[0].price * 2 and available_capacity >= medium_barrels[0].ml_per_barrel * 2:
                    barrel = medium_barrels[0]
                    quantity = 2
                    success, gold_total = try_purchase_barrels(gold_total, barrel, barrels_to_purchase, quantity)
                    if success:
                        ml_added = barrel.ml_per_barrel * quantity
                        ml_counts[color] += ml_added
                        gold_spent += barrel.price * quantity
                        total_ml += ml_added
                        available_capacity -= ml_added
                        net_total += barrel.ml_per_barrel * quantity
                    continue

            # if catalog and gold_total >= catalog[0].price and available_capacity >= catalog[0].ml_per_barrel:
            #     barrel = catalog[0]
            #     quantity = 1
            #     success, gold_total = try_purchase_barrels(gold_total, barrel, barrels_to_purchase, quantity)
            #     if success:
            #         ml_added = barrel.ml_per_barrel * quantity
            #         ml_counts[color] += ml_added
            #         total_ml += ml_added
            #         available_capacity -= ml_added
            #         net_total += barrel.ml_per_barrel * quantity

            
            # # Sort the catalog by ml_per_barrel in descending order
            # catalog.sort(key=lambda x: x.ml_per_barrel, reverse=True)
            # current_ml_deficit = desired_ml_per_color - ml_counts[color]  # Calculate deficit

        
            # for barrel in catalog:
                
            #     # # if ml_counts[color] >= 3000 and color != 'dark':
            #     # if ml_counts[color] >= 6000:
            #     #     continue #if I have 500ml, for now that's good 

            #     if gold_total < barrel.price:
            #         continue

            #     # quantity = min(barrel.quantity, (gold_total // barrel.price), (ml_capacity - total_ml) // barrel.ml_per_barrel)
            #     # Hard coded FOR NOW to max out at 10000 so I can have 10000 reserve for dark barrel purchases
            #     # if color == 'dark':
            #     #     quantity = 1
            #     # else:


            #     # Calculate the maximum quantity of barrels that can be purchased without exceeding 20,000 ml per color
            #     max_ml_quantity = (desired_ml_per_color - ml_counts[color]) // barrel.ml_per_barrel
            #     print(f"max_ml_quantity: {max_ml_quantity}")


            #     proportional_quantity = int((current_ml_deficit / desired_ml_per_color) * barrel.quantity)
            #     # Then incorporate this into your quantity calculation
            #     quantity = min(barrel.quantity, (gold_total // barrel.price), available_capacity // barrel.ml_per_barrel, proportional_quantity, max_ml_quantity)
            #     print(f"quantity: {quantity}")

            #     # Ensure that adding this quantity does not exceed the desired ml per color
            #     if ml_counts[color] + barrel.ml_per_barrel * quantity > desired_ml_per_color:
            #         quantity = (desired_ml_per_color - ml_counts[color]) // barrel.ml_per_barrel
            #     print(f"checked quantity: {quantity}")

            #     if color == 'dark':
            #         quantity = 1

            #     # Final purchasing decision
            #     if quantity > 0:
            #         success, gold_total = try_purchase_barrels(gold_total, barrel, barrels_to_purchase, quantity)
            #         if success:
            #             ml_added = barrel.ml_per_barrel * quantity
            #             ml_counts[color] += ml_added
            #             total_ml += ml_added
            #             available_capacity -= ml_added
            #             net_total += barrel.ml_per_barrel * quantity
                                
            #     # quantity = min(barrel.quantity, (gold_total // barrel.price), available_capacity // barrel.ml_per_barrel)

            #     # if quantity <= 0:
            #     #     continue

            #     # success, gold_total = try_purchase_barrels(gold_total, barrel, barrels_to_purchase, quantity)
            #     # if success:
            #     #     ml_added = barrel.ml_per_barrel * quantity
            #     #     ml_counts[color] += barrel.ml_per_barrel * quantity
            #     #     total_ml += ml_added
            #     #     available_capacity -= ml_added  # Deduct the used capacity from available

            #     #     if available_capacity <= 0:
            #     #         break  # Exit if no more capacity is available

            #     # else:
            #     #     print(f"Not enough gold, has {gold_total} but requires {barrel.price * quantity}")

        # # Don'y buy anymore barrels it's grindtime
        # print("setting the barrel plan to empty, closing down our shop!")
        # barrels_to_purchase = []

        print(f"Barrels to purchase: {barrels_to_purchase}\n******************************\n******************************\n******************************\n")   
        print(f"The total amount of ml we purchased on this tick was {net_total}")
        print(f"The amount of gold spent on purchasing barrels was {gold_spent}")
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
