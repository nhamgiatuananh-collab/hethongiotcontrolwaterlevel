import gradio as gr
from picamera2 import Picamera2
import time
import threading
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from pyngrok import ngrok, conf
import sys
import random
import string
import numpy as np
import atexit
from flask import Flask, request
import logging

# Tắt log thừa của Flask để đỡ rối mắt
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==========================================
# ⚙️ CẤU HÌNH HỆ THỐNG
# ==========================================

# 1. Cấu hình Ngrok
NGROK_AUTH_TOKEN = "36pW7wOKNSUtDvGZ5ZSZUSQxsKq_64Weo7fdSWzmauvyNNL6t"
NGROK_DOMAIN     = "tiara-complaisant-healingly.ngrok-free.dev"

# 2. Cấu hình Email
EMAIL_SENDER     = "kaitokidbaralic123@gmail.com"
EMAIL_PASSWORD   = "fhol dtxe pxxe xnng"
EMAIL_ADMIN      = "kaitokidbaralic123@gmail.com"

# 3. Cấu hình Camera (KHÔI PHỤC CODE CŨ)
RESOLUTION = (640, 480)
FRAMERATE  = 15 

# Biến lưu mã OTP
otp_storage = {}

# Biến toàn cục lưu trạng thái lửa
fire_status_global = {
    "status": "AN TOAN",
    "color": "#10b981", # Xanh lá
    "last_update": time.time()
}

# ==========================================
# 0. MODULE NHẬN DỮ LIỆU TỪ ESP32 (FLASK)
# ==========================================
app_flask = Flask(__name__)

@app_flask.route('/update', methods=['GET'])
def update_sensor():
    global fire_status_global
    canhbao = request.args.get('canhbao', default='0', type=str)
    
    # Logic cập nhật trạng thái
    if canhbao == '1':
        fire_status_global["status"] = "CÓ CHÁY !!!"
        fire_status_global["color"] = "#ef4444" # Đỏ rực
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 CẢNH BÁO: CÓ CHÁY!")
    else:
        fire_status_global["status"] = "AN TOÀN - HỆ THỐNG ỔN ĐỊNH"
        fire_status_global["color"] = "#10b981"
        
    fire_status_global["last_update"] = time.time()
    return "OK"

def run_flask_server():
    # Chạy Flask ở port 5000 để ESP32 gửi dữ liệu tới
    print("🔥 Server cảm biến lửa đang chạy (Port 5000)...")
    app_flask.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# Chạy Flask ở luồng riêng (Daemon Thread)
threading.Thread(target=run_flask_server, daemon=True).start()

# ==========================================
# 1. MODULE KẾT NỐI NGROK (KHÔI PHỤC)
# ==========================================
def start_ngrok():
    print("🌍 Đang khởi tạo đường hầm Ngrok...")
    if "DÁN_MÃ" in NGROK_AUTH_TOKEN:
        print("❌ LỖI: Bạn chưa điền Token Ngrok!")
        return None
    try:
        conf.get_default().auth_token = NGROK_AUTH_TOKEN
        ngrok.kill()
        url = ngrok.connect(7860, domain=NGROK_DOMAIN).public_url
        print(f"\n✅ ĐÃ KẾT NỐI THÀNH CÔNG!")
        print(f"👉 Truy cập tại: {url}\n")
        return url
    except Exception as e:
        print(f"❌ Lỗi Ngrok: {e}")
        return None

# ==========================================
# 2. MODULE CAMERA (KHÔI PHỤC NGUYÊN BẢN)
# ==========================================
picam2 = None

def init_camera():
    global picam2
    try:
        print("📷 Đang khởi động Camera (Chế độ Manual)...")
        picam2 = Picamera2()
        
        # Cấu hình độ phân giải
        config = picam2.create_preview_configuration(main={"size": RESOLUTION, "format": "RGB888"})
        picam2.configure(config)
        picam2.start()
        
        # --- KHÔI PHỤC PHẦN CẤU HÌNH BỊ THIẾU ---
        # Đây là phần quan trọng để Cam chạy mượt ở 15FPS mà code tối ưu đã bỏ qua
        try:
            picam2.set_controls({
                "FrameDurationLimits": (int(1000000 / FRAMERATE), int(1000000 / FRAMERATE)),
                "ExposureValue": 0.0,
                "AeMeteringMode": 0
            })
            print("✅ Đã nạp cấu hình Manual Controls thành công.")
        except Exception as e: 
            print(f"⚠️ Không set được Controls: {e}")
            pass
            
        print("✅ Camera hoạt động tốt.")
        
    except Exception as e:
        print(f"⚠️ Cảnh báo Camera: {e}")
        picam2 = None

# Gọi khởi động camera
init_camera()

def cleanup_camera():
    global picam2
    if picam2:
        try:
            picam2.stop()
            picam2.close()
            print("🛑 Đã tắt Camera an toàn.")
        except: pass

atexit.register(cleanup_camera)

def get_frame():
    """Hàm lấy ảnh từ camera"""
    global picam2
    try:
        if picam2:
            return picam2.capture_array()
        else:
            raise Exception("Camera chưa sẵn sàng")
    except Exception:
        # Trả về màn hình đen nếu lỗi (tránh crash web)
        return np.zeros((480, 640, 3), dtype=np.uint8)

def stream_loop():
    """Vòng lặp stream ảnh"""
    while True:
        frame = get_frame()
        yield frame
        # Giữ nguyên tốc độ frame như code cũ
        time.sleep(1.0 / FRAMERATE)

