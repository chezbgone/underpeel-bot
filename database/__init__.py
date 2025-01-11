import logging

import boto3

from config import CONFIG

_boto_config = {}
_boto_config['region_name'] = 'us-east-1'

if not CONFIG['production_mode']:
    _boto_config['aws_access_key_id'] = 'anything'
    _boto_config['aws_secret_access_key'] = 'anything'
    _boto_config['endpoint_url'] = 'http://db:8000'

_table_confirmed_exists = False
LOG = logging.getLogger(__name__)

def _table_exists() -> bool:
    global _table_confirmed_exists
    if _table_confirmed_exists:
        return True
    client = boto3.client('dynamodb', **_boto_config)
    try:
        client.describe_table(TableName=CONFIG['dynamodb_table'])
        _table_confirmed_exists = True
        return True
    except client.exceptions.ResourceNotFoundException:
        return False

def _ensure_table_exists() -> bool:
    if _table_exists():
        return True
    ddb = boto3.resource('dynamodb', **_boto_config)
    try:
        ddb.create_table(
            TableName=CONFIG['dynamodb_table'],
            AttributeDefinitions=[
                {
                    'AttributeName': 'id',
                    'AttributeType': 'S',
                },
                {
                    'AttributeName': 'sk',
                    'AttributeType': 'S',
                },
            ],
            KeySchema=[
                {
                    'AttributeName': 'id',
                    'KeyType': 'HASH',
                },
                {
                    'AttributeName': 'sk',
                    'KeyType': 'RANGE',
                },
            ],
            BillingMode='PAY_PER_REQUEST',
            DeletionProtectionEnabled=True,
        )
        LOG.info(f'created table {CONFIG['dynamodb_table']}')
        global _table_confirmed_exists
        _table_confirmed_exists = True
        return True
    except ddb.meta.client.exceptions.ResourceInUseException:
        LOG.warning(f'could not create table {CONFIG['dynamodb_table']}')
        return False

def the_table():
    ddb = boto3.resource('dynamodb', **_boto_config)
    assert(_ensure_table_exists())
    return ddb.Table(CONFIG['dynamodb_table'])

