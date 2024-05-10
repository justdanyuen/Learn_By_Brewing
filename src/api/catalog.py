from fastapi import APIRouter
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Generates a catalog of available potions by aggregating changes from the potion_ledger.
    """

    catalog = []
    with db.engine.begin() as connection:
        # Aggregate current quantities from the potion_ledger
        current_inventory = connection.execute(sqlalchemy.text(
            """
            SELECT pi.id, pi.sku, pi.name, pi.price, 
                   pi.red_ml, pi.green_ml, pi.blue_ml, pi.dark_ml,
                   COALESCE(SUM(pl.quantity), 0) AS total_quantity
            FROM potion_inventory pi
            LEFT JOIN potion_ledger pl ON pi.id = pl.potion_id
            GROUP BY pi.id
            HAVING COALESCE(SUM(pl.quantity), 0) > 0
            """
        ))

        for row in current_inventory:
            # print("Adding to catalog: " + str(row))
            sku = row.sku
            potion_type = [row.red_ml, row.green_ml, row.blue_ml, row.dark_ml]
            quantity = row.total_quantity
            name = row.name
            price = row.price
            print("Number of " + str(potion_type) + " potions offered: " + str(quantity))
            
            catalog.append({
                "sku": sku,
                "name": name,
                "quantity": quantity,
                "price": price,
                "potion_type": potion_type,
            })

    catalog = catalog[:6]


    print(catalog)
    return catalog
