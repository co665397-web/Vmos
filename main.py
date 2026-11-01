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
    "message": "Chưa chạy"
}

# Hàm tạo email 10 phút
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

# Hàm đọc OTP từ mail 10 phút
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
    state["message"] = "Đang khởi động trình duyệt ảo (có thể mất 15-20s)..."

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=False, 
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            state["message"] = "Đã mở trình duyệt. Đang truy cập VMOS..."
            
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()

            await page.goto("https://cloud.vmoscloud.com", timeout=60000)
            await page.wait_for_selector('input[type="text"]', timeout=20000)

            # CẢI TIẾN: Dùng fill() thay vì evaluate để React nhận diện
            state["message"] = "Đang tự động điền email..."
            email_input = page.locator('input[type="text"]').first
            await email_input.fill(email)
            await email_input.press("Enter") # Nhấn Enter cho chắc chắn
            await page.wait_for_timeout(1000)

            # Tự động tích điều khoản
            try:
                await page.locator('input[type="checkbox"]').first.check(force=True)
            except: pass
            
            # CẢI TIẾN: Click nút Đăng ký (hỗ trợ cả tiếng Anh và Việt)
            state["message"] = "Đang bấm nút Đăng ký..."
            try:
                await page.locator('button:has-text("Login/Register")').first.click(force=True)
            except:
                await page.locator('button:has-text("Đăng nhập/Đăng ký")').first.click(force=True)

            state["message"] = "Hãy giải Captcha trên màn hình (Nên xoay ngang điện thoại). Tool đang canh mã OTP..."
            otp_found = False
            start_wait = time.time()

            # Vòng lặp chờ OTP
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

            state["message"] = "Đã thấy ô OTP. Đang tự động lấy mã từ mail..."
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
                    await page.locator('button:has-text("Confirm")').first.click(force=True)
                except:
                    await page.locator('button:has-text("Xác nhận")').first.click(force=True)

                state["message"] = "Đăng nhập thành công. Đang vào trang quản lý..."
                await page.wait_for_timeout(7000)

                try:
                    view_now = page.locator('button:has-text("View now")')
                    if await view_now.count() > 0:
                        await view_now.first.click(force=True)
                        await page.wait_for_timeout(4000)
                except: pass

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
            else:
                state["status"] = "idle"
                state["message"] = "Không tìm thấy OTP trong mail 10 phút."
        except Exception as e:
            state["message"] = f"Lỗi Playwright: {str(e)}"
            state["status"] = "idle"
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
        <title>VMOS Tool Auto</title>
        <style>
            * { box-sizing: border-box; }
            body { margin: 0; padding: 0; height: 100vh; font-family: Arial, sans-serif; background: #1e1e1e; color: white; display: flex; overflow: hidden; }
            
            .sidebar { width: 350px; padding: 20px; background: #2d2d2d; display: flex; flex-direction: column; box-shadow: 2px 0 10px rgba(0,0,0,0.8); z-index: 20; transition: 0.3s; height: 100%; overflow-y: auto;}
            .browser { flex: 1; display: flex; position: relative; background: #000; width: 100%; height: 100%;}
            
            /* CSS cho iframe để nó tự phóng to hết mức */
            iframe { flex: 1; border: none; width: 100%; height: 100%; object-fit: contain; }
            
            .menu-btn { display: none; position: absolute; top: 10px; left: 10px; z-index: 30; background: #007bff; color: white; border: none; padding: 10px 15px; font-size: 20px; border-radius: 5px; cursor: pointer; opacity: 0.8;}
            
            button.btn-start { padding: 12px; font-size: 16px; margin-top: 20px; cursor: pointer; border-radius: 5px; border: none; font-weight: bold; background: #007bff; color: white; transition: 0.2s;}
            button.btn-start:hover { background: #0056b3; }
            button.btn-start:disabled { background: #555; cursor: not-allowed; }
            
            .btn-vpn { background: #dc3545; color: white; display: none; text-decoration: none; text-align: center; margin-top: 15px; padding: 12px; border-radius: 5px; font-weight: bold;}
            
            .email-box { background: #444; padding: 10px; border-radius: 5px; margin-top: 15px; display: none; border: 1px solid #555;}
            .email-box input { border: none; background: transparent; text-align: center; color: #00ff00; font-weight: bold; width: 100%; font-size: 16px;}
            
            .message { margin-top: 15px; font-size: 14px; color: #ffc107; line-height: 1.5; padding: 10px; background: rgba(255,193,7,0.1); border-radius: 5px;}
            .success-box { background: #28a745; color: white; padding: 15px; border-radius: 5px; margin-top: 15px; display: none; word-break: break-all; }
            .success-box a { color: #fff; font-weight: bold; text-decoration: underline; }

            @media (max-width: 768px) {
                .menu-btn { display: block; }
                .sidebar { position: absolute; left: -100%; width: 85%; height: 100vh; border-right: 1px solid #444; }
                .sidebar.active { left: 0; }
                .browser { width: 100%; }
                /* Xoay ngang trên điện thoại sẽ thấy rõ hơn */
            }
        </style>
    </head>
    <body>
        <button class="menu-btn" onclick="toggleMenu()">☰ Menu</button>

        <div class="sidebar" id="sidebar">
            <h2 style="margin-top:0; color:#007bff; text-align: center;">VMOS Tool Auto</h2>
            
            <div style="font-size: 13px; color: #aaa; margin-bottom: 10px;">
                Tool sẽ tự động tạo Mail 10 phút, tự động lấy OTP. Chỉ cần bấm nút và giải Captcha.
                <br><br>
                <b>💡 Mẹo:</b> Hãy xoay ngang điện thoại để màn hình VNC to hơn, dễ giải Captcha hơn!
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
        </div>

        <div class="browser">
            <iframe id="vnc" src="/vnc/vnc.html?autoconnect=true&resize=scale&reconnect=true&reconnect_delay=1000&path=/vncproxy"></iframe>
        </div>

        <script>
            let polling;
            
            function toggleMenu() {
                document.getElementById('sidebar').classList.toggle('active');
            }

            async function startTask() {
                document.getElementById('btn-start').disabled = true;
                document.getElementById('btn-start').innerText = "Đang chạy...";
                document.getElementById('success-box').style.display = 'none';
                document.getElementById('btn-vpn').style.display = 'none';
                document.getElementById('email-box').style.display = 'none';

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
                        
                        if(window.innerWidth <= 768) {
                            document.getElementById('sidebar').classList.add('active');
                        }
                    }
                    else if (data.status === 'error_ip') {
                        clearInterval(polling);
                        document.getElementById('btn-start').disabled = false;
                        document.getElementById('btn-start').innerText = "Thử Lại";
                        document.getElementById('btn-vpn').style.display = 'block';
                        
                        if(window.innerWidth <= 768) {
                            document.getElementById('sidebar').classList.add('active');
                        }
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
        "message": "Đang khởi tạo..."
    })
    
    background_tasks.add_task(run_tool)
    return {"msg": "OK"}

@app.get("/api/status")
async def api_status():
    return state

@app.websocket("/vncproxy")
async def websocket_proxy(websocket: WebSocket):
    await websocket.accept()
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 5900)

        async def ws_to_tcp():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    writer.write(data)
                    await writer.drain()
            except: pass

        async def tcp_to_ws():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except: pass

        await asyncio.gather(ws_to_tcp(), tcp_to_ws())
    except Exception as e:
        print("VNC Proxy Error:", e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except: pass
