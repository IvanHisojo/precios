import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = "8567347766:AAESVdFSOxJ6bKREMuu47pJCAUg8NiIxn-Q"

# Datos por usuario: {user_id: {"links": [listado de URLs], "min_price": float, "monitoring": bool, "first_run": bool, "last_prices": {}}}
user_data = {}

# === COMANDOS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data[user_id] = {
        "links": [],
        "min_price": None,
        "monitoring": False,
        "first_run": True,
        "last_prices": {}
    }
    await update.message.reply_text(
        "👋 ¡Hola! Envíame los links de los productos que quieras monitorear (Amazon o Mercado Libre).\n"
        "Cuando termines, envía el precio mínimo con el comando:\n"
        "`/precio 1200`\n"
        "Y para iniciar el monitoreo usa:\n"
        "`/iniciar`\n\n"
        "Puedes detenerlo con `/detener`",
        parse_mode="Markdown"
    )

async def agregar_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if not text.startswith("http"):
        return await update.message.reply_text("❌ Envíame un link válido que empiece con http o https.")

    user_data.setdefault(user_id, {
        "links": [],
        "min_price": None,
        "monitoring": False,
        "first_run": True,
        "last_prices": {}
    })

    user_data[user_id]["links"].append(text)
    await update.message.reply_text(f"✅ Link agregado ({len(user_data[user_id]['links'])} total).")

async def set_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if len(context.args) == 0:
        return await update.message.reply_text("Debes indicar el precio mínimo, por ejemplo: `/precio 1200`", parse_mode="Markdown")

    try:
        precio = float(context.args[0])
    except ValueError:
        return await update.message.reply_text("❌ Precio inválido. Usa solo números.")

    user_data.setdefault(user_id, {
        "links": [],
        "min_price": None,
        "monitoring": False,
        "first_run": True,
        "last_prices": {}
    })
    user_data[user_id]["min_price"] = precio
    await update.message.reply_text(f"💰 Precio mínimo establecido en ${precio:.2f}")

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    data = user_data.get(user_id)

    if not data or not data["links"]:
        return await update.message.reply_text("❌ No has agregado ningún link.")
    if data["min_price"] is None:
        return await update.message.reply_text("❌ No has establecido un precio mínimo con `/precio`.")

    if data["monitoring"]:
        return await update.message.reply_text("⏳ Ya estoy monitoreando tus productos.")

    data["monitoring"] = True
    await update.message.reply_text("✅ Monitoreo iniciado. Revisaré los precios cada 10 minutos 🔄")
    asyncio.create_task(monitor_precios(update, context, user_id))

async def detener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in user_data:
        user_data[user_id]["monitoring"] = False
        await update.message.reply_text("🛑 Monitoreo detenido.")
    else:
        await update.message.reply_text("No hay monitoreo activo.")

# === FUNCIONES DE MONITOREO ===

async def monitor_precios(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Revisa los precios cada 10 minutos mientras monitoring=True"""
    while user_data.get(user_id, {}).get("monitoring", False):
        await revisar_precios(update, context, user_id)
        await asyncio.sleep(600)  # 10 minutos

async def revisar_precios(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = user_data.get(user_id)
    links = data["links"]
    min_price = data["min_price"]
    first_run = data.get("first_run", True)
    last_prices = data.setdefault("last_prices", {})

    if first_run:
        await update.message.reply_text("🔍 Revisando precios por primera vez...")
    else:
        print(f"Revisando precios en segundo plano para {user_id}")

    for link in links:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(link, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")

            current_price = None

            if "amazon" in link:
                price_tag = soup.find("span", class_="a-price-whole")
                if price_tag:
                    current_price = float(price_tag.text.replace(",", "").replace("$", "").strip())
            elif "mercadolibre" in link:
                price_tag = soup.find("span", class_="andes-money-amount__fraction")
                if price_tag:
                    current_price = float(price_tag.text.replace(",", "").replace("$", "").strip())

            if current_price is None:
                await update.message.reply_text(f"⚠️ No pude obtener el precio de:\n{link}")
                continue

            last_price = last_prices.get(link)
            last_prices[link] = current_price

            # Lógica de notificación
            if first_run:
                await update.message.reply_text(f"💰 Precio actual de:\n{link}\n➡️ ${current_price}")
            elif last_price and current_price < last_price:
                await update.message.reply_text(
                    f"🎉 ¡El precio bajó!\nAntes: ${last_price}\nAhora: ${current_price}\n🔗 {link}"
                )
            elif current_price <= min_price:
                await update.message.reply_text(
                    f"✅ ¡Precio por debajo del mínimo!\nActual: ${current_price}\n🔗 {link}"
                )
            # No se envía nada si no cumple las condiciones

        except Exception as e:
            await update.message.reply_text(f"⚠️ Error al revisar {link}: {e}")

    data["first_run"] = False  # Después de la primera revisión

# === INICIO DEL BOT ===

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("precio", set_precio))
    app.add_handler(CommandHandler("iniciar", iniciar))
    app.add_handler(CommandHandler("detener", detener))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, agregar_link))

    print("🤖 Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
