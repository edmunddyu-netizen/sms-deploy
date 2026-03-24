import os
import json
import time
import random
import subprocess
import sys
from datetime import datetime

BASE_DIR = "/storage/emulated/0/sms_tool"

NUMBER_FILE = os.path.join(BASE_DIR, "number.txt")
CONTENT1_FILE = os.path.join(BASE_DIR, "guanggao.txt")
SENT_NUMBER_FILE = os.path.join(BASE_DIR, "sent number.txt")

CONTENT2_FILE = os.path.join(BASE_DIR, "yzp huashu.txt")
YZP_INFO_FILE = os.path.join(BASE_DIR, "yzp info.txt")
YZP_QUEUE_FILE = os.path.join(BASE_DIR, "yzp queue.txt")

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "logs.json")

DEFAULT_CONFIG = {
    "send_mode_round1": "rotate",         # sim1 / sim2 / rotate
    "send_mode_round2": "inherit",        # sim1 / sim2 / inherit / rotate
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
        YZP_QUEUE_FILE,
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


def load_round2_queue():
    if not os.path.exists(YZP_QUEUE_FILE):
        return []

    result = []
    with open(YZP_QUEUE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            name = parts[0].strip()
            phone = normalize_phone(parts[1].strip())
            slot_raw = parts[2].strip()
            if not name or not phone:
                continue
            try:
                slot = int(slot_raw)
            except Exception:
                continue
            result.append({
                "name": name,
                "phone": phone,
                "slot": slot
            })
    return result


def save_round2_queue(items):
    with open(YZP_QUEUE_FILE, "w", encoding="utf-8") as f:
        for item in items:
            name = item.get("name", "").strip()
            phone = normalize_phone(item.get("phone", ""))
            slot = item.get("slot")
            if not name or not phone or slot is None:
                continue
            f.write(f"{name}\t{phone}\t{slot}\n")


def generate_round2_queue():
    cfg = load_config()
    prefix = cfg.get("contact_prefix", "YZP_")

    contacts, err = load_prefixed_contacts(prefix)
    if contacts is None:
        print("读取联系人失败：", err)
        return

    if not contacts:
        print(f"未找到名称包含前缀 {prefix} 的联系人")
        return

    queue_items = []
    for idx, item in enumerate(contacts):
        phone = item["phone"]
        slot = pick_slot_for_round2(idx, phone, cfg)
        queue_items.append({
            "name": item["name"],
            "phone": phone,
            "slot": slot
        })

    save_round2_queue(queue_items)

    print(f"已生成第二轮队列：{YZP_QUEUE_FILE}")
    print(f"队列数量：{len(queue_items)}")
    print("格式：联系人名称\t号码\t继承卡槽")


def show_status():
    cfg = load_config()
    n1 = load_numbers_txt(NUMBER_FILE)
    sent = load_numbers_txt(SENT_NUMBER_FILE)
    content1 = read_text(CONTENT1_FILE)
    content2 = read_text(CONTENT2_FILE)
    round2_queue = load_round2_queue()
    logs = load_logs()

    print("\n===== 当前状态 =====")
    print("共享目录：", BASE_DIR)
    print("号码合集1剩余数量：", len(n1))
    print("已发送成功数量：", len(sent))
    print("第二轮队列剩余数量：", len(round2_queue))
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


def send_batch_round1():
    cfg = load_config()
    errors = validate_runtime_config(cfg)
    if errors:
        print("\n运行前检查未通过：")
        for e in errors:
            print("-", e)
        return

    text = read_text(CONTENT1_FILE)
    remaining_numbers = load_numbers_txt(NUMBER_FILE)
    sent_set = set(load_numbers_txt(SENT_NUMBER_FILE))

    confirmed = confirm_before_round(
        "第一轮发送确认",
        "guanggao.txt",
        text,
        [
            f"号码剩余数量: {len(remaining_numbers)}",
            f"已发送成功数量: {len(sent_set)}",
            f"发送模式: {cfg['send_mode_round1']}",
            f"SIM1区间: {cfg['sim1_min_interval']}-{cfg['sim1_max_interval']} 秒",
            f"SIM2区间: {cfg['sim2_min_interval']}-{cfg['sim2_max_interval']} 秒",
            "如内容不对，请先退出并修改 guanggao.txt"
        ]
    )
    if not confirmed:
        print("已取消发送")
        return

    total_at_start = len(remaining_numbers)
    success = 0
    fail = 0
    skipped = 0

    if cfg["send_mode_round1"] == "sim1":
        active_slots = [cfg["sim1_slot"]]
    elif cfg["send_mode_round1"] == "sim2":
        active_slots = [cfg["sim2_slot"]]
    else:
        active_slots = [cfg["sim1_slot"], cfg["sim2_slot"]]

    now_ts = time.time()
    next_ready = {}

    if len(active_slots) == 1:
        next_ready[active_slots[0]] = now_ts
    else:
        sim1 = cfg["sim1_slot"]
        sim2 = cfg["sim2_slot"]
        if sim1 in active_slots:
            next_ready[sim1] = now_ts
        if sim2 in active_slots:
            next_ready[sim2] = now_ts + 5

    status_dirty_slots = set()

    print(f"\n开始第一轮发送，共 {total_at_start} 个号码")
    print("规则：发送成功一条，就从 number.txt 删除一条，并写入 sent number.txt")
    print("规则：如果号码已存在于 sent number.txt，会直接跳过不再发送")
    print("模式：双卡独立计时，谁先到时间谁先发")
    print("按 Ctrl + C 可手动停止，未成功发送的号码会保留。")

    try:
        while True:
            current_numbers = load_numbers_txt(NUMBER_FILE)
            if not current_numbers:
                break

            now_ts = time.time()
            ready_slots = [slot for slot in active_slots if now_ts >= next_ready[slot]]

            if not ready_slots:
                nearest = min(next_ready.values())
                sleep_for = max(0.0, nearest - now_ts)
                time.sleep(min(sleep_for, 0.5))
                continue

            ready_slots.sort(key=lambda s: (next_ready[s], s))
            slot = ready_slots[0]

            current_numbers = load_numbers_txt(NUMBER_FILE)
            if not current_numbers:
                break

            phone = current_numbers[0]

            if phone in sent_set:
                skipped += 1
                current_numbers.pop(0)
                save_numbers_txt(NUMBER_FILE, current_numbers)
                print_send_skip(slot, phone, cfg, "已存在于 sent number.txt", len(current_numbers))
                next_ready[slot] = time.time()
                status_dirty_slots.add(slot)
            else:
                print(f"准备发送 -> {get_slot_label(slot, cfg)} / {phone}", flush=True)
                ok, out, err = termux_send_sms(phone, text, slot)

                append_log({
                    "time": now_str(),
                    "round": 1,
                    "phone": phone,
                    "slot": slot,
                    "text": text,
                    "ok": ok,
                    "stdout": out,
                    "stderr": err
                })

                if ok:
                    success += 1
                    current_numbers = load_numbers_txt(NUMBER_FILE)
                    if current_numbers and current_numbers[0] == phone:
                        current_numbers.pop(0)
                    else:
                        current_numbers = [x for x in current_numbers if x != phone]
                    save_numbers_txt(NUMBER_FILE, current_numbers)

                    append_number_if_missing(SENT_NUMBER_FILE, phone)
                    sent_set.add(phone)

                    print_send_success(slot, phone, cfg, len(current_numbers))
                else:
                    fail += 1
                    print_send_fail(slot, phone, cfg, err or out, len(load_numbers_txt(NUMBER_FILE)))

                wait_sec = random_interval_for_slot(slot, cfg)
                next_ready[slot] = time.time() + wait_sec
                status_dirty_slots.add(slot)

            if len(active_slots) > 1 and all(s in status_dirty_slots for s in active_slots):
                print_compact_next_times(next_ready, cfg, active_slots)
                status_dirty_slots.clear()
            elif len(active_slots) == 1 and status_dirty_slots:
                print_compact_next_times(next_ready, cfg, active_slots)
                status_dirty_slots.clear()

    except KeyboardInterrupt:
        print("\n已手动停止第一轮发送")
        print(
            f"当前结果 -> 成功: {success} 失败: {fail} 跳过: {skipped} "
            f"剩余: {len(load_numbers_txt(NUMBER_FILE))} 已发送库: {len(load_numbers_txt(SENT_NUMBER_FILE))}"
        )
        return

    print(f"{now_str()}  本轮全部完成")
    print(
        f"总数: {total_at_start}  成功: {success} 失败: {fail} 跳过: {skipped} "
        f"剩余: {len(load_numbers_txt(NUMBER_FILE))}"
    )


def scan_replies_to_info():
    cfg = load_config()
    sent_numbers = set(load_numbers_txt(SENT_NUMBER_FILE))

    print(f"\n开始扫描收件箱，最多读取最近 {cfg['scan_inbox_limit']} 条短信...")

    sms_result = subprocess.run(
        ["termux-sms-list", "-t", "inbox", "-l", str(cfg["scan_inbox_limit"])],
        capture_output=True,
        text=True
    )
    if sms_result.returncode != 0:
        print("读取收件箱失败")
        if sms_result.stderr.strip():
            print("错误：", sms_result.stderr.strip())
        elif sms_result.stdout.strip():
            print("输出：", sms_result.stdout.strip())
        return

    try:
        sms_data = json.loads(sms_result.stdout)
    except Exception as e:
        print("短信JSON解析失败：", e)
        return

    contact_name_map, contact_err = build_contact_name_map()

    first_reply_map = {}
    for msg in sms_data:
        if not isinstance(msg, dict):
            continue

        phone = normalize_phone(msg.get("address", ""))
        if not phone or phone not in sent_numbers:
            continue

        if phone in first_reply_map:
            continue

        body = str(msg.get("body", "")).strip()
        raw_time = msg.get("received", msg.get("date", msg.get("timestamp", "")))
        reply_time = format_sms_time(raw_time)

        first_reply_map[phone] = {
            "reply_time": reply_time,
            "reply_text": body,
            "raw_time": raw_time
        }

    sent_slot_map = get_sent_slot_map()

    lines = []
    lines.append("===== yzp info =====")
    lines.append(f"生成时间: {now_str()}")
    lines.append("说明: 第二轮发送不读取这个文件，只给你查看。")
    lines.append("先扫描回复，再手动给联系人加前缀，然后单独生成第二轮队列。")
    lines.append("")

    count = 0
    sorted_items = sorted(
        first_reply_map.items(),
        key=lambda x: str(x[1].get("raw_time", "")),
        reverse=True
    )

    for phone, info in sorted_items:
        count += 1
        slot = sent_slot_map.get(phone, "未知")
        contact_name = contact_name_map.get(phone, "未命名联系人")
        lines.append("========================================")
        lines.append(f"号码: {phone}")
        lines.append(f"联系人名称: {contact_name}")
        lines.append(f"回复时间: {info.get('reply_time', '未知')}")
        lines.append(f"第一条回复内容: {info.get('reply_text', '')}")
        lines.append(f"继承卡槽: {slot}")
        lines.append("========================================")
        lines.append("")

    if count == 0:
        lines.append("未发现来自 sent number.txt 的回复号码。")
        lines.append("")

    write_text(YZP_INFO_FILE, "\n".join(lines))

    print("扫描完成，已更新 yzp info.txt")
    print("识别到回复号码数量：", count)
    if contact_err:
        print("联系人名称读取未完全成功：", contact_err)


def generate_round2_queue_menu():
    cfg = load_config()
    prefix = cfg.get("contact_prefix", "YZP_")
    contacts, err = load_prefixed_contacts(prefix)

    if contacts is None:
        print("读取联系人失败：", err)
        return

    print("\n===== 生成第二轮队列确认 =====")
    print(f"联系人前缀: {prefix}")
    print(f"当前匹配联系人数量: {len(contacts)}")
    print(f"第二轮发送模式: {cfg['send_mode_round2']}")
    print("将生成 yzp queue.txt，后续第二轮发送只读取这个队列文件。")
    print("这样发送时会发一条删一条，避免卡死后重复发送。")
    print("")

    answer = input("确认生成第二轮队列吗？输入 1 开始，其它任意内容取消: ").strip()
    if answer != "1":
        print("已取消生成第二轮队列")
        return

    generate_round2_queue()


def send_batch_round2():
    cfg = load_config()
    errors = validate_runtime_config(cfg)
    if errors:
        print("\n运行前检查未通过：")
        for e in errors:
            print("-", e)
        return

    text = read_text(CONTENT2_FILE)
    queue_items = load_round2_queue()

    confirmed = confirm_before_round(
        "第二轮发送确认",
        "yzp huashu.txt",
        text,
        [
            f"第二轮队列数量: {len(queue_items)}",
            f"发送模式: 队列文件 yzp queue.txt",
            f"SIM1区间: {cfg['sim1_min_interval']}-{cfg['sim1_max_interval']} 秒",
            f"SIM2区间: {cfg['sim2_min_interval']}-{cfg['sim2_max_interval']} 秒",
            "规则：第二轮按 yzp queue.txt 发一条删一条，避免卡死后重复发送",
            "如内容不对，请先退出并修改 yzp huashu.txt"
        ]
    )
    if not confirmed:
        print("已取消发送")
        return

    if not queue_items:
        print("第二轮队列为空")
        print("请先执行：生成第二轮队列")
        return

    total = len(queue_items)
    success = 0
    fail = 0

    slot_queues = {
        cfg["sim1_slot"]: [],
        cfg["sim2_slot"]: []
    }

    for item in queue_items:
        slot = item["slot"]
        if slot not in slot_queues:
            slot_queues[slot] = []
        slot_queues[slot].append(item)

    active_slots = [slot for slot, q in slot_queues.items() if len(q) > 0]
    if not active_slots:
        print("没有可发送的联系人")
        return

    now_ts = time.time()
    next_ready = {}

    if len(active_slots) == 1:
        next_ready[active_slots[0]] = now_ts
    else:
        sim1 = cfg["sim1_slot"]
        sim2 = cfg["sim2_slot"]
        if sim1 in active_slots:
            next_ready[sim1] = now_ts
        if sim2 in active_slots:
            next_ready[sim2] = now_ts + 5

    status_dirty_slots = set()

    print(f"\n开始第二轮发送，共 {total} 个联系人号码")
    print("发送源：yzp queue.txt")
    print("规则：发送成功一条，就从 yzp queue.txt 删除一条")
    print("模式：双卡独立计时，谁先到时间谁先发")
    print("按 Ctrl + C 可手动停止。")

    try:
        while True:
            # 每轮都从文件重载，确保删除后的进度真实落盘
            current_queue = load_round2_queue()
            if not current_queue:
                break

            slot_queues = {}
            for item in current_queue:
                slot = item["slot"]
                slot_queues.setdefault(slot, []).append(item)

            current_active_slots = [slot for slot, q in slot_queues.items() if len(q) > 0]
            remaining_total = sum(len(slot_queues[s]) for s in current_active_slots)
            if remaining_total == 0:
                break

            for slot in current_active_slots:
                if slot not in next_ready:
                    next_ready[slot] = time.time()

            now_ts = time.time()
            ready_slots = [slot for slot in current_active_slots if now_ts >= next_ready[slot]]

            if not ready_slots:
                nearest = min(next_ready[s] for s in current_active_slots)
                sleep_for = max(0.0, nearest - now_ts)
                time.sleep(min(sleep_for, 0.5))
                continue

            ready_slots.sort(key=lambda s: (next_ready[s], s))

            for slot in ready_slots:
                current_queue = load_round2_queue()
                if not current_queue:
                    break

                current_slot_items = [x for x in current_queue if x["slot"] == slot]
                if not current_slot_items:
                    continue

                item = current_slot_items[0]
                name = item["name"]
                phone = item["phone"]

                print(f"准备发送 -> {get_slot_label(slot, cfg)} / {name} / {phone}", flush=True)
                ok, out, err_text = termux_send_sms(phone, text, slot)

                append_log({
                    "time": now_str(),
                    "round": 2,
                    "phone": phone,
                    "contact_name": name,
                    "slot": slot,
                    "text": text,
                    "ok": ok,
                    "stdout": out,
                    "stderr": err_text
                })

                if ok:
                    success += 1
                    # 成功才删这一条，避免重启重复发前面已经发过的
                    new_queue = []
                    removed = False
                    for q in current_queue:
                        if (not removed and
                            q["name"] == name and
                            q["phone"] == phone and
                            q["slot"] == slot):
                            removed = True
                            continue
                        new_queue.append(q)
                    save_round2_queue(new_queue)
                    print_send_success(slot, phone, cfg, len(new_queue), name)
                else:
                    fail += 1
                    # 失败不删，留在队列里，后续可重试
                    print_send_fail(slot, phone, cfg, err_text or out, len(current_queue), name)

                wait_sec = random_interval_for_slot(slot, cfg)
                next_ready[slot] = time.time() + wait_sec
                status_dirty_slots.add(slot)

            current_queue = load_round2_queue()
            current_slots_after = sorted(list(set(item["slot"] for item in current_queue)))

            if len(current_slots_after) > 1 and all(slot in status_dirty_slots for slot in current_slots_after):
                print_compact_next_times(next_ready, cfg, current_slots_after)
                for slot in current_slots_after:
                    status_dirty_slots.discard(slot)
            elif len(current_slots_after) == 1 and current_slots_after[0] in status_dirty_slots:
                print_compact_next_times(next_ready, cfg, current_slots_after)
                status_dirty_slots.discard(current_slots_after[0])

    except KeyboardInterrupt:
        remaining_total = len(load_round2_queue())
        print("\n已手动停止第二轮发送")
        print(
            f"当前结果 -> 成功: {success} 失败: {fail} "
            f"队列剩余: {remaining_total}"
        )
        return

    print(f"{now_str()}  本轮全部完成")
    print(f"总数: {total}  成功: {success} 失败: {fail} 队列剩余: {len(load_round2_queue())}")


def show_recent_logs():
    logs = load_logs()
    if not logs:
        print("暂无日志")
        return

    print("\n===== 最近30条日志 =====")
    for item in logs[-30:]:
        status = "成功" if item.get("ok") else "失败"
        round_no = item.get("round")
        phone = item.get("phone", "")
        slot = item.get("slot", "")
        name = item.get("contact_name", "")
        if name:
            print(f"{item.get('time')} | R{round_no} | {name} | {phone} | slot={slot} | {status}")
        else:
            print(f"{item.get('time')} | R{round_no} | {phone} | slot={slot} | {status}")
    print("=======================")


def show_file_locations():
    print("\n===== 文件位置 =====")
    print("共享目录：", BASE_DIR)
    print("号码合集1：", NUMBER_FILE)
    print("内容1：", CONTENT1_FILE)
    print("已发送：", SENT_NUMBER_FILE)
    print("内容2：", CONTENT2_FILE)
    print("回复详情：", YZP_INFO_FILE)
    print("第二轮队列：", YZP_QUEUE_FILE)
    print("配置文件：", CONFIG_FILE)
    print("发送日志：", LOG_FILE)
    print("====================")


def show_help():
    print("\n===== 菜单使用说明 =====")
    print("一、第一轮发送前")
    print("1. 到手机文件管理器里打开 /storage/emulated/0/sms_tool")
    print("2. 手动编辑 number.txt，放入号码，一行一个")
    print("3. 手动编辑 guanggao.txt，写入第一轮内容")
    print("4. 如需修改模式、卡槽、随机区间、联系人前缀，进入配置菜单设置")
    print("5. 回主菜单执行“第一轮发送”")
    print("")
    print("二、第一轮发送规则")
    print("1. 发送成功一条，就会从 number.txt 删除一条")
    print("2. 同时会写入 sent number.txt")
    print("3. 如果发送失败，该号码会保留在 number.txt")
    print("4. 如果号码已存在于 sent number.txt，会被直接跳过，不再发送内容1")
    print("5. 双卡模式下，两张卡独立计时，谁先到时间谁先发")
    print("")
    print("三、扫描回复")
    print("1. 第一轮完成后，执行“扫描回复”")
    print("2. 程序会生成 yzp info.txt")
    print("3. 你根据 yzp info.txt，去联系人里手动加前缀")
    print("")
    print("四、生成第二轮队列")
    print("1. 执行“生成第二轮队列”")
    print("2. 程序会扫描符合前缀的联系人")
    print("3. 生成 yzp queue.txt")
    print("4. 后续第二轮发送只认这个队列文件")
    print("")
    print("五、第二轮发送规则")
    print("1. 第二轮读取 yzp queue.txt")
    print("2. 发送成功一条，就从 yzp queue.txt 删除一条")
    print("3. 如果中途卡死，重新启动时会从剩余队列继续")
    print("4. 这样可以避免重复给前面已发送联系人再发一次")
    print("")
    print("六、快捷命令")
    print("sd      = 打开菜单")
    print("123.sh  = 直接执行第一轮")
    print("yzp.sh  = 直接执行第二轮")
    print("========================")


def main_menu():
    ensure_files()

    while True:
        print("\n========== 短信工具 ==========")
        print("1. 查看当前状态")
        print("2. 执行第一轮发送")
        print("3. 扫描回复 -> 生成 yzp info.txt")
        print("4. 生成第二轮队列（按联系人前缀）")
        print("5. 执行第二轮发送（按 yzp queue.txt）")
        print("6. 配置模式 / 卡槽 / 随机区间 / 前缀")
        print("7. 查看最近日志")
        print("8. 查看文件位置")
        print("9. 菜单使用说明")
        print("10. 退出")
        print("================================")

        choice = input("请选择：").strip()

        if choice == "1":
            show_status()
            pause()
        elif choice == "2":
            send_batch_round1()
            pause()
        elif choice == "3":
            scan_replies_to_info()
            pause()
        elif choice == "4":
            generate_round2_queue_menu()
            pause()
        elif choice == "5":
            send_batch_round2()
            pause()
        elif choice == "6":
            config_menu()
        elif choice == "7":
            show_recent_logs()
            pause()
        elif choice == "8":
            show_file_locations()
            pause()
        elif choice == "9":
            show_help()
            pause()
        elif choice == "10":
            print("已退出")
            break
        else:
            print("无效选择")


def run_mode_round1():
    ensure_files()
    send_batch_round1()


def run_mode_round2():
    ensure_files()
    send_batch_round2()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower()
        if arg == "round1":
            run_mode_round1()
        elif arg == "round2":
            run_mode_round2()
        else:
            main_menu()
    else:
        main_menu()
