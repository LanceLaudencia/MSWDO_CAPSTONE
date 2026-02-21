import requests
from django.conf import settings

def send_sms(phone_number, message):
    # Convert PH number 09XXXXXXXXX → 639XXXXXXXXX
    if phone_number.startswith("09"):
        phone_number = "63" + phone_number[1:]

    payload = {
        "api_token": settings.IPROG_API_KEY,
        "phone_number": phone_number,
        "message": message,
    }

    print("===== SMS DEBUG =====")
    print("Sending SMS to:", phone_number)
    print("Message:", message)
    print("Payload:", payload)
    print("=====================")

    try:
        response = requests.post(settings.IPROG_URL, data=payload, timeout=10)
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)

        try:
            return response.json()
        except ValueError:
            return {"error": "Non-JSON response", "content": response.text}

    except Exception as e:
        print("SMS ERROR:", e)
        return {"error": str(e)}
