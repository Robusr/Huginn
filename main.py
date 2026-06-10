"""
统计智能体 v4 — 通用入口
用法：
    python main.py <你的数据文件.csv|xlsx>

输出（每次运行独立子文件夹）：
    ./outputs/YYYYMMDD_HHMMSS_<文件名>/
        ├── data_profile.json      — 数据画像
        ├── stats_results.json     — 统计推断（含卡方拟合优度）
        ├── charts/*.png           — 可视化图表
        ├── insights.json          — 显著性洞察 (JSON)
        └── insights.md            — 显著性洞察 (Markdown)
"""
import sys
from pathlib import Path
from datetime import datetime

from data_loader import load_and_clean
from data_profiler import generate_profile
from analysis_engine import run_analysis
from chart_generator import generate_charts
from insight_generator import generate_insights


def main(file_path: str) -> None:
    fp = Path(file_path)
    if not fp.exists():
        print(f"[错误] 文件不存在: {fp}")
        sys.exit(1)

    # 每次运行独立输出目录
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{ts}_{fp.stem}"
    run_dir = Path("./outputs") / run_name
    chart_dir = run_dir / "charts"

    print("=" * 60)
    print(f"  统计智能体 v4 — 全流程分析")
    print(f"  文件: {fp}")
    print(f"  输出: {run_dir}/")
    print("=" * 60)

    # ── [1/5] 数据加载 ──────────────────────────────────────────
    print("\n[1/5] 数据读取与预处理...")
    df = load_and_clean(str(fp))
    print(f"      清洗后: {df.shape[0]} 行 × {df.shape[1]} 列")

    # ── [2/5] 数据画像 ──────────────────────────────────────────
    print("\n[2/5] 生成数据画像...")
    profile = generate_profile(df, output_dir=str(run_dir))
    print(f"      总缺失: {profile['meta']['total_missing_pct']}%")
    for f_item in profile["fields"]:
        print(f"      {f_item['column']:16s} | {f_item['inferred_type']:22s} | "
              f"missing={f_item['missing_pct']:5.1f}%")
    print(f"      → {run_dir / 'data_profile.json'}")

    # ── [3/5] 统计推断 ──────────────────────────────────────────
    print("\n[3/5] 执行统计推断...")
    stats = run_analysis(df, output_dir=str(run_dir))
    cc = stats.get("counts_check", {})
    print(f"      点估计: {stats['point_estimation']['total_fields']} 列")
    print(f"      区间估计: {cc.get('interval_estimation_fields', '?')} 列")
    print(f"      假设检验: {cc.get('hypothesis_test_types', '?')} 类")
    print(f"      ANOVA: {cc.get('anova_tests', '?')} 项")
    print(f"      卡方拟合优度: {cc.get('chi_square_tests', '?')} 个")
    for note in cc.get("notes", []):
        marker = "[WARN]" if "不足" in note else "[OK]"
        print(f"      {marker} {note}")
    print(f"      → {run_dir / 'stats_results.json'}")

    # ── [4/5] 可视化 ────────────────────────────────────────────
    print("\n[4/5] 生成可视化图表...")
    charts = generate_charts(df, output_dir=str(chart_dir))
    for p in charts:
        print(f"      {p}")
    if not charts:
        print("      (无足够数据生成图表)")

    # ── [5/5] 洞察提炼 ──────────────────────────────────────────
    print("\n[5/5] 提炼显著性洞察...")
    insights = generate_insights(
        stats_json_path=str(run_dir / "stats_results.json"),
        profile_json_path=str(run_dir / "data_profile.json"),
        output_dir=str(run_dir),
        output_format="both",
    )
    s = insights.get("summary", {})
    print(f"      检验总数: {s.get('total_tests_checked', '?')}")
    print(f"      显著结果: {s.get('significant_count', '?')} ({s.get('significant_pct', '?')}%)")
    print(f"      研究问题: {len(insights.get('research_questions', []))} 个")
    print(f"      → {run_dir / 'insights.json'}")
    print(f"      → {run_dir / 'insights.md'}")

    print("\n" + "=" * 60)
    print(f"  全流程完成 → {run_dir}/")
    print(f"  产物: data_profile.json | stats_results.json | charts/*.png | insights.json | insights.md")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
