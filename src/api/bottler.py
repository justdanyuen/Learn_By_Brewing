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

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    print(f"potions delivered: {potions_delivered} order_id: {order_id}")

    num_req_red = 0
    num_req_green = 0
    num_req_blue = 0
    num_req_dark = 0
    for i in potions_delivered:
        if i.potion_type == [100, 0, 0, 0]:
            num_req_red += i.quantity
        elif i.potion_type == [0, 100, 0, 0]:
            num_req_green += i.quantity
        elif i.potion_type == [0, 0, 100, 0]:
            num_req_blue += i.quantity
        elif i.potion_type == [0, 0, 0, 100]:
            num_req_dark += i.quantity

    with db.engine.begin() as connection:
        globe = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).one()
        id = globe.id
        num_red_potions = globe.num_red_potions
        num_green_potions = globe.num_green_potions
        num_blue_potions = globe.num_blue_potions
        num_dark_potions = globe.num_dark_potions

        num_red_ml = globe.num_red_ml
        num_green_ml = globe.num_green_ml
        num_blue_ml = globe.num_blue_ml
        num_dark_ml = globe.num_dark_ml

        ml_req_red = num_req_red * 100
        ml_req_green = num_req_green * 100
        ml_req_blue = num_req_blue * 100
        ml_req_dark = num_req_dark * 100

        connection.execute(sqlalchemy.text("""
                                    UPDATE global_inventory
                                    SET num_red_ml = :ml_red, num_red_potions = :pot_red, num_green_ml = :ml_green, num_green_potions = :pot_green, num_blue_ml = :ml_blue, num_blue_potions = :pot_blue, num_dark_ml = :ml_dark, num_dark_potions = :pot_dark
                                    WHERE id = :id;
                                    """),
                                    {'ml_red': num_red_ml - ml_req_red, 'pot_red': num_red_potions + num_req_red, 'ml_green': num_green_ml - ml_req_green, 'pot_green': num_green_potions + num_req_green, 'ml_blue': num_blue_ml - ml_req_blue, 'pot_blue': num_blue_potions + num_req_blue, 'ml_dark': num_dark_ml - ml_req_dark, 'pot_dark': num_dark_potions + num_req_dark,'id': id})

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
        globe = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).one()
        num_red_ml = globe.num_red_ml
        num_green_ml = globe.num_green_ml
        num_blue_ml = globe.num_blue_ml
        num_dark_ml = globe.num_dark_ml
        num_red_potions = globe.num_red_potions
        num_green_potions = globe.num_green_potions
        num_blue_potions = globe.num_blue_potions
        num_dark_potions = globe.num_dark_potions

        if num_red_potions < 10 and num_red_ml >= 100:
            quantity = min(10, num_red_ml // 100)
            bottle_plan.append({
                "potion_type": [100, 0, 0, 0],
                "quantity": quantity,
        })
            
        if num_green_potions < 10 and num_green_ml >= 100:
            quantity = min(10, num_green_ml // 100)
            bottle_plan.append({
                "potion_type": [0, 100, 0, 0],
                "quantity": quantity,
        })
            
        if num_blue_potions < 10 and num_blue_ml >= 100:
            quantity = min(10, num_blue_ml // 100)
            bottle_plan.append({
                "potion_type": [0, 0, 100, 0],
                "quantity": quantity,
        })
            
        if num_dark_potions < 10 and num_dark_ml >= 100:
            quantity = min(10, num_dark_ml // 100)
            bottle_plan.append({
                "potion_type": [0, 0, 0, 100],
                "quantity": quantity,
        })
    
    print(bottle_plan) # for debugging
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())