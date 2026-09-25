import os
from pathlib import Path
import boto3

ROOT = Path(os.environ.get('STORAGE_DIR', '.data/objects')).resolve()
BUCKET = os.environ.get('S3_BUCKET')


def client():
    return boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT'],
                        aws_access_key_id=os.environ['S3_ACCESS_KEY_ID'],
                        aws_secret_access_key=os.environ['S3_SECRET_ACCESS_KEY'],
                        region_name=os.environ.get('S3_REGION', 'auto'))


def put(key, data):
    if BUCKET:
        client().put_object(Bucket=BUCKET, Key=key, Body=data)
    else:
        ROOT.mkdir(parents=True, exist_ok=True)
        (ROOT / key).write_bytes(data)


def get(key):
    if BUCKET:
        return client().get_object(Bucket=BUCKET, Key=key)['Body'].read()
    return (ROOT / key).read_bytes()


def delete(key):
    if BUCKET:
        client().delete_object(Bucket=BUCKET, Key=key)
    else:
        (ROOT / key).unlink(missing_ok=True)
