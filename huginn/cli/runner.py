# -*- coding: utf-8 -*-
"""
@File    : agent_runner.py
@Author  : Robusr
@Date    : 2026/6/10 16:31
@Description: 智能体主流程控制器 — 域感知 · 多轮 LLM · 证据驱动
@Software: PyCharm
"""

# agent_runner.py
"""
智能体主流程控制器
功能：串联所有模块，实现从文件输入到完整报告输出的四轮模型流程
用法：python agent_runner.py <数据文件路径> <分析需求> [--offline]
"""
import sys
import json
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from huginn.data.loader import load_and_clean
from huginn.data.profiler import generate_profile
from huginn.analysis.engine import AnalysisEngine
from huginn.analysis.charts import generate_charts
from huginn.core.config import Config
from huginn.planning.analysis_planning import build_candidate_task_pool, build_planning_field_map, save_planning_artifacts
from huginn.planning.feature_miner import mine_distinctive_features, save_distinctive_features
from huginn.domain.context import detect_domain_context
from huginn.core.logger import get_logger
from huginn.llm.client import LLMClient
from huginn.planning.task_planner import TaskPlanner
from huginn.domain.registry import detect_domain, get_domain_config
from huginn.domain.fields import build_field_registry, save_field_registry

logger = get_logger(__name__)


def publish_readable_exports(
        source_paths: list[Path],
        dataset_stem: str,
        *,
        output_dir: str = "./outputs"
) -> list[Path]:
    """把最新报告复制到稳定位置，便于直接交付给读者。"""
    repo_output_dir = Path(output_dir).resolve()
    workspace_output_dir = repo_output_dir.parent.parent / "outputs"
    workspace_output_dir.mkdir(parents=True, exist_ok=True)

    published: list[Path] = []
    suffix_map = {".md": "md", ".docx": "docx", ".pdf": "pdf"}
    dataset_names = [dataset_stem]
    if dataset_stem.endswith("数据") and len(dataset_stem) > 2:
        dataset_names.append(dataset_stem[:-2])

    for source in source_paths:
        if not source or not source.exists():
            continue
        ext = source.suffix.lower()
        label = suffix_map.get(ext, ext.lstrip(".") or "report")
        for readable_stem in dataset_names:
            target = workspace_output_dir / f"Huginn_{readable_stem}分析报告_新版.{label}"
            shutil.copy2(source, target)
            if target not in published:
                published.append(target)
    return published


def run_validation(run_dir: Path) -> dict | None:
    """运行验证器并打印模块得分。"""
    try:
        from huginn.reporting.validator import ReportValidator
        validator = ReportValidator(str(run_dir))
        val_result = validator.run_all_checks()
        score = val_result["meta"]["score"]
        passed = val_result["meta"]["overall_pass"]
        print(f"       验证得分: {score}/100")
        print(f"       整体结果: {'Done 通过' if passed else 'Error 不通过'}")

        module_map = Config.MODULE_NAMES
        for check_name, check_data in val_result["checks"].items():
            status = "Done" if check_data["pass"] else "Error"
            label = module_map.get(check_name, check_name)
            print(f"         {status} {label}: {check_data['score']}分")

        improvement_items = val_result.get("improvement_suggestions", [])
        if improvement_items and not passed:
            print(f"\n       改进建议:")
            for item in improvement_items[:3]:
                print(f"         {item}")
        return val_result
    except FileNotFoundError as e:
        logger.warning("验证所需文件缺失: %s", e)
        print(f"       Warn: 验证所需文件缺失: {e}")
        print(f"       提示: 可稍后手动运行 python report_validator.py {run_dir}")
    except ImportError as e:
        logger.warning("缺少验证依赖: %s", e)
        print(f"       Warn: 缺少验证依赖: {e}")
    except Exception as e:
        logger.error("验证失败", exc_info=True)
        print(f"       Warn: 验证失败: {e}")
        print(f"       提示: 可稍后手动运行 python report_validator.py {run_dir}")
    return None


def generate_report_bundle(
        run_dir: Path,
        user_requirement: str,
        dataset_stem: str,
        *,
        output_dir: str,
        publish: bool = False,
) -> tuple[Path | None, Path | None, Path | None, list[Path]]:
    """生成 md/docx/pdf；publish=True 时同步覆盖用户可看版本。"""
    try:
        from huginn.reporting.generator import ReportGenerator
        report_gen = ReportGenerator(run_dir, user_requirement)
        report_path = report_gen.save("final_report.md")
        word_path = report_gen.export_word("final_report.docx")
        pdf_path = report_gen.export_pdf("final_report.pdf")
        published_paths = []
        if publish:
            published_paths = publish_readable_exports(
                [p for p in [report_path, word_path, pdf_path] if p],
                dataset_stem,
                output_dir=output_dir,
            )
        return report_path, word_path, pdf_path, published_paths
    except FileNotFoundError as e:
        logger.warning("报告所需文件缺失: %s", e)
        print(f"       Warn: 报告所需文件缺失: {e}")
        print(f"       提示: 可稍后手动运行 python report_generator.py {run_dir}")
    except ImportError as e:
        logger.warning("缺少报告生成依赖: %s", e)
        print(f"       Warn: 缺少报告生成依赖: {e}")
    except Exception as e:
        logger.error("报告生成失败", exc_info=True)
        print(f"       Warn: 报告生成失败: {e}")
    return None, None, None, []


