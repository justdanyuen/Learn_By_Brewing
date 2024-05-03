from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db


router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)

class Timestamp(BaseModel):
    day: str
    hour: int

@router.post("/current_time")
def post_time(timestamp: Timestamp):
    """
    Share current time, and store it in our time_table
    """

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("""
                INSERT INTO time_table (day, hour)
                VALUES (:day, :hour);
                """), {'day': timestamp.day, 'hour': timestamp.hour})

    print("Day: ", timestamp.day, "\nHour: ", str(timestamp.hour), "\n")

    return "OK"