# ==========================================
# 3. MODULE GỬI EMAIL & OTP (KHÔI PHỤC)
# ==========================================
def send_email_generic(to_email, subject, body):
    if "your_email" in EMAIL_SENDER: return False
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = to_email

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi mail: {e}")
        return False

def send_otp(user_email):
    if not user_email or "@" not in user_email:
        return "⚠️ Email không hợp lệ!"
    
    otp_code = ''.join(random.choices(string.digits, k=6))
    otp_storage[user_email] = otp_code 
    print(f"🔑 Debug OTP ({user_email}): {otp_code}") 
    
    subject = "🔑 MÃ XÁC THỰC CAMERA (OTP)"
    body = f"Mã xác thực của bạn là: {otp_code}"
    
    if send_email_generic(user_email, subject, body):
        return f"✅ Đã gửi OTP đến {user_email}."
    else:
        return "❌ Lỗi gửi email."

def notify_admin_login(user_email, request: gr.Request):
    client_ip = request.client.host if request else "Unknown IP"
    subject = "🚨 CẢNH BÁO: CÓ NGƯỜI TRUY CẬP CAMERA"
    body = f"User: {user_email}\nIP: {client_ip}\nTime: {datetime.now()}"
    threading.Thread(target=send_email_generic, args=(EMAIL_ADMIN, subject, body)).start()

# ==========================================
# 4. LOGIC ĐĂNG NHẬP
# ==========================================
def verify_login(user_email, input_otp, request: gr.Request):
    if user_email not in otp_storage:
        return gr.update(visible=True), gr.update(visible=False), "❌ Email chưa yêu cầu OTP."
    
    if input_otp == otp_storage[user_email]:
        del otp_storage[user_email]
        notify_admin_login(user_email, request)
        return gr.update(visible=False), gr.update(visible=True), "" 
    else:
        return gr.update(visible=True), gr.update(visible=False), "❌ Mã OTP sai."

# Hàm cập nhật trạng thái lửa cho giao diện
# Dùng generator (while True + yield) để tương thích với bản Gradio cũ
def check_fire_status():
    while True:
        status = fire_status_global["status"]
        color = fire_status_global["color"]
        
        html_content = f"""
        <div style="
            background-color: {color}; 
            color: white; 
            padding: 15px; 
            border-radius: 10px; 
            text-align: center;
            font-family: Arial, sans-serif;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border: 2px solid white;
        ">
            <h2 style="margin:0; font-size: 24px; text-transform: uppercase;">🔥 {status}</h2>
        </div>
        """
        yield html_content
        time.sleep(1) # Cập nhật mỗi 1 giây

# ==========================================
# 5. GIAO DIỆN WEB (GOM CẢ 2)
# ==========================================
css_style = """
.gradio-container {background-color: #111827} 
h1 {color: #10b981; text-align: center}
.login-box {max-width: 400px; margin: 0 auto; padding: 20px; background: #1f2937; border-radius: 10px;}
"""

with gr.Blocks(title="IoT Fire & Cam", css=css_style, theme=gr.themes.Soft()) as demo:
    
    gr.Markdown("# 🔥 HỆ THỐNG GIÁM SÁT AN NINH & PCCC")

    # --- KHU VỰC 1: ĐĂNG NHẬP ---
    with gr.Column(visible=True, elem_classes="login-box") as login_col:
        gr.Markdown("### 🔒 Xác thực danh tính")
        email_input = gr.Textbox(label="Nhập Email", placeholder="example@gmail.com")
        btn_send_otp = gr.Button("📨 Gửi mã OTP")
        otp_msg = gr.Markdown("")
        
        otp_input = gr.Textbox(label="Nhập mã OTP", type="password")
        btn_login = gr.Button("🚀 Đăng nhập", variant="primary")
        login_msg = gr.Markdown("") 

    # --- KHU VỰC 2: DASHBOARD (CAMERA + CẢM BIẾN) ---
    with gr.Column(visible=False) as camera_col:
        with gr.Row():
            btn_logout = gr.Button("Đăng xuất")
        
        # 1. Hiển thị Trạng thái lửa (Ưu tiên đưa lên đầu)
        gr.Markdown("### 🌡️ GIÁM SÁT CẢM BIẾN LỬA")
        fire_display = gr.HTML(label="Trạng thái lửa")
        
        # 2. Hiển thị Camera
        gr.Markdown("### 🎥 Camera Trực Tiếp")
        video_display = gr.Image(label="Live Stream", streaming=True)
        
        # --- KÍCH HOẠT CÁC LUỒNG DỮ LIỆU ---
        # Load Stream Camera
        demo.load(stream_loop, inputs=None, outputs=video_display)
        
        # Load Trạng thái cảm biến (Chạy song song)
        demo.load(check_fire_status, inputs=None, outputs=fire_display)

    # --- SỰ KIỆN NÚT BẤM ---
    btn_send_otp.click(fn=send_otp, inputs=email_input, outputs=otp_msg)
    
    btn_login.click(
        fn=verify_login,
        inputs=[email_input, otp_input],
        outputs=[login_col, camera_col, login_msg]
    )

    btn_logout.click(
        fn=lambda: (gr.update(visible=True), gr.update(visible=False)),
        inputs=None,
        outputs=[login_col, camera_col]
    )

if __name__ == "__main__":
    start_ngrok()
    print("🚀 Đang khởi động Server Gradio (Port 7860)...")
    # Cho phép truy cập từ mọi IP
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, show_error=True)

