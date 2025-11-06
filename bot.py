import os
import json
import base64
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# --- CONFIGURACIÓN ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPO")
DATA_PATH = os.environ.get("DATA_PATH", "data.json")
GITHUB_API = "https://api.github.com"

# --- FUNCIONES AUXILIARES ---

def github_get_file(path):
    url = f"{GITHUB_API}/repos/{REPO}/contents/{path}"
    r = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    data = r.json()
    content = base64.b64decode(data['content']).decode()
    return json.loads(content), data['sha']

def github_put_file(path, content_dict, sha=None, message="update data.json"):
    url = f"{GITHUB_API}/repos/{REPO}/contents/{path}"
    content = json.dumps(content_dict, indent=2, ensure_ascii=False)
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode()
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, json=payload)
    r.raise_for_status()

def load_data():
    try:
        data, sha = github_get_file(DATA_PATH)
        return data, sha
    except:
        return {"articles": {}, "next_id": 1}, None

# --- COMANDOS TELEGRAM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenido. Envíame un link y luego te pediré el precio mínimo que deseas.\n"
        "Comandos:\n"
        "/list - Ver tus artículos\n"
        "/clear - Borrar todo"
    )

# --- Mensaje de texto recibido (link) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("http"):
        context.user_data["link"] = text
        await update.message.reply_text("🔢 Ingresa el precio mínimo deseado (solo número):")
        return

    # Si el usuario envía el precio
    if text.replace(".", "", 1).isdigit():
        price = float(text)
        link = context.user_data.get("link")
        if not link:
            await update.message.reply_text("❌ Primero envíame un link.")
            return

        data, sha = load_data()
        nid = data["next_id"]
        data["articles"][str(nid)] = {
            "title": f"Artículo {nid}",
            "target_price": price,
            "links": [link],
            "chat_id": update.effective_chat.id,
            "active": True
        }
        data["next_id"] = nid + 1
        github_put_file(DATA_PATH, data, sha, message=f"add item {nid}")
        await update.message.reply_text(f"✅ Guardado: {link}\nPrecio objetivo: {price}")
        context.user_data.clear()
        return

    await update.message.reply_text("❌ Envíame un link o un número de precio.")

async def list_articles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data, _ = load_data()
    if not data["articles"]:
        await update.message.reply_text("No tienes artículos guardados.")
        return
    msg = "📦 Artículos guardados:\n"
    for aid, a in data["articles"].items():
        msg += f"\nID {aid}: {a['title']} (${a['target_price']})\nLinks: {len(a['links'])}"
    await update.message.reply_text(msg)

async def clear_articles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data, sha = load_data()
    data["articles"] = {}
    data["next_id"] = 1
    github_put_file(DATA_PATH, data, sha, message="clear all")
    await update.message.reply_text("🧹 Todos los artículos fueron eliminados.")

# --- MAIN ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_articles))
    app.add_handler(CommandHandler("clear", clear_articles))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
