#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
台风数据抓取脚本
数据源：中央气象台台风网 (typhoon.nmc.cn)

输出：data/typhoon.json  —— 供大屏看板离线渲染

用法：
    python fetch_typhoon.py            # 抓取当年数据
    python fetch_typhoon.py 2025       # 抓取指定年份
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_FILE = os.path.join(DATA_DIR, "typhoon.json")

LIST_URL = "http://typhoon.nmc.cn/weatherservice/typhoon/jsons/list_{year}"
VIEW_URL = "http://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_{tid}"

# 被 JSONP 回调名包裹，需剥离
JSONP_RE = re.compile(r"^[^(]+\((.*)\)\s*$", re.S)

CST = timezone(timedelta(hours=8))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 强度等级 -> 中文名 / 配色 / 风速下限(m/s)
STRENGTH = {
    "TD":      ("热带低压",   "#63b3ed", 10.8),
    "TS":      ("热带风暴",   "#38b2ac", 17.2),
    "STS":     ("强热带风暴", "#48bb78", 24.5),
    "TY":      ("台风",       "#f6ad55", 32.7),
    "STY":     ("强台风",     "#ed8936", 41.5),
    "SuperTY": ("超强台风",   "#e53e3e", 51.0),
}

# 预报机构代码 -> 名称
AGENCY = {
    "BABJ": "中国中央气象台",
    "RJTD": "日本气象厅",
    "PGTW": "美国联合台风警报中心",
    "VHHH": "香港天文台",
    "ECMF": "欧洲中期预报中心",
    "KMA":  "韩国气象厅",
}

# 风圈等级 -> 中文
WIND_CIRCLE = {
    "30KTS": ("七级风圈", 17.2),
    "50KTS": ("十级风圈", 24.5),
    "64KTS": ("十二级风圈", 32.7),
    "85KTS": ("十六级风圈", 43.7),
}

# 影响我国的参考省（用于"可能影响区域"提示）
CN_PROVINCES = [
    "辽宁", "河北", "天津", "山东", "江苏", "上海", "浙江", "福建",
    "广东", "广西", "海南", "台湾", "香港", "澳门",
]


