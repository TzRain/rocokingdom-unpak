#!/usr/bin/env python3
"""
SKILL_CONF.json 的 name/desc 字段对调修正工具。

游戏源数据里有约 240 条 skill 在策划录入时把 name 和 desc 两列填反了。
上游已在 sync-pet-data.mjs:1167-1189 (resolveMoveText) 用正则识别后做了 swap，
但只对派生文件 (moves.json / Pets.json 等) 生效，原始 BinData/SKILL_CONF.json
仍然是错位的。本脚本就是把这套修正直接应用到 SKILL_CONF.json，方便下游直读。

正则规则与 sync-pet-data.mjs:1160 完全一致 (MOVE_EFFECT_TEXT_PATTERN)。

用法:
    python fixup_skill_conf.py [INPUT] [-o OUTPUT] [--in-place] [--report report.csv]

默认 INPUT  = output/data/BinData/SKILL_CONF.json
默认 OUTPUT = 同目录 SKILL_CONF.fixed.json

退出码:
    0  正常完成
    1  IO / 解析错误
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

# 完全照搬 scripts/sync-pet-data.mjs:1160 的正则
MOVE_EFFECT_TEXT_PATTERN = re.compile(
    r"(造成|对敌方|敌方|自己|回复|恢复|获得|减伤|连击|本技能|魔法伤害|物理伤害|"
    r"物伤|魔伤|消耗|能量|速度|物攻|魔攻|物防|魔防|威力|命中|应对|印记|萌化|"
    r"睡眠|中毒|烧伤|暴击|先手|后手|生命|回合|下次|本次|永久|打断|蓄力|吸血|"
    r"脱离|交换|失去|赋予|翻倍|冷却|眩晕|冻结|变成|无法更换)"
)


def looks_like_effect_text(s: str | None) -> bool:
    return isinstance(s, str) and bool(MOVE_EFFECT_TEXT_PATTERN.search(s))


def fixup_skill(skill: dict) -> tuple[dict, bool]:
    """返回 (修正后的 skill, 是否被改动)。原对象不被修改。"""
    name = skill.get("name", "") or ""
    desc = skill.get("desc", "") or ""

    # 与 resolveMoveText 一致：name 像描述文本，desc 不像 → 对调
    if name and looks_like_effect_text(name) and not looks_like_effect_text(desc):
        new = dict(skill)
        new["name"], new["desc"] = desc, name
        return new, True

    return skill, False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "input",
        nargs="?",
        default="output/data/BinData/SKILL_CONF.json",
        help="输入 SKILL_CONF.json 路径 (默认 output/data/BinData/SKILL_CONF.json)",
    )
    parser.add_argument("-o", "--output", help="输出路径 (默认 <input>.fixed.json)")
    parser.add_argument("--in-place", action="store_true", help="直接覆盖输入文件")
    parser.add_argument("--report", help="可选：把被改动的记录写入 CSV (id, old_name, old_desc)")
    parser.add_argument("-q", "--quiet", action="store_true", help="不打印每条改动")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: 输入文件不存在: {in_path}", file=sys.stderr)
        return 1

    try:
        with in_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: 读取/解析失败: {e}", file=sys.stderr)
        return 1

    rows = data.get("RocoDataRows")
    if not isinstance(rows, dict):
        print("ERROR: 不是合法的 SKILL_CONF.json (缺 RocoDataRows)", file=sys.stderr)
        return 1

    changes: list[tuple[int, str, str]] = []
    new_rows: dict[str, dict] = {}

    for key, skill in rows.items():
        fixed, changed = fixup_skill(skill)
        new_rows[key] = fixed
        if changed:
            changes.append((skill.get("id"), skill.get("name", ""), skill.get("desc", "")))

    data["RocoDataRows"] = new_rows

    if args.in_place:
        out_path = in_path
    elif args.output:
        out_path = Path(args.output)
    else:
        out_path = in_path.with_suffix(".fixed.json")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"完成: 共修正 {len(changes)} 条, 写入 {out_path}")

    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        with rp.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "original_name", "original_desc"])
            for cid, name, desc in changes:
                w.writerow([cid, name, desc])
        print(f"修改报告: {rp}")

    if not args.quiet and changes:
        print("\n前 10 条被修改的记录:")
        for cid, name, desc in changes[:10]:
            print(f"  {cid}: name={name[:40]!r} <-> desc={desc[:40]!r}")
        if len(changes) > 10:
            print(f"  ... 还有 {len(changes) - 10} 条 (用 --report 输出完整 CSV)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
