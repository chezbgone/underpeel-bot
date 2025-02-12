import logging
from math import ceil
from typing import Literal

from pydantic import BaseModel

from database import GetItemResponse, QueryResponse, UpdateItemResponse, the_table
from database.currency import get_user_points, add_to_user

LOG = logging.getLogger(__name__)

#####  SCHEMA  #####


# prediction#{prediction_id}, meta
class PredictionInfo(BaseModel):
    prediction_id: str
    message_id: int
    title: str
    status: Literal["open", "closed", "paid"]
    choice_a: str
    choice_b: str
    votes_a: int
    votes_b: int


# prediction#{prediction_id}, vote#{user_id}
class PredictionVote(BaseModel):
    prediction_id: str
    user_id: int
    amount: int
    choice: Literal["a", "b"]


# prediction_message_status_index
class PredictionMessageStatus(BaseModel):
    message_id: int
    prediction_id: str
    status: Literal["open", "closed", "paid"]


#####  UTILS  #####


def _make_id(prediction_id: str) -> str:
    return f"prediction#{prediction_id}"


def _make_key(prediction_id: str, *layers: str):
    return {"id": _make_id(prediction_id), "sk": "#".join(layers)}


#####  INTERACTIONS  #####


def create_prediction(
    prediction_id: str, message_id: int, title: str, choice_a: str, choice_b: str
):
    item = {
        **_make_key(prediction_id, "meta"),
        "prediction_id": prediction_id,
        "message_id": message_id,
        "title": title,
        "status": "open",
        "choice_a": choice_a,
        "choice_b": choice_b,
        "votes_a": 0,
        "votes_b": 0,
    }
    the_table().put_item(Item=item)
    return PredictionInfo.model_validate(item)


def get_prediction(prediction_id: str):
    raw_response = the_table().get_item(Key=_make_key(prediction_id, "meta"))
    response = GetItemResponse[PredictionInfo].model_validate(raw_response)
    return response.item


def get_prediction_id_from_message_id(message_id: int):
    raw_response = the_table().query(
        IndexName="prediction_message_status_index",
        KeyConditionExpression="message_id = :message_id AND begins_with(#id, :prefix)",
        ExpressionAttributeNames={
            "#id": "id",
        },
        ExpressionAttributeValues={
            ":prefix": "prediction#",
            ":message_id": message_id,
        },
    )
    response = QueryResponse[PredictionMessageStatus].model_validate(raw_response)
    assert response.count == 1
    return response.items[0].prediction_id


def add_prediction_vote(
    prediction_id: str, user_id: int, choice: Literal["a", "b"], amount: int
):
    # ensure prediction exists
    raw_response = the_table().get_item(Key=_make_key(prediction_id, "meta"))
    response = GetItemResponse[PredictionInfo].model_validate(raw_response)
    if response.item is None:
        LOG.error(f"{user_id=} voted for nonexistent {prediction_id=}")
        return "nonexistent prediction"

    if response.item.status != "open":
        return "prediction is not open"

    # take funds from user
    if get_user_points(user_id) < amount:
        return "not enough points"
    add_to_user(user_id, -amount)

    the_table().put_item(
        Item={
            **_make_key(prediction_id, "vote", str(user_id)),
            "prediction_id": prediction_id,
            "user_id": user_id,
            "amount": amount,
            "choice": choice,
        }
    )
    raw_response = the_table().update_item(
        Key=_make_key(prediction_id, "meta"),
        UpdateExpression=f"ADD votes_{choice} :amount",
        ExpressionAttributeValues={":amount": amount},
        ReturnValues="ALL_NEW",
    )
    response = UpdateItemResponse.model_validate(raw_response)
    if response.attributes is None:
        LOG.error(f"could not add vote to {prediction_id=}")
        return "unknown error"

    return PredictionInfo.model_validate(response.attributes)


def close_prediction(prediction_id: str):
    prediction = get_prediction(prediction_id)
    if prediction is None:
        raise ValueError(f"could not find {prediction_id=}")
    if prediction.status == "closed":
        return "prediction has already been closed"
    if prediction.status == "paid":
        return "prediction has already been paid"
    raw_response = the_table().update_item(
        Key=_make_key(prediction_id, "meta"),
        ConditionExpression="#status = :open",
        UpdateExpression="SET #status = :closed",
        ExpressionAttributeNames={
            "#status": "status",
        },
        ExpressionAttributeValues={
            ":open": "open",
            ":closed": "closed",
        },
        ReturnValues="UPDATED_NEW",
    )
    response = UpdateItemResponse.model_validate(raw_response)
    if response.attributes is None:
        return "could not close prediction"


def pay_out_prediction(prediction_id: str, choice: Literal["a", "b"]):
    prediction = get_prediction(prediction_id)
    if prediction is None:
        raise ValueError(f"could not find {prediction_id=}")
    if prediction.status == "paid":
        return "prediction has already been paid out"
    if prediction.status != "closed":
        raise ValueError(f"{prediction_id=} is not closed")
    total_votes = prediction.votes_a + prediction.votes_b

    raw_response = the_table().query(
        KeyConditionExpression="id = :id AND begins_with(sk, :vote_prefix)",
        ExpressionAttributeValues={
            ":id": _make_id(prediction_id),
            ":vote_prefix": "vote#",
        },
    )
    response = QueryResponse[PredictionVote].model_validate(raw_response)
    total_winning_votes = sum(
        vote.amount for vote in response.items if vote.choice == choice
    )
    for vote in response.items:
        if vote.choice == choice:
            reward = ceil(total_votes * vote.amount / total_winning_votes)
            add_to_user(vote.user_id, reward)

    raw_response = the_table().update_item(
        Key=_make_key(prediction_id, "meta"),
        UpdateExpression="SET #status = :paid",
        ExpressionAttributeNames={
            "#status": "status",
        },
        ExpressionAttributeValues={
            ":paid": "paid",
        },
        ReturnValues="ALL_NEW",
    )
    response = UpdateItemResponse.model_validate(raw_response)
    if response.attributes is None:
        return "could not pay out prediction"
    return PredictionInfo.model_validate(response.attributes)
