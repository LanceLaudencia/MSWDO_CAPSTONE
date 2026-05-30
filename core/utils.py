import requests
from django.conf import settings


def send_sms(phone, message):
    # format number
    if phone.startswith("09"):
        phone = "63" + phone[1:]

    url = "https://dashboard.philsms.com/api/v3/sms/send"  # ✅ NEW URL

    payload = {
        "recipient": phone,
        "sender_id": getattr(settings, "PHILSMS_SENDER_ID", ""),
        "type": "plain",
        "message": message,
    }

    headers = {
        "Authorization": f"Bearer {settings.PHILSMS_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",  # ✅ IMPORTANT (from docs)
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        print("===== SMS DEBUG (PhilSMS NEW API) =====")
        print("URL:", url)
        print("Number:", phone)
        print("Status:", response.status_code)
        print("Response:", response.text)
        print("=======================================")

        response.raise_for_status()

        return {
            "success": True,
            "data": response.json()
        }

    except requests.exceptions.RequestException as e:
        print("SMS ERROR:", str(e))
        return {
            "success": False,
            "error": str(e)
        }