import os
import dotenv
from sqlalchemy import create_engine, MetaData

def database_connection_url():
    dotenv.load_dotenv()

    return os.environ.get("POSTGRES_URI")

engine = create_engine(database_connection_url(), pool_pre_ping=True)
metadata = MetaData()
metadata.reflect(bind=engine)
carts = metadata.tables['carts']
cart_items = metadata.tables['cart_items']
potion_inventory = metadata.tables['potion_inventory']