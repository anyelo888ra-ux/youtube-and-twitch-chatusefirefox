import os
import asyncio
import pytchat
from playwright.async_api import async_playwright

# Configuración de Canales
TWITCH_CHANNEL = "" # tu username de tu twitch
YOUTUBE_VIDEO_ID = "13nhDilPZc8"  # ID del en vivo de YouTube (si aplica)

# Rutas exactas a las extensiones
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UBLOCK_PATH = os.path.join(BASE_DIR, "extensions", "uBlock0_1.75.1b5.firefox.signed.xpi")
PLANETVPN_PATH = os.path.join(BASE_DIR, "extensions", "planetvpn.xpi")

# Variables del ratón virtual
current_mouse_x = 640
current_mouse_y = 360
page_ref = None

# Script JS para el cursor flotante
CURSOR_JS = """
(() => {
    let cursor = document.getElementById('nexus-cursor');
    if (!cursor) {
        cursor = document.createElement('div');
        cursor.id = 'nexus-cursor';
        cursor.style.position = 'fixed';
        cursor.style.width = '20px';
        cursor.style.height = '20px';
        cursor.style.borderRadius = '50%';
        cursor.style.backgroundColor = 'rgba(66, 133, 244, 0.8)';
        cursor.style.border = '2px solid #ffffff';
        cursor.style.boxShadow = '0 0 10px #4285f4, 0 0 20px #4285f4';
        cursor.style.pointerEvents = 'none';
        cursor.style.zIndex = '999999';
        cursor.style.transition = 'all 0.1s ease-out';
        cursor.style.transform = 'translate(-50%, -50%)';
        document.body.appendChild(cursor);
    }
    return cursor;
})();
"""

def update_cursor_position(x, y):
    if page_ref:
        asyncio.create_task(
            page_ref.evaluate(f"""
                const c = document.getElementById('nexus-cursor');
                if (c) {{
                    c.style.left = '{x}px';
                    c.style.top = '{y}px';
                }}
            """)
        )

