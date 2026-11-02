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
    "show_vnc": False # CỜ BÁO HIỆN MÀN HÌNH VNC
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

            # ==========================================
            # KHU VỰC CẦN CAPTCHA: BẬT MÀN HÌNH VNC LÊN
            # ==========================================
            state["show_vnc"] = True
            state["message"] = "Hãy giải Captcha trên màn hình. Tool đang đợi bạn..."
            
            # Đợi 2 giây cho Captcha load xong
            await page.wait_for_timeout(2000)

            otp_found = False
            start_wait = time.time()

            while time.time() - start_wait < 300:
                # Nếu thấy ô OTP -> Giải xong -> Tắt màn hình VNC
                if await page.locator('input[maxlength="1"]').count() > 0:
                    otp_found = True
                    state["show_vnc"] = False 
                    break
                
                # Nếu bị chặn IP -> Tắt màn hình VNC
                if await page.locator('text="Số người nhận quá nhiều"').count() > 0:
                    state["status"] = "error_ip"
                    state["message"] = "IP đã bị chặn. Vui lòng tự bật VPN và thao tác thủ công."
                    state["show_vnc"] = False
                    return
                    
                await asyncio.sleep(1.5)

            if not otp_found:
                state["message"] = "Hết thời gian chờ OTP."
                state["status"] = "idle"
                state["show_vnc"] = False
                return

            # ==========================================
            # ĐÃ GIẢI XONG CAPTCHA: TIẾP TỤC CHẠY NGẦM
            # ==========================================
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

                state["message"] = "Đăng nhập thành công. Đang vào trang quản lý..."
                await page.wait_for_timeout(5000)

                try:
                    view_now = page.locator('button:has-text("View now"), button:has-text("Xem ngay")')
                    if await view_now.count() > 0:
                        await view_now.first.click(force=True)
                        await page.wait_for_timeout(3000)
                except: pass

                state["message"] = "Đang thử nhận máy ảo..."
                claim_btn = page.locator('button:has-text("Claim now")')
                if await claim_btn.count() > 0:
                    await claim_btn.first.click(force=True)
                    await page.wait_for_timeout(3000)

                    if await page.locator('text="Số người nhận quá nhiều"').count() > 0:
                        state["status"] = "error_ip"
                        state["message"] = "IP đã bị chặn khi mua máy."
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
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>VMOS Bot Auto</title>
        <style>
            * { box-sizing: border-box; }
            body { margin: 0; padding: 0; height: 100vh; width: 100vw; font-family: Arial, sans-serif; background: #1e1e1e; color: white; display: flex; flex-direction: column; overflow: hidden; }
            
            .main-layout { display: flex; height: 100%; width: 100%; }
            
            .sidebar { width: 350px; padding: 20px; background: #2d2d2d; display: flex; flex-direction: column; box-shadow: 2px 0 10px rgba(0,0,0,0.8); z-index: 10; height: 100%; overflow-y: auto;}
            .content { flex: 1; display: flex; justify-content: center; align-items: center; text-align: center; color: #666; background: #151515; padding: 20px;}
            
            .menu-btn { display: none; position: absolute; top: 10px; left: 10px; z-index: 40; background: #007bff; color: white; border: none; padding: 10px 15px; font-size: 20px; border-radius: 5px; cursor: pointer; opacity: 0.8;}
            
            button.btn-start { padding: 15px; font-size: 16px; margin-top: 20px; cursor: pointer; border-radius: 5px; border: none; font-weight: bold; background: #007bff; color: white; transition: 0.2s; width: 100%;}
            button.btn-start:hover { background: #0056b3; }
            button.btn-start:disabled { background: #555; cursor: not-allowed; }
            
            .btn-vpn { background: #dc3545; color: white; display: none; text-decoration: none; text-align: center; margin-top: 15px; padding: 12px; border-radius: 5px; font-weight: bold;}
            .btn-manual-vnc { background: #6c757d; color: white; display: block; text-align: center; margin-top: 15px; padding: 10px; border-radius: 5px; cursor: pointer; border: none; width: 100%; font-weight: bold;}
            
            .email-box { background: #444; padding: 10px; border-radius: 5px; margin-top: 15px; display: none; border: 1px solid #555;}
            .email-box input { border: none; background: transparent; text-align: center; color: #00ff00; font-weight: bold; width: 100%; font-size: 16px;}
            
            .message { margin-top: 15px; font-size: 14px; color: #ffc107; line-height: 1.5; padding: 10px; background: rgba(255,193,7,0.1); border-radius: 5px;}
            .success-box { background: #28a745; color: white; padding: 15px; border-radius: 5px; margin-top: 15px; display: none; word-break: break-all; }
            .success-box a { color: #fff; font-weight: bold; text-decoration: underline; }

            /* LỚP PHỦ VNC BÍ MẬT (Chỉ hiện khi cần) */
            #vnc-container { display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 100; background: #000; }
            #vnc-container iframe { width: 100%; height: 100%; border: none; display: block; }
            .vnc-header { position: absolute; top: 10px; right: 10px; z-index: 110; display: flex; gap: 10px; }
            .vnc-header button { padding: 10px 15px; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
            .vnc-close { background: #dc3545; color: white; }
            .vnc-note { position: absolute; top: 10px; left: 10px; z-index: 110; background: rgba(0,0,0,0.8); color: #00ff00; padding: 5px 10px; border-radius: 5px; font-size: 14px; pointer-events: none;}

            @media (max-width: 768px) {
                .menu-btn { display: block; }
                .sidebar { position: absolute; left: -100%; width: 85%; height: 100%; border-right: 1px solid #444; z-index: 20;}
                .sidebar.active { left: 0; }
                .content { width: 100%; }
            }
        </style>
    </head>
    <body>
        <button class="menu-btn" onclick="toggleMenu()">☰ Menu</button>

        <div class="main-layout">
            <div class="sidebar" id="sidebar">
                <h2 style="margin-top:0; color:#007bff; text-align: center;">VMOS Bot Auto</h2>
                
                <div style="font-size: 13px; color: #aaa; margin-bottom: 10px; text-align: center;">
                    Tool chạy ngầm 100%.<br>Màn hình sẽ <b>tự động bật lên</b> khi cần giải Captcha.
                </div>

                <button class="btn-start" id="btn-start" onclick="startTask()">Bắt Đầu Tạo Máy</button>

                <div class="email-box" id="email-box">
                    <div style="font-size:12px; text-align:center; color:#ccc; margin-bottom:5px;">Email 10 phút (Đã tự Copy)</div>
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
                
                <button class="btn-manual-vnc" onclick="toggleVnc(true)">👁️ Xem màn hình (Thủ công)</button>
            </div>

            <div class="content">
                <div>
                    <h1>🤖</h1>
                    <h2>Bot đang chạy ngầm...</h2>
                    <p>Bạn không cần làm gì cả.</p>
                    <p>Khi nào trang web yêu cầu Captcha,<br>màn hình VNC sẽ <b>tự động bật lên</b>.<br>Giải xong nó sẽ tự tắt.</p>
                </div>
            </div>
        </div>

        <!-- Lớp phủ VNC -->
        <div id="vnc-container">
            <div class="vnc-note">✍️ Chạm và kéo để giải Captcha</div>
            <div class="vnc-header">
                <button class="vnc-close" onclick="toggleVnc(false)">Đóng</button>
            </div>
            <iframe id="vnc" src="about:blank"></iframe>
        </div>

        <script>
            let polling;
            const vncSrc = "/vnc/vnc.html?autoconnect=true&resize=scale&reconnect=true&reconnect_delay=1000&path=/vncproxy&view_only=0";
            
            function toggleMenu() {
                document.getElementById('sidebar').classList.toggle('active');
            }

            function toggleVnc(show) {
                const container = document.getElementById('vnc-container');
                const iframe = document.getElementById('vnc');
                if (show) {
                    container.style.display = 'block';
                    // Chỉ kết nối WebSocket khi hiển thị
                    if (iframe.src === 'about:blank' || iframe.src === window.location.href) {
                        iframe.src = vncSrc;
                    }
                } else {
                    container.style.display = 'none';
                    // Ngắt kết nối để tiết kiệm dữ liệu mạng
                    iframe.src = 'about:blank'; 
                }
            }

            async function startTask() {
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-start').innerText = "Đang chạy...";
                document.getElementById('success-box').style.display = 'none';
                document.getElementById('btn-vpn').style.display = 'none';
                document.getElementById('email-box').style.display = 'none';
                toggleVnc(false); // Tắt VNC nếu đang mở

                if(window.innerWidth <= 768) {
                    document.getElementById('sidebar').classList.remove('active');
                }

                await fetch('/api/start', { method: 'POST' });
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
                 
