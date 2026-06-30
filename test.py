from ollama import chat

try:
    response = chat(
        model="nemotron-3-super:cloud",
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: Connection Successful"
            }
        ]
    )

    print(response.message.content)

except Exception as e:
    print(f"Error: {e}")