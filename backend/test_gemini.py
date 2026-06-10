from google import genai

client = genai.Client(api_key="AIzaSyDCZkkX-ZLDu1WmDhDAOX15aWgNzsRTido")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello, test working"
)

print(response.text)