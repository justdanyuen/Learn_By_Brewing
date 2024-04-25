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
        result = connection.execute(sqlalchemy.text("SELECT * FROM potion_inventory WHERE quantity > 0;"))
        for row in result:
            print("Adding to catalog: " + str(row))
            sku = row.sku
            type = [row.red_ml, row.green_ml, row.blue_ml, row.dark_ml]
            quantity = row.quantity
            name = row.name
            price = row.price
            print("Number of " + str(type) + " potions offered: " + str(quantity))
            if quantity > 0: # should be unecessary because of our query params but fail-safe
                catalog.append({
                    "sku": sku,
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "potion_type": type,
                })

    print(catalog)
    return catalog
