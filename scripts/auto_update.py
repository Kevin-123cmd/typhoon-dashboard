# -*- coding: utf-8 -*-
"""
台风数据自动更新入口（纯本地脚本方案，由 Windows 计划任务定时调用）

- 由 Windows 任务计划程序每天调用（计划任务里配 08:30 / 12:30）
- 运行 scripts/fetch_typhoon.py 抓取最新数据
- 把退出码、抓取输出、结果摘要写入 logs/fetch.log，供事后查看

用法：
    pythonw scripts/auto_update.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FETCH = os.path.join(BASE_DIR, "scripts", "fetch_typhoon.py")
DATA = os.path.join(BASE_DIR, "data", "typhoon.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "fetch.log")


def log(msg):
    line = "%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print("日志写入失败：%s" % e, file=sys.stderr)
    print(line)


def summarize():
    """从最新 typhoon.json 提炼一行摘要，便于日志快速浏览。"""
    try:
        with open(DATA, encoding="utf-8") as f:
            j = json.load(f)
    except Exception as e:
        return "  摘要解析失败：%s" % e

    parts = [
        "updateTime=%s" % j.get("updateTime"),
        "yearCount=%d" % j.get("yearCount", 0),
        "activeCount=%d" % j.get("activeCount", 0),
    ]
    rows = []
    for t in j.get("typhoons", []):
        latest = t.get("latest") or {}
        rows.append("%s %s(%s) active=%s %s %sm/s %shPa" % (
            t.get("num"),
            t.get("cnName"),
            t.get("enName"),
            t.get("active"),
            latest.get("strengthName", ""),
            latest.get("wind", ""),
            latest.get("pressure", ""),
        ))
    return "  抓取到 %d 个台风：%s" % (len(rows), "；".join(rows))


def main():
    log("===== 台风数据自动更新开始 =====")
    try:
        # 子进程在 Windows 管道下默认用 GBK 输出，强制 UTF-8 保证日志不乱码
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, FETCH],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=env,
        )
        log("退出码=%d" % result.returncode)
        for line in (result.stdout or "").splitlines():
            log("  [out] " + line)
        for line in (result.stderr or "").splitlines():
            log("  [err] " + line)
        log(summarize())
    except Exception as e:
        log("执行失败：%s" % e)
    log("===== 结束 =====\n")


if __name__ == "__main__":
    main()
