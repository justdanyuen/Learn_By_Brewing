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

    for i in barrels_delivered:
        quantity = i.quantity
        price = i.price
        potion_type = i.potion_type
        ml_per_barrel = i.ml_per_barrel

        if potion_type == [0, 1, 0, 0]:
            with db.engine.begin() as connection:
                result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
                data = result.fetchone()
                id = data[0]
                num_green_ml = data[3]
                gold = data[4]

                new_ml = num_green_ml + (ml_per_barrel * quantity)
                new_gold = gold - (price * quantity)

                update_statement = sqlalchemy.text(
                "UPDATE global_inventory SET num_green_ml = :new_ml, gold = :new_gold WHERE id = :id"
                )
                with db.engine.begin() as connection:
                    result = connection.execute(update_statement, new_ml=new_ml, new_gold=new_gold, id=id)

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    # print(wholesale_catalog)

    filtered_green_barrels = []
    num_green_potions = 0

    for i in wholesale_catalog:
        quantity = i.quantity
        price = i.price
        potion_type = i.potion_type
        ml_per_barrel = i.ml_per_barrel

        if potion_type == [0, 1, 0, 0]:
            with db.engine.begin() as connection:
                result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
                data = result.fetchone()
                id = data[0]
                num_green_ml = data[3]
                num_green_potions = data[2]
                gold = data[4]
                num_purchase = 0
                while gold >= price and quantity > 0:
                    gold -= price
                    num_purchase += 1
                    quantity -= 1

                if num_purchase > 0:
                    new_num_green_ml = num_green_ml + (num_purchase * ml_per_barrel)
                    with db.engine.begin() as connection:
                        update_stmt = sqlalchemy.text("""
                        UPDATE global_inventory 
                        SET num_green_ml = :new_ml, gold = :new_gold 
                        WHERE id = :id
                    """)
                        connection.execute(update_stmt, {'new_ml': new_num_green_ml, 'new_gold': gold, 'id': id})
                        
                filtered_green_barrels.append({'id': id, 'num_purchase': num_purchase})
    if num_green_potions >= 10:
        return []
    else:
        print(filtered_green_barrels)
        return filtered_green_barrels
                