from pyscript import document, window
from pyodide.ffi import create_proxy
import random
import time
import json
from datetime import datetime
import asyncio

# Globals
current_level = 1
streak = 0
grid_size = 3
numbers_count = 3
target_grid_data = []
user_grid_data = []
selected_cell = None

last_interaction_time = time.time()
flashing_active = False

stats_start_time = 0
left_neglect_cues = 0

# DOM Elements
el_game_view = document.getElementById("game-view")
el_dashboard = document.getElementById("dashboard")
el_target_grid = document.getElementById("target-grid")
el_user_grid = document.getElementById("user-grid")
el_numpad_popup = document.getElementById("numpad-popup")
el_reward_overlay = document.getElementById("reward-overlay")
el_left_line = document.getElementById("left-anchor-line")
el_chart_container = document.getElementById("chart-container")

# Setup global Audio Context if available
audio_ctx = None
ctx_constructor = getattr(window, "AudioContext", getattr(window, "webkitAudioContext", None))
if ctx_constructor:
    try:
        audio_ctx = ctx_constructor.new()
    except:
        pass

def get_level_config(level):
    if level == 1: return 3, 3
    if level == 2: return 4, 5
    if level >= 3: return 5, 7
    return 3, 3

def init_round():
    global grid_size, numbers_count, target_grid_data, user_grid_data, last_interaction_time, stats_start_time, flashing_active
    grid_size, numbers_count = get_level_config(current_level)
    
    target_grid_data = [[None for _ in range(grid_size)] for _ in range(grid_size)]
    user_grid_data = [[None for _ in range(grid_size)] for _ in range(grid_size)]
    
    positions = [(r, c) for r in range(grid_size) for c in range(grid_size)]
    selected_pos = random.sample(positions, numbers_count)
    
    for r, c in selected_pos:
        target_grid_data[r][c] = random.randint(1, 9)
        
    render_grids()
    reset_timer()
    stats_start_time = time.time()
    flashing_active = False
    el_left_line.classList.remove("vibrate-animation")

def render_grids():
    el_target_grid.innerHTML = generate_svg(target_grid_data, "target")
    el_user_grid.innerHTML = generate_svg(user_grid_data, "user")

def generate_svg(grid_data, prefix):
    svg_size = 400
    cell_size = svg_size / grid_size
    svg_html = f'<svg class="game-grid" viewBox="0 0 {svg_size} {svg_size}">'
    for r in range(grid_size):
        for c in range(grid_size):
            x = c * cell_size
            y = r * cell_size
            val = grid_data[r][c]
            css_class = ""
            
            if val is None:
                text_content = ""
            else:
                text_content = str(val)
            
            onclick = ""
            if prefix == "user":
                if target_grid_data[r][c] is not None and user_grid_data[r][c] is None:
                    onclick = f'onclick="window.handle_cell_click({r}, {c})"'
            
            svg_html += f'''
            <g class="svg-cell {css_class}" id="{prefix}-cell-{r}-{c}" {onclick}>
                <rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" />
                <text x="{x + cell_size/2}" y="{y + cell_size/2}">{text_content}</text>
            </g>
            '''
    svg_html += '</svg>'
    return svg_html

def handle_cell_click(r, c):
    global selected_cell
    reset_timer()
    if flashing_active:
        stop_flashing()
    
    selected_cell = (r, c)
    show_numpad()

window.handle_cell_click = create_proxy(handle_cell_click)

def show_numpad():
    el_numpad_popup.classList.remove("hidden")
    numpad_grid = window.document.querySelector(".numpad-grid")
    numpad_grid.innerHTML = ""
    for i in range(1, 10):
        btn = window.document.createElement("div")
        btn.className = "numpad-btn"
        btn.textContent = str(i)
        
        def make_handler(num):
            def handler(e):
                handle_number_input(num)
            return create_proxy(handler)
            
        btn.addEventListener("click", make_handler(i))
        numpad_grid.appendChild(btn)

def close_numpad(*args):
    el_numpad_popup.classList.add("hidden")
    reset_timer()

window.document.getElementById("btn-numpad-close").addEventListener("click", create_proxy(close_numpad))

def play_audio(type_str):
    global audio_ctx
    if not audio_ctx:
        return
    try:
        # Resume context if suspended (browser auto-play policy)
        if audio_ctx.state == "suspended":
            audio_ctx.resume()
            
        osc = audio_ctx.createOscillator()
        gain = audio_ctx.createGain()
        osc.connect(gain)
        gain.connect(audio_ctx.destination)
        
        now = audio_ctx.currentTime
        if type_str == "ding":
            osc.type = "sine"
            osc.frequency.setValueAtTime(880, now) # A5
            gain.gain.setValueAtTime(1, now)
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5)
            osc.start(now)
            osc.stop(now + 0.5)
        elif type_str == "success":
            osc.type = "square"
            osc.frequency.setValueAtTime(440, now)
            osc.frequency.setValueAtTime(554, now + 0.2)
            osc.frequency.setValueAtTime(659, now + 0.4)
            osc.frequency.setValueAtTime(880, now + 0.6)
            gain.gain.setValueAtTime(0.2, now)
            gain.gain.exponentialRampToValueAtTime(0.01, now + 1.0)
            osc.start(now)
            osc.stop(now + 1.0)
    except Exception as e:
        print("Audio playback failed:", e)

