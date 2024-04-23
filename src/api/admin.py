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

    # with db.engine.begin() as connection:
    #         result = connection.execute(sqlalchemy.text("SELECT id, num_green_potions, num_green_ml FROM global_inventory")).one()
    #         id = result.id
    #         num_green_potions = result.num_green_potions
    #         num_green_ml = result.num_green_ml
    #         ml_req = num_req * 100

    #         connection.execute(sqlalchemy.text("""
    #                                     UPDATE global_inventory
    #                                     SET num_green_ml = :ml, num_green_potions = :potions
    #                                     WHERE id = :id;
    #                                     """),
    #                                     {'ml': num_green_ml - ml_req, 'potions': num_green_potions + num_req, 'id': id})


    return "OK"

