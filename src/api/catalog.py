from fastapi import APIRouter
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    catalog = []

    with db.engine.begin() as connection:
        num_green_potions, num_red_potions, num_blue_potions, num_dark_potions = connection.execute(sqlalchemy.text("SELECT num_green_potions, num_red_potions, num_blue_potions, num_dark_potions FROM global_inventory")).fetchone()
        
#cursor result in SQL
        if num_green_potions > 0:
            catalog.append({
                "sku": "GREEN_POTION_0",
                "name": "green potion",
                "quantity": num_green_potions,
                "price": 50,
                "potion_type": [0, 100, 0, 0],
            })
        if num_red_potions > 0:
            catalog.append({
                "sku": "RED_POTION_0",
                "name": "red potion",
                "quantity": num_red_potions,
                "price": 50,
                "potion_type": [100, 0, 0, 0],
            })
        if num_blue_potions > 0:
            catalog.append({
                "sku": "BLUE_POTION_0",
                "name": "blue potion",
                "quantity": num_red_potions,
                "price": 50,
                "potion_type": [0, 0, 100, 0],
            })
        if num_dark_potions > 0:
            catalog.append({
                "sku": "BLACK_POTION_0",
                "name": "black potion",
                "quantity": num_dark_potions,
                "price": 50,
                "potion_type": [0, 0, 0, 100],
            })
    print(catalog)
    return catalog
