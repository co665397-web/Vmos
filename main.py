import asyncio
import re
import time
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from fastapi import FastAPI, BackgroundTasks, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Tắt cảnh báo SSL
urllib3.disable_warnings(InsecureRequestWarning)

app = FastAPI()

# Gắn thư mục noVNC tĩnh để load giao diện VNC
app.mount("/vnc", StaticFiles(directory="/usr/share/novnc", html=True), name="static")

# Trạng thái hệ thống
state = {
    "status": "idle",  # idle, running, success, error_ip
    "email": "",
    "link": "",
    "message": "Chưa chạy"
}

def create_temp_email():
    try:
        r = requests.get("https://api.mail.tm/domains", verify=False)
        domains = [d["domain"] for d in r.json()["hydra:member"]]
        domain = domains[0]
        login = f"user{int(time.time())}"
        email = f"{login}@{domain}"
        password = "Password123!"
        requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password}, verify=False)
        return email, password
    except Exception:
        return None, None

def get_otp(email, password):
    try:
        token_req = requests.post("https://api.mail.tm/token", json={"address": email, "password": password}, verify=False)
        token = token_req.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        for _ in range(30):
            r = requests.get("https://api.mail.tm/messages", headers=headers, verify=False)
            msgs = r.json().get("hydra:member", [])
            if msgs:
                msg_r = requests.get(f"https://api.mail.tm/messages/{msgs[0]['id']}", headers=headers, verify=False)
                body = str(msg_r.json().get("text", "")) + str(msg_r.json().get("html", ""))
                match = re.search(r'\b(\d{6})\b', body)
                if match:
                    return match.group(1)
            time.sleep(3)
    except Exception:
        pass
    return None

