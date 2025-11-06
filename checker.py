import os, base64, json, re, requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# === CONFIGURACIÓN DE TOKENS Y VARIABLES ===
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["REPO"]
DATA_PATH = os.environ.get("DATA_PATH", "data.json")
GITHUB_API = "https://api.github.com"

# === FUNCIONES AUXILIARES ===

def github_get_file(path):
    """Descarga el archivo data.json desde GitHub"""
    url = f"{GITHUB_API}/repos/{REPO}/contents/{path}"
    r = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    data = r.json()
    content = base64.b64decode(data["content"]).decode()
    return json.loads(content)

def github_update_file(path, content, message="update data"):
    """Sube la nueva versión de data.json al repositorio"""
    url = f"{GITHUB_API}/repos/{REPO}/contents/{path}"
    get_r = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    sha = get_r.json().get("sha")

    encoded = base64.b64encode(json.dumps(content, indent=2).encode()).decode()

    payload = {
        "message": message,
        "content": encoded,
        "sha": sha
    }

    requests.put(url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, json=payload)

def send_telegram(chat_id, msg):
    """Envía mensaje a Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

def get_price(url):
    """Obtiene el precio de un enlace (Amazon o Mercado Libre)"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        # Buscar precio en texto general
        text = soup.get_text(" ", strip=True)
        m = re.search(r"\$[\s]*([0-9.,]+)", text)
        if m:
            price = m.group(1).replace(",", "").replace(".", "", m.group(1).count(".") - 1)
            return float(price)
    except Exception as e:
        print(f"Error obteniendo precio de {url}: {e}")
    return None

# === FUNCIÓN PRINCIPAL ===

def main():
    data = github_get_file(DATA_PATH)
    if "last_prices" not in data:
        data["last_prices"] = {}

    first_run = not bool(data["last_prices"])

    def check(a):
        found = []
        for link in a["links"]:
            p = get_price(link)
            if not p:
                continue

            # Comparar con precio anterior (si existe)
            last_p = data["last_prices"].get(link)
            if first_run or (last_p and p < last_p) or p <= a["target_price"]:
                found.append((link, p))

            # Actualizar registro de precio
            data["last_prices"][link] = p

        return a["chat_id"], a["title"], found

    # Ejecutar en paralelo
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = ex.map(check, data["articles"].values())

    # Enviar mensajes si corresponde
    for chat_id, title, found in results:
        for link, price in found:
            msg = f"✅ {title} alcanzó ${price}\n{link}"
            send_telegram(chat_id, msg)

    # Actualizar archivo en GitHub
    github_update_file(DATA_PATH, data, message="Actualización automática de precios")

if __name__ == "__main__":
    main()