def http_get(url, retries=3, timeout=25):
    """带重试的 GET 请求，返回文本"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": "http://typhoon.nmc.cn/web.html",
                "Accept": "*/*",
            })
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("请求失败: %s (%s)" % (url, last_err))


def parse_jsonp(text):
    """剥离 JSONP 回调外壳"""
    m = JSONP_RE.match(text.strip())
    raw = m.group(1) if m else text.strip()
    return json.loads(raw)


def fmt_time(tstr):
    """202609010000 -> 2026-09-01 00:00"""
    if not tstr or len(tstr) < 12:
        return tstr or ""
    return "%s-%s-%s %s:%s" % (tstr[0:4], tstr[4:6], tstr[6:8], tstr[8:10], tstr[10:12])


def strength_of(code, wind=None):
    """返回 (code, 中文名, 颜色)"""
    if code in STRENGTH:
        name, color, _ = STRENGTH[code]
        return code, name, color
    # 依据风速兜底判定
    w = wind or 0
    for k in ("SuperTY", "STY", "TY", "STS", "TS", "TD"):
        if w >= STRENGTH[k][2]:
            return k, STRENGTH[k][0], STRENGTH[k][1]
    return code or "TD", "热带低压", STRENGTH["TD"][1]


def parse_point(p):
    """解析单个观测点"""
    if not p or len(p) < 11:
        return None

    pid, tstr, ts, code, lng, lat, pressure, wind, mvdir, mvspd = p[0:10]
    circles_raw = p[10] if len(p) > 10 else []
    forecast_raw = p[11] if len(p) > 11 else None
    land_raw = p[12] if len(p) > 12 else None

    code, sname, color = strength_of(code, wind)

    # 风圈：[[level, rNE, rSE, rSW, rNW, pid], ...]
    circles = []
    for c in circles_raw or []:
        if not c or len(c) < 5:
            continue
        lv = c[0]
        cname, _ = WIND_CIRCLE.get(lv, (lv, 0))
        circles.append({
            "level": lv,
            "name": cname,
            "radius": [c[1], c[2], c[3], c[4]],  # NE / SE / SW / NW，单位 km
        })

    # 登陆信息：仅当登陆地点非空时才视为真实登陆
    # 原始字段 [发报时间, 发报时间文本, 登陆地点, 登陆省份]，未登陆时后两项为 null
    land = None
    if land_raw and len(land_raw) > 2 and (land_raw[2] or (len(land_raw) > 3 and land_raw[3])):
        land = {
            "time": land_raw[0],
            "timeText": land_raw[1] if len(land_raw) > 1 else "",
            "place": land_raw[2],
            "province": land_raw[3] if len(land_raw) > 3 else None,
        }

    return {
        "id": pid,
        "time": fmt_time(tstr),
        "timeRaw": tstr,
        "timestamp": ts,
        "lng": lng,
        "lat": lat,
        "pressure": pressure,
        "wind": wind,
        "moveDir": mvdir,
        "moveSpeed": mvspd,
        "strength": code,
        "strengthName": sname,
        "color": color,
        "circles": circles,
        "land": land,
        "_forecast": forecast_raw,
    }


def parse_forecast(forecast_raw):
    """解析预报路径：{机构: [[时效h, 时间, lng, lat, 气压, 风速, 机构, 强度], ...]}"""
    out = []
    if not forecast_raw or not isinstance(forecast_raw, dict):
        return out
    for agc, rows in forecast_raw.items():
        if not rows:
            continue
        pts = []
        for r in rows:
            if not r or len(r) < 6:
                continue
            hour = r[0]
            code = r[7] if len(r) > 7 else None
            _, sname, _ = strength_of(code, r[5])
            pts.append({
                "hour": hour,
                "time": fmt_time(r[1]) if len(r) > 1 else "",
                "lng": r[2],
                "lat": r[3],
                "pressure": r[4],
                "wind": r[5],
                "strength": code,
                "strengthName": sname,
            })
        if pts:
            pts.sort(key=lambda x: x["hour"])
            out.append({
                "agency": agc,
                "agencyName": AGENCY.get(agc, agc),
                "points": pts,
            })
    # 中央气象台排最前
    out.sort(key=lambda x: 0 if x["agency"] == "BABJ" else 1)
    return out


# ---------- 地理判定：台风路径与我国省级行政区的关系 ----------

SPECIAL_NAMES = {
    "新疆维吾尔自治区": "新疆", "宁夏回族自治区": "宁夏", "广西壮族自治区": "广西",
    "内蒙古自治区": "内蒙古", "西藏自治区": "西藏", "香港特别行政区": "香港",
    "澳门特别行政区": "澳门", "台湾省": "台湾", "北京市": "北京", "天津市": "天津",
    "上海市": "上海", "重庆市": "重庆",
}

_GEO_CACHE = None


def short_name(n):
    return SPECIAL_NAMES.get(n) or n.replace("省", "").replace("市", "")


def load_geo():
    """加载中国省界多边形，带 bbox 预筛索引"""
    global _GEO_CACHE
    if _GEO_CACHE is not None:
        return _GEO_CACHE
    path = os.path.join(DATA_DIR, "china_province.json")
    shapes = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for feat in data.get("features") or []:
            name = (feat.get("properties") or {}).get("name") or ""
            if not name:
                continue
            geom = feat.get("geometry") or {}
            # Polygon:   coordinates = [ring, ring, ...]
            # MultiPolygon: coordinates = [[ring, ...], [ring, ...], ...]
            # 统一成 "多边形列表"，每个多边形取首环（外环）即可
            polys = []
            if geom.get("type") == "Polygon":
                polys = [geom.get("coordinates") or []]
            elif geom.get("type") == "MultiPolygon":
                polys = geom.get("coordinates") or []
            rings = []
            for rings_of_poly in polys:
                if not rings_of_poly:
                    continue
                r = rings_of_poly[0]
                if not r or len(r) < 4:
                    continue
                xs = [c[0] for c in r]
                ys = [c[1] for c in r]
                rings.append({"ring": r, "x0": min(xs), "y0": min(ys),
                              "x1": max(xs), "y1": max(ys)})
            if rings:
                shapes.append({"name": short_name(name), "rings": rings})
    _GEO_CACHE = shapes
    return shapes


def in_ring(lng, lat, r):
    """射线法判断点是否在多边形内"""
    inside = False
    n = len(r)
    j = n - 1
    for i in range(n):
        xi, yi = r[i][0], r[i][1]
        xj, yj = r[j][0], r[j][1]
        if (yi > lat) != (yj > lat):
            xint = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < xint:
                inside = not inside
        j = i
    return inside


def province_at(lng, lat):
    """返回该经纬度所属省份简称，不在陆地上返回 None"""
    if lng is None or lat is None:
        return None
    for shp in load_geo():
        hit = False
        for item in shp["rings"]:
            if lng < item["x0"] or lng > item["x1"] or lat < item["y0"] or lat > item["y1"]:
                continue
            if in_ring(lng, lat, item["ring"]):
                hit = True
                break
        if hit:
            return shp["name"]
    return None


def province_near(lng, lat, max_deg=4.0):
    """未精确命中时，返回临近省份（判定台风中心与省界的欧氏距离，单位：度）。
    阈值 4 度（约 400km），超出则视为远离我国，返回 None。"""
    if lng is None or lat is None:
        return None
    best, bestd = None, max_deg
    for shp in load_geo():
        for item in shp["rings"]:
            # 点到 bbox 的最短距离
            dx = 0.0 if item["x0"] <= lng <= item["x1"] else min(
                abs(lng - item["x0"]), abs(lng - item["x1"]))
            dy = 0.0 if item["y0"] <= lat <= item["y1"] else min(
                abs(lat - item["y0"]), abs(lat - item["y1"]))
            d = (dx * dx + dy * dy) ** 0.5
            if d < bestd:
                bestd, best = d, shp["name"]
    return best


def build_impact(points, forecast):
    """汇总台风对我国的影响范围"""
    hist, seen = [], set()
    for p in points:
        pv = province_at(p["lng"], p["lat"])
        if pv and pv not in seen:
            seen.add(pv)
            hist.append(pv)

    cur = province_at(points[-1]["lng"], points[-1]["lat"]) if points else None
    near = None
    if not cur and points:
        near = province_near(points[-1]["lng"], points[-1]["lat"])

    fc, fseen = [], set()
    for fcst in forecast:
        for fp in fcst["points"]:
            pv = province_at(fp["lng"], fp["lat"])
            if pv and pv not in fseen:
                fseen.add(pv)
                fc.append(pv)

    return {
        "history": hist,
        "current": cur,
        "near": near,
        "forecast": fc,
        "land": bool(hist),
    }


def fetch_year_list(year):
    raw = http_get(LIST_URL.format(year=year))
    data = parse_jsonp(raw)
    lst = data.get("typhoonList") or []
    result = []
    for item in lst:
        if not item or len(item) < 8:
            continue
        result.append({
            "id": item[0],
            "enName": item[1],
            "cnName": item[2],
            "num": str(item[3]),
            "numAlt": str(item[4]) if item[4] else None,
            "desc": item[6] if len(item) > 6 else None,
            "status": item[7] if len(item) > 7 else "stop",
        })
    return result


def fetch_view(tid):
    raw = http_get(VIEW_URL.format(tid=tid))
    data = parse_jsonp(raw)
    return data.get("typhoon") or []


def build_typhoon(meta, points_raw):
    points = []
    for p in points_raw:
        pp = parse_point(p)
        if pp:
            points.append(pp)
    points.sort(key=lambda x: x["timestamp"] or 0)

    # 预报取最后一个有效点的预报
    forecast = []
    for p in reversed(points):
        f = parse_forecast(p.pop("_forecast", None))
        if f:
            forecast = f
            break
    for p in points:
        p.pop("_forecast", None)

    if not points:
        return None

    latest = points[-1]
    max_wind = max((p["wind"] or 0) for p in points)
    min_pressure = min((p["pressure"] or 9999) for p in points)
    landfall = [p["land"] for p in points if p.get("land")]

    # 峰值强度点
    peak = max(points, key=lambda x: x["wind"] or 0)

    return {
        "id": meta["id"],
        "num": meta["num"],
        "numAlt": meta["numAlt"],
        "cnName": meta["cnName"],
        "enName": meta["enName"],
        "desc": meta["desc"],
        "status": meta["status"],
        "active": meta["status"] == "start",
        "startTime": points[0]["time"],
        "endTime": latest["time"],
        "latest": latest,
        "peak": {
            "wind": peak["wind"],
            "pressure": peak["pressure"],
            "strengthName": peak["strengthName"],
            "time": peak["time"],
        },
        "maxWind": max_wind,
        "minPressure": min_pressure,
        "landfall": landfall,
        "impact": build_impact(points, forecast),
        "pointCount": len(points),
        "points": points,
        "forecast": forecast,
    }


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(CST).year

    print("[1/3] 获取 %d 年台风列表 ..." % year)
    metas = fetch_year_list(year)
    if not metas:
        print("  ! 列表为空，尝试上一年")
        metas = fetch_year_list(year - 1)
    print("  共 %d 个编号" % len(metas))

    # 活跃台风优先；无活跃时取当年最近编号的若干个
    active = [m for m in metas if m["status"] == "start"]

    # 上游列表顺序不保证（实测为按时间倒序），不能直接取末尾切片，
    # 否则会误取到当年最早的编号。这里按「年+序号」归一化排序后再取最新。
    def recency(m):
        n = re.sub(r"\D", "", m["num"] or "")
        if len(n) >= 4:
            return (int(n[:2]), int(n[2:4]))
        return (-1, -1)

    ordered = sorted(metas, key=recency, reverse=True)
    targets = active if active else ordered[:3]

    # 为完整展示，除活跃台风外再带上最近的 2 个历史台风
    recent = [m for m in ordered if m not in targets][:2]
    all_targets = targets + recent

    print("[2/3] 抓取详情：%s" % ", ".join(
        "%s(%s)" % (m["cnName"], m["num"]) for m in all_targets))

    typhoons = []
    for m in all_targets:
        try:
            raw = fetch_view(m["id"])
            if not raw or len(raw) < 9:
                print("  x %s 无详情" % m["cnName"])
                continue
            t = build_typhoon(m, raw[8])
            if t:
                typhoons.append(t)
                print("  √ %s %s：%d 个观测点，%d 条预报线路"
                      % (t["num"], t["cnName"], t["pointCount"], len(t["forecast"])))
        except Exception as e:  # noqa: BLE001
            print("  x %s 抓取失败：%s" % (m["cnName"], e))

    if not typhoons:
        print("! 未获取到任何台风数据，保留历史文件")
        return 1

    typhoons.sort(key=lambda x: (not x["active"], -(x["latest"]["timestamp"] or 0)))

    active_count = sum(1 for t in typhoons if t["active"])
    payload = {
        "updateTime": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
        "year": year,
        "source": "中央气象台台风网 typhoon.nmc.cn",
        "activeCount": active_count,
        "totalCount": len(typhoons),
        "yearCount": len(metas),  # 当年编号总数
        "provinces": CN_PROVINCES,
        "typhoons": typhoons,
    }

    print("[3/3] 写入 %s" % OUT_FILE)
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print("完成：活跃 %d / 总计 %d" % (active_count, len(typhoons)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