async def run_tool():
    global state
    state["status"] = "running"
    state["message"] = "Đang tạo email..."

    email, password = create_temp_email()
    if not email:
        state["message"] = "Lỗi tạo email."
        state["status"] = "idle"
        return

    state["email"] = email

    async with async_playwright() as p:
        # Chạy headless=False để hiển thị lên màn hình ảo Xvfb
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        await Stealth().use_async(page)

        state["message"] = "Đang mở VMOS. Vui lòng nhìn sang màn hình bên phải để giải Captcha."

        try:
            await page.goto("https://cloud.vmoscloud.com", timeout=60000)
            await page.wait_for_selector('input[type="text"]', timeout=20000)

            await page.evaluate(f'''() => {{
                let input = document.querySelector('input[type="text"]');
                if(input) {{
                    input.value = "{email}";
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}''')

            try:
                await page.locator('input[type="checkbox"]').first.check(force=True)
                await page.locator('button:has-text("Đăng nhập/Đăng ký")').first.click(force=True)
            except Exception:
                pass

            state["message"] = "Hãy giải Captcha trên màn hình. Tool đang canh mã OTP..."
            otp_found = False
            start_wait = time.time()

            while time.time() - start_wait < 300:
                if await page.locator('input[maxlength="1"], input[placeholder*="OTP"]').count() > 0:
                    otp_found = True
                    break
                if await page.locator('text="Số người nhận quá nhiều"').count() > 0:
                    state["status"] = "error_ip"
                    state["message"] = "IP đã bị chặn. Vui lòng tự bật VPN và thao tác thủ công."
                    return
                await asyncio.sleep(2)

            if not otp_found:
                state["message"] = "Hết thời gian chờ OTP."
                state["status"] = "idle"
                return

            state["message"] = "Đã thấy ô OTP. Đang tự động lấy mã từ email..."
            otp = get_otp(email, password)

            if otp:
                otp_inputs = page.locator('input[maxlength="1"]')
                if await otp_inputs.count() > 0:
                    for i in range(6):
                        await otp_inputs.nth(i).click(force=True)
                        await page.keyboard.type(otp[i], delay=100)
                else:
                    await page.keyboard.type(otp, delay=100)

                await page.locator('button:has-text("Xác nhận")').first.click(force=True)
                state["message"] = "Đăng nhập thành công. Đang vào trang quản lý..."
                await page.wait_for_timeout(7000)

                try:
                    view_now = page.locator('button:has-text("View now")')
                    if await view_now.count() > 0:
                        await view_now.first.click(force=True)
                        await page.wait_for_timeout(4000)
                except:
                    pass

                state["message"] = "Đang thử nhận máy ảo..."
                claim_btn = page.locator('button:has-text("Claim now")')
                if await claim_btn.count() > 0:
                    await claim_btn.first.click(force=True)
                    await page.wait_for_timeout(3000)

                    if await page.locator('text="Số người nhận quá nhiều"').count() > 0:
                        state["status"] = "error_ip"
                        state["message"] = "IP đã bị chặn khi mua máy."
                        return

                    await page.wait_for_timeout(12000)
                    await page.locator('text="Máy đám mây của tôi"').first.click(force=True)
                    await page.wait_for_timeout(15000)

                    state["message"] = "Đang tìm nút Chia sẻ..."
                    await page.evaluate('''() => {
                        let els = Array.from(document.querySelectorAll('svg, i, span, path, div'));
                        let gear = els.find(el => (el.getAttribute('class') || '').toLowerCase().includes('setting'));
                        if (gear) gear.click();
                    }''')
                    await page.wait_for_timeout(2000)
                    await page.evaluate('''() => {
                        let el = Array.from(document.querySelectorAll('*')).find(e => e.textContent.trim() === 'Chia sẻ máy đám mây');
                        if (el) el.click();
                    }''')
                    await page.wait_for_timeout(3000)

                    link_in = page.locator('input[readonly]')
                    if await link_in.count() > 0:
                        state["link"] = await link_in.first.input_value()
                        state["status"] = "success"
                        state["message"] = "Tạo máy thành công!"
                    else:
                        state["status"] = "idle"
                        state["message"] = "Không lấy được link chia sẻ."
        except Exception as e:
            state["message"] = f"Lỗi: {str(e)}"
            state["status"] = "idle"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>VMOS Tool</title>
        <style>
            body { display: flex; margin: 0; height: 100vh; font-family: Arial; background: #1e1e1e; color: white; }
            .sidebar { width: 320px; padding: 20px; background: #2d2d2d; display: flex; flex-direction: column; box-shadow: 2px 0 5px rgba(0,0,0,0.5); z-index: 10;}
            .browser { flex: 1; display: flex; }
            iframe { flex: 1; border: none; width: 100%; height: 100%; }
            button { padding: 12px; font-size: 16px; margin-top: 10px; cursor: pointer; border-radius: 5px; border: none; font-weight: bold; transition: 0.2s;}
            .btn-start { background: #007bff; color: white; }
            .btn-start:hover { background: #0056b3; }
            .btn-start:disabled { background: #555; cursor: not-allowed; }
            .btn-vpn { background: #dc3545; color: white; display: none; text-decoration: none; text-align: center; margin-top: 15px; padding: 12px; border-radius: 5px; font-weight: bold;}
            .btn-vpn:hover { background: #c82333; }
            .email-box { background: #444; padding: 10px; border-radius: 5px; margin-top: 15px; display: none; border: 1px solid #555;}
            input { background: transparent; border: none; color: #00ff00; font-size: 16px; width: 100%; text-align: center; font-weight: bold; }
            .message { margin-top: 15px; font-size: 14px; color: #aaa; line-height: 1.5; }
            .success-box { background: #28a745; color: white; padding: 15px; border-radius: 5px; margin-top: 15px; display: none; word-break: break-all; }
            .success-box a { color: #fff; font-weight: bold; text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="sidebar">
            <h2 style="margin-top:0; color:#007bff;">VMOS Tool</h2>
            <button class="btn-start" id="btn-start" onclick="startTask()">Tạo Máy Ngay</button>

            <div class="email-box" id="email-box">
                <div style="font-size:12px; text-align:center; color:#ccc; margin-bottom:5px;">Email (Đã tự động Copy)</div>
                <input type="text" id="email-text" readonly>
            </div>

            <div class="message" id="message">Chưa có tiến trình nào.</div>

            <div class="success-box" id="success-box">
                <div style="font-size:14px; margin-bottom:8px;">Link chia sẻ của bạn:</div>
                <a id="share-link" href="#" target="_blank"></a>
            </div>

            <a href="https://cloud.vmoscloud.com" target="_blank" class="btn-vpn" id="btn-vpn">
                ⚠️ IP Bị Chặn. Bấm vào đây để mở Web thật, bật VPN và tự mua.
            </a>
        </div>

        <div class="browser">
            <!-- Load giao diện VNC và kết nối websocket qua proxy /vncproxy -->
            <iframe id="vnc" src="/vnc/vnc.html?autoconnect=true&resize=scale&path=/vncproxy"></iframe>
        </div>

        <script>
            let polling;
            async function startTask() {
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-start').innerText = "Đang chạy...";
                document.getElementById('success-box').style.display = 'none';
                document.getElementById('btn-vpn').style.display = 'none';
                document.getElementById('email-box').style.display = 'none';

                await fetch('/api/start');
                polling = setInterval(checkStatus, 2000);
            }

            async function checkStatus() {
                try {
                    const res = await fetch('/api/status');
                    const data = await res.json();

                    document.getElementById('message').innerText = data.message;

                    if (data.email && document.getElementById('email-box').style.display === 'none') {
                        document.getElementById('email-box').style.display = 'block';
                        document.getElementById('email-text').value = data.email;
                        navigator.clipboard.writeText(data.email).catch(e => console.log('Lỗi copy:', e));
                    }

                    if (data.status === 'success') {
                        clearInterval(polling);
                        document.getElementById('btn-start').disabled = false;
                        document.getElementById('btn-start').innerText = "Tạo Máy Mới";
                        document.getElementById('success-box').style.display = 'block';
                        let a = document.getElementById('share-link');
                        a.href = data.link;
                        a.innerText = data.link;
                    }
                    else if (data.status === 'error_ip') {
                        clearInterval(polling);
                        document.getElementById('btn-start').disabled = false;
                        document.getElementById('btn-start').innerText = "Thử Lại";
                        document.getElementById('btn-vpn').style.display = 'block';
                    }
                } catch (e) {
                    console.log("Đang chờ server...");
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/start")
async def api_start(background_tasks: BackgroundTasks):
    if state["status"] == "running":
        return {"msg": "Đang chạy"}
    state.update({"status": "running", "email": "", "link": "", "message": "Đang khởi tạo..."})
    background_tasks.add_task(run_tool)
    return {"msg": "OK"}

@app.get("/api/status")
async def api_status():
    return state

# ==========================================
# PROXY WEBSOCKET TỰ VIẾT (Chuyển tiếp VNC)
# ==========================================
@app.websocket("/vncproxy")
async def websocket_proxy(websocket: WebSocket):
    await websocket.accept()
    try:
        # Kết nối trực tiếp tới VNC Server ở cổng 5900 nội bộ
        reader, writer = await asyncio.open_connection('127.0.0.1', 5900)

        async def ws_to_tcp():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    writer.write(data)
                    await writer.drain()
            except:
                pass

        async def tcp_to_ws():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except:
                pass

        await asyncio.gather(ws_to_tcp(), tcp_to_ws())
    except Exception as e:
        print("VNC Proxy Error:", e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass
