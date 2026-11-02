import asyncio
import re
import time
import requests
import urllib3
import random
from urllib3.exceptions import InsecureRequestWarning
from fastapi import FastAPI, BackgroundTasks, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright

urllib3.disable_warnings(InsecureRequestWarning)

app = FastAPI()

app.mount("/vnc", StaticFiles(directory="/usr/share/novnc", html=True), name="static")

state = {
    "status": "idle",
    "email": "",
    "link": "",
    "message": "Chưa chạy",
    "show_vnc": False
}

def create_temp_email():
    try:
        r = requests.get("https://api.mail.tm/domains", verify=False)
        domains = [d["domain"] for d in r.json()["hydra:member"]]
        domain = random.choice(domains)
        login = f"user{random.randint(10000, 99999)}"
        email = f"{login}@{domain}"
        password = "Password123!"
        
        r = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password}, verify=False)
        
        if r.status_code == 201:
            return email, password
        else:
            return None, None
    except Exception:
        return None, None

def get_otp_from_temp_mail(email, password, timeout=120):
    start_time = time.time()
    try:
        token_req = requests.post("https://api.mail.tm/token", json={"address": email, "password": password}, verify=False)
        token = token_req.json()["token"]
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    except Exception:
        return None

    while time.time() - start_time < timeout:
        try:
            r = requests.get("https://api.mail.tm/messages", headers=headers, verify=False)
            data = r.json()
            messages = data.get("hydra:member", []) if isinstance(data, dict) else data

            if messages:
                msg_id = messages[0]["id"]
                msg_r = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers=headers, verify=False)
                msg_data = msg_r.json()
                
                raw_text = msg_data.get("text", "")
                raw_html = msg_data.get("html", "")
                if isinstance(raw_text, list): raw_text = "".join(raw_text)
                if isinstance(raw_html, list): raw_html = "".join(raw_html)
                
                body = str(raw_text) + str(raw_html)
                otp_match = re.search(r'\b(\d{6})\b', body)
                if otp_match:
                    return otp_match.group(1)
        except Exception:
            pass
        time.sleep(3)
    return None

async def run_tool():
    global state
    state["status"] = "running"
    state["message"] = "Đang tạo email 10 phút..."
    
    email, password = create_temp_email()
    if not email:
        state["message"] = "Lỗi tạo email 10 phút."
        state["status"] = "idle"
        return
        
    state["email"] = email
    state["message"] = "Đang khởi động điện thoại ảo..."

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=False, 
                args=[
                    '--kiosk', 
                    '--no-sandbox', 
                    '--disable-dev-shm-usage', 
                    '--disable-gpu',
                    '--blink-settings=imagesEnabled=false'
                ]
            )
            state["message"] = "Đang truy cập VMOS..."
            
            context = await browser.new_context(
                viewport={"width": 600, "height": 1024},
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
                is_mobile=True,
                has_touch=True,
                device_scale_factor=1
            )
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()

            await page.goto("https://cloud.vmoscloud.com", timeout=60000)
            await page.wait_for_selector('input[placeholder*="email" i]', timeout=30000)
            await page.wait_for_timeout(1000)

            state["message"] = "Đang điền email..."
            await page.evaluate(f'''() => {{
                let input = document.querySelector('input[placeholder*="email" i]');
                if (input) {{
                    let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    setter.call(input, "{email}");
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    input.blur(); 
                }}
            }}''')
            
            await page.wait_for_timeout(1500)

            state["message"] = "Đang tích Điều khoản..."
            await page.evaluate('''() => {
                let checkboxes = document.querySelectorAll('input[type="checkbox"]');
                if (checkboxes.length > 0) {
                    checkboxes[0].checked = true;
                    checkboxes[0].dispatchEvent(new Event('change', { bubbles: true }));
                }
            }''')
            await page.wait_for_timeout(1000)

            state["message"] = "Đang bấm nút Đăng ký..."
            
            clicked = await page.evaluate('''() => {
                let els = Array.from(document.querySelectorAll('button, div[role="button"], span, a'));
                let target = els.find(el => {
                    let text = (el.innerText || el.textContent || "").trim();
                    let lowerText = text.toLowerCase();
                    let isTarget = (text === 'Login/Register' || text === 'Đăng nhập/Đăng ký');
                    let isNotSocial = !lowerText.includes('facebook') && !lowerText.includes('google');
                    let isVisible = el.offsetParent !== null;
                    return isTarget && isNotSocial && isVisible;
                });
                if (target) { target.click(); return true; }
                return false;
            }''')

            state["show_vnc"] = True
            state["message"] = "Vui lòng giải Captcha trên khung hình nổi..."
            
            await page.wait_for_timeout(2000)
            otp_found = False
            start_wait = time.time()

            while time.time() - start_wait < 300:
                if await page.locator('input[maxlength="1"]').count() > 0:
                    otp_found = True
                    state["show_vnc"] = False 
                    break
                
                if await page.locator('text="Số người nhận quá nhiều"').count() > 0:
                    state["status"] = "error_ip"
                    state["message"] = "IP đã bị chặn."
                    state["show_vnc"] = False
                    return
                    
                await asyncio.sleep(1.5)

            if not otp_found:
                state["message"] = "Hết thời gian chờ OTP."
                state["status"] = "idle"
                state["show_vnc"] = False
                return

            state["message"] = "Đã giải Captcha xong. Đang lấy mã từ mail..."
            otp = await asyncio.to_thread(get_otp_from_temp_mail, email, password)

            if otp:
                otp_inputs = page.locator('input[maxlength="1"]')
                if await otp_inputs.count() > 0:
                    for i in range(6):
                        await otp_inputs.nth(i).click(force=True)
                        await page.keyboard.type(otp[i], delay=100)
                else:
                    await page.keyboard.type(otp, delay=100)

                try:
                    await page.locator('button:has-text("Confirm"), button:has-text("Xác nhận")').first.click(force=True)
                except: pass

                state["message"] = "Đăng nhập thành công. Đang mua máy..."
                await page.wait_for_timeout(5000)

                try:
                    view_now = page.locator('button:has-text("View now"), button:has-text("Xem ngay")')
                    if await view_now.count() > 0:
                        await view_now.first.click(force=True)
                        await page.wait_for_timeout(3000)
                except: pass

                claim_btn = page.locator('button:has-text("Claim now")')
                if await claim_btn.count() > 0:
                    await claim_btn.first.click(force=True)
                    await page.wait_for_timeout(3000)

                    if await page.locator('text="Số người nhận quá nhiều"').count() > 0:
                        state["status"] = "error_ip"
                        state["message"] = "IP đã bị chặn. Hãy mua thủ công."
                        state["show_vnc"] = False
                        return

                    await page.wait_for_timeout(10000)
                    await page.locator('text="Máy đám mây của tôi"').first.click(force=True)
                    await page.wait_for_timeout(12000)

                    state["message"] = "Đang tìm nút Chia sẻ..."
                    await page.evaluate('''() => {
                        let els = Array.from(document.querySelectorAll('svg, i, span, path, div'));
                        let gear = els.find(el => (el.getAttribute('class') || '').toLowerCase().includes('setting'));
                        if (gear) gear.click();
                    }''')
                    await page.wait_for_timeout(1500)
                    await page.evaluate('''() => {
                        let el = Array.from(document.querySelectorAll('*')).find(e => e.textContent.trim() === 'Chia sẻ máy đám mây');
                        if (el) el.click();
                    }''')
                    await page.wait_for_timeout(2000)

                    link_in = page.locator('input[readonly]')
                    if await link_in.count() > 0:
                        state["link"] = await link_in.first.input_value()
                        state["status"] = "success"
                        state["message"] = "Tạo máy thành công!"
                    else:
                        state["status"] = "idle"
                        state["message"] = "Không lấy được link chia sẻ."
            else:
                state["status"] = "idle"
                state["message"] = "Không tìm thấy OTP trong mail 10 phút."
        except Exception as e:
            state["message"] = f"Lỗi: {str(e)}"
            state["status"] = "idle"
            state["show_vnc"] = False
            try:
                await browser.close()
            except: pass

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>VMOS Bot Auto</title>
        <style>
            * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
            body { margin: 0; padding: 0; height: 100vh; width: 100vw; font-family: Arial, sans-serif; background: #1e1e1e; color: white; display: flex; flex-direction: column; overflow: hidden; }
            
            .topbar { padding: 20px; background: #2d2d2d; text-align: center; border-bottom: 1px solid #444; z-index: 10; box-shadow: 0 2px 10px rgba(0,0,0,0.5);}
            .topbar h1 { margin: 0; color: #007bff; font-size: 24px;}
            .main-content { flex: 1; padding: 20px; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; overflow-y: auto;}
            
            button.btn-start { padding: 18px; font-size: 18px; margin-top: 10px; cursor: pointer; border-radius: 10px; border: none; font-weight: bold; background: #007bff; color: white; transition: 0.2s; width: 100%; max-width: 400px; box-shadow: 0 4px 10px rgba(0,123,255,0.4);}
            button.btn-start:hover { background: #0056b3; }
            button.btn-start:disabled { background: #555; cursor: not-allowed; box-shadow: none;}
            
            .status-card { background: #2d2d2d; border: 1px solid #444; padding: 20px; border-radius: 10px; margin-top: 20px; width: 100%; max-width: 400px; }
            
            .email-box { background: #111; padding: 15px; border-radius: 8px; margin-top: 15px; display: none; border: 1px solid #333; text-align: center;}
            .email-box input { border: none; background: transparent; color: #00ff00; font-weight: bold; width: 100%; font-size: 18px; text-align: center;}
            
            .message { margin-top: 15px; font-size: 15px; color: #ffc107; line-height: 1.5; text-align: center;}
            .success-box { background: #28a745; color: white; padding: 15px; border-radius: 8px; margin-top: 15px; display: none; word-break: break-all; text-align: center; box-shadow: 0 4px 10px rgba(40,167,69,0.4);}
            .success-box a { color: #fff; font-weight: bold; text-decoration: underline; font-size: 16px;}

            .btn-vpn { background: #dc3545; color: white; display: none; text-decoration: none; text-align: center; margin-top: 15px; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 10px rgba(220,53,69,0.4);}
            
            .vnc-modal { display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1000; background: rgba(0,0,0,0.9); flex-direction: column; }
            .vnc-header { padding: 15px; background: #2d2d2d; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #444;}
            .vnc-header span { color: #ffc107; font-weight: bold; font-size: 16px;}
            .vnc-header button { padding: 8px 15px; border: none; border-radius: 5px; background: #dc3545; color: white; font-weight: bold; cursor: pointer;}
            .vnc-body { flex: 1; position: relative; background: #000; }
            .vnc-body iframe { width: 100%; height: 100%; border: none; display: block; }
        </style>
    </head>
    <body>
        <div class="topbar">
            <h1>VMOS Bot</h1>
        </div>

        <div class="main-content">
            <button class="btn-start" id="btn-start" onclick="startTask()">Khởi Chạy Bot</button>

            <div class="status-card">
                <div class="message" id="message">Nhấn nút để bắt đầu. Bot sẽ chạy ngầm tự động.</div>

                <div class="email-box" id="email-box">
                    <div style="font-size:12px; color:#aaa; margin-bottom:5px;">Email (Đã tự Copy)</div>
                    <input type="text" id="email-text" readonly>
                </div>

                <div class="success-box" id="success-box">
                    <div style="font-size:14px; margin-bottom:8px;">Link chia sẻ của bạn:</div>
                    <a id="share-link" href="#" target="_blank"></a>
                </div>

                <a href="https://cloud.vmoscloud.com" target="_blank" class="btn-vpn" id="btn-vpn">
                    ⚠️ Lỗi IP. Bấm vào đây để mở VMOS và tự mua bằng VPN.
                </a>
            </div>
        </div>

        <div class="vnc-modal" id="vnc-modal">
            <div class="vnc-header">
                <span>✍️ Chạm & Kéo để giải Captcha</span>
                <button onclick="closeVnc()">Đóng</button>
            </div>
            <div class="vnc-body">
                <iframe id="vnc-iframe" src="about:blank"></iframe>
            </div>
        </div>

        <script>
            let polling;
            const vncSrc = "/vnc/vnc.html?autoconnect=true&resize=scale&reconnect=true&reconnect_delay=1000&path=/vncproxy&view_only=0";
            
            function openVnc() {
                const modal = document.getElementById('vnc-modal');
                const iframe = document.getElementById('vnc-iframe');
                modal.style.display = 'flex';
                if (iframe.src === 'about:blank' || iframe.src === window.location.href) {
                    iframe.src = vncSrc;
                }
            }

            function closeVnc() {
                const modal = document.getElementById('vnc-modal');
                const iframe = document.getElementById('vnc-iframe');
                modal.style.display = 'none';
                iframe.src = 'about:blank'; 
            }

            async function startTask() {
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-start').innerText = "Bot Đang Chạy...";
                document.getElementById('success-box').style.display = 'none';
                document.getElementById('btn-vpn').style.display = 'none';
                document.getElementById('email-box').style.display = 'none';
                closeVnc();

                await fetch('/api/start', { method: 'POST' });
                polling = setInterval(checkStatus, 1500);
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

                    if (data.show_vnc) {
                        if (document.getElementById('vnc-modal').style.display !== 'flex') {
                            openVnc();
                        }
                    } else {
                        if (document.getElementById('vnc-modal').style.display === 'flex') {
                            closeVnc();
                        }
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
                        
                        setTimeout(() => {
                            window.location.href = "https://cloud.vmoscloud.com";
                        }, 2000);
                    }
                } catch (e) {
                    console.log("Đang chờ server...");
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/start")
async def api_start(background_tasks: BackgroundTasks):
    if state["status"] == "running":
        return {"msg": "Đang chạy"}
    
    state.update({
        "status": "running", 
        "email": "", 
        "link": "", 
        "message": "Đang khởi tạo...",
        "show_vnc": False
    })
    
    background_tasks.add_task(run_tool)
    return {"msg": "OK"}

@app.get("/api/status")
async def api_status():
    return state

@app.websocket("/vncproxy")
async def websocket_pro