async def handle_browser_command(cmd_str, author_name, platform):
    global current_mouse_x, current_mouse_y, page_ref
    
    if not page_ref:
        return

    parts = cmd_str.split(" ", 1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    print(f"[{platform}] <{author_name}>: {cmd_str}")

    try:
        if command == "!goto":
            url = args if args.startswith("http") else f"https://{args}"
            print(f"🔗 Navegando a: {url}")
            await page_ref.goto(url)
            await page_ref.evaluate(CURSOR_JS)

        elif command == "!type":
            print(f"⌨️ Escribiendo: {args}")
            await page_ref.keyboard.type(args, delay=40)

        elif command == "!send":
            print(f"📩 Enviando: {args} + Enter")
            await page_ref.keyboard.type(args, delay=40)
            await page_ref.keyboard.press("Enter")

        elif command == "!move":
            coords = args.split()
            if len(coords) == 2 and coords[0].isdigit() and coords[1].isdigit():
                current_mouse_x = int(coords[0])
                current_mouse_y = int(coords[1])
                await page_ref.mouse.move(current_mouse_x, current_mouse_y, steps=5)
                update_cursor_position(current_mouse_x, current_mouse_y)

        elif command == "!click":
            print(f"👆 Clic en ({current_mouse_x}, {current_mouse_y})")
            await page_ref.mouse.click(current_mouse_x, current_mouse_y)

        elif command == "!clickat":
            coords = args.split()
            if len(coords) == 2 and coords[0].isdigit() and coords[1].isdigit():
                current_mouse_x = int(coords[0])
                current_mouse_y = int(coords[1])
                await page_ref.mouse.click(current_mouse_x, current_mouse_y)
                update_cursor_position(current_mouse_x, current_mouse_y)

        elif command == "!press":
            print(f"🔤 Presionando tecla: {args}")
            await page_ref.keyboard.press(args)

        elif command == "!scroll":
            delta = int(args) if args.replace("-", "").isdigit() else 400
            await page_ref.mouse.wheel(0, delta)

        elif command == "!back":
            await page_ref.go_back()

        elif command == "!reload":
            await page_ref.reload()

    except Exception as e:
        print(f"⚠️ Error al ejecutar {command}: {e}")

async def twitch_listener():
    server = 'irc.chat.twitch.tv'
    port = 6667
    nickname = 'justinfan12345'

    reader, writer = await asyncio.open_connection(server, port)
    writer.write(f"NICK {nickname}\r\n".encode('utf-8'))
    writer.write(f"JOIN #{TWITCH_CHANNEL.lower()}\r\n".encode('utf-8'))
    await writer.drain()

    print(f"📡 Conectado al chat de Twitch: #{TWITCH_CHANNEL}")

    while True:
        data = await reader.read(2048)
        if not data:
            break
        
        message = data.decode('utf-8', errors='ignore')
        
        if message.startswith('PING'):
            writer.write("PONG :tmi.twitch.tv\r\n".encode('utf-8'))
            await writer.drain()
            continue

        for line in message.split('\r\n'):
            if "PRIVMSG" in line:
                try:
                    user = line.split('!')[0][1:]
                    content = line.split(f"#{TWITCH_CHANNEL.lower()} :")[1].strip()
                    if content.startswith('!'):
                        await handle_browser_command(content, user, "Twitch")
                except IndexError:
                    pass

async def youtube_listener():
    if not YOUTUBE_VIDEO_ID:
        print("⚠️ No se proporcionó YOUTUBE_VIDEO_ID. El bot solo escuchará en Twitch.")
        return

    chat = pytchat.create(video_id=YOUTUBE_VIDEO_ID)
    print(f"📡 Conectado al chat de YouTube (Video ID: {YOUTUBE_VIDEO_ID})")

    while chat.is_alive():
        for c in chat.get().sync_items():
            if c.message.startswith('!'):
                await handle_browser_command(c.message, c.author.name, "YouTube")
        await asyncio.sleep(1)

async def install_firefox_addon(context, addon_path):
    """Instala una extensión .xpi en la sesión de Firefox de Playwright de forma compatible."""
    if not os.path.exists(addon_path):
        print(f"❌ El archivo no existe: {addon_path}")
        return

    abs_path = os.path.abspath(addon_path)
    
    try:
        # Método 1: A través del canal de comunicación del objeto BrowserContext interno
        impl_context = context._impl_obj
        if hasattr(impl_context, "_channel"):
            await impl_context._channel.send("installAddon", {"path": abs_path, "temporary": True})
            print(f"✅ Extensión instalada con éxito: {os.path.basename(addon_path)}")
            return
    except Exception:
        pass

    try:
        # Método 2: A través del objeto de conexión interna
        connection = context._impl_obj._connection
        if hasattr(connection, "_raw_send"):
            await connection._raw_send("Firefox.installAddon", {"path": abs_path, "temporary": True})
            print(f"✅ Extensión instalada con éxito: {os.path.basename(addon_path)}")
            return
        elif hasattr(connection, "send"):
            await connection.send("Firefox.installAddon", {"path": abs_path, "temporary": True})
            print(f"✅ Extensión instalada con éxito: {os.path.basename(addon_path)}")
            return
    except Exception as e:
        print(f"⚠️ No se pudo instalar dinámicamente {os.path.basename(addon_path)}: {e}")

async def main():
    global page_ref

    async with async_playwright() as p:
        print("🚀 Lanzando Firefox con extensiones (.xpi)...")
        
        user_data_dir = os.path.join(BASE_DIR, "firefox_profile")

        context = await p.firefox.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            viewport={"width": 1280, "height": 720},
            firefox_user_prefs={
                "xpinstall.signatures.required": False,
                "extensions.autoDisableScopes": 0
            }
        )

        if os.path.exists(UBLOCK_PATH):
            print(f"🛡️ Cargando uBlock Origin...")
            await install_firefox_addon(context, UBLOCK_PATH)

        if os.path.exists(PLANETVPN_PATH):
            print(f"🔒 Cargando Planet VPN...")
            await install_firefox_addon(context, PLANETVPN_PATH)

        page = context.pages[0] if context.pages else await context.new_page()
        page_ref = page

        await page.goto("https://www.google.com")
        await page.evaluate(CURSOR_JS)

        await asyncio.gather(
            twitch_listener(),
            youtube_listener()
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot detenido por el usuario.")
