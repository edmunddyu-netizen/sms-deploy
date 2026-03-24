import os
import json
import time
import random
import subprocess
from datetime import datetime

BASE_DIR = "/storage/emulated/0/sms_tool"

NUMBER_FILE = os.path.join(BASE_DIR, "number.txt")
CONTENT1_FILE = os.path.join(BASE_DIR, "guanggao.txt")
SENT_NUMBER_FILE = os.path.join(BASE_DIR, "sent number.txt")
CONTENT2_FILE = os.path.join(BASE_DIR, "yzp huashu.txt")
YZP_INFO_FILE = os.path.join(BASE_DIR, "yzp info.txt")

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "logs.json")

DEFAULT_CONFIG = {
    "send_mode_round1": "rotate",  # sim1 / sim2 / rotate
    "send_mode_round2": "inherit",  # sim1 / sim2 / inherit / rotate
    "sim1_slot": 0,
    "sim2_slot": 1,
    "sim1_min_interval": 1200,
    "sim1_max_interval": 1500,
    "sim2_min_interval": 1200,
    "sim2_max_interval": 1500,
    "scan_inbox_limit": 500,
    "contact_prefix": "YZP_"
}

SMS_SEND_TIMEOUT = 45
SMS_SEND_RETRY_COUNT = 1
SMS_SEND_RETRY_DELAY = 2


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def short_time_str():
    return datetime.now().strftime("%d %H:%M:%S")


def pause():
    input("\n按回车继续...")


def ensure_files():
    os.makedirs(BASE_DIR, exist_ok=True)

    files_to_init = [
        NUMBER_FILE,
        CONTENT1_FILE,
        SENT_NUMBER_FILE,
        CONTENT2_FILE,
        YZP_INFO_FILE,
    ]
    for path in files_to_init:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("")

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)

    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config():
    cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
    for k, v in DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = v
    return cfg


def save_config(cfg):
    save_json(CONFIG_FILE, cfg)


def load_logs():
    return load_json(LOG_FILE, [])


def append_log(item):
    logs = load_logs()
    logs.append(item)
    save_json(LOG_FILE, logs)


def normalize_phone(phone):
    if phone is None:
        return ""
    s = str(phone).strip()
    for ch in [" ", "-", "(", ")", "\t", "\n", "\r"]:
        s = s.replace(ch, "")
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) > 11:
        s = s[2:]
    return s