def handle_number_input(num):
    global selected_cell, user_grid_data
    if not selected_cell: return
    r, c = selected_cell
    
    if target_grid_data[r][c] == num:
        user_grid_data[r][c] = num
        play_audio("ding")
        render_grids()
        close_numpad()
        check_win()
    else:
        close_numpad()
        user_cell = window.document.getElementById(f"user-cell-{r}-{c}")
        if user_cell:
            user_cell.classList.add("error-flash")
            def remove_flash():
                user_cell.classList.remove("error-flash")
            window.setTimeout(create_proxy(remove_flash), 500)
    
    reset_timer()

def check_win():
    global streak, current_level
    for r in range(grid_size):
        for c in range(grid_size):
            if target_grid_data[r][c] is not None and user_grid_data[r][c] != target_grid_data[r][c]:
                return
                
    play_audio("success")
    save_stats()
    
    streak += 1
    if streak >= 3:
        current_level += 1
        streak = 0
        
    show_reward()

def show_reward():
    el_reward_overlay.classList.remove("hidden")
    def next_round():
        el_reward_overlay.classList.add("hidden")
        init_round()
    window.setTimeout(create_proxy(next_round), 3000)

def reset_timer():
    global last_interaction_time
    last_interaction_time = time.time()
    
def check_timer():
    global flashing_active, left_neglect_cues
    # Only active when game is visible, numpad is hidden, reward is hidden
    if time.time() - last_interaction_time > 5 and not flashing_active:
        if "hidden" in el_numpad_popup.className and "hidden" in el_reward_overlay.className and "hidden" not in el_game_view.className:
            flashing_active = True
            left_neglect_cues += 1
            el_left_line.classList.add("vibrate-animation")
            
            for r in range(grid_size):
                for c in range(grid_size):
                    if target_grid_data[r][c] is not None and user_grid_data[r][c] is None:
                        cell = window.document.getElementById(f"target-cell-{r}-{c}")
                        if cell:
                            cell.classList.add("glow")

def stop_flashing():
    global flashing_active
    flashing_active = False
    el_left_line.classList.remove("vibrate-animation")
    elements = window.document.querySelectorAll(".glow")
    for i in range(elements.length):
        elements[i].classList.remove("glow")

async def timer_loop():
    while True:
        check_timer()
        await asyncio.sleep(1)

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def save_stats():
    global stats_start_time, left_neglect_cues
    total_time = time.time() - stats_start_time
    avg_click_time = total_time / numbers_count if numbers_count > 0 else 0
    today = get_today_str()
    
    data_str = window.localStorage.getItem("rehab_grid_stats")
    if data_str:
        data = json.loads(data_str)
    else:
        data = {}
        
    if today not in data:
        data[today] = {"rounds": 0, "cues": 0, "avg_time_sum": 0.0, "max_level": 1}
        
    data[today]["rounds"] += 1
    data[today]["cues"] += left_neglect_cues
    data[today]["avg_time_sum"] += avg_click_time
    data[today]["max_level"] = max(data[today]["max_level"], current_level)
    
    window.localStorage.setItem("rehab_grid_stats", json.dumps(data))
    
    left_neglect_cues = 0

def load_dashboard():
    data_str = window.localStorage.getItem("rehab_grid_stats")
    if data_str:
        data = json.loads(data_str)
    else:
        el_chart_container.innerHTML = "<p>目前尚無紀錄</p>"
        return

    dates = sorted(data.keys(), reverse=True)[:7]
    
    html = "<table><tr><th>日期</th><th>完成回合</th><th>左側提醒</th><th>最高難度</th></tr>"
    for d in dates:
        r = data[d]["rounds"]
        c = data[d]["cues"]
        ml = data[d]["max_level"]
        html += f"<tr><td>{d}</td><td>{r}</td><td>{c}次</td><td>Level {ml}</td></tr>"
    html += "</table>"
    el_chart_container.innerHTML = html

def start_game(*args):
    # Try to initialize audio ctx on first user interaction
    global audio_ctx
    if audio_ctx and audio_ctx.state == "suspended":
        audio_ctx.resume()
    elif not audio_ctx and ctx_constructor:
        try:
            audio_ctx = ctx_constructor.new()
        except:
            pass

    el_dashboard.classList.add("hidden")
    el_game_view.classList.remove("hidden")
    init_round()

window.document.getElementById("btn-start").addEventListener("click", create_proxy(start_game))

asyncio.ensure_future(timer_loop())
load_dashboard()

start_btn = window.document.getElementById("btn-start")
start_btn.removeAttribute("disabled")
start_btn.innerText = "開始訓練"
