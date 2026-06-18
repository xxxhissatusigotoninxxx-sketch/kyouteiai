import os
import re
import sys
import json
import glob
import time
import webbrowser
import urllib.request
import urllib.parse
from datetime import datetime

# Windows環境での日本語・絵文字出力エラー対策
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ---------------------------------------------------------------------------
# Constants & Stadium Mappings
# ---------------------------------------------------------------------------
STADIUM_MAP = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "琵琶湖", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"
}

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def clean_html_tags(text):
    if not text:
        return ""
    cleaned = re.sub(r'<[^>]*>', ' ', text)
    return ' '.join(cleaned.split()).strip()

def safe_float(val_str, default=0.0):
    try:
        cleaned = re.sub(r'[^\d.]', '', val_str)
        return float(cleaned) if cleaned else default
    except:
        return default

def safe_int(val_str, default=0):
    try:
        cleaned = re.sub(r'[^\d]', '', val_str)
        return int(cleaned) if cleaned else default
    except:
        return default

def fetch_html(url):
    """HTMLを取得（エンコーディングの自動判別とエラーハンドリング）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://www.boatrace.jp/"
    }
    req = urllib.request.Request(url, headers=headers)
    
    # 接続再試行（最大3回）
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                content_type = response.headers.get("Content-Type", "").lower()
                
                charset = "utf-8"
                if "charset" in content_type:
                    for part in content_type.split(";"):
                        part = part.strip()
                        if part.startswith("charset="):
                            charset = part.split("=")[1].strip()
                
                # HTML内のmetaタグから文字コードを検出
                if charset == "utf-8":
                    try:
                        temp_text = content.decode("utf-8", errors="ignore")
                        meta_match = re.search(r'<meta[^>]+charset=["\']?(euc-jp|shift_jis|sjis|utf-8)["\']?', temp_text, re.IGNORECASE)
                        if meta_match:
                            charset = meta_match.group(1).lower().replace("sjis", "shift-jis").replace("shift_jis", "shift-jis")
                    except:
                        pass
                
                try:
                    return content.decode(charset, errors="ignore")
                except:
                    return content.decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(1.0)

# ---------------------------------------------------------------------------
# Fan Handbook Parser (モーターボートファン手帳)
# ---------------------------------------------------------------------------
def load_fan_data(data_dir="data"):
    """
    最新の fan*.txt をパースして登番キーの辞書を返します。
    """
    search_path = os.path.join(data_dir, "fan*.txt")
    files = glob.glob(search_path)
    
    if not files:
        print(f"[FanParser] Warning: '{data_dir}' 内に fan*.txt が見つかりませんでした。出走表データのみで予想します。")
        return {}
        
    latest_file = sorted(files)[-1]
    print(f"[FanParser] ファン手帳からレーサーデータを読み込んでいます: {os.path.basename(latest_file)}")
    
    racer_db = {}
    try:
        with open(latest_file, "rb") as f:
            for line in f:
                if len(line) < 92:
                    continue
                try:
                    toban = line[0:4].decode('cp932', errors='ignore').strip()
                    if not toban.isdigit():
                        continue
                        
                    name = line[4:20].decode('cp932', errors='ignore').strip().replace('\u3000', ' ').strip()
                    class_level = line[39:41].decode('cp932', errors='ignore').strip()
                    branch = line[35:39].decode('cp932', errors='ignore').strip()
                    
                    def parse_val(b, divisor=100.0, default=0.0):
                        val_str = b.decode('cp932', errors='ignore').strip()
                        if val_str.isdigit():
                            return float(val_str) / divisor
                        return default

                    win_rate = parse_val(line[58:62]) # 全国勝率 (例: '0618' -> 6.18)
                    double_rate = parse_val(line[62:66], divisor=10.0) # 全国2連率 (例: '0456' -> 45.6%)
                    local_win_rate = parse_val(line[85:89]) # 当地勝率 (例: '0800' -> 8.00)
                    local_double_rate = parse_val(line[92:94], divisor=1.0) # 当地2連率 (例: '31' -> 31.0%)
                    avg_st = parse_val(line[79:82], divisor=100.0, default=0.15) # 全国平均ST (例: '017' -> 0.17)
                    
                    f_str = line[78:79].decode('cp932', errors='ignore').strip()
                    l_str = line[82:83].decode('cp932', errors='ignore').strip()
                    flying = int(f_str) if f_str.isdigit() else 0
                    late = int(l_str) if l_str.isdigit() else 0
                    
                    racer_db[toban] = {
                        "toban": toban,
                        "name": name,
                        "class": class_level,
                        "branch": branch,
                        "winRate": win_rate,
                        "doubleRate": double_rate,
                        "localWinRate": local_win_rate,
                        "localDoubleRate": local_double_rate,
                        "avgST": avg_st,
                        "flying": flying,
                        "late": late,
                        "isMerged": True
                    }
                except Exception:
                    pass
        print(f"[FanParser] ファン手帳から {len(racer_db)} 名の選手情報をパースしました。")
    except Exception as e:
        print(f"[FanParser] ファン手帳の読み込みに失敗しました: {e}")
    return racer_db

# ---------------------------------------------------------------------------
# Scraping Parsers
# ---------------------------------------------------------------------------
def parse_stadium_rates(html):
    """競艇場のコース別入着率をパース"""
    tables = re.findall(r'<table.*?>.*?</table>', html, re.DOTALL)
    if not tables:
        return {}
        
    result = {}
    table_names = {0: "recent3", 2: "spring", 3: "autumn", 4: "summer", 5: "winter"}
    
    for idx, name in table_names.items():
        if idx >= len(tables):
            continue
        table = tables[idx]
        rows = re.findall(r'<tr.*?>.*?</tr>', table, re.DOTALL)
        
        rates = []
        for row in rows:
            cells = re.findall(r'<t[dh].*?>(.*?)</t[dh]>', row, re.DOTALL)
            cells = [clean_html_tags(c) for c in cells if clean_html_tags(c)]
            
            if not cells:
                continue
                
            course_candidate = cells[0]
            if course_candidate.isdigit() and 1 <= int(course_candidate) <= 6:
                course_num = int(course_candidate)
                try:
                    p_values = [safe_float(c) for c in cells[1:7]]
                    rates.append({
                        "course": course_num,
                        "p1": p_values[0],
                        "p2": p_values[1],
                        "p3": p_values[2],
                        "p4": p_values[3],
                        "p5": p_values[4],
                        "p6": p_values[5]
                    })
                except:
                    pass
        if rates:
            result[name] = rates
    return result

def parse_racelist(html):
    """出走表から選手基本情報をパース"""
    tbodies = re.findall(r'<tbody.*?>.*?</tbody>', html, re.DOTALL)
    racers = []
    
    race_title = "一般レース"
    title_match = re.search(r'<h2 class="heading2_titleName[^>]*>(.*?)</h2>', html, re.DOTALL)
    if title_match:
        race_title = clean_html_tags(title_match.group(1))
    else:
        title_match2 = re.search(r'<span class="heading2_titleName[^>]*>(.*?)</span>', html, re.DOTALL)
        if title_match2:
            race_title = clean_html_tags(title_match2.group(1))
            
    for boat_num in range(1, 7):
        target_tbody = None
        color_class = f"is-boatColor{boat_num} is-fs14"
        for tbody in tbodies:
            if color_class in tbody:
                target_tbody = tbody
                break
                
        if not target_tbody:
            continue
            
        toban = ""
        racer_class = "B1"
        racer_name = f"選手{boat_num}"
        
        info_match = re.search(r'<div class="is-fs11">\s*(\d{4,5})\s*/\s*<span[^>]*>\s*([A-B][1-2])\s*</span>', target_tbody)
        if info_match:
            toban = info_match.group(1).strip()
            racer_class = info_match.group(2).strip()
            
        name_match = re.search(r'<div class="is-fs18 is-fBold">.*?<a[^>]*>(.*?)</a>', target_tbody, re.DOTALL)
        if name_match:
            racer_name = clean_html_tags(name_match.group(1)).replace(" ", "").replace("　", "")
            
        line_h2_cells = re.findall(r'<td class="is-lineH2"[^>]*>(.*?)</td>', target_tbody, re.DOTALL)
        
        avg_st = 0.15
        flying = 0
        late = 0
        win_rate = 5.00
        double_rate = 30.00
        local_win_rate = 5.00
        local_double_rate = 30.00
        
        if len(line_h2_cells) >= 3:
            st_lines = [clean_html_tags(line) for line in re.split(r'<br\s*/?>', line_h2_cells[0], flags=re.IGNORECASE) if clean_html_tags(line)]
            for line_val in st_lines:
                if "F" in line_val:
                    flying = safe_int(line_val.replace("F", ""))
                elif "L" in line_val:
                    late = safe_int(line_val.replace("L", ""))
                elif "." in line_val:
                    avg_st = safe_float(line_val, 0.15)
                    
            nation_lines = [clean_html_tags(line) for line in re.split(r'<br\s*/?>', line_h2_cells[1], flags=re.IGNORECASE) if clean_html_tags(line)]
            if len(nation_lines) >= 2:
                win_rate = safe_float(nation_lines[0], 5.00)
                double_rate = safe_float(nation_lines[1], 30.00)
                
            local_lines = [clean_html_tags(line) for line in re.split(r'<br\s*/?>', line_h2_cells[2], flags=re.IGNORECASE) if clean_html_tags(line)]
            if len(local_lines) >= 2:
                local_win_rate = safe_float(local_lines[0], 5.00)
                local_double_rate = safe_float(local_lines[1], 30.00)
                
        rowspan_cells = re.findall(r'<td rowspan="4"[^>]*>(.*?)</td>', target_tbody, re.DOTALL)
        motor_rate = 35.0
        boat_rate = 35.0
        
        if len(rowspan_cells) >= 2:
            m_lines = [clean_html_tags(line) for line in re.split(r'<br\s*/?>', rowspan_cells[-2], flags=re.IGNORECASE) if clean_html_tags(line)]
            if len(m_lines) >= 2:
                motor_rate = safe_float(m_lines[1], 35.0)
            b_lines = [clean_html_tags(line) for line in re.split(r'<br\s*/?>', rowspan_cells[-1], flags=re.IGNORECASE) if clean_html_tags(line)]
            if len(b_lines) >= 2:
                boat_rate = safe_float(b_lines[1], 35.0)
                
        racers.append({
            "num": boat_num,
            "toban": toban,
            "name": racer_name,
            "racerClass": racer_class,
            "avgST": avg_st,
            "winRate": win_rate,
            "doubleRate": double_rate,
            "localWinRate": local_win_rate,
            "localDoubleRate": local_double_rate,
            "motorRate": motor_rate,
            "boatRate": boat_rate,
            "flying": flying,
            "late": late
        })
        
    return {"title": race_title, "racers": racers}

def parse_beforeinfo(html):
    """直前情報・展示タイム・気象をパース"""
    tbodies = re.findall(r'<tbody.*?>.*?</tbody>', html, re.DOTALL)
    exhibitions = {}
    
    for boat_num in range(1, 7):
        target_tbody = None
        color_class = f"is-boatColor{boat_num}"
        for tbody in tbodies:
            if color_class in tbody:
                target_tbody = tbody
                break
                
        if not target_tbody:
            continue
            
        rowspan_cells = re.findall(r'<td rowspan="4"[^>]*>(.*?)</td>', target_tbody, re.DOTALL)
        ex_time = 6.80
        tilt = -0.5
        
        for cell in rowspan_cells:
            text = clean_html_tags(cell)
            if re.match(r'^\d+\.\d{2}$', text):
                ex_time = safe_float(text, 6.80)
            elif '-' in text or '+' in text or '0.0' in text or '0.5' in text:
                try:
                    tilt = float(text.replace('°', ''))
                except:
                    pass
                    
        exhibitions[boat_num] = {"exhibit": ex_time, "tilt": tilt}
        
    weather = "fine"
    wind_speed = 2
    wind_dir = "tailwind"
    wave = 2
    
    weather_match = re.search(r'class="weather1_bodyUnit is-weather".*?<span class="weather1_bodyUnitLabelTitle[^>]*>(.*?)</span>', html, re.DOTALL)
    if weather_match:
        w_text = clean_html_tags(weather_match.group(1))
        if "曇" in w_text:
            weather = "cloudy"
        elif "雨" in w_text or "雪" in w_text:
            weather = "rain"
            
    wind_match = re.search(r'class="weather1_bodyUnit is-wind".*?<span class="weather1_bodyUnitLabelData[^>]*>(.*?)</span>', html, re.DOTALL)
    if wind_match:
        wind_speed = safe_int(wind_match.group(1).replace("m", ""))
        
    wind_dir_match = re.search(r'class="weather1_bodyUnitImage is-windDirection\s*is-wind(\d+)"', html)
    if wind_dir_match:
        dir_num = int(wind_dir_match.group(1))
        if 3 <= dir_num <= 7:
            wind_dir = "tailwind"
        elif 11 <= dir_num <= 15:
            wind_dir = "headwind"
        else:
            wind_dir = "cross"
            
    wave_match = re.search(r'class="weather1_bodyUnit is-wave".*?<span class="weather1_bodyUnitLabelData[^>]*>(.*?)</span>', html, re.DOTALL)
    if wave_match:
        wave = safe_int(wave_match.group(1).replace("cm", ""))
        
    return {
        "exhibitions": exhibitions,
        "weather": {
            "weather": weather,
            "windSpeed": wind_speed,
            "windDir": wind_dir,
            "wave": wave
        }
    }

def parse_odds_3t_3f(html_3t, html_3f):
    """オッズをパース（公式サイトHTMLの配置順序に完全同期）"""
    odds_3t = []
    odds_3f = []
    
    if html_3t:
        odds_cells = re.findall(r'<td class="[^"]*oddsPoint[^"]*"[^>]*>(.*?)</td>', html_3t, re.DOTALL)
        if odds_cells:
            # 3連単のHTML出現順に合わせた combos を生成
            block_orders = {}
            for first in range(1, 7):
                order = []
                for second in range(1, 7):
                    if second == first: continue
                    for third in range(1, 7):
                        if third == first or third == second: continue
                        order.append((second, third))
                block_orders[first] = order
                
            combos_3t = []
            for r in range(20):
                for first in range(1, 7):
                    second, third = block_orders[first][r]
                    combos_3t.append([first, second, third])
            
            for idx, cell in enumerate(odds_cells):
                if idx >= len(combos_3t):
                    break
                val_str = clean_html_tags(cell)
                val = safe_float(val_str, -1.0)
                if val > 0:
                    odds_3t.append({"combo": combos_3t[idx], "odds": val})
                    
    if html_3f:
        odds_cells = re.findall(r'<td class="[^"]*oddsPoint[^"]*"[^>]*>(.*?)</td>', html_3f, re.DOTALL)
        if odds_cells:
            # 3連複のHTML出現順に合わせた combos を生成
            rows_data = [
                [(1, 2, 3)],
                [(1, 2, 4)],
                [(1, 2, 5)],
                [(1, 2, 6)],
                [(1, 3, 4), (2, 3, 4)],
                [(1, 3, 5), (2, 3, 5)],
                [(1, 3, 6), (2, 3, 6)],
                [(1, 4, 5), (2, 4, 5), (3, 4, 5)],
                [(1, 4, 6), (2, 4, 6), (3, 4, 6)],
                [(1, 5, 6), (2, 5, 6), (3, 5, 6), (4, 5, 6)]
            ]
            combos_3f = []
            for row in rows_data:
                for combo in row:
                    combos_3f.append(list(combo))
                    
            for idx, cell in enumerate(odds_cells):
                if idx >= len(combos_3f):
                    break
                val_str = clean_html_tags(cell)
                val = safe_float(val_str, -1.0)
                if val > 0:
                    odds_3f.append({"combo": combos_3f[idx], "odds": val})
                    
    return {"odds3t": odds_3t, "odds3f": odds_3f}

# ---------------------------------------------------------------------------
# AI Prediction Logic (Plackett-Luce)
# ---------------------------------------------------------------------------
def calculate_predictions(racers, stadium_rates, weather, fan_db):
    """AI予想コア（Plackett-Luce確率モデル）"""
    scores = []
    base_lane_scores = {1: 95.0, 2: 52.0, 3: 46.0, 4: 38.0, 5: 28.0, 6: 20.0}
    
    stadium_in_win = 55.0
    stadium_by_course = {}
    if stadium_rates and "recent3" in stadium_rates:
        for r in stadium_rates["recent3"]:
            stadium_by_course[r["course"]] = r
        if 1 in stadium_by_course:
            stadium_in_win = stadium_by_course[1]["p1"]
            
    in_win_diff = stadium_in_win - 55.0
    base_lane_scores[1] += in_win_diff * 1.5
    base_lane_scores[2] -= in_win_diff * 0.2
    base_lane_scores[3] -= in_win_diff * 0.3
    base_lane_scores[4] -= in_win_diff * 0.3
    base_lane_scores[5] -= in_win_diff * 0.3
    base_lane_scores[6] -= in_win_diff * 0.4
    
    for c in range(1, 7):
        if c in stadium_by_course:
            base_lane_scores[c] = base_lane_scores[c] * 0.4 + stadium_by_course[c]["p1"] * 1.2

    exhibits = [r["exhibit"] for r in racers if r.get("exhibit") is not None]
    avg_exhibit = sum(exhibits) / len(exhibits) if len(exhibits) > 0 else 6.80

    for racer in racers:
        num = racer["num"]
        toban = racer["toban"]
        
        # ファン手帳からマージ
        fan_info = fan_db.get(toban, {})
        racer_class = fan_info.get("class", racer["racerClass"])
        win_rate = fan_info.get("winRate", racer["winRate"])
        double_rate = fan_info.get("doubleRate", racer["doubleRate"])
        avg_st = fan_info.get("avgST", racer["avgST"])
        local_win_rate = fan_info.get("localWinRate", racer["localWinRate"])
        local_double_rate = fan_info.get("localDoubleRate", racer.get("localDoubleRate", 30.0))
        
        # F/Lのマージ（出走表のリアルタイム情報を優先）
        flying = racer.get("flying", fan_info.get("flying", 0))
        late = racer.get("late", fan_info.get("late", 0))
        
        score = base_lane_scores.get(num, 20.0)
        score += (win_rate - 5.5) * 15.0
        score += (local_win_rate - 5.5) * 4.0
        
        class_bonuses = {"A1": 25.0, "A2": 12.0, "B1": 3.0, "B2": -5.0}
        score += class_bonuses.get(racer_class, 0.0)
        
        score += (racer["motorRate"] - 35.0) * 0.8
        score += (racer["boatRate"] - 35.0) * 0.3
        
        st_diff = 0.16 - avg_st
        score += st_diff * 180.0
        
        exhibit_val = racer.get("exhibit", 6.80)
        ex_diff = avg_exhibit - exhibit_val
        score += ex_diff * 250.0
        
        # フライング・出遅れ補正
        if flying > 0:
            score -= flying * 15.0 # F1なら-15, F2なら-30
        if late > 0:
            score -= late * 10.0
        
        # 気象影響
        wind_dir = weather.get("windDir", "tailwind")
        wind_speed = weather.get("windSpeed", 2)
        wave = weather.get("wave", 2)
        
        if wind_dir == "tailwind":
            if wind_speed <= 3:
                if num == 1: score += 12.0
                if num == 2: score += 4.0
            else:
                if num == 1: score -= 8.0
                if num == 2: score += 12.0
                if num == 3: score += 8.0
        elif wind_dir == "headwind":
            if wind_speed >= 4:
                if num == 1: score -= 15.0
                if num == 3: score += 6.0
                if num == 4: score += 18.0
                if num == 5: score += 10.0
            else:
                if num == 3: score += 6.0
                if num == 4: score += 8.0
        elif wind_dir == "cross":
            if num == 1: score -= 5.0
            if num >= 3: score += 3.0
            
        if wave >= 5:
            wave_scale = wave * 0.8
            if num == 1: score -= wave_scale
            if racer_class == "A1": score += wave_scale * 0.8
            if racer_class == "B2": score -= wave_scale * 1.2
            
        scores.append({
            "num": num,
            "name": racer["name"],
            "racerClass": racer_class,
            "winRate": win_rate,
            "doubleRate": double_rate,
            "localWinRate": local_win_rate,
            "localDoubleRate": local_double_rate,
            "avgST": avg_st,
            "exhibit": exhibit_val,
            "motorRate": racer["motorRate"],
            "boatRate": racer["boatRate"],
            "flying": flying,
            "late": late,
            "score": max(5.0, score),
            "isMerged": toban in fan_db
        })
        
    N = len(scores)
    alpha = 2.8
    power_scores = [r["score"] ** alpha for r in scores]
    total_power = sum(power_scores)
    if total_power <= 0:
        total_power = 1.0
    
    p1 = [ps / total_power for ps in power_scores]
    p2 = [0.0] * N
    p3 = [0.0] * N
    combos = []
    
    if N >= 3:
        for i in range(N):
            prob1 = p1[i]
            rem_power1 = total_power - power_scores[i]
            if rem_power1 <= 0: continue
            
            for j in range(N):
                if i == j: continue
                prob2_given_1 = power_scores[j] / rem_power1
                prob12 = prob1 * prob2_given_1
                p2[j] += prob12
                rem_power2 = rem_power1 - power_scores[j]
                if rem_power2 <= 0: continue
                
                for k in range(N):
                    if k == i or k == j: continue
                    prob3_given_12 = power_scores[k] / rem_power2
                    prob123 = prob12 * prob3_given_12
                    p3[k] += prob123
                    combos.append({
                        "combo": [scores[i]["num"], scores[j]["num"], scores[k]["num"]],
                        "prob": prob123
                    })
                    
    racers_prob = []
    for idx, r in enumerate(scores):
        racers_prob.append({
            "num": r["num"],
            "name": r["name"],
            "racerClass": r["racerClass"],
            "winRate": r["winRate"],
            "doubleRate": r["doubleRate"],
            "localWinRate": r["localWinRate"],
            "localDoubleRate": r["localDoubleRate"],
            "avgST": r["avgST"],
            "exhibit": r["exhibit"],
            "motorRate": r["motorRate"],
            "boatRate": r["boatRate"],
            "flying": r["flying"],
            "late": r["late"],
            "score": r["score"],
            "isMerged": r["isMerged"],
            "p1": p1[idx] * 100.0,
            "p2": p2[idx] * 100.0,
            "p3": p3[idx] * 100.0
        })
        
    combos.sort(key=lambda x: x["prob"], reverse=True)
    return {"racers": racers_prob, "combos": combos}

# ---------------------------------------------------------------------------
# Report Generator (Generates self-contained report.html)
# ---------------------------------------------------------------------------
def generate_report(data, output_path="report.html"):
    """
    データ構造を JSON に埋め込み、自己完結型の report.html を生成します。
    """
    template_path = "report_template.html"
    if not os.path.exists(template_path):
        print(f"[Generator] Error: テンプレートファイル '{template_path}' が見つかりません。")
        sys.exit(1)
        
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    # HTML中の `const DATA_PLACEHOLDER = null;` を実際のデータで置き換える
    data_json = json.dumps(data, ensure_ascii=False)
    html_content = html_content.replace("const DATA_PLACEHOLDER = null;", f"const DATA_PLACEHOLDER = {data_json};")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"[Generator] 結果レポートを生成しました: {output_path}")

def run_prediction_flow(jcd_input, rno_input, total_budget, hd):
    """
    指定されたレースのデータを取得・予測し、辞書形式で結果を返します。
    """
    jcd_input = str(jcd_input).zfill(2)
    stadium_name = STADIUM_MAP.get(jcd_input)
    if not stadium_name:
        raise ValueError(f"無効な開催場コードです: {jcd_input}")
        
    if not (1 <= rno_input <= 12):
        raise ValueError(f"無効なレース番号です: {rno_input}")
        
    print(f"\n📡 データを取得中: {stadium_name} {rno_input}R (日付: {hd})...")
    
    racelist_url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno_input}&jcd={jcd_input}&hd={hd}"
    beforeinfo_url = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={rno_input}&jcd={jcd_input}&hd={hd}"
    odds3t_url = f"https://www.boatrace.jp/owpc/pc/race/odds3t?rno={rno_input}&jcd={jcd_input}&hd={hd}"
    odds3f_url = f"https://www.boatrace.jp/owpc/pc/race/odds3f?rno={rno_input}&jcd={jcd_input}&hd={hd}"
    stadium_url = f"https://www.boatrace.jp/owpc/pc/data/stadium?jcd={jcd_input}"
    
    # スクレイピング実行
    print("- 出走表データを取得中...")
    racelist_html = fetch_html(racelist_url)
    print("- 直前情報を取得中...")
    before_html = fetch_html(beforeinfo_url)
    print("- 3連単オッズを取得中...")
    odds3t_html = fetch_html(odds3t_url)
    print("- 3連複オッズを取得中...")
    odds3f_html = fetch_html(odds3f_url)
    print("- コース別入着率を取得中...")
    stadium_html = fetch_html(stadium_url)
    
    # パース処理
    race_info = parse_racelist(racelist_html)
    ex_info = parse_beforeinfo(before_html)
    odds_info = parse_odds_3t_3f(odds3t_html, odds3f_html)
    stadium_rates = parse_stadium_rates(stadium_html)
    
    # 展示タイム・チルトのマージ
    for r in race_info["racers"]:
        num = r["num"]
        ex_data = ex_info["exhibitions"].get(num, {"exhibit": 6.80, "tilt": -0.5})
        r["exhibit"] = ex_data["exhibit"]
        r["tilt"] = ex_data["tilt"]
        
    print("✅ データの取得とパースが完了しました。")
    
    # ファン手帳の読み込み
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    fan_db = load_fan_data(data_dir=data_dir)
    
    # AI予想計算
    print("🧠 AI予想確率を計算中...")
    prediction = calculate_predictions(race_info["racers"], stadium_rates, ex_info["weather"], fan_db)
    
    # 結果データJSONのビルド
    data = {
        "stadiumId": jcd_input,
        "stadiumName": stadium_name,
        "raceNum": rno_input,
        "date": hd,
        "raceTitle": race_info["title"],
        "weather": ex_info["weather"],
        "stadiumRates": stadium_rates,
        "prediction": prediction,
        "odds": odds_info,
        "totalInvestment": total_budget,
        "fanHandBookCount": len(fan_db)
    }
    return data

# ---------------------------------------------------------------------------
# Main Routine (Interactive CLI)
# ---------------------------------------------------------------------------
def main():
    print("==================================================")
    print("🚤 AI競艇予想＆資金配分シミュレータ (サーバー不要) 🚤")
    print("==================================================")
    
    jcd_input = ""
    rno_input = 12
    total_budget = 3000
    hd = datetime.now().strftime("%Y%m%d")
    
    # 引数が渡されている場合は、対話プロンプトをスキップして直接実行
    if len(sys.argv) >= 3:
        jcd_input = sys.argv[1].zfill(2)
        if jcd_input not in STADIUM_MAP:
            print(f"❌ エラー: 無効な開催場コードです: {jcd_input}")
            sys.exit(1)
        
        try:
            rno_input = int(sys.argv[2])
            if not (1 <= rno_input <= 12):
                raise ValueError()
        except ValueError:
            print(f"❌ エラー: 無効なレース番号です (1〜12を入力): {sys.argv[2]}")
            sys.exit(1)
            
        if len(sys.argv) >= 4:
            try:
                total_budget = int(sys.argv[3])
                if total_budget < 100:
                    raise ValueError()
            except ValueError:
                print(f"❌ エラー: 総賭け金は100円以上の数値を指定してください: {sys.argv[3]}")
                sys.exit(1)
        
        if len(sys.argv) >= 5:
            val_hd = sys.argv[4].strip()
            if len(val_hd) == 8 and val_hd.isdigit():
                hd = val_hd
            else:
                print(f"❌ エラー: 日付はYYYYMMDD形式で指定してください: {sys.argv[4]}")
                sys.exit(1)
                
        print(f"💡 コマンドライン引数を検出しました: 開催場={STADIUM_MAP[jcd_input]}({jcd_input}), レース={rno_input}R, 予算={total_budget}円, 日付={hd}")
    else:
        # 1. 開催場の選択
        print("\n【1】レース開催場を選択してください（番号で入力）:")
        sorted_jcds = sorted(STADIUM_MAP.keys())
        for i, jcd in enumerate(sorted_jcds, 1):
            name = STADIUM_MAP[jcd]
            print(f"{jcd}:{name}".ljust(10), end="\n" if i % 6 == 0 else "")
        print()
        
        while True:
            val = input("開催場コード (例 01 または 12): ").strip()
            val_pad = val.zfill(2)
            if val_pad in STADIUM_MAP:
                jcd_input = val_pad
                break
            print("❌ 無効な場コードです。もう一度入力してください。")
            
        # 2. レース番号の選択
        print("\n【2】レース番号を入力してください (1〜12):")
        while True:
            val = input("レース番号 (例 12): ").strip()
            if val.isdigit() and 1 <= int(val) <= 12:
                rno_input = int(val)
                break
            print("❌ 1から12の数値を入力してください。")
            
        # 3. 総賭け金の設定
        print("\n【3】総賭け金を設定してください（円単位、100円〜）:")
        while True:
            val = input("総掛け金 (デフォルト 3000): ").strip()
            if not val:
                break
            if val.isdigit() and int(val) >= 100:
                total_budget = int(val)
                break
            print("❌ 100以上の数値を入力してください。")
            
        # 4. 対象日の設定
        print("\n【4】対象日を設定してください（YYYYMMDD形式、Enterで今日）:")
        while True:
            val = input(f"対象日 (デフォルト {hd}): ").strip()
            if not val:
                break
            if val.isdigit() and len(val) == 8:
                hd = val
                break
            print("❌ YYYYMMDD形式（8桁の数字）を入力してください。")
        
    try:
        data_to_save = run_prediction_flow(jcd_input, rno_input, total_budget, hd)
        
        # 9. HTMLの書き出しと起動
        generate_report(data_to_save)
        
        webbrowser.open("report.html")
        print("\n🎉 ブラウザで予想レポートを開きました。")
        print("report.html をダブルクリックしていつでも結果を再確認できます。")
        
    except Exception as e:
        import traceback
        print("\n❌ 処理中にエラーが発生しました。")
        traceback.print_exc()

if __name__ == "__main__":
    main()
