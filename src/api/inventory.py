from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """
    with db.engine.begin() as connection:
        red_pot, green_pot, blue_pot, dark_pot, red_ml, green_ml, blue_ml, dark_ml, gold = connection.execute(sqlalchemy.text("SELECT num_red_potions, num_green_potions, num_blue_potions, num_dark_potions, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, gold FROM global_inventory")).one()
    print({"red potions:": red_pot, " red ml: ": red_ml,"green potions:": green_pot, " green ml: ": green_ml, "blue potions:": blue_pot, " blue ml: ": blue_ml, "dark potions:": dark_pot, " dark ml: ": dark_ml, " gold: ": gold})
    return {"red potions": red_pot, "red ml": red_ml,"green potions": green_pot, "green ml": green_ml, "blue potions": blue_pot, "blue ml": blue_ml, "dark potions": dark_pot, "dark ml": dark_ml, "gold": gold}
    

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return {
        "potion_capacity": 0,
        "ml_capacity": 0
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return "OK"
