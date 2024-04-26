from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

# dictionary do index into my potion names
potions_library = {
    (100, 0, 0, 0): "red potion",
    (0, 100, 0, 0): "green potion",
    (0, 0, 100, 0): "blue potion",
    (0, 0, 0, 100): "black potion",
    (50, 0, 50, 0): "purple potion",
    (33, 34, 33, 0): "white potion"
}
@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    print(f"potions delivered: {potions_delivered} order_id: {order_id}")

    red_used = 0
    green_used = 0
    blue_used = 0
    dark_used = 0

    with db.engine.begin() as connection:
    # determine amount of ml for each type used by the potions delivered
        for potion in potions_delivered:
            name = potions_library[tuple(potion.potion_type)]
            sku = name.upper()
            sku = sku.replace(" ", "_")
            sku += "_0"
            quantity = potion.quantity
            potion_sku = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory WHERE sku = :sku LIMIT 1;"), {'sku': sku}).fetchone()
            if not potion_sku:
                # insert
                price = 50
                connection.execute(sqlalchemy.text("INSERT INTO potion_inventory (sku, red_ml, green_ml, blue_ml, dark_ml, quantity, name, price) VALUES (:sku, :red_ml, :green_ml, :blue_ml, :dark_ml, :quantity, :name, :price);"), 
                                {'sku': sku,
                                    'red_ml': potion.potion_type[0],
                                    'green_ml': potion.potion_type[1],
                                    'blue_ml': potion.potion_type[2],
                                    'dark_ml': potion.potion_type[3],
                                    'quantity': quantity,
                                    'name': name,
                                    'price': price
                                    })
                print("inserting potion type: " + str(type))
            else:
                # Fetch current quantity from the database first
                current_quantity = potion_sku.quantity  # Assuming quantity is fetched correctly from the DB
                new_quantity = current_quantity + quantity  # Add the newly delivered quantity to the existing one

                # Update the database with the new total quantity
                connection.execute(sqlalchemy.text("""
                                                    UPDATE potion_inventory
                                                    SET quantity = :new_quantity
                                                    WHERE sku = :sku;
                                                    """),
                                                    {'new_quantity': new_quantity, 
                                                    'sku': sku})
            red_used += potion.potion_type[0] * potion.quantity
            green_used += potion.potion_type[1] * potion.quantity
            blue_used += potion.potion_type[2] * potion.quantity
            dark_used += potion.potion_type[3] * potion.quantity

            red_ml, green_ml, blue_ml, dark_ml = connection.execute(sqlalchemy.text("SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory")).one()

            red_ml -= red_used
            green_ml -= green_used
            blue_ml -= blue_used
            dark_ml -= dark_used

            connection.execute(sqlalchemy.text("""
                                    UPDATE global_inventory
                                    SET num_green_ml = :green, num_red_ml = :red, num_blue_ml = :blue, num_dark_ml = :dark
                                    WHERE id = 1;
                                    """),
                                    {'green': green_ml, 'red': red_ml, 'blue': blue_ml, 'dark': dark_ml})
            
    return "OK"


    # num_req_red = 0
    # num_req_green = 0
    # num_req_blue = 0
    # num_req_dark = 0
    # for i in potions_delivered:
    #     if i.potion_type == [100, 0, 0, 0]:
    #         num_req_red += i.quantity
    #     elif i.potion_type == [0, 100, 0, 0]:
    #         num_req_green += i.quantity
    #     elif i.potion_type == [0, 0, 100, 0]:
    #         num_req_blue += i.quantity
    #     elif i.potion_type == [0, 0, 0, 100]:
    #         num_req_dark += i.quantity

    # with db.engine.begin() as connection:
    #     globe = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).one()
    #     id = globe.id
    #     num_red_potions = globe.num_red_potions
    #     num_green_potions = globe.num_green_potions
    #     num_blue_potions = globe.num_blue_potions
    #     num_dark_potions = globe.num_dark_potions

    #     num_red_ml = globe.num_red_ml
    #     num_green_ml = globe.num_green_ml
    #     num_blue_ml = globe.num_blue_ml
    #     num_dark_ml = globe.num_dark_ml

    #     ml_req_red = num_req_red * 100
    #     ml_req_green = num_req_green * 100
    #     ml_req_blue = num_req_blue * 100
    #     ml_req_dark = num_req_dark * 100

    #     connection.execute(sqlalchemy.text("""
    #                                 UPDATE global_inventory
    #                                 SET num_red_ml = :ml_red, num_red_potions = :pot_red, num_green_ml = :ml_green, num_green_potions = :pot_green, num_blue_ml = :ml_blue, num_blue_potions = :pot_blue, num_dark_ml = :ml_dark, num_dark_potions = :pot_dark
    #                                 WHERE id = :id;
    #                                 """),
    #                                 {'ml_red': num_red_ml - ml_req_red, 'pot_red': num_red_potions + num_req_red, 'ml_green': num_green_ml - ml_req_green, 'pot_green': num_green_potions + num_req_green, 'ml_blue': num_blue_ml - ml_req_blue, 'pot_blue': num_blue_potions + num_req_blue, 'ml_dark': num_dark_ml - ml_req_dark, 'pot_dark': num_dark_potions + num_req_dark,'id': id})

    # return "OK"


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

        potion_inventory = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory ORDER BY id ASC;")).fetchall()

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
        if recipe.quantity >= 3:
            continue  # Skip to the next recipe if already enough stock
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