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
        # reset/clear potion_inventory, carts, cart_items
        # set carts / cart items to nonactive for this run, but still save results
        connection.execute(sqlalchemy.text("DELETE FROM carts;"))
        connection.execute(sqlalchemy.text("DELETE FROM cart_items;"))
        connection.execute(sqlalchemy.text("DELETE FROM gold_ledger;"))
        connection.execute(sqlalchemy.text("DELETE FROM ml_ledger;"))
        connection.execute(sqlalchemy.text("DELETE FROM potion_ledger;"))
        connection.execute(sqlalchemy.text("DELETE FROM time_table;"))
        connection.execute(sqlalchemy.text("DELETE FROM capacity_ledger;"))

        # Reset the ID sequences for all tables with auto-incremented IDs
        connection.execute(sqlalchemy.text("ALTER SEQUENCE carts_id_seq RESTART WITH 1;"))
        connection.execute(sqlalchemy.text("ALTER SEQUENCE cart_items_id_seq RESTART WITH 1;"))
        connection.execute(sqlalchemy.text("ALTER SEQUENCE gold_ledger_id_seq RESTART WITH 1;"))
        connection.execute(sqlalchemy.text("ALTER SEQUENCE ml_ledger_id_seq RESTART WITH 1;"))
        connection.execute(sqlalchemy.text("ALTER SEQUENCE potion_ledger_id_seq RESTART WITH 1;"))
        connection.execute(sqlalchemy.text("ALTER SEQUENCE time_table_id_seq RESTART WITH 1;"))



        # Reinitialize the gold to 100
        connection.execute(sqlalchemy.text("""
            INSERT INTO gold_ledger (net_change, function, transaction)
            VALUES (100, 'reset', 'Initial gold set to 100 upon reset');
            """))
        
        connection.execute(sqlalchemy.text("INSERT INTO capacity_ledger (ml_capacity, potion_capacity) VALUES (10000, 50)"))


    print("Game state has been reset. All ledgers cleared and gold set to 100.")

    return "OK"

