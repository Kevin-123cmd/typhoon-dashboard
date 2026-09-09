#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按省份 / 日期查询台风影响情况

用法：
    python scripts/query_region.py 福建                    # 查今天
    python scripts/query_region.py 福建 --date 2026-09-03  # 查指定日期
    python scripts/query_region.py 广东 --all              # 忽略日期，查全程
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_typhoon import load_geo, province_at, short_name  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "data", "typhoon.json")
CST = timezone(timedelta(hours=8))

# 七级风圈对应的距离阈值（km），用于"风圈是否影响该省"
CIRCLE_KM = {"30KTS": 17.2, "50KTS": 24.5, "64KTS": 32.7, "85KTS": 43.7}


def _dist_to_seg(px, py, ax, ay, bx, by):
    """点到线段最短距离（度）"""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def dist_to_province(lng, lat, name):
    """点到某省边界的最短距离（km）。点在省内返回 0。"""
    if province_at(lng, lat) == name:
        return 0.0
    best = None
    for shp in load_geo():
        if shp["name"] != name:
            continue
        for item in shp["rings"]:
            if lng < item["x0"] - 8 or lng > item["x1"] + 8 or \
               lat < item["y0"] - 8 or lat > item["y1"] + 8:
                continue
            r = item["ring"]
            for i in range(len(r) - 1):
                d = _dist_to_seg(lng, lat, r[i][0], r[i][1], r[i + 1][0], r[i + 1][1])
                if best is None or d < best:
                    best = d
    if best is None:
        return None
    return best * 111.32 * 0.85  # 度 -> km（取纬度余弦近似）


def max_circle_km(circles):
    """取最大风圈半径（km）"""
    mx = 0
    for c in circles or []:
        r = [x for x in c.get("radius", []) if x and x > 0]
        if r:
            mx = max(mx, max(r))
    return mx


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    if not args:
        print(__doc__)
        return 1

    target = args[0]
    # 支持输入"福建"、"福建省"等不同写法
    tname = target if not target.endswith(("省", "市")) else target[:-1]

    all_mode = "--all" in flags
    date = None
    if "--date" in flags:
        i = flags.index("--date")
        date = sys.argv[1:][sys.argv[1:].index("--date") + 1]
    if not all_mode and not date:
        date = datetime.now(CST).strftime("%Y-%m-%d")

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 62)
    print("  台风影响查询：%s%s" % (tname, "" if all_mode else "　日期 " + date))
    print("  数据更新：%s" % data["updateTime"])
    print("=" * 62)

    found = []
    for t in data["typhoons"]:
        pts = t["points"]
        if not all_mode and date:
            pts = [p for p in pts if p["time"].startswith(date)]
        if not pts:
            continue

        dists = []
        for p in pts:
            d = dist_to_province(p["lng"], p["lat"], tname)
            if d is not None:
                dists.append((d, p))
        if not dists:
            continue

        mind, mp = min(dists, key=lambda x: x[0])
        # 风圈是否可能覆盖该省
        cr = max_circle_km(mp.get("circles"))
        cover = mind <= cr if cr else False

        # 预报是否指向该省
        fc_hit = []
        for fc in t.get("forecast") or []:
            for fp in fc["points"]:
                if province_at(fp["lng"], fp["lat"]) == tname:
                    fc_hit.append(fp)

        if mind > 400 and not fc_hit:
            continue

        found.append({
            "t": t, "mind": mind, "mp": mp, "circle": cr,
            "cover": cover, "fc_hit": fc_hit, "npts": len(pts),
        })

    if not found:
        print("\n  该范围今日无台风活动记录。\n")
        # 提示最近的台风
        print("  参考：当前载入的台风")
        for t in data["typhoons"]:
            L = t["latest"]
            print("    %s %s（%s，%s）中心 %.1f°E %.1f°N，距%s约 %s km" % (
                t["num"], t["cnName"], L["strengthName"],
                "活跃" if t["active"] else "已停编",
                L["lng"], L["lat"], tname,
                "%.0f" % dist_to_province(L["lng"], L["lat"], tname)
                if dist_to_province(L["lng"], L["lat"], tname) is not None else "--"))
        return 0

    found.sort(key=lambda x: x["mind"])

    for f in found:
        t, mp, mind = f["t"], f["mp"], f["mind"]
        L = t["latest"]
        print("\n【%s %s / %s】%s" % (t["num"], t["cnName"], t["enName"],
                                   "活跃中" if t["active"] else "已停编"))
        print("  今日观测点：%d 个，时间 %s ~ %s" % (
            f["npts"],
            min(p["time"] for p in t["points"] if (all_mode or p["time"].startswith(date))),
            max(p["time"] for p in t["points"] if (all_mode or p["time"].startswith(date)))))
        print("  最近时刻：%s" % mp["time"])
        print("  当时强度：%s　风速 %s m/s　气压 %s hPa" % (
            mp["strengthName"], mp["wind"], mp["pressure"]))
        print("  当时位置：%.1f°E  %.1f°N" % (mp["lng"], mp["lat"]))
        print("  距%s边界：约 %.0f km" % (tname, mind))
        if f["circle"]:
            print("  七级风圈半径：%.0f km → %s" % (
                f["circle"], "可能覆盖%s" % tname if f["cover"] else "未覆盖%s" % tname))
        else:
            print("  风圈数据：无（强度较弱，未发布风圈半径）")
        if f["fc_hit"]:
            hit = f["fc_hit"][0]
            print("  预报路径：%d 个预报点进入%s，最早 %s 小时后（%s）" % (
                len(f["fc_hit"]), tname, hit["hour"], hit["time"]))
        print("  最新定位：%s，%s %s m/s / %s hPa，位置 %.1f°E %.1f°N" % (
            L["time"], L["strengthName"], L["wind"], L["pressure"], L["lng"], L["lat"]))
        print("  全程影响：%s" % (" → ".join(t["impact"]["history"]) or "未进入我国陆地"))
        print("  " + "-" * 56)

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
