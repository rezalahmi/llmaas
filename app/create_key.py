import redis
import secrets
import json

r = redis.Redis()

key = secrets.token_urlsafe(32)

data = {
    "user_id":1,
    "user":"test",
    "quota":1000000
}

r.set(f"api_key:{key}", json.dumps(data))

print("API KEY:", key)
