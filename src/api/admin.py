from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    with db.engine.begin() as connection:
                # reset global_inventory
                result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory;")) # for debugging
                globe = result.fetchone()
                print("Current database status before reset: " + str(globe[1]) + " " + str(globe[2]) + " " + str(globe[3]) + " " + str(globe[4]) + " " + str(globe[5])) # for debugging
                connection.execute(sqlalchemy.text("""
                                                UPDATE global_inventory
                                                SET num_green_ml = 0, gold = 100, num_dark_ml = 0, num_red_ml = 0, num_blue_ml = 0
                                                WHERE id = 1;
                                                """))
                
                # reset/clear potion_inventory, carts, cart_items
                connection.execute(sqlalchemy.text("UPDATE potion_inventory SET quantity = 0;"))
                # set carts / cart items to nonactive for this run, but still save results
                connection.execute(sqlalchemy.text("UPDATE carts SET current_shop = False;"))
                connection.execute(sqlalchemy.text("UPDATE cart_items SET current_shop = False;"))


                 
    return "OK"

