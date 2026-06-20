# -*- coding: utf-8 -*-
"""
@File    : app.py
@Author  : Robusr
@Date    : 2026/6/16
@Description: Streamlit 交互式界面 — 课程问卷分析智能体
              功能：文件上传 → 分析执行 → 结果展示 → 报告下载
              用法：streamlit run app.py
@Software: PyCharm
"""

import sys
import json
import tempfile
import zipfile
import io
from pathlib import Path
from datetime import datetime

import streamlit as st

from huginn.core.config import Config, clean_field_name
from huginn.core.logger import get_logger

logger = get_logger(__name__)

# 页面配置
st.set_page_config(
    page_title=Config.APP_PAGE_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

def load_run_results(run_dir: Path) -> dict:
    """加载运行结果目录中的所有内容。"""
    results = {
        "run_dir": run_dir,
        "data_profile": None,
        "stats_results": None,
        "findings": [],
        "suggestions": [],
        "valid_tasks": [],
        "validation_result": None,
        "charts": [],
        "report_md": "",
    }

    # 加载 JSON 文件
    json_files = {
        "data_profile": "data_profile.json",
        "stats_results": "stats_results.json",
        "validation_result": "validation_result.json",
    }
    for key, filename in json_files.items():
        path = run_dir / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                results[key] = json.load(f)

    # 加载数组文件
    for key, filename in [("findings", "findings.json"), ("suggestions", "suggestions.json"),
                           ("valid_tasks", "valid_tasks.json")]:
        path = run_dir / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                results[key] = data if isinstance(data, list) else []

    # 发现图表
    chart_dir = run_dir / "charts"
    if chart_dir.exists():
        results["charts"] = sorted(chart_dir.glob("*.png"))

    # 加载报告
    report_path = run_dir / "final_report.md"
    if report_path.exists():
        results["report_md"] = report_path.read_text(encoding="utf-8")

    return results


# ==================================================================
# 界面渲染
# ==================================================================

def main():
    st.title(f"📊 数据分析智能体 Huginn {Config.APP_VERSION}")
    st.markdown("> **全自动数据分析**：上传 Excel/CSV 表格，自动完成统计分析、业务诊断和报告生成")

    # ── 侧边栏 ────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ 分析配置")

        uploaded_file = st.file_uploader(
            "📁 上传数据文件",
            type=["csv", "xlsx"],
            help="支持 .csv 和 .xlsx 格式的数据文件",
        )

        user_requirement = st.text_area(
            "📝 分析需求",
            value=Config.DEFAULT_REQUIREMENT,
            help="描述你希望智能体关注的分析重点",
        )

        offline_mode = st.checkbox(
            "🔌 离线模式",
            value=False,
            help="不调用 DeepSeek API，使用预生成演示数据",
        )

        st.divider()

        run_button = st.button(
            "🚀 开始分析",
            type="primary",
            width="stretch",
            disabled=uploaded_file is None,
        )

        if not uploaded_file:
            st.info("👆 请先上传一个数据文件")

        st.divider()
        st.caption("Built with ☕️ by Robusr👨🏻‍💻")
        st.caption(f"v1.0 | {datetime.now().year}")

    # ── 主区域 ────────────────────────────────────────────────
    if run_button and uploaded_file:
        # 保存上传文件到临时目录
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(uploaded_file.name).suffix,
        ) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        # 执行分析
        with st.spinner("🔄 正在执行分析流程，请稍候..."):
            try:
                from huginn.cli.runner import run_agent

                # 创建进度容器
                progress_placeholder = st.empty()
                log_placeholder = st.empty()

                run_dir = run_agent(
                    tmp_path,
                    user_requirement,
                    output_dir=Config.OUTPUT_DIR,
                    offline_mode=offline_mode,
                )

                st.success(f"✅ 分析完成！结果保存在: `{run_dir}`")

                # 加载结果
                results = load_run_results(run_dir)

                # 存到 session_state
                st.session_state.results = results
                st.session_state.analysis_done = True

            except FileNotFoundError as e:
                st.error(f"❌ 文件未找到: {str(e)}")
            except Exception as e:
                logger.error("Streamlit 分析流程失败", exc_info=True)
                st.error(f"❌ 分析失败: {str(e)}")
                import traceback
                with st.expander("🔍 错误详情"):
                    st.code(traceback.format_exc())
            finally:
                # 清理临时文件
                try:
                    Path(tmp_path).unlink()
                except Exception:
                    pass

    # ── 结果展示 ──────────────────────────────────────────────
    if st.session_state.get("analysis_done") and st.session_state.get("results"):
        results = st.session_state.results
        run_dir = results["run_dir"]

        st.divider()
        st.header("📋 分析结果")

        # 标签页
        tabs = st.tabs([
            "📊 概况", "📈 图表", "🔬 统计", "💡 发现",
            "🎯 建议", "✅ 验证", "📄 完整报告",
        ])

        # ── Tab 1: 概况 ──────────────────────────────────
        with tabs[0]:
            profile = results.get("data_profile")
            if profile:
                meta = profile.get("meta", {})
                overview = profile.get("overview", {})
                fields = profile.get("fields", [])

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("总行数", meta.get("n_rows", "?"))
                col2.metric("总列数", meta.get("n_columns", "?"))
                col3.metric("缺失率", f"{meta.get('total_missing_pct', 0):.1f}%")
                col4.metric("重复行", overview.get("duplicate_rows", 0))

                st.divider()

                # 字段类型 + 执行统计
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("字段类型分布")
                    type_counts = overview.get("field_type_counts", {})
                    type_labels = Config.TYPE_LABELS
                    cols = st.columns(len(type_counts) if type_counts else 1)
                    for i, (ftype, count) in enumerate(sorted(type_counts.items())):
                        cols[i % len(cols)].metric(
                            type_labels.get(ftype, ftype), count
                        )
                with c2:
                    st.subheader("执行统计")
                    valid_tasks = results.get("valid_tasks", [])
                    findings = results.get("findings", [])
                    suggestions = results.get("suggestions", [])
                    charts = results.get("charts", [])
                    val = results.get("validation_result")
                    val_score = val.get("meta", {}).get("score", "?") if val else "?"

                    st.metric("执行任务", f"{len(valid_tasks)} 项")
                    st.metric("数据发现", f"{len(findings)} 条")
                    st.metric("改进建议", f"{len(suggestions)} 条")
                    st.metric("验证得分", f"{val_score}/100")

                st.divider()
                st.subheader("字段详情")
                field_data = []
                for f in fields:
                    field_data.append({
                        "字段名": clean_field_name(f.get("column", "")),
                        "类型": type_labels.get(f.get("inferred_type", ""), f.get("inferred_type")),
                        "有效值": f.get("count"),
                        "缺失": f"{f.get('missing_pct', 0):.1f}%",
                        "唯一值": f.get("unique"),
                    })
                st.dataframe(field_data, width="stretch")
            else:
                st.info("未找到数据画像文件")

        # ── Tab 2: 图表 ──────────────────────────────────
        with tabs[1]:
            charts = results.get("charts", [])
            if charts:
                chart_labels = Config.CHART_LABELS
                cols = st.columns(2)
                for i, chart_path in enumerate(charts):
                    desc = chart_labels.get(chart_path.stem, chart_path.stem)
                    with cols[i % 2]:
                        st.subheader(desc)
                        st.image(str(chart_path), width="stretch")
            else:
                st.info("未生成可视化图表")

        # ── Tab 3: 统计 ──────────────────────────────────
        with tabs[2]:
            stats = results.get("stats_results")
            if stats:
                # 点估计
                pe = stats.get("point_estimation", {}).get("fields", {})
                st.subheader(f"点估计（{len(pe)} 列）")
                if pe:
                    pe_data = []
                    for col, info in pe.items():
                        if isinstance(info, dict) and "error" not in info:
                            pe_data.append({
                                "字段": clean_field_name(col),
                                "样本量": info.get("n"),
                                "均值": f"{info.get('mean', 0):.4f}",
                                "标准差": f"{info.get('std', 0):.4f}",
                                "中位数": f"{info.get('median', 0):.4f}",
                            })
                    st.dataframe(pe_data, width="stretch")

                # 假设检验显著结果
                ht = stats.get("hypothesis_tests", {}).get("tests", {})
                st.subheader("假设检验显著结果")
                sig_tests = []
                for name, test in ht.items():
                    if isinstance(test, dict) and "p_value" in test:
                        p = test.get("p_value", 1.0)
                        if isinstance(p, (int, float)) and p < Config.SIGNIFICANCE_THRESHOLD:
                            sig_tests.append({
                                "检验": test.get("method", name),
                                "变量": test.get("variables", test.get("column", "")),
                                "统计量": f"{test.get('t_statistic') or test.get('statistic') or '':.4f}",
                                "p值": f"**{p:.4f}**",
                            })
                if sig_tests:
                    st.dataframe(sig_tests, width="stretch")
                else:
                    st.info("无显著假设检验结果")

                # ANOVA 显著结果
                anova = stats.get("anova", {}).get("tests", {})
                sig_anova = []
                for name, test in anova.items():
                    if isinstance(test, dict) and "p_value" in test:
                        p = test.get("p_value", 1.0)
                        if isinstance(p, (int, float)) and p < Config.SIGNIFICANCE_THRESHOLD:
                            sig_anova.append({
                                "因变量": test.get("dependent"),
                                "因子": test.get("factor"),
                                "F值": f"{test.get('F_statistic', 0):.4f}",
                                "p值": f"**{p:.4f}**",
                            })
                if sig_anova:
                    st.subheader("ANOVA 显著结果")
                    st.dataframe(sig_anova, width="stretch")

                # 数量自查
                cc = stats.get("counts_check", {})
                if cc:
                    st.subheader("统计数量自查")
                    st.json(cc)
            else:
                st.info("未找到统计结果文件")

        # ── Tab 4: 发现 ──────────────────────────────────
        with tabs[3]:
            findings = results.get("findings", [])
            if findings:
                st.subheader(f"核心数据发现（{len(findings)} 条）")
                sorted_findings = sorted(
                    findings,
                    key=lambda x: x.get("importance", 0) if isinstance(x.get("importance"), (int, float)) else 0,
                    reverse=True,
                )
                for i, f in enumerate(sorted_findings, 1):
                    importance = f.get("importance", "?")
                    stars = "⭐" * min(int(importance), 5) if isinstance(importance, (int, float)) else ""
                    with st.container(border=True):
                        st.markdown(f"### 发现 {i}：{f.get('conclusion', '')} {stars}")
                        st.caption(f"重要性: {importance}/5 | 方法: {f.get('method', '')}")
                        st.markdown(f"**证据**: {f.get('evidence', '')}")
            else:
                st.info("未生成数据发现")

        # ── Tab 5: 建议 ──────────────────────────────────
        with tabs[4]:
            suggestions = results.get("suggestions", [])
            if suggestions:
                st.subheader(f"改进建议（{len(suggestions)} 条）")
                for i, s in enumerate(suggestions, 1):
                    with st.container(border=True):
                        st.markdown(f"### 建议 {i}：{s.get('suggestion', '')}")
                        st.markdown(f"**数据依据**: {s.get('evidence', '')}")
                        st.markdown(f"**改进方向**: {s.get('direction', '')}")
            else:
                st.info("未生成改进建议")

        # ── Tab 6: 验证 ──────────────────────────────────
        with tabs[5]:
            val = results.get("validation_result")
            if val:
                meta = val.get("meta", {})
                score = meta.get("score", 0)
                passed = meta.get("overall_pass", False)

                col1, col2 = st.columns(2)
                col1.metric("总分", f"{score}/100")
                col2.metric("结果", "✅ 通过" if passed else "❌ 不通过")

                st.subheader("各模块得分")
                checks = val.get("checks", {})
                module_names = Config.MODULE_NAMES
                for key, check in checks.items():
                    check_score = check.get("score", 0)
                    check_pass = check.get("pass", False)
                    icon = "✅" if check_pass else "❌"
                    st.markdown(f"{icon} **{module_names.get(key, key)}**: {check_score}分")

                improvements = val.get("improvement_suggestions", [])
                if improvements:
                    st.subheader("改进建议")
                    for sug in improvements:
                        st.markdown(f"- {sug}")
            else:
                st.info("未找到验证结果。请确保已运行 report_validator.py")

        # ── Tab 7: 完整报告 ──────────────────────────────
        with tabs[6]:
            report_md = results.get("report_md", "")
            if report_md:
                # 提供下载和预览切换
                view_mode = st.radio(
                    "查看方式",
                    ["📖 章节预览", "📄 原始 Markdown"],
                    horizontal=True,
                )
                if view_mode == "📄 原始 Markdown":
                    st.code(report_md, language="markdown")
                else:
                    # 按章节分割报告，折叠显示
                    sections = report_md.split("\n# ")
                    # 第一部分是报告头
                    if sections:
                        st.markdown(sections[0])
                    for sec in sections[1:]:
                        sec = sec.strip()
                        if not sec:
                            continue
                        # 提取章节标题
                        title_end = sec.find("\n")
                        title = sec[:title_end].strip() if title_end > 0 else sec[:80]
                        # 折叠显示
                        with st.expander(f"# {title}", expanded=len(sections) <= 4):
                            st.markdown(sec)
            else:
                st.info("未找到完整报告文件")

        # ── 下载区域 ──────────────────────────────────────
        st.divider()
        st.header("📥 下载")

        col1, col2, col3, col4 = st.columns(4)

        # Markdown 报告
        md_path = run_dir / "final_report.md"
        if md_path.exists():
            with col1:
                with open(md_path, "r", encoding="utf-8") as f:
                    st.download_button(
                        "📝 下载报告 (Markdown)",
                        data=f.read(),
                        file_name="final_report.md",
                        mime="text/markdown",
                        width="stretch",
                    )

        # Word 报告
        docx_path = run_dir / "final_report.docx"
        if docx_path.exists():
            with col2:
                with open(docx_path, "rb") as f:
                    st.download_button(
                        "📄 下载报告 (Word)",
                        data=f.read(),
                        file_name="final_report.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width="stretch",
                    )

        # 统计结果 JSON
        with col3:
            stats_path = run_dir / "stats_results.json"
            if stats_path.exists():
                with open(stats_path, "r", encoding="utf-8") as f:
                    st.download_button(
                        "📊 下载统计结果 (JSON)",
                        data=f.read(),
                        file_name="stats_results.json",
                        mime="application/json",
                        width="stretch",
                    )

        # 打包下载
        with col4:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fpath in sorted(run_dir.rglob("*")):
                    if fpath.is_file():
                        zf.write(fpath, fpath.relative_to(run_dir))
            zip_buffer.seek(0)
            st.download_button(
                "💾 下载完整报告 (ZIP)",
                data=zip_buffer,
                file_name=f"{run_dir.name}.zip",
                mime="application/zip",
                width="stretch",
            )


if __name__ == "__main__":
    # 初始化 session state
    if "analysis_done" not in st.session_state:
        st.session_state.analysis_done = False
    if "results" not in st.session_state:
        st.session_state.results = None

    main()
