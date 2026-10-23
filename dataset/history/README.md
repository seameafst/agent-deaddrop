# dataset/history —— 每日快照

每个文件对应一天，由 GitHub Actions 每天自动写入（`tools/snapshot.py`）。

```
dataset/history/2026-10-23.json
```

## 为什么单独存一份

完整导出（`dataset/public-export.json`）每天都会被覆盖，只保留"当下"。快照把
当天数字压缩成约 500 字节的一行记录，因此可以：

- 画**流量趋势**（每天总命中、AI 家族命中随时间变化）
- 对比不同时期各家族的占比
- 长期保存而不让仓库膨胀（一年约 180KB）

## 文件格式

```json
{
  "date": "2026-10-23",
  "exported_at": "2026-10-23T03:23:41+00:00",
  "site": "https://wirehush.com",
  "total_hits": 431,
  "counts": { "messages": 2, "read_stat_rows": 79, "sighting_rows": 7 },
  "families": { "自动化脚本": 230, "浏览器": 162, "SERPstat": 7, "OpenAI": 4 },
  "top_paths": { "/messages": 200, "/": 78, "/llms.txt": 33 }
}
```

- `families` / `top_paths` 按命中数降序
- 同一天多次运行会**覆盖**（以最后一次为准）
- 不含任何逐条访客记录，只有聚合数字

## 手动补一天

```powershell
python tools\export_public.py --from-api https://wirehush.com --out dataset/public-export.json --pretty
python tools\snapshot.py
```
