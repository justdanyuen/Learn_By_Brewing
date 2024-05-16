from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
import json
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """
    


    with db.engine.begin() as connection:

        # Decide sort column type
        if sort_col == search_sort_options.timestamp:
            sort_by = db.cart_items.c.created_at
        elif sort_col == search_sort_options.customer_name:
            sort_by = db.carts.c.name
        elif sort_col == search_sort_options.item_sku:
            sort_by = db.cart_items.c.item_sku
        elif sort_col == search_sort_options.line_item_total:
            sort_by = db.cart_items.c.quantity
        else:
            assert False

        if sort_order == search_sort_order.desc:
            order_by = sqlalchemy.desc(sort_by)
        else:
            order_by = sqlalchemy.asc(sort_by)

        filter_conditions = []
        if customer_name:
            filter_conditions.append(db.carts.c.name.ilike(f"%{customer_name}%"))
        if potion_sku:
            filter_conditions.append(db.cart_items.c.item_sku.ilike(f"%{potion_sku}%"))

        total_carts = connection.execute(sqlalchemy.text("SELECT COUNT(*) FROM cart_items")).scalar_one()

        current_page = int(search_page) if search_page else 0

        # Calculate the offset based on the current page
        offset = current_page * 5

        # Determine the tokens for previous and next pages
        prev_token = str(current_page - 1) if current_page > 0 else ""
        next_token = str(current_page + 1) if (current_page + 1) * 5 < total_carts else ""

        stmt = (
            sqlalchemy.select(
                db.cart_items.c.cart_id,
                db.cart_items.c.potion_id,
                db.cart_items.c.quantity,
                db.cart_items.c.item_sku,
                db.cart_items.c.price,
                (db.cart_items.c.quantity * db.potion_inventory.c.price).label("line_item_total"),
                db.carts.c.id,
                db.carts.c.name,
                db.potion_inventory.c.name,
                db.carts.c.created_at.label("timestamp"),
                db.potion_inventory.c.sku,
            )
            .order_by(order_by)
            .limit(5)
            .offset(offset)
            .select_from(
                db.cart_items
                .join(db.carts, db.cart_items.c.cart_id == db.carts.c.id)
                .join(db.potion_inventory, db.cart_items.c.potion_id == db.potion_inventory.c.id)
            )
        )

        if customer_name != "":
        # filter for similar names
            stmt = stmt.where(db.carts.c.name.ilike(f"%{customer_name}%"))

        if potion_sku != "":
            # filter for sku
            stmt = stmt.where(db.potion_inventory.c.sku.ilike(f"%{potion_sku}%"))


        result = connection.execute(stmt)

        json_result = []
        for row in result:
            json_result.append({
                "line_item_id": row.cart_id,
                "item_sku": row.item_sku,
                "customer_name": row.name,
                "line_item_total": row.line_item_total,
                "timestamp": row.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")  # ISO 8601
            })

        print(json_result)

    
    return {
        "previous": prev_token,
        "next": next_token,
        "results": json_result
    }

class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int

@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """
    print(customers)

    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ """

    with db.engine.begin() as connection:
        
        id = connection.execute(sqlalchemy.text("INSERT INTO carts (name, class, level) VALUES (:name, :class, :level) returning id;"),
                                    {
                                        'name': new_cart.customer_name,
                                        'class': new_cart.character_class,
                                        'level': new_cart.level
                                    }).fetchone()[0]

        print("Cart: " + str(id) + " " + new_cart.customer_name + " " + new_cart.character_class + " " + str(new_cart.level))

    return {"cart_id": id} # trying to return cart_id as an int instead to hopefully resolve an error?


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    with db.engine.begin() as connection:
        potion_info = connection.execute(sqlalchemy.text("SELECT id, price FROM potion_inventory WHERE sku = :sku"), {"sku": item_sku}).first()
        potion_id = potion_info.id
        item_price = potion_info.price        

        current_time = connection.execute(sqlalchemy.text("""
                SELECT day, hour FROM time_table ORDER BY created_at DESC LIMIT 1;
            """)).first()  # Use first() to fetch the first result directly

        if current_time:  # Check if a result was returned
            day = current_time.day  # Access columns directly via the result
            hour = current_time.hour
            connection.execute(sqlalchemy.text("INSERT INTO cart_items (item_sku, quantity, cart_id, potion_id, day, hour, price) VALUES (:sku , :quantity, :cart_id, :potion_id, :day, :hour, :price)"), {"sku": item_sku, "quantity": cart_item.quantity, "cart_id": cart_id, "potion_id": potion_id, "day": day, "hour": hour, "price": item_price})
        else:
            print("error retrieving the time...\n")
            connection.execute(sqlalchemy.text("INSERT INTO cart_items (item_sku, quantity, cart_id, potion_id, price) VALUES (:sku , :quantity, :cart_id, :potion_id, :price)"), {"sku": item_sku, "quantity": cart_item.quantity, "cart_id": cart_id, "potion_id": potion_id, "price": item_price})


    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ Process checkout, updating financial and inventory records using ledgers """
    gold_spent = 0
    potions_bought = 0
    with db.engine.begin() as connection:
        # Fetch all items in the cart
        cart_contents = connection.execute(sqlalchemy.text(
            "SELECT quantity, item_sku FROM cart_items WHERE cart_id = :cart_id"), 
            {"cart_id": cart_id}).fetchall()

        for item in cart_contents:
            quantity, item_sku = item
            # Retrieve price from the potion inventory
            potion_data = connection.execute(sqlalchemy.text(
                "SELECT id, price FROM potion_inventory WHERE sku = :item_sku"), 
                {"item_sku": item_sku}).first()

            # Calculate the current inventory of this potion from the ledger
            current_quantity = connection.execute(sqlalchemy.text(
                """
                SELECT SUM(quantity) as total_quantity 
                FROM potion_ledger 
                WHERE potion_id = :potion_id
                """), 
                {"potion_id": potion_data.id}).scalar() or 0

            if potion_data and quantity <= current_quantity:
                potion_id, price = potion_data
                total_cost = quantity * price
                potions_bought += quantity
                gold_spent += total_cost

                current_time = connection.execute(sqlalchemy.text("""
                SELECT hour FROM time_table ORDER BY created_at DESC LIMIT 1;
                """)).first()  # Use first() to fetch the first result directly

                if current_time:

                    # Record potion transaction in potion_ledger
                    connection.execute(sqlalchemy.text(
                        """
                        INSERT INTO potion_ledger (potion_id, quantity, function, transaction, cost, day, hour)
                        VALUES (:potion_id, - :quantity, 'sale', :transaction, :cost, :day, :hour);
                        """),
                        {
                            "potion_id": potion_id,
                            "quantity": quantity,  # Negative because it's a sale
                            "function": "checkout",
                            "transaction": json.dumps({"cart_id": cart_id, "item_sku": item_sku}),
                            "cost": total_cost, 
                            "day": current_time.day,
                            "hour": current_time.hour
                        }
                    )
                else:
                    # Record potion transaction in potion_ledger
                    connection.execute(sqlalchemy.text(
                        """
                        INSERT INTO potion_ledger (potion_id, quantity, function, transaction, cost)
                        VALUES (:potion_id, - :quantity, 'sale', :transaction, :cost);
                        """),
                        {
                            "potion_id": potion_id,
                            "quantity": quantity,  # Negative because it's a sale
                            "function": "checkout",
                            "transaction": json.dumps({"cart_id": cart_id, "item_sku": item_sku}),
                            "cost": total_cost
                        }
                    )
            
                if current_time:
                    connection.execute(sqlalchemy.text(
                                            """
                                            INSERT INTO gold_ledger (net_change, function, transaction, day, hour)
                                            VALUES (:net_change, 'checkout', :transaction, :day, :hour);
                                            """),   {'net_change': total_cost,  # Negative because it is an expenditure
                                                    'transaction': json.dumps({"cart_id": cart_id, "item_sku": item_sku, "quantity": quantity}),
                                                    'day': current_time.day,
                                                    'hour': current_time.hour
                                            })
                else:
                    # Update the gold ledger for tracking money spent
                    connection.execute(sqlalchemy.text(
                        """
                        INSERT INTO gold_ledger (net_change, function, transaction)
                        VALUES (:net_change, 'checkout', :transaction);
                        """),
                        {
                            'net_change': total_cost,  # Negative because it is an expenditure
                            'transaction': json.dumps({"cart_id": cart_id, "item_sku": item_sku, "quantity": quantity})
                        }
                    )
            else:
                quantity = 0  # Reset quantity if not enough stock

    return {"total_potions_bought": potions_bought, "total_gold_paid": gold_spent}
