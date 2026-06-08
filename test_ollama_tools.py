import requests
import json

url = "http://localhost:11434/api/chat"

payload = {
    "model": "gemma4:e4b",
    "stream": False,
    "messages": [
        {
            "role": "user",
            "content": "What are the current weather conditions and temperature in New York and London?"
        }
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_temperature",
                "description": "Get the current temperature for a city",
                "parameters": {
                    "type": "object",
                    "required": ["city"],
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_conditions",
                "description": "Get the current weather conditions for a city",
                "parameters": {
                    "type": "object",
                    "required": ["city"],
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city"
                        }
                    }
                }
            }
        }
    ]
}

response = requests.post(url, json=payload)

print("Status:", response.status_code)
print("\nResponse JSON:\n")
print(json.dumps(response.json(), indent=2))
