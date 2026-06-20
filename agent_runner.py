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
功能：串联所有模块，实现从文件输入到完整报告输出的全自动流程
支持：域自动检测（零售/教育/通用）、多轮 LLM 调用、业务分析模块、证据表
用法：python agent_runner.py <数据文件路径> <分析需求> [--offline] [--domain retail_sales]
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from data_loader import load_and_clean
from data_profiler import generate_profile
from analysis_engine import AnalysisEngine
from chart_generator import generate_charts
from config import Config
from logger import get_logger
from llm_client import LLMClient
from task_planner import TaskPlanner
from domain_registry import detect_domain, get_domain_config, RETAIL_SALES
from field_registry import build_field_registry, save_field_registry

logger = get_logger(__name__)


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

    # 初始化 LLM 调用审计
    llm_audit = {
        "run_name": run_name,
        "expected_rounds": Config.LLM_EXPECTED_ROUNDS,
        "actual_rounds": 0,
        "all_success": False,
        "calls": [],
    }

    # ------------------------------
    # 步骤1：数据加载与清洗
    # ------------------------------
    print("\n[1/??] 数据读取与预处理...")
    df = load_and_clean(str(fp))
    print(f"       清洗后: {df.shape[0]} 行 × {df.shape[1]} 列")

    # ------------------------------
    # 步骤2：生成数据画像
    # ------------------------------
    print("\n[2/??] 生成数据画像...")
    data_profile = generate_profile(df, output_dir=str(run_dir))
    print(f"       总缺失率: {data_profile['meta']['total_missing_pct']}%")
    print(f"       字段类型分布: {data_profile['overview']['field_type_counts']}")

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
    print("\n[3/??] [LLM Round 1] 生成候选分析任务...")
    llm_client = LLMClient(offline_mode=offline_mode, domain_config=domain_config)
    candidate_questions = llm_client.generate_candidate_questions(
        data_profile, user_requirement
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
    print("\n[4/??] 筛选可执行任务...")
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
    print("\n[5/??] 执行统计分析...")
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
    # 步骤5b：执行业务分析模块（按域开关）
    # ------------------------------
    business_results = {}
    if active_business_modules:
        print(f"\n[5b] 执行业务分析模块...")
        # 隐蔽导入，避免对非零售场景造成依赖问题
        try:
            from granularity_detector import detect_granularity
            granularity = detect_granularity(df, field_registry)
            print(f"      数据粒度: {granularity.get('row_entity_type', '未知')}")
            print(f"      总行数: {granularity.get('row_count', 0)}")
            print(f"      唯一订单数: {granularity.get('unique_order_ids', 0)}")
            print(f"      唯一客户数: {granularity.get('unique_customer_ids', 0)}")
            print(f"      唯一产品数: {granularity.get('unique_product_ids', 0)}")
            # 保存粒度信息
            with open(run_dir / Config.GRANULARITY_FILENAME, "w", encoding="utf-8") as gf:
                json.dump(granularity, gf, ensure_ascii=False, indent=2)
        except ImportError:
            granularity = {}
            print(f"      粒度检测不可用（模块未加载）")

        # 初始化证据表
        try:
            from evidence_table import EvidenceTable
            evidence_table = EvidenceTable(domain_config)
        except ImportError:
            evidence_table = None
            print(f"      证据表不可用（模块未加载）")

        # 亏损驱动分析
        if "loss_driver_analysis" in active_business_modules:
            try:
                from loss_driver import LossDriverAnalyzer
                lda = LossDriverAnalyzer(df, field_registry)
                loss_results = lda.analyze_all()
                business_results["loss_driver"] = loss_results
                # 保存
                with open(run_dir / "loss_driver_results.json", "w", encoding="utf-8") as lf:
                    json.dump(loss_results, lf, ensure_ascii=False, indent=2)
                print(f"      亏损驱动分析: 完成 ({len(loss_results.get('top_loss_contributors', []))} 个主要亏损来源)")
                # 写入证据表
                if evidence_table:
                    for item in loss_results.get("top_loss_contributors", [])[:5]:
                        evidence_table.add_finding(
                            source_module="loss_driver",
                            finding_type="LOSS_CONCENTRATION",
                            conclusion=f"{item.get('name', '?')}: 亏损金额 {item.get('loss_amount', 0):.2f}",
                            magnitude=f"占总体亏损的 {item.get('loss_contribution_pct', 0):.1f}%",
                            comparison_baseline=f"利润率 {item.get('profit_margin', 0):.2f}%",
                            cause_clues=f"销售额 {item.get('total_sales', 0):.2f}, 折扣区间 {item.get('avg_discount', 0):.1%}",
                            business_implications=f"该分类是亏损的主要来源，需重点关注定价和折扣策略",
                            stat_reference_path=f"loss_driver.{item.get('dimension', '')}.{item.get('name', '')}",
                        )
            except ImportError:
                print(f"      亏损驱动分析: 跳过（模块未加载）")
            except Exception as e:
                logger.warning("亏损驱动分析失败: %s", e)
                print(f"      亏损驱动分析: 失败 ({e})")

        # 折扣响应分析
        if "discount_response_analysis" in active_business_modules:
            try:
                from discount_analyzer import DiscountAnalyzer
                da = DiscountAnalyzer(df, field_registry)
                discount_results = da.analyze_all()
                business_results["discount_response"] = discount_results
                with open(run_dir / "discount_analysis_results.json", "w", encoding="utf-8") as dfh:
                    json.dump(discount_results, dfh, ensure_ascii=False, indent=2)
                print(f"      折扣响应分析: 完成 (阈值={discount_results.get('profit_tipping_point', '?')})")
                if evidence_table and discount_results.get("profit_tipping_point"):
                    evidence_table.add_finding(
                        source_module="discount_analyzer",
                        finding_type="DISCOUNT_THRESHOLD",
                        conclusion=f"折扣超过 {discount_results['profit_tipping_point']} 后利润转负",
                        magnitude=discount_results.get("tipping_point_detail", ""),
                        comparison_baseline=f"基于 {discount_results.get('n_discount_bins', '?')} 个折扣分箱分析",
                        cause_clues=discount_results.get("anomalies_summary", ""),
                        business_implications="建议控制折扣不超过该阈值，或针对不同品类设置差异化的折扣上限",
                        stat_reference_path="discount_analyzer.profit_tipping_point",
                    )
            except ImportError:
                print(f"      折扣响应分析: 跳过（模块未加载）")
            except Exception as e:
                logger.warning("折扣响应分析失败: %s", e)
                print(f"      折扣响应分析: 失败 ({e})")

        # Pareto/集中度分析
        if "pareto_analysis" in active_business_modules:
            try:
                from pareto_analyzer import ParetoAnalyzer
                pa = ParetoAnalyzer(df, field_registry)
                pareto_results = pa.analyze_all()
                business_results["pareto"] = pareto_results
                with open(run_dir / "pareto_results.json", "w", encoding="utf-8") as pf:
                    json.dump(pareto_results, pf, ensure_ascii=False, indent=2)
                print(f"      集中度分析: 完成")
                if evidence_table and pareto_results.get("product_concentration"):
                    pc = pareto_results["product_concentration"]
                    evidence_table.add_finding(
                        source_module="pareto_analyzer",
                        finding_type="PARETO_CONTRIBUTION",
                        conclusion=f"前 {pc.get('top_n', '?')} 的商品贡献了 {pc.get('cumulative_sales_pct', 0):.1f}% 的销售额",
                        magnitude=f"共 {pc.get('total_items', 0)} 个商品",
                        comparison_baseline=f"前20%商品贡献={pc.get('top20_sales_pct', 0):.1f}%",
                        cause_clues=f"头部集中度指数: {pc.get('concentration_index', 0):.2f}",
                        business_implications="需要关注头部商品的库存和定价，同时优化长尾商品的盈利模式",
                        stat_reference_path="pareto.product_concentration",
                    )
            except ImportError:
                print(f"      集中度分析: 跳过（模块未加载）")
            except Exception as e:
                logger.warning("集中度分析失败: %s", e)
                print(f"      集中度分析: 失败 ({e})")

        # 交叉维度分析
        if "cross_dimension_analysis" in active_business_modules:
            try:
                from cross_dimension import CrossDimensionAnalyzer
                cda = CrossDimensionAnalyzer(df, field_registry)
                cross_dim_results = cda.analyze_all()
                business_results["cross_dimension"] = cross_dim_results
                with open(run_dir / "cross_dimension_results.json", "w", encoding="utf-8") as cf:
                    json.dump(cross_dim_results, cf, ensure_ascii=False, indent=2)
                print(f"      交叉维度分析: 完成 ({len(cross_dim_results.get('combinations', []))} 个组合)")
            except ImportError:
                print(f"      交叉维度分析: 跳过（模块未加载）")
            except Exception as e:
                logger.warning("交叉维度分析失败: %s", e)
                print(f"      交叉维度分析: 失败 ({e})")

        # 保存证据表
        if evidence_table:
            evidence_path = run_dir / Config.EVIDENCE_TABLE_FILENAME
            with open(evidence_path, "w", encoding="utf-8") as ef:
                json.dump(evidence_table.to_dict(), ef, ensure_ascii=False, indent=2)
            print(f"      证据表: {len(evidence_table.to_dict()['findings'])} 条发现")
    else:
        evidence_table = None
        granularity = {}

    # ------------------------------
    # 步骤6：生成可视化图表
    # ------------------------------
    print("\n[6/??] 生成可视化图表...")
    charts = generate_charts(df, output_dir=str(chart_dir))
    for p in charts:
        print(f"       {Path(p).name}")
    if not charts:
        print("        无足够数据生成图表")

    # ------------------------------
    # 步骤7：LLM 第2轮 — 发现问题
    # ------------------------------
    print("\n[7/??] [LLM Round 2] 发现值得深入的问题...")
    try:
        problems = llm_client.discover_problems(
            stats_results=stats_results,
            data_profile=data_profile,
            evidence_table=evidence_table,
            field_registry=field_registry,
            granularity=granularity,
        )
        print(f"       发现问题: {len(problems)} 个")
        llm_audit["calls"].append({
            "round": 2,
            "round_name": "problem_discovery",
            "model": llm_client.model if not offline_mode else "offline",
            "success": True,
            "timestamp": datetime.now().isoformat(),
        })
        llm_audit["actual_rounds"] += 1
    except Exception as e:
        logger.warning("问题发现失败: %s", e)
        print(f"       Warn: 问题发现失败: {e}")
        problems = []
        llm_audit["calls"].append({
            "round": 2,
            "round_name": "problem_discovery",
            "model": llm_client.model if not offline_mode else "offline",
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })

    # ------------------------------
    # 步骤8：LLM 第3轮 — 生成发现和建议
    # ------------------------------
    print("\n[8/??] [LLM Round 3] 生成基于证据的发现和建议...")
    try:
        findings, suggestions = llm_client.generate_findings_and_suggestions(
            stats_results=stats_results,
            data_profile=data_profile,
            valid_tasks=valid_tasks,
            evidence_table=evidence_table,
            problems=problems,
        )
        print(f"       生成主要发现: {len(findings)} 条")
        print(f"       生成建议: {len(suggestions)} 条")
        llm_audit["calls"].append({
            "round": 3,
            "round_name": "findings_suggestions",
            "model": llm_client.model if not offline_mode else "offline",
            "success": True,
            "timestamp": datetime.now().isoformat(),
        })
        llm_audit["actual_rounds"] += 1
    except Exception as e:
        logger.warning("发现和建议生成失败: %s", e)
        print(f"       Warn: 发现和建议生成失败: {e}")
        # 回退到离线生成
        findings, suggestions = llm_client._load_offline_findings_suggestions(stats_results)
        llm_audit["calls"].append({
            "round": 3,
            "round_name": "findings_suggestions",
            "model": "offline",
            "success": False,
            "error": str(e),
            "fallback": "offline",
            "timestamp": datetime.now().isoformat(),
        })

    # 保存发现和建议
    with open(run_dir / "findings.json", "w", encoding="utf-8") as f:
        json.dump([f.model_dump() for f in findings], f, ensure_ascii=False, indent=2)
    with open(run_dir / "suggestions.json", "w", encoding="utf-8") as f:
        json.dump([s.model_dump() for s in suggestions], f, ensure_ascii=False, indent=2)

    # ------------------------------
    # 步骤9：LLM 第4轮 — 正式报告写作与语言润色
    # ------------------------------
    print("\n[9/??] [LLM Round 4] 报告写作与润色...")
    try:
        report_text = llm_client.generate_report(
            data_profile=data_profile,
            stats_results=stats_results,
            findings=findings,
            suggestions=suggestions,
            evidence_table=evidence_table,
            business_results=business_results,
            user_requirement=user_requirement,
            valid_tasks=valid_tasks,
        )
        # 保存 LLM 生成的报告
        with open(run_dir / "llm_generated_report.md", "w", encoding="utf-8") as rf:
            rf.write(report_text)
        print(f"       LLM 报告草稿已保存")
        llm_audit["calls"].append({
            "round": 4,
            "round_name": "report_writing",
            "model": llm_client.model if not offline_mode else "offline",
            "success": True,
            "timestamp": datetime.now().isoformat(),
        })
        llm_audit["actual_rounds"] += 1
    except Exception as e:
        logger.warning("报告写作失败: %s，将使用模板报告", e)
        print(f"       Warn: 报告写作失败: {e}，回退到模板报告")
        report_text = ""
        llm_audit["calls"].append({
            "round": 4,
            "round_name": "report_writing",
            "model": "offline",
            "success": False,
            "error": str(e),
            "fallback": "template",
            "timestamp": datetime.now().isoformat(),
        })

    # ------------------------------
    # 步骤10：生成结构化报告（Markdown + Word）
    # ------------------------------
    print(f"\n[10/??] 生成结构化分析报告...")
    try:
        from report_generator import ReportGenerator
        report_gen = ReportGenerator(run_dir, user_requirement, domain_config=domain_config)
        report_path = report_gen.save("final_report.md")
        print(f"       报告已生成: {report_path.name}")
        # 如果有 LLM 报告，作为第二报告保存
        if report_text:
            llm_report_path = run_dir / "llm_report.md"
            with open(llm_report_path, "w", encoding="utf-8") as lr:
                lr.write(report_text)
    except FileNotFoundError as e:
        logger.warning("报告所需文件缺失: %s", e)
        print(f"       Warn: 报告所需文件缺失: {e}")
    except ImportError as e:
        logger.warning("缺少报告生成依赖: %s", e)
        print(f"       Warn: 缺少报告生成依赖: {e}")
    except Exception as e:
        logger.error("报告生成失败", exc_info=True)
        print(f"       Warn: 报告生成失败: {e}")

    # ------------------------------
    # 步骤11：合规性验证
    # ------------------------------
    print("\n[11/??] 运行合规性验证...")
    try:
        from report_validator import ReportValidator
        validator = ReportValidator(str(run_dir))
        val_result = validator.run_all_checks()
        score = val_result["meta"]["score"]
        passed = val_result["meta"]["overall_pass"]
        print(f"       验证得分: {score}/100")
        print(f"       整体结果: {'Done 通过' if passed else 'Error 不通过'}")

        # 打印各模块得分
        module_map = Config.MODULE_NAMES
        for check_name, check_data in val_result["checks"].items():
            status = "Done" if check_data["pass"] else "Error"
            label = module_map.get(check_name, check_name)
            print(f"         {status} {label}: {check_data['score']}分")

        improvement_suggestions = val_result.get("improvement_suggestions", [])
        if improvement_suggestions and not passed:
            print(f"\n       改进建议:")
            for sug in improvement_suggestions[:3]:
                print(f"         {sug}")
    except FileNotFoundError as e:
        logger.warning("验证所需文件缺失: %s", e)
        print(f"       Warn: 验证所需文件缺失: {e}")
    except ImportError as e:
        logger.warning("缺少验证依赖: %s", e)
        print(f"       Warn: 缺少验证依赖: {e}")
    except Exception as e:
        logger.error("验证失败", exc_info=True)
        print(f"       Warn: 验证失败: {e}")

    # ------------------------------
    # 保存 LLM 调用审计
    # ------------------------------
    llm_audit["all_success"] = all(c.get("success", False) for c in llm_audit["calls"])
    audit_path = run_dir / Config.LLM_AUDIT_FILENAME
    with open(audit_path, "w", encoding="utf-8") as af:
        json.dump(llm_audit, af, ensure_ascii=False, indent=2)

    # 验证轮次数
    if llm_audit["actual_rounds"] != Config.LLM_EXPECTED_ROUNDS:
        print(f"\n       ⚠️ LLM 调用轮次异常: 预期 {Config.LLM_EXPECTED_ROUNDS}, 实际 {llm_audit['actual_rounds']}")
    else:
        print(f"\n       ✅ LLM 调用审计: {llm_audit['actual_rounds']}/{Config.LLM_EXPECTED_ROUNDS} 轮, "
              f"全部成功={llm_audit['all_success']}")

    # ------------------------------
    # 完成
    # ------------------------------
    print("\n" + "=" * 70)
    print(f"   智能体分析完成！")
    print(f"   所有结果已保存到: {run_dir.resolve()}")
    print(f"   产物清单:")
    print(f"     - data_profile.json          数据画像")
    print(f"     - field_registry.json        字段角色注册表")
    print(f"     - stats_results.json         统计结果")
    print(f"     - valid_tasks.json           执行任务")
    if business_results:
        print(f"     - loss_driver_results.json  亏损驱动分析")
        print(f"     - discount_analysis_results.json 折扣响应分析")
        print(f"     - pareto_results.json       集中度分析")
        print(f"     - cross_dimension_results.json 交叉维度分析")
    if evidence_table:
        print(f"     - evidence_table.json        证据表")
    print(f"     - findings.json              数据发现")
    print(f"     - suggestions.json           改进建议")
    print(f"     - charts/                    可视化图表")
    print(f"     - final_report.md            完整分析报告")
    print(f"     - llm_call_audit.json        LLM调用审计")
    print(f"     - validation_result.json     合规性验证结果")
    print(f"     - validation_report.md       合规性验证报告")
    print("=" * 70)

    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="数据分析智能体")
    parser.add_argument("file_path", help="数据文件路径（.csv/.xlsx）")
    parser.add_argument("requirement", help="分析需求")
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
