from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

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

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ """
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    with db.engine.begin() as connection:
        globe = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).one()
        gold = globe.gold
        num_red_ml = globe.num_red_ml
        num_green_ml = globe.num_green_ml
        num_blue_ml = globe.num_blue_ml
        num_dark_ml = globe.num_dark_ml
        new_red = 0
        new_green = 0
        new_blue = 0
        new_dark = 0
        cost = 0


        for item in barrels_delivered:
            quantity = item.quantity
            ml_per_barrel = item.ml_per_barrel
            price = item.price

            if item.potion_type == [1, 0, 0, 0]: #red
                new_red += quantity * ml_per_barrel

            elif item.potion_type == [0, 1, 0, 0]: #green
                new_green += quantity * ml_per_barrel

            elif item.potion_type == [0, 0, 1, 0]: #green
                new_blue += quantity * ml_per_barrel

            elif item.potion_type == [0, 0, 0, 1]: #green
                new_dark += quantity * ml_per_barrel

            else:
                print("potion delivered wasn't red, green, blue, or dark?.....") #error case
            cost += price * quantity
        
        # Define the SQL update statement using sqlalchemy.text for prepared statements
        update_statement = sqlalchemy.text("""
            UPDATE global_inventory 
            SET num_red_ml = :new_red, 
                num_green_ml = :new_green, 
                num_blue_ml = :new_blue, 
                num_dark_ml = :new_dark, 
                gold = :new_gold 
            WHERE id = :id;
        """)

        # Execute the update within a transaction using context management
        with db.engine.begin() as connection:
            result = connection.execute(update_statement, {
                'new_red': new_red + num_red_ml,  # Assuming you want to add the new amount to the existing
                'new_green': new_green + num_green_ml, 
                'new_blue': new_blue + num_blue_ml, 
                'new_dark': new_dark + num_dark_ml, 
                'new_gold': gold - cost,  # Assuming cost is deducted from the existing gold
                'id': 1  # Assuming the ID is static as per your example
            })

        # Output the results of the operation
        print(f"DELIVERY - gold paid: {cost}, red_ml: {new_red}, green_ml: {new_green}, blue_ml: {new_blue}, dark_ml: {new_dark}")

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

    MIN_POTIONS = 10

    barrels_to_purchase = []

    with db.engine.begin() as connection:
        globe = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).one()
        print("Global inventory current values:")
        print("Red Potions:", globe.num_red_potions, "Red ml:", globe.num_red_ml)
        print("Green Potions:", globe.num_green_potions, "Green ml:", globe.num_green_ml)
        print("Blue Potions:", globe.num_blue_potions, "Blue ml:", globe.num_blue_ml)
        print("Dark Potions:", globe.num_dark_potions, "Dark ml:", globe.num_dark_ml)
        print("Gold:", globe.gold)

        gold = globe.gold
        num_red_potions = globe.num_red_potions
        num_green_potions = globe.num_green_potions
        num_blue_potions = globe.num_blue_potions
        num_dark_potions = globe.num_dark_potions

        num_red_ml = globe.num_red_ml
        num_green_ml = globe.num_green_ml
        num_blue_ml = globe.num_blue_ml
        num_dark_ml = globe.num_dark_ml

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
        
        wholesale_total = 0
        for item in wholesale_catalog:
            wholesale_total += item.quantity

        barrels_purchased = 0
        while gold > min and min != -1 and barrels_purchased < wholesale_total:

            for item in red_sorted:
                if try_purchase_barrels(gold, item, num_red_potions, MIN_POTIONS, barrels_to_purchase) == True and num_red_ml < 1000:
                    gold -= item.price
                    barrels_purchased += 1
                    break

            for item in green_sorted:
                if try_purchase_barrels(gold, item, num_green_potions, MIN_POTIONS, barrels_to_purchase) == True and num_green_ml < 1000:
                    gold -= item.price
                    barrels_purchased += 1
                    break
            
            for item in blue_sorted:
                if try_purchase_barrels(gold, item, num_blue_potions, MIN_POTIONS, barrels_to_purchase) == True and num_blue_ml < 1000:
                    gold -= item.price
                    barrels_purchased += 1
                    break

            for item in dark_sorted:
                if try_purchase_barrels(gold, item, num_dark_potions, MIN_POTIONS, barrels_to_purchase) == True and num_dark_ml < 1000:
                    gold -= item.price
                    barrels_purchased += 1
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

def try_purchase_barrels(gold, barrel, current_potions, min_potions, barrels_to_purchase):
    if current_potions >= min_potions:
        return False

    if barrel.price <= gold and barrel.quantity > 0 and current_potions < min_potions:
        check = check_purchase_plan(barrel.sku, barrels_to_purchase)
        if check == -1:
            barrels_to_purchase.append({
                "sku": barrel.sku,
                "quantity": 1
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



    # print(f"barrel catalog: {wholesale_catalog}")

    # with db.engine.begin() as connection:
    #     results = connection.execute(sqlalchemy.text("""
    #                                  SELECT
    #                                  green_ml,
    #                                  blue_ml,
    #                                  red_ml,
    #                                  dark_ml,
    #                                  gold,
    #                                  ml_threshold_normal,
    #                                  ml_threshold_large,
    #                                  ml_capacity
    #                                  FROM global_inventory""")).one()
        
    # ml_inventory = [results.red_ml, results.green_ml, results.blue_ml, results.dark_ml]
    # ml_threshold_normal = results.ml_threshold_normal
    # ml_threshold_large = results.ml_threshold_large
    # MAX_ML = results.ml_capacity
    # barrel_purchases = []
    # current_ml = sum(ml_inventory)
    # gold = results.gold

    # selling_large = any(item.sku_startwith('LARGE') for item in wholesale_catalog)

    # threshold = ml_threshold_large if selling_large else ml_threshold_normal
    # for i, ml in enumerate(ml_inventory):
    #     if ml < threshold:
    #         potion_type = [int(j=i) for j in range(4)]
    #         barrel_purchase = calculate_barrel_to_purchase(wholesale_catalog, gold/4 if gold > 300 else gold, potion_type, MAX_ML - current_ml)
    #         if barrel_purchase is not None:
    #             price = next(item.price for item in wholesale_catalog if item.sku == barrel_purchase['sku'])
    #             ml_per_barrel