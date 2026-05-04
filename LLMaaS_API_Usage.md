## LLMaaS API Usage Guide (`/v1/responses`)

---

### 1. General Info

- **Base URL Example:**  
  `http://185.155.9.107:8000`
- **Main Endpoint:**  
  `POST /v1/responses`
- **Authentication:**  
  Include the header:
  ```http
  Authorization: Bearer <API_KEY>
  ```
  For testing, simply use `Bearer test-key`.
- **Content-Type:**  
  Always set:
  ```http
  Content-Type: application/json
  ```

---

### 2. Request Data Model

The request body should follow the `ResponseRequest` schema.

#### Example Request Body

```json
{
  "model": "gemma4:e4b",
  "input": "Hello, introduce yourself.",
  "stream": false,
  "temperature": 0.7,
  "top_p": 1.0,
  "max_output_tokens": 512,
  "tools": [],
  "tool_choice": "auto",
  "instructions": "..."
}
```

#### Field descriptions

| Field              | Type                    | Required | Default  | Description                       |
|--------------------|------------------------|----------|----------|-----------------------------------|
| `model`            | `string`               | Yes      | —        | Model name/identifier             |
| `input`            | `string` or `array`    | Yes      | —        | The prompt, or a message list     |
| `stream`           | `boolean`              | No       | `false`  | Enable server-sent events (SSE)   |
| `temperature`      | `float`                | No       | `0.7`    | Sampling creativity               |
| `top_p`            | `float`                | No       | `1.0`    | Nucleus sampling cutoff           |
| `max_output_tokens`| `integer`              | No       | `512`    | Maximum output tokens             |
| `tools`            | `array<object>`        | No       | `null`   | Reserved for future, not required |
| `tool_choice`      | `string` or `object`   | No       | `"auto"` | Reserved for future, not required |
| `instructions`     | `string`               | No       | `null`   | Optional system-level instructions|

---

#### Input Formats

##### A) Simple text prompt
```json
{
  "model": "gemma4:e4b",
  "input": "Tell me a story about robots.",
  "stream": false
}
```

##### B) Message (role/content) structure

```json
{
  "model": "gemma4:e4b",
  "input": [
    {
      "role": "user",
      "content": [
        { "type": "input_text", "text": "Hello" },
        { "type": "input_text", "text": "Give me a poem" }
      ]
    }
  ],
  "stream": false
}
```

---

### 3. Response Structure

#### Non-streaming (`stream=false`)

```json
{
  "id": "resp_<uuid>",
  "object": "response",
  "created": 1710000000,
  "model": "gemma4:e4b",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 42,
    "total_tokens": 52
  },
  "output": [
    {
      "id": "msg_<uuid>",
      "type": "message",
      "role": "assistant",
      "content": [
        { "type": "output_text", "text": "..." }
      ]
    }
  ]
}
```

- The generated text is at:  
  `output[0].content[0].text`

---

#### Streaming (`stream=true`, SSE)

- Response headers:
  ```http
  Content-Type: text/event-stream
  Cache-Control: no-cache
  Connection: keep-alive
  ```
- Each event is sent line by line and ends with **two newlines (`\n\n`)**.
- The stream ends with:

  ```
  data: [DONE]

  ```

- You may receive specific events such as `event: response.usage` (the shape is determined by your backend publisher).
- Your client should read the stream line by line, and stop on `data: [DONE]`.

---

### 4. Practical Examples

#### 4.1) Non-streaming with `curl`:
```bash
curl -X POST "http://185.155.9.107:8000/v1/responses" \
  -H "Authorization: Bearer test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:e4b",
    "input": "Summarize this text.",
    "stream": false,
    "temperature": 0.7,
    "top_p": 1,
    "max_output_tokens": 150
  }'
```

#### 4.2) Streaming with `curl` (SSE):

```bash
curl -N -X POST "http://185.155.9.107:8000/v1/responses" \
  -H "Authorization: Bearer test-key" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "model": "gemma4:e4b",
    "input": "Stream this answer please.",
    "stream": true,
    "max_output_tokens": 150
  }'
```
- Use `-N` in curl to disable buffering and see output as it's received.

---

### 5. Python Example (No SDK)

#### Non-streamed:

```python
import httpx

url = "http://185.155.9.107:8000/v1/responses"
headers = {
    "Authorization": "Bearer test-key",
    "Content-Type": "application/json"
}
payload = {
    "model": "gemma4:e4b",
    "input": "Hello! Write me a joke.",
    "stream": False
}
resp = httpx.post(url, headers=headers, json=payload, timeout=60)
data = resp.json()
print(data["output"][0]["content"][0]["text"])
```

#### Streaming:

```python
import httpx

url = "http://185.155.9.107:8000/v1/responses"
headers = {
    "Authorization": "Bearer test-key",
    "Content-Type": "application/json",
    "Accept": "text/event-stream"
}
payload = {
    "model": "gemma4:e4b",
    "input": "Stream a creative paragraph.",
    "stream": True,
    "max_output_tokens": 150
}
with httpx.stream("POST", url, headers=headers, json=payload, timeout=60) as r:
    for line in r.iter_lines():
        if not line:
            continue
        print(line)
        if line.strip() == "data: [DONE]":
            break
```

---

### 6. Common Errors

#### Pydantic/Validation: “Input should be a valid dictionary/string”
- Reason: Usually `Content-Type` header is missing, so the body arrives as a raw string.
- Solution:  
  Always provide  
  `Content-Type: application/json`  
  and send **strict, valid JSON** as body.

#### Stream output not showing / stuck
- Use `-N` with curl and make sure your client (or reverse proxy) doesn’t buffer the stream.
- Your backend must emit proper SSE (with `\n\n` after each event).

---

### 7. Quick Checklist

- [ ] `Authorization: Bearer ...` header set
- [ ] `Content-Type: application/json` header set
- [ ] Required fields: `model` and `input`
- [ ] For streaming: `stream=true` and `Accept: text/event-stream`
- [ ] End stream check: `data: [DONE]`

---