def run_agent(
        file_path: str,
        user_requirement: str,
        output_dir: str = "./outputs",
        offline_mode: bool = False,
        domain_key: str = None,
) -> Path:
    """
    运行完整的数据分析智能体流程。
    :param file_path: 数据文件路径（.csv/.xlsx）
    :param user_requirement: 用户输入的分析需求
    :param output_dir: 输出目录
    :param offline_mode: 离线模式，不调用API
    :param domain_key: 可选，手动指定领域（如 'retail_sales', 'education_survey'）
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
    print(f"   通用数据分析报告智能体 v1.1")
    print(f"   文件: {fp.name}")
    print(f"   需求: {user_requirement}")
    print(f"   输出: {run_dir.resolve()}")
    print(f"   模式: {'离线演示' if offline_mode else '在线API'}")
    print("=" * 70)

    # ------------------------------
    # 步骤1：数据加载与清洗
    # ------------------------------
    print("\n[1/11] 数据读取与预处理...")
    df = load_and_clean(str(fp))
    print(f"       清洗后: {df.shape[0]} 行 × {df.shape[1]} 列")

    # ------------------------------
    # 步骤2：生成数据画像
    # ------------------------------
    print("\n[2/11] 生成数据画像与识别领域...")
    data_profile = generate_profile(df, output_dir=str(run_dir))
    print(f"       总缺失率: {data_profile['meta']['total_missing_pct']}%")
    print(f"       字段类型分布: {data_profile['overview']['field_type_counts']}")
    domain_context = detect_domain_context(data_profile, user_requirement)
    (run_dir / "domain_context.json").write_text(
        json.dumps(domain_context, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"       数据领域: {domain_context['domain_label']}")

    # ------------------------------
    # 步骤2a：领域检测
    # ------------------------------
    print("\n[2a] 检测数据领域...")
    column_names = list(df.columns)
    if domain_key:
        domain_config = get_domain_config(domain_key=domain_key)
        print(f"      手动指定领域: {domain_config.name} ({domain_config.key})")
    else:
        domain_config = detect_domain(column_names)
        print(f"      自动检测领域: {domain_config.name} ({domain_config.key})")

    # 确定激活的业务分析模块
    active_business_modules = [
        m for m in Config.DOMAIN_MODULES.get(domain_config.key, [])
        if Config.BUSINESS_MODULES_ENABLED.get(m, False)
    ]
    if active_business_modules:
        print(f"      激活业务模块: {', '.join(active_business_modules)}")

    # ------------------------------
    # 步骤2b：构建字段角色注册表
    # ------------------------------
    print("\n[2b] 构建字段角色注册表...")
    field_registry = build_field_registry(data_profile, domain_config)
    reg_path = save_field_registry(field_registry, str(run_dir))
    reg_sum = field_registry.get("summary", {})
    print(f"      ID字段: {', '.join(reg_sum.get('id_fields', [])) or '无'}")
    print(f"      收入字段: {', '.join(reg_sum.get('revenue_fields', [])) or '无'}")
    print(f"      利润字段: {', '.join(reg_sum.get('profit_fields', [])) or '无'}")
    print(f"      折扣字段: {', '.join(reg_sum.get('discount_fields', [])) or '无'}")
    print(f"      维度字段: {len(reg_sum.get('dimension_fields', []))} 个")
    meaningless = reg_sum.get("meaningless_fields", [])
    if meaningless:
        print(f"      无意义字段（已过滤）: {', '.join(meaningless)}")

    # 打印 banner
    print("\n" + "=" * 70)
    print(f"   {domain_config.name}分析智能体 {Config.APP_VERSION}")
    print(f"   文件: {fp.name}")
    print(f"   需求: {user_requirement}")
    print(f"   输出: {run_dir.resolve()}")
    print(f"   模式: {'离线演示' if offline_mode else '在线API'}")
    print(f"   领域: {domain_config.name}")
    print("=" * 70)

    # ------------------------------
    # 步骤3：LLM 第1轮 — 生成候选分析任务
    # ------------------------------
    print("\n[3/11] 模型第1轮：规划合法统计任务...")
    llm_client = LLMClient(offline_mode=offline_mode)
    field_registry = build_planning_field_map(data_profile, domain_context)
    candidate_task_pool = build_candidate_task_pool(
        data_profile, field_registry, domain_context=domain_context
    )
    save_planning_artifacts(run_dir, field_registry, candidate_task_pool)
    print(f"       字段注册表: {len(field_registry.get('fields', []))} 个可用字段")
    print(f"       合法候选任务池: {candidate_task_pool.get('total_tasks', 0)} 个任务")
    candidate_questions = llm_client.generate_candidate_questions(
        data_profile,
        user_requirement,
        field_registry=field_registry,
        task_pool=candidate_task_pool,
        domain_context=domain_context,
    )
    print(f"       生成候选问题: {len(candidate_questions)} 个")
    llm_audit["calls"].append({
        "round": 1,
        "round_name": "task_planning",
        "model": llm_client.model if not offline_mode else "offline",
        "success": True,
        "timestamp": datetime.now().isoformat(),
    })
    llm_audit["actual_rounds"] += 1

    # ------------------------------
    # 步骤4：筛选可执行任务
    # ------------------------------
    print("\n[4/11] 筛选可执行任务...")
    task_planner = TaskPlanner(data_profile, domain_context)
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
    print("\n[5/11] 执行统计分析与代码特色挖掘...")
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

    print("       挖掘特色数据信号...")
    distinctive_features = mine_distinctive_features(df, domain_context=domain_context)
    save_distinctive_features(run_dir, distinctive_features)
    feature_count = len(distinctive_features.get("features", []))
    feature_types = distinctive_features.get("feature_type_counts", {})
    print(f"       特色信号: {feature_count} 条")
    if feature_types:
        print(f"       信号类型: {feature_types}")

    # ------------------------------
    # 步骤6：模型发现特色问题
    # ------------------------------
    print("\n[6/11] 模型第2轮：发现特色问题与异常信号...")
    discovered_problems = llm_client.discover_analysis_problems(
        stats_results,
        data_profile,
        valid_tasks,
        distinctive_features,
        domain_context,
    )
    (run_dir / "discovered_problems.json").write_text(
        json.dumps([item.model_dump() for item in discovered_problems], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"       识别特色问题: {len(discovered_problems)} 条")

    # ------------------------------
    # 步骤7：生成可视化图表
    # ------------------------------
    print("\n[7/11] 生成可视化图表...")
    charts = generate_charts(
        df,
        output_dir=str(chart_dir),
        stats_results=stats_results,
        domain_context=domain_context,
    )
    for p in charts:
        print(f"       {Path(p).name}")
    if not charts:
        print("        无足够数据生成图表")

    # ------------------------------
    # 步骤8：模型生成发现和行动建议
    # ------------------------------
    print("\n[8/11] 模型第3轮：生成证据化发现与行动建议...")
    findings, suggestions = llm_client.generate_findings_and_suggestions(
        stats_results,
        data_profile,
        valid_tasks,
        distinctive_features=distinctive_features,
        discovered_problems=discovered_problems,
        domain_context=domain_context,
    )
    print(f"       生成主要发现: {len(findings)} 条")
    print(f"       生成行动建议: {len(suggestions)} 条")

    (run_dir / "findings_round3.json").write_text(
        json.dumps([item.model_dump() for item in findings], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "suggestions_round3.json").write_text(
        json.dumps([item.model_dump() for item in suggestions], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ------------------------------
    # 步骤9：模型完成报告写作与语言润色
    # ------------------------------
    print("\n[9/11] 模型第4轮：完成正式报告写作与语言润色...")
    chart_metadata_path = run_dir / "chart_metadata.json"
    chart_metadata = json.loads(chart_metadata_path.read_text(encoding="utf-8")) if chart_metadata_path.exists() else {}
    narrative = llm_client.polish_report_content(
        data_profile,
        stats_results,
        findings,
        suggestions,
        chart_metadata,
        domain_context,
        user_requirement,
    )
    (run_dir / "report_narrative.json").write_text(
        json.dumps(narrative.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    findings = narrative.findings or findings
    suggestions = narrative.suggestions or suggestions

    # 保存发现和建议
    with open(run_dir / "findings.json", "w", encoding="utf-8") as f:
        json.dump([f.model_dump() for f in findings], f, ensure_ascii=False, indent=2)
    with open(run_dir / "suggestions.json", "w", encoding="utf-8") as f:
        json.dump([s.model_dump() for s in suggestions], f, ensure_ascii=False, indent=2)

    # ------------------------------
    llm_client.save_call_audit(run_dir)
    if not offline_mode:
        expected_stages = ["task_planning", "problem_discovery", "findings_suggestions", "report_writing"]
        actual_stages = [item["stage"] for item in llm_client.call_audit if item.get("success")]
        if actual_stages != expected_stages or len(llm_client.call_audit) != 4:
            raise RuntimeError(f"模型调用轮次校验失败: 期望{expected_stages}，实际{actual_stages}")
        print("       四轮模型调用审计: 通过")

    # 步骤10：生成报告草稿（供验证器读取最终正文结构）
    # ------------------------------
    print("\n[10/11] 生成完整分析报告草稿...")
    report_path, word_path, pdf_path, _ = generate_report_bundle(
        run_dir,
        user_requirement,
        fp.stem,
        output_dir=output_dir,
        publish=False,
    )
    if report_path:
        print(f"       Markdown 报告: {report_path.name}")
    if word_path:
        print(f"       Word 报告: {word_path.name}")
    if pdf_path:
        print(f"       PDF 报告: {pdf_path.name}")

    # ------------------------------
    # 步骤11：合规性验证 + 刷新正式报告导出
    # ------------------------------
    print("\n[11/11] 运行合规性验证并发布报告...")
    run_validation(run_dir)

    report_path, word_path, pdf_path, published_paths = generate_report_bundle(
        run_dir,
        user_requirement,
        fp.stem,
        output_dir=output_dir,
        publish=True,
    )
    if report_path:
        print(f"       Markdown 报告: {report_path.name}")
    if word_path:
        print(f"       Word 报告: {word_path.name}")
    if pdf_path:
        print(f"       PDF 报告: {pdf_path.name}")
    if published_paths:
        print("       用户可看版本:")
        for path in published_paths:
            print(f"         {path}")
    print(f"       风格: 正式报告版（目录 + 图表解读 + 主要发现 + 建议）")

    # ------------------------------
    # 完成
    # ------------------------------
    print("\n" + "=" * 70)
    print(f"   智能体分析完成！")
    print(f"   所有结果已保存到: {run_dir.resolve()}")
    print(f"   产物清单:")
    print(f"     - data_profile.json       数据画像")
    print(f"     - stats_results.json      统计结果")
    print(f"     - distinctive_features.json 特色数据信号")
    print(f"     - valid_tasks.json        执行任务")
    print(f"     - findings.json           数据发现")
    print(f"     - suggestions.json        行动建议")
    print(f"     - discovered_problems.json 模型发现的问题")
    print(f"     - report_narrative.json   第四轮正式文稿")
    print(f"     - llm_call_audit.json     四轮模型调用审计")
    print(f"     - charts/                 可视化图表")
    print(f"     - final_report.md         Markdown 报告")
    print(f"     - final_report.docx       Word 正式报告")
    print(f"     - final_report.pdf        PDF 正式报告")
    print(f"     - validation_result.json  合规性验证结果")
    print(f"     - validation_report.md    合规性验证报告")
    print("=" * 70)

    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="通用数据分析报告智能体")
    parser.add_argument("file_path", help="数据文件路径（.csv/.xlsx）")
    parser.add_argument("requirement", help="分析需求，例如：'分析销售与利润并提出经营建议'")
    parser.add_argument("--offline", action="store_true", help="离线模式，不调用API")
    parser.add_argument("--domain", type=str, default=None,
                       help="手动指定领域 (retail_sales/education_survey/general_business)")
    args = parser.parse_args()

    try:
        run_agent(
            args.file_path,
            args.requirement,
            offline_mode=args.offline,
            domain_key=args.domain,
        )
    except Exception as e:
        logger.critical("智能体管线运行失败", exc_info=True)
        print(f"\nError 运行失败: {str(e)}")
        sys.exit(1)