def load_numbers_txt(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = [x.strip() for x in f.readlines() if x.strip()]
    result = []
    seen = set()
    for x in raw:
        n = normalize_phone(x)
        if n and n not in seen:
            seen.add(n)
            result.append(n)
    return result


def save_numbers_txt(path, numbers):
    seen = set()
    clean = []
    for n in numbers:
        n = normalize_phone(n)
        if n and n not in seen:
            seen.add(n)
            clean.append(n)
    with open(path, "w", encoding="utf-8") as f:
        for n in clean:
            f.write(n + "\n")


def append_number_if_missing(path, phone):
    numbers = load_numbers_txt(path)
    phone = normalize_phone(phone)
    if phone and phone not in numbers:
        numbers.append(phone)
        save_numbers_txt(path, numbers)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def format_sms_time(value):
    if value is None or value == "":
        return "未知"
    try:
        s = str(value).strip()
        if s.isdigit():
            num = int(s)
            if num > 10**12:
                dt = datetime.fromtimestamp(num / 1000)
            elif num > 10**9:
                dt = datetime.fromtimestamp(num)
            else:
                return s
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return s
    except Exception:
        return str(value)


def termux_send_sms(phone, text, slot):
    cmd = ["termux-sms-send", "-n", phone, "-s", str(slot), text]
    last_out = ""
    last_err = ""

    for attempt in range(SMS_SEND_RETRY_COUNT + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SMS_SEND_TIMEOUT
            )
            ok = result.returncode == 0
            return ok, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            last_err = f"发送超时（>{SMS_SEND_TIMEOUT}秒）"
            last_out = ""
        except Exception as e:
            last_err = f"发送异常: {e}"
            last_out = ""

        if attempt < SMS_SEND_RETRY_COUNT:
            time.sleep(SMS_SEND_RETRY_DELAY)

    return False, last_out, last_err


def get_slot_label(slot, cfg):
    if slot == cfg["sim1_slot"]:
        return "SIM1"
    if slot == cfg["sim2_slot"]:
        return "SIM2"
    return f"SLOT{slot}"


def get_interval_range_for_slot(slot, cfg):
    if slot == cfg["sim1_slot"]:
        return cfg["sim1_min_interval"], cfg["sim1_max_interval"]
    if slot == cfg["sim2_slot"]:
        return cfg["sim2_min_interval"], cfg["sim2_max_interval"]
    return cfg["sim1_min_interval"], cfg["sim1_max_interval"]


def random_interval_for_slot(slot, cfg):
    min_sec, max_sec = get_interval_range_for_slot(slot, cfg)
    return random.randint(min_sec, max_sec)


def format_next_time(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def print_send_success(slot, phone, cfg, remaining_count, contact_name=""):
    sim_label = get_slot_label(slot, cfg)
    if contact_name:
        print(f"({sim_label})-{short_time_str()}  已发送: {contact_name} / {phone}  剩余: {remaining_count}", flush=True)
    else:
        print(f"({sim_label})-{short_time_str()}  已发送: {phone}  剩余: {remaining_count}", flush=True)


def print_send_skip(slot, phone, cfg, reason, remaining_count):
    sim_label = get_slot_label(slot, cfg)
    print(f"({sim_label})-{short_time_str()}  已跳过: {phone}  原因: {reason}  剩余: {remaining_count}", flush=True)


def print_send_fail(slot, phone, cfg, reason, remaining_count, contact_name=""):
    sim_label = get_slot_label(slot, cfg)
    if contact_name:
        print(f"({sim_label})-{short_time_str()}  发送失败: {contact_name} / {phone}  剩余: {remaining_count}", flush=True)
    else:
        print(f"({sim_label})-{short_time_str()}  发送失败: {phone}  剩余: {remaining_count}", flush=True)
    if reason:
        print(f"原因: {reason}", flush=True)


def print_compact_next_times(next_ready, cfg, active_slots):
    parts = []
    if cfg["sim1_slot"] in active_slots:
        parts.append(f"SIM1: {format_next_time(next_ready[cfg['sim1_slot']])}")
    if cfg["sim2_slot"] in active_slots:
        parts.append(f"SIM2: {format_next_time(next_ready[cfg['sim2_slot']])}")
    if parts:
        print("下次时间 -> " + " | ".join(parts), flush=True)


def validate_runtime_config(cfg):
    errors = []

    if cfg["sim1_slot"] == cfg["sim2_slot"]:
        errors.append("SIM1 和 SIM2 的 slot 不能相同")

    if cfg["sim1_min_interval"] <= 0 or cfg["sim1_max_interval"] <= 0:
        errors.append("SIM1 间隔必须大于 0")
    if cfg["sim2_min_interval"] <= 0 or cfg["sim2_max_interval"] <= 0:
        errors.append("SIM2 间隔必须大于 0")

    if cfg["sim1_min_interval"] > cfg["sim1_max_interval"]:
        errors.append("SIM1 最小间隔不能大于最大间隔")
    if cfg["sim2_min_interval"] > cfg["sim2_max_interval"]:
        errors.append("SIM2 最小间隔不能大于最大间隔")

    if cfg["send_mode_round1"] not in ["sim1", "sim2", "rotate"]:
        errors.append("第一轮模式无效")
    if cfg["send_mode_round2"] not in ["sim1", "sim2", "inherit", "rotate"]:
        errors.append("第二轮模式无效")

    return errors


def confirm_before_round(title, content_file, content_text, extra_lines):
    print(f"\n===== {title} =====")
    print(f"当前发送文件: {content_file}")
    print("当前发送内容:\n")
    print(content_text if content_text else "(空内容)")
    print("")
    for line in extra_lines:
        print(line)
    print("")
    answer = input("确认开始发送吗？输入 1 开始，其它任意内容取消: ").strip()
    return answer == "1"


def get_sent_slot_map():
    logs = load_logs()
    result = {}
    for item in logs:
        if item.get("round") == 1 and item.get("ok") is True:
            phone = normalize_phone(item.get("phone", ""))
            if phone:
                result[phone] = item.get("slot")
    return result


def pick_slot_for_round2(item_index, phone, cfg):
    mode = cfg["send_mode_round2"]
    if mode == "sim1":
        return cfg["sim1_slot"]
    if mode == "sim2":
        return cfg["sim2_slot"]
    if mode == "rotate":
        return cfg["sim1_slot"] if item_index % 2 == 0 else cfg["sim2_slot"]

    sent_slot_map = get_sent_slot_map()
    return sent_slot_map.get(phone, cfg["sim1_slot"])


def extract_contact_name(contact):
    for key in ["name", "display_name", "nickname"]:
        val = contact.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def extract_contact_numbers(contact):
    result = []

    numbers = contact.get("numbers")
    if isinstance(numbers, list):
        for item in numbers:
            if isinstance(item, str):
                p = normalize_phone(item)
                if p:
                    result.append(p)
            elif isinstance(item, dict):
                for k in ["number", "phone", "value"]:
                    if k in item:
                        p = normalize_phone(item.get(k))
                        if p:
                            result.append(p)

    phone_numbers = contact.get("phoneNumbers")
    if isinstance(phone_numbers, list):
        for item in phone_numbers:
            if isinstance(item, str):
                p = normalize_phone(item)
                if p:
                    result.append(p)
            elif isinstance(item, dict):
                for k in ["number", "phone", "value"]:
                    if k in item:
                        p = normalize_phone(item.get(k))
                        if p:
                            result.append(p)

    for k, v in contact.items():
        if k.lower() in ["number", "phone", "mobile"]:
            p = normalize_phone(v)
            if p:
                result.append(p)

    clean = []
    seen = set()
    for x in result:
        if x and x not in seen:
            seen.add(x)
            clean.append(x)
    return clean


def load_contacts_raw():
    cmd = ["termux-contact-list"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()

    try:
        data = json.loads(result.stdout)
    except Exception as e:
        return None, f"联系人JSON解析失败: {e}"

    if not isinstance(data, list):
        return [], ""
    return data, ""


def build_contact_name_map():
    raw_contacts, err = load_contacts_raw()
    if raw_contacts is None:
        return {}, err

    contact_name_map = {}
    for item in raw_contacts:
        if not isinstance(item, dict):
            continue
        name = extract_contact_name(item)
        if not name:
            continue
        for phone in extract_contact_numbers(item):
            if phone and phone not in contact_name_map:
                contact_name_map[phone] = name
    return contact_name_map, ""


def load_prefixed_contacts(prefix):
    raw_contacts, err = load_contacts_raw()
    if raw_contacts is None:
        return None, err

    selected = []
    for item in raw_contacts:
        if not isinstance(item, dict):
            continue
        name = extract_contact_name(item)
        if prefix in name:
            numbers = extract_contact_numbers(item)
            for phone in numbers:
                selected.append({
                    "name": name,
                    "phone": phone
                })

    clean = []
    seen = set()
    for item in selected:
        key = (item["name"], item["phone"])
        if key not in seen:
            seen.add(key)
            clean.append(item)
    return clean, ""


def show_status():
    cfg = load_config()
    n1 = load_numbers_txt(NUMBER_FILE)
    sent = load_numbers_txt(SENT_NUMBER_FILE)
    content1 = read_text(CONTENT1_FILE)
    content2 = read_text(CONTENT2_FILE)
    logs = load_logs()

    print("\n===== 当前状态 =====")
    print("共享目录：", BASE_DIR)
    print("号码合集1剩余数量：", len(n1))
    print("已发送成功数量：", len(sent))
    print("内容1长度：", len(content1))
    print("内容2长度：", len(content2))
    print("第一轮模式：", cfg.get("send_mode_round1"))
    print("第二轮模式：", cfg.get("send_mode_round2"))
    print("联系人前缀：", cfg.get("contact_prefix"))
    print(
        "SIM1 slot：", cfg.get("sim1_slot"),
        "区间：", f"{cfg.get('sim1_min_interval')}-{cfg.get('sim1_max_interval')} 秒"
    )
    print(
        "SIM2 slot：", cfg.get("sim2_slot"),
        "区间：", f"{cfg.get('sim2_min_interval')}-{cfg.get('sim2_max_interval')} 秒"
    )
    print("扫描收件箱条数：", cfg.get("scan_inbox_limit"))
    print("日志总条数：", len(logs))
    print("====================")


def config_menu():
    while True:
        cfg = load_config()
        print("\n===== 配置菜单 =====")
        print("1. 设置第一轮模式（sim1 / sim2 / rotate）")
        print("2. 设置第二轮模式（sim1 / sim2 / inherit / rotate）")
        print("3. 设置SIM1对应slot")
        print("4. 设置SIM2对应slot")
        print("5. 设置SIM1最小发送间隔秒数")
        print("6. 设置SIM1最大发送间隔秒数")
        print("7. 设置SIM2最小发送间隔秒数")
        print("8. 设置SIM2最大发送间隔秒数")
        print("9. 设置扫描收件箱条数")
        print("10. 设置联系人前缀")
        print("11. 返回")

        choice = input("请选择：").strip()

        if choice == "1":
            val = input("请输入 sim1 / sim2 / rotate：").strip().lower()
            if val in ["sim1", "sim2", "rotate"]:
                cfg["send_mode_round1"] = val
                save_config(cfg)
                print("已保存")
            else:
                print("输入无效")
        elif choice == "2":
            val = input("请输入 sim1 / sim2 / inherit / rotate：").strip().lower()
            if val in ["sim1", "sim2", "inherit", "rotate"]:
                cfg["send_mode_round2"] = val
                save_config(cfg)
                print("已保存")
            else:
                print("输入无效")
        elif choice == "3":
            try:
                cfg["sim1_slot"] = int(input("请输入SIM1对应slot（一般0或1）：").strip())
                save_config(cfg)
                print("已保存")
            except Exception:
                print("输入无效")
        elif choice == "4":
            try:
                cfg["sim2_slot"] = int(input("请输入SIM2对应slot（一般0或1）：").strip())
                save_config(cfg)
                print("已保存")
            except Exception:
                print("输入无效")
        elif choice == "5":
            try:
                cfg["sim1_min_interval"] = int(input("请输入SIM1最小发送间隔秒数：").strip())
                save_config(cfg)
                print("已保存")
            except Exception:
                print("输入无效")
        elif choice == "6":
            try:
                cfg["sim1_max_interval"] = int(input("请输入SIM1最大发送间隔秒数：").strip())
                save_config(cfg)
                print("已保存")
            except Exception:
                print("输入无效")
        elif choice == "7":
            try:
                cfg["sim2_min_interval"] = int(input("请输入SIM2最小发送间隔秒数：").strip())
                save_config(cfg)
                print("已保存")
            except Exception:
                print("输入无效")
        elif choice == "8":
            try:
                cfg["sim2_max_interval"] = int(input("请输入SIM2最大发送间隔秒数：").strip())
                save_config(cfg)
                print("已保存")
            except Exception:
                print("输入无效")
        elif choice == "9":
            try:
                cfg["scan_inbox_limit"] = int(input("请输入扫描收件箱条数（如500）：").strip())
                save_config(cfg)
                print("已保存")
            except Exception:
                print("输入无效")
        elif choice == "10":
            val = input("请输入联系人前缀（如 YZP_）：").strip()
            if val:
                cfg["contact_prefix"] = val
                save_config(cfg)
                print("已保存")
            else:
                print("前缀不能为空")
        elif choice == "11":
            break
        else:
            print("无效选择")
