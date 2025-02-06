from pydantic import BaseModel

from database import GetItemResponse, UpdateItemResponse, the_table

#####  SCHEMA  #####


# user#{userid}, currency
class CurrencyInfo(BaseModel):
    amount: int


#####  UTILS  #####


def _make_key(user_id: int):
    return {"id": f"user#{user_id}", "sk": "currency"}


#####  INTERACTIONS  #####


def get_user_points(id: int) -> int:
    """
    Returns the amount of currency in chatter `id`'s wallet.
    """
    raw_response = the_table().get_item(
        Key=_make_key(id),
        ProjectionExpression="amount",
    )
    response = GetItemResponse[CurrencyInfo].model_validate(raw_response)
    if response.item is None:
        return 0
    return response.item.amount


def add_to_user(id: int, amount: int) -> int:
    """
    Add `amount` currency to chatter `id`'s wallet.
    Returns the new amount the user has.
    """
    raw_response = the_table().update_item(
        Key=_make_key(id),
        UpdateExpression="ADD amount :amount",
        ExpressionAttributeValues={":amount": amount},
        ReturnValues="UPDATED_NEW",
    )
    response = UpdateItemResponse.model_validate(raw_response)
    if response.attributes is None:
        raise Exception(f"could not add currency to {id} {raw_response}")
    return response.attributes["amount"]
