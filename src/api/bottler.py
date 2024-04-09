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

    order_quantity = 0
    for i in potions_delivered:
        if i.potion_type == [0, 100, 0, 0]:
            order_quantity += i.quantity

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        data = result.fetchone()
        id = data[0]
        num_potions = data[1]
        num_green_ml = data[2]
        ml = order_quantity * 100

        new_num_green_ml = num_green_ml - ml
        new_num_potions = num_potions + order_quantity

        update_statement = sqlalchemy.text("""
            UPDATE global_inventory
            SET num_green_ml = :ml, num_green_potions = :potions
            WHERE id = :id;
        """)

        params = {
            'ml': new_num_green_ml,
            'potions': new_num_potions,
            'id': id
        }

        connection.execute(update_statement, params)

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
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        data = result.fetchone()
        ml = data[2]
        quantity = ml // 100 #each potion requires 100ml

    if quantity > 0:
        bottle_plan.append({
                "potion_type": [0, 100, 0, 0], #hard coded to create just green potions for now...
                "quantity": quantity,
        })
    print(bottle_plan) # for debugging
        
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())