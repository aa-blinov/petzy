"""Check that a Backblaze B2 / S3 key can write to the petzy bucket.

Asks for the key interactively (nothing is echoed or saved), then writes a
small object, reads it back, fetches it through a signed URL and deletes it.

    .venv/bin/python scripts/check_storage.py

S3_KEY_ID / S3_SECRET_KEY from the environment are used when set.
"""

import os
import sys
import time
import urllib.request
import uuid
from getpass import getpass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ENDPOINT = os.getenv("S3_ENDPOINT", "https://s3.eu-central-003.backblazeb2.com")
REGION = os.getenv("S3_REGION", "eu-central-003")
BUCKET = os.getenv("S3_BUCKET", "petzy-1")


def main() -> int:
    key_id = os.getenv("S3_KEY_ID") or input("keyID: ").strip()
    secret = os.getenv("S3_SECRET_KEY") or getpass("applicationKey (hidden): ").strip()
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    key = f"healthcheck/local-{uuid.uuid4().hex}.txt"
    body = f"petzy storage check {time.time()}".encode()

    def step(name, fn):
        try:
            result = fn()
        except ClientError as e:
            err = e.response.get("Error", {})
            print(f"FAIL  {name}: {err.get('Code')} {err.get('Message')}")
            sys.exit(1)
        print(f"ok    {name}")
        return result

    print(f"bucket {BUCKET} at {ENDPOINT}")
    step("put object", lambda: s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="text/plain"))
    got = step("get object", lambda: s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    print("ok    read-back matches" if got == body else "FAIL  read-back differs")
    url = step(
        "signed download URL",
        lambda: s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=60),
    )
    with urllib.request.urlopen(url, timeout=20) as r:
        print("ok    signed URL serves the object" if r.read() == body else "FAIL  signed URL content differs")
    step("delete object", lambda: s3.delete_object(Bucket=BUCKET, Key=key))
    print("The key can write to the bucket.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
