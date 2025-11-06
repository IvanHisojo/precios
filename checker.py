import os, base64, json, re, requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["REPO"]
DATA_PATH = os.environ.get("DATA_PATH", "data.json")
GITHUB_API = "https://api.github.com"

def github_get_file(path):
    url = f"{GITHUB_API}/repos/{REPO}/contents/{path}"
    r = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    data = r.json()
    content = base64.b64decode(data["content"]).decode()
    return json.loads(content)

def send_telegram(chat_id, msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

def get_price(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text(" ", strip=True)
        m = re.search(r"\$[\s]*([0-9.,]+)", text)
        if m:
            price = m.group(1).replace(",", "").replace(".", "", m.group(1).count(".") - 1)
            return float(price)
    except:
        pass
    return None

def main():
    data = github_get_file(DATA_PATH)
    def check(a):
        found = []
        for link in a["links"]:
            p = get_price(link)
            if p and p <= a["target_price"]:
                found.append((link, p))
        return a["chat_id"], a["title"], found

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = ex.map(check, data["articles"].values())

    for chat_id, title, found in results:
        for link, price in found:
            msg = f"✅ {title} alcanzó ${price}\n{link}"
            send_telegram(chat_id, msg)

if __name__ == "__main__":
    main()
