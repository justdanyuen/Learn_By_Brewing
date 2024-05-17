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
            ORDER BY CASE 
                WHEN pi.sku LIKE '%RED%' THEN 1
                WHEN pi.sku LIKE '%BLACK%' THEN 2
                WHEN pi.sku LIKE '%GREEN%' THEN 3
                WHEN pi.sku LIKE '%PURPLE%' THEN 4
                WHEN pi.sku LIKE '%YELLOW%' THEN 5
                WHEN pi.sku LIKE '%WHITE%' THEN 6
                WHEN pi.sku LIKE '%BLUE%' THEN 7
                ELSE 8
            END, pi.sku
            """
        ))

        inventory_list = list(current_inventory.mappings())

        # print("CURRENT INVENTORY LIST:")
        # for row in inventory_list:
        #     print(f"ID: {row['id']}, SKU: {row['sku']}, Name: {row['name']}, Price: {row['price']}, "
        #           f"Red ML: {row['red_ml']}, Green ML: {row['green_ml']}, Blue ML: {row['blue_ml']}, "
        #           f"Dark ML: {row['dark_ml']}, Total Quantity: {row['total_quantity']}")

        # current_inventory = connection.execute(sqlalchemy.text(
        #     """
        #     SELECT pi.id, pi.sku, pi.name, pi.price, 
        #            pi.red_ml, pi.green_ml, pi.blue_ml, pi.dark_ml,
        #            COALESCE(SUM(pl.quantity), 0) AS stock_quantity,
        #            pqs.total_quantity
        #     FROM potion_inventory pi
        #     LEFT JOIN potion_ledger pl ON pi.id = pl.potion_id
        #     LEFT JOIN (
        #         SELECT item_sku, SUM(quantity) AS total_quantity
        #         FROM cart_items
        #         GROUP BY item_sku
        #     ) pqs ON pi.sku = pqs.item_sku
        #     GROUP BY pi.id, pqs.total_quantity
        #     ORDER BY pqs.total_quantity DESC NULLS LAST
        #     """
        # ))

        current_time = connection.execute(sqlalchemy.text("""
                            SELECT day, hour FROM time_table ORDER BY created_at DESC LIMIT 1;
                        """)).first()  # Use first() to fetch the first result directly
        
        print(f"\nThe current time is {current_time.day}  {current_time.hour}")

        dark_blue = None

        # Find the inventory item with id 10
        for item in inventory_list:
            if item['id'] == 10:
                dark_blue = item
                break

        if dark_blue:
            current_time = connection.execute(sqlalchemy.text("""
                                SELECT day, hour FROM time_table ORDER BY created_at DESC LIMIT 1;
                            """)).first()  # Use first() to fetch the first result directly
            
            print(f"\nThe current time is {current_time.day}  {current_time.hour}")
            
            sku = dark_blue['sku']
            potion_type = [dark_blue['red_ml'], dark_blue['green_ml'], dark_blue['blue_ml'], dark_blue['dark_ml']]
            quantity = dark_blue['total_quantity']
            name = dark_blue['name']
            price = dark_blue['price']
            catalog.append({
                    "sku": sku,
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "potion_type": potion_type,
                })

        for row in inventory_list:
            # print("Adding to catalog: " + str(row))
            sku = row.sku
            potion_type = [row.red_ml, row.green_ml, row.blue_ml, row.dark_ml]
            quantity = row.total_quantity
            name = row.name
            price = row.price
            print("Number of " + str(potion_type) + " potions offered: " + str(quantity))

            if any([(current_time.day == "Edgeday" and current_time.hour <= 22) and potion_type[0] == 100, #RED
                    (current_time.day == "Bloomday" and current_time.hour <= 22) and potion_type[1] == 100, #GREEN
                    (current_time.day == "Arcanaday" and current_time.hour <= 22) and potion_type[2] == 100, #BLUE
                    (current_time.day == "Edgeday" and current_time.hour <= 22) and potion_type[3] == 100, #BLACK 
                    (current_time.day == "Edgeday" and current_time.hour <= 22) and (potion_type[0] == 50 and potion_type[1] == 50), #YELLOW
                    (current_time.day == "Soulday" and current_time.hour <= 22) and (potion_type[0] == 50 and potion_type[2] == 50), #PURPLE POTIONS
                    (potion_type[0] == 50 and potion_type[3] == 50)]): #DARK RED
                print(f"Not adding {name} to catalog because it's {current_time.day} {current_time.hour}")
                continue

            catalog.append({
                "sku": sku,
                "name": name,
                "quantity": quantity,
                "price": price,
                "potion_type": potion_type,
            })
        print("\n")

    catalog = catalog[:6]
    print("Final Catalog:")
    for item in catalog:
        print(f"SKU: {item['sku']}, Name: {item['name']}, Quantity: {item['quantity']}, Price: {item['price']}, Potion Types: {item['potion_type']}")
        
    return catalog
