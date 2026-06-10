# -*- coding: utf-8 -*-
"""
@File    : agent_runner.py
@Author  : Robusr
@Date    : 2026/6/10 16:31
@Description: 请在此处填写文件功能描述
@Software: PyCharm
"""

# agent_runner.py
"""
智能体主流程控制器
功能：串联所有模块，实现从文件输入到报告输出的完整自动化流程
用法：python agent_runner.py <数据文件路径> <分析需求> [--offline]
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from data_loader import load_and_clean
from data_profiler import generate_profile
from analysis_engine_patch import AnalysisEngine
from chart_generator import generate_charts
from llm_client import LLMClient
from task_planner import TaskPlanner


def run_agent(
        file_path: str,
        user_requirement: str,
        output_dir: str = "./outputs",
        offline_mode: bool = False
) -> Path:
    """
    运行完整的数据分析智能体流程
    :param file_path: 数据文件路径（.csv/.xlsx）
    :param user_requirement: 用户输入的分析需求
    :param output_dir: 输出目录
    :param offline_mode: 离线模式，不调用API
    :return: 本次运行的输出目录路径
    """
    fp = Path(file_path)
    if not fp.exists():
        raise FileNotFoundError(f"文件不存在: {fp}")

    # 创建本次运行的独立输出目录
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{ts}_{fp.stem}"
    run_dir = Path(output_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    chart_dir = run_dir / "charts"

    print("=" * 70)
    print(f"   课程问卷分析智能体 v1.0")
    print(f"   文件: {fp.name}")
    print(f"   需求: {user_requirement}")
    print(f"   输出: {run_dir.resolve()}")
    print(f"   模式: {'离线演示' if offline_mode else '在线API'}")
    print("=" * 70)

    # ------------------------------
    # 步骤1：数据加载与清洗
    # ------------------------------
    print("\n[1/7]  数据读取与预处理...")
    df = load_and_clean(str(fp))
    print(f"       清洗后: {df.shape[0]} 行 × {df.shape[1]} 列")

    # ------------------------------
    # 步骤2：生成数据画像
    # ------------------------------
    print("\n[2/7]  生成数据画像...")
    data_profile = generate_profile(df, output_dir=str(run_dir))
    print(f"       总缺失率: {data_profile['meta']['total_missing_pct']}%")
    print(f"       字段类型分布: {data_profile['overview']['field_type_counts']}")

    # ------------------------------
    # 步骤3：LLM生成候选分析问题
    # ------------------------------
    print("\n[3/7]  生成候选分析问题...")
    llm_client = LLMClient(offline_mode=offline_mode)
    candidate_questions = llm_client.generate_candidate_questions(data_profile, user_requirement)
    print(f"       生成候选问题: {len(candidate_questions)} 个")

    # ------------------------------
    # 步骤4：筛选可执行任务
    # ------------------------------
    print("\n[4/7]  筛选可执行任务...")
    task_planner = TaskPlanner(data_profile)
    valid_tasks = task_planner.filter_and_convert_tasks(candidate_questions)

    print("\n      最终执行任务列表:")
    for i, task in enumerate(valid_tasks, 1):
        print(f"      {i}. {task['question']} [{task['method']}]")

    # 保存有效任务
    with open(run_dir / "valid_tasks.json", "w", encoding="utf-8") as f:
        json.dump(valid_tasks, f, ensure_ascii=False, indent=2)

    # ------------------------------
    # 步骤5：执行统计分析
    # ------------------------------
    print("\n[5/7]  执行统计分析...")
    engine = AnalysisEngine(df, output_dir=str(run_dir))
    stats_results = engine.run_tasks(valid_tasks)
    cc = stats_results.get("counts_check", {})

    print(f"       点估计: {len(stats_results['point_estimation'].get('fields', {}))} 列")
    print(f"       区间估计: {cc.get('interval_estimation_fields', '?')} 列")
    print(f"       假设检验: {cc.get('hypothesis_test_types', '?')} 类")
    print(f"       ANOVA: {cc.get('anova_tests', '?')} 项")
    print(f"       卡方检验: {cc.get('chi_square_tests', '?')} 个")

    for note in cc.get("notes", []):
        marker = "Warn️" if "不足" in note else "Done"
        print(f"      {marker} {note}")

    # ------------------------------
    # 步骤6：生成可视化图表
    # ------------------------------
    print("\n[6/7]  生成可视化图表...")
    charts = generate_charts(df, output_dir=str(chart_dir))
    for p in charts:
        print(f"       {Path(p).name}")
    if not charts:
        print("        无足够数据生成图表")

    # ------------------------------
    # 步骤7：生成数据发现和课程建议
    # ------------------------------
    print("\n[7/7]  生成数据发现和课程建议...")
    findings, suggestions = llm_client.generate_findings_and_suggestions(
        stats_results, data_profile, valid_tasks
    )
    print(f"       生成主要发现: {len(findings)} 条")
    print(f"       生成课程建议: {len(suggestions)} 条")

    # 保存发现和建议
    with open(run_dir / "findings.json", "w", encoding="utf-8") as f:
        json.dump([f.dict() for f in findings], f, ensure_ascii=False, indent=2)
    with open(run_dir / "suggestions.json", "w", encoding="utf-8") as f:
        json.dump([s.dict() for s in suggestions], f, ensure_ascii=False, indent=2)

    # ------------------------------
    # 完成
    # ------------------------------
    print("\n" + "=" * 70)
    print(f"   智能体分析完成！")
    print(f"   所有结果已保存到: {run_dir.resolve()}")
    print(f"   产物清单:")
    print(f"     - data_profile.json    数据画像")
    print(f"     - stats_results.json   统计结果")
    print(f"     - valid_tasks.json     执行任务")
    print(f"     - findings.json        数据发现")
    print(f"     - suggestions.json     课程建议")
    print(f"     - charts/              可视化图表")
    print("=" * 70)

    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="课程问卷分析智能体")
    parser.add_argument("file_path", help="数据文件路径（.csv/.xlsx）")
    parser.add_argument("requirement", help="分析需求，例如：'为下一次上课的老师生成课程建议报告'")
    parser.add_argument("--offline", action="store_true", help="离线模式，不调用API")
    args = parser.parse_args()

    try:
        run_agent(args.file_path, args.requirement, offline_mode=args.offline)
    except Exception as e:
        print(f"\nError 运行失败: {str(e)}")
        sys.exit(1)