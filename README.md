# 全国台风实时监测大屏

基于中央气象台台风网数据（typhoon.nmc.cn）的可视化看板。每 6-12 小时自动抓取最新台风实况、预报路径、风圈、影响省份。

## 文件结构

```
typhoon-dashboard/
├── index.html            # 大屏主页面
├── assets/
│   ├── style.css         # 大屏样式
│   ├── app.js            # 渲染逻辑（ECharts 地图 + 路径 + 风圈）
│   └── dashboard.ico     # 快捷方式图标（由 preview.png 生成）
├── data/
│   ├── china_province.json   # 中国省界 GeoJSON（含九段线）
│   └── typhoon.json          # 抓取的台风数据
├── vendor/
│   └── echarts.min.js    # 本地化的 ECharts 5.5.1
├── scripts/
│   ├── fetch_typhoon.py  # 数据抓取脚本
│   ├── auto_update.py    # 自动更新入口（计划任务调用，写日志）
│   ├── query_region.py   # 省级影响查询
│   └── serve_hidden.py   # 无控制台静态服务（快捷方式调用）
├── logs/
│   └── fetch.log         # 定时抓取日志（auto_update.py 写入）
├── open_dashboard.vbs    # 无黑框启动器：起服务 + 开浏览器
├── preview.png            # 大屏效果预览图
├── start.bat             # Windows 一键启动（自动抓数据 + 起 HTTP 服务）
└── start.sh              # macOS / Linux 一键启动
```

> 项目路径：`D:\PycharmProjects\typhoon-dashboard`
> 用 PyCharm 打开该目录即可直接编辑；运行配置指向 `scripts/fetch_typhoon.py`。

## 启动

```bash
# Windows：双击 start.bat
# macOS / Linux：
bash start.sh
```

启动脚本会先运行 `fetch_typhoon.py` 抓取最新数据，然后启动本地 HTTP 服务在 `http://localhost:8080`。
浏览器会自动打开该地址。

### 桌面快捷方式（推荐日常使用）

桌面上的「台风监测大屏」快捷方式走 `open_dashboard.vbs`：

- 用 `pythonw.exe` 后台拉起 `scripts/serve_hidden.py`，**不弹黑框**；
- 服务已在 8080 运行时直接复用，不会重复启动；
- 服务就绪后自动用默认浏览器打开 `http://localhost:8080`；
- 找不到 `pythonw.exe` 时自动退回 `start.bat`（有窗口，便于看报错）。

快捷方式不主动抓数据（抓取脚本单请求超时 25s × 3 次重试，不适合放在启动路径上）。
数据由定时任务每天 08:30 / 12:30 自动刷新；想手动刷新就双击 `start.bat`。

> 直接双击 `index.html` 打不开大屏 —— 浏览器禁止 `file://` 协议读取本地 JSON。请使用启动脚本。

## 数据字段说明（typhoon.json）

| 字段 | 说明 |
| --- | --- |
| `updateTime` | 数据更新时间（北京时） |
| `year` / `yearCount` | 年度 / 当年编号总数 |
| `activeCount` | 当前活跃台风数（status=start） |
| `typhoons[].num` | 国内编号（如 2618） |
| `typhoons[].cnName` / `enName` | 中文名 / 英文名 |
| `typhoons[].active` | 是否活跃 |
| `typhoons[].latest.*` | 最新观测：经纬度、风速、气压、强度、方向、速度 |
| `typhoons[].points[]` | 历史观测点序列（含 windCircles 风圈数据） |
| `typhoons[].forecast[]` | 多机构预报路径 |
| `typhoons[].impact.history` | 已过境省份 |
| `typhoons[].impact.current` | 当前位置所属省份 |
| `typhoons[].impact.forecast` | 预报可能影响省份 |
| `typhoons[].impact.near` | 海上临近省份（4°/400km 内） |

## 强度等级

| 代码 | 中文 | 风速下限 (m/s) |
| --- | --- | --- |
| TD | 热带低压 | 10.8 |
| TS | 热带风暴 | 17.2 |
| STS | 强热带风暴 | 24.5 |
| TY | 台风 | 32.7 |
| STY | 强台风 | 41.5 |
| SuperTY | 超强台风 | 51.0 |

## 自动化任务（Windows 计划任务）

已配置每日自动刷新：

- **频率**：每天 2 次，北京时间 08:30 和 12:30
- **任务名**：`TyphoonFetch-0830` / `TyphoonFetch-1230`
- **行为**：用 `pythonw` 静默运行 `scripts/auto_update.py` → 调用 `fetch_typhoon.py` 抓取最新数据，并把退出码、过程输出、结果摘要写入 `logs/fetch.log`
- **管理方式**：
  - 图形界面：`taskschd.msc`（任务计划程序）中查看 / 禁用 / 删除
  - 命令行：`schtasks /Query /TN "TyphoonFetch-*" /V`
  - 手动抓取：双击 `start.bat` 或运行 `python scripts/fetch_typhoon.py`

> 说明：本项目此前通过 WorkBuddy 自动化触发更新，现已完全迁移为本地 Windows 计划任务 + 脚本方案，WorkBuddy 相关目录与任务已全部移除。

## 大屏交互

- **滚轮**：缩放地图
- **拖拽**：平移地图
- **左栏列表**：点击切换当前台风
- **重置视野**：恢复默认视野
- **路径回放**：动画播放台风历史路径
- **风圈 / 预报路径** 按钮：显示/隐藏对应图层

台风数量 ≥ 2 时，自动每 15 秒轮播活跃台风。

## 数据源

- 台风实况：[中央气象台台风网](http://typhoon.nmc.cn)
- 中国省界：[阿里 DataV.GeoAtlas](https://datav.aliyun.com/portal/school/atlas/area_selector)