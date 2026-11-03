
from app.services.browser_service import BrowserService

service = BrowserService()

result = service.inspect_portal()

print("\n========== BROWSER TEST ==========")

print("Success:", result["success"])
print("HTTP Status:", result["http_status"])
print("Page Title:", result["title"])
print("Page URL:", result["url"])

print("\nVisible inputs:")
for item in result["inputs"]:
    print(item)

print("\nVisible dropdowns:")
for item in result["dropdowns"]:
    print(item)

print("\nVisible buttons:")
for item in result["buttons"]:
    print(item)

print("\nScreenshot:", result["screenshot"])

print("\nBrowser test completed.")
