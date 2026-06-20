# -*- coding: utf-8 -*-
"""
@File    : llm_client.py
@Author  : Robusr
@Date    : 2026/6/10 15:59
@Description: LLM 客户端 — 域感知四轮调用（task_planning/problem_discovery/findings_suggestions/report_writing）
"""

"""
LLM 客户端封装
支持域感知的多轮 LLM 调用：
  Round 1 — task_planning: 生成候选分析任务
  Round 2 — problem_discovery: 发现有特点、值得深入的问题
  Round 3 — findings_suggestions: 基于证据生成发现和建议
  Round 4 — report_writing: 正式报告写作和润色

所有 LLM 调用只能引用 evidence_table 中存在的预计算数据。
"""
import os
import json
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from pydantic import BaseModel, Field

from config import Config
from logger import get_logger

logger = get_logger(__name__)

load_dotenv()


# ============================================================================
# Pydantic 结构化输出模型
# ============================================================================

class CandidateQuestion(BaseModel):
    """单个候选分析问题。"""
    question: str = Field(description="自然语言描述的分析问题")
    variables: List[str] = Field(description="涉及的变量名，必须与数据画像中的column字段完全一致")
    method: str = Field(
        description="建议使用的统计方法：t检验、配对t检验、ANOVA、卡方检验、相关性分析、分布检验"
    )
    value: str = Field(description="该问题的业务分析价值")


class CandidateQuestionsResponse(BaseModel):
    """候选问题列表。"""
    questions: List[CandidateQuestion] = Field(description="8-12个候选分析问题")


class DataFinding(BaseModel):
    """单个数据发现。"""
    conclusion: str = Field(description="基于统计结果的明确结论")
    evidence: str = Field(description="数据依据，引用具体的统计量和p值")
    method: str = Field(description="使用的统计方法")
    importance: int = Field(description="重要性评分 1-5")
    evidence_ref: str = Field(default="", description="证据表引用路径")
    magnitude: str = Field(default="", description="规模/量级说明")
    business_meaning: str = Field(default="", description="业务含义")


class Suggestion(BaseModel):
    """单条改进建议。"""
    suggestion: str = Field(description="具体可落地的建议")
    evidence: str = Field(description="支撑该建议的数据发现")
    direction: str = Field(description="改进方向和预期效果")
    priority_score: int = Field(default=3, description="优先级 1-5")


class FindingsAndSuggestionsResponse(BaseModel):
    """发现和建议输出。"""
    findings: List[DataFinding] = Field(description="5-8条核心数据发现")
    suggestions: List[Suggestion] = Field(description="3-5条针对性建议")


class DiscoveredProblem(BaseModel):
    """Round 2 发现的值得深入的问题。"""
    problem: str = Field(description="值得深入研究的分析问题")
    rationale: str = Field(description="为什么这个问题值得关注")
    evidence_preview: str = Field(description="当前已知的初步证据")
    suggested_angle: str = Field(description="建议的分析角度")


class DiscoveredProblemsResponse(BaseModel):
    """Round 2 问题发现输出。"""
    problems: List[DiscoveredProblem] = Field(description="3-8个值得深入研究的问题")


# ============================================================================
# LLM 客户端核心
# ============================================================================

class LLMClient:
    """域感知的 LLM 客户端，支持最多4轮在线调用。"""

    def __init__(self, offline_mode: bool = False, domain_config=None):
        self.offline_mode = offline_mode
        self.domain_config = domain_config
        if not offline_mode:
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", Config.LLM_BASE_URL),
            )
            self.model = Config.LLM_MODEL
            self.max_retries = Config.LLM_MAX_RETRIES
            self.retry_delay = Config.LLM_RETRY_DELAY

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @property
    def persona(self) -> str:
        """获取当前领域的 LLM persona。"""
        if self.domain_config:
            return self.domain_config.persona
        return "你是一位专业的数据分析专家。"

    @property
    def domain_key(self) -> str:
        if self.domain_config:
            return self.domain_config.key
        return "general_business"

    @property
    def is_education(self) -> bool:
        return self.domain_key == "education_survey"

    def _call_with_retry(self, messages: List[Dict], response_format: Optional[BaseModel] = None) -> Any:
        """带重试机制的 API 调用。"""
        if self.offline_mode:
            raise Exception("离线模式下无法调用API")

        if response_format:
            schema_json = response_format.model_json_schema()
            schema_str = json.dumps(schema_json, ensure_ascii=False)
            augmented_messages = [
                *messages[:-1],
                {
                    "role": messages[-1]["role"],
                    "content": messages[-1]["content"] + (
                        f"\n\n【输出格式 - JSON Schema】\n{schema_str}"
                    ),
                },
            ]
        else:
            augmented_messages = messages

        for attempt in range(self.max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": augmented_messages,
                    "temperature": Config.LLM_TEMPERATURE,
                    "top_p": Config.LLM_TOP_P,
                    "max_tokens": Config.LLM_MAX_TOKENS,
                }
                if response_format:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**kwargs)

                if response_format:
                    content = response.choices[0].message.content
                    parsed_dict = json.loads(content)
                    return response_format.model_validate(parsed_dict)
                return response
            except RateLimitError:
                if attempt == self.max_retries - 1:
                    raise Exception("DeepSeek API 速率限制超限")
                time.sleep(self.retry_delay * (attempt + 1))
            except APITimeoutError:
                if attempt == self.max_retries - 1:
                    raise Exception("DeepSeek API 超时")
                time.sleep(self.retry_delay)
            except APIError as e:
                raise Exception(f"DeepSeek API 调用失败: {str(e)}")

    def _build_evidence_block(self, evidence_table) -> str:
        """构建证据表约束块。"""
        if evidence_table is None:
            return "（无预计算证据表——仅可使用 stats_results 中的数据）"

        try:
            return evidence_table.to_llm_context()
        except Exception:
            return "（证据表读取失败）"

    def _build_common_constraints(self) -> str:
        """构建所有 LLM 调用的公共约束。"""
        if self.is_education:
            return """
【约束】
1. 禁止编造数据或统计量
2. 禁止将相关性表述为因果关系
3. 不显著的结果（p≥0.05）不得作为"显著发现"
4. 不使用模糊词汇（可能、大概、也许）
5. 建议必须具体可落地
"""
        else:
            return """
【约束】
1. 所有结论必须基于提供的证据表或统计结果，禁止编造数据
2. 禁止将相关性表述为因果关系——必须使用"相关"、"关联"而非"导致"、"影响"
3. 统计显著（p<0.05）≠ 实际重要——必须结合效应量和业务场景综合判断
4. 所有比率必须明确分母（如"亏损订单率 = 亏损订单数 / 总订单数"）
5. ID、邮编、流水号等字段不得作为连续业务指标
6. 不使用模糊词汇（可能、大概、也许）
7. 建议必须具体可落地，含预期效果
"""

    # ==================================================================
    # Round 1: 生成候选分析任务（task_planning）
    # ==================================================================

    def generate_candidate_questions(
        self, data_profile: Dict, user_requirement: str
    ) -> List[CandidateQuestion]:
        """Round 1: 基于数据画像生成候选分析任务。"""
        if self.offline_mode:
            return self._load_offline_questions()

        # 构建域感知提示词
        if self.is_education:
            domain_guidance = """
【领域要求】
- 所有问题围绕课程教学改进展开
- 优先选择能体现群体差异、模块难度、学习效果相关性的问题
- 强制包含：≥2个ANOVA、≥2个卡方检验、≥3个t检验
"""
        else:
            domain_guidance = """
【领域要求】
- 所有问题围绕数据中的业务模式、异常和机会展开
- 优先选择具有实际经营指导意义的问题
- 覆盖：组间差异（ANOVA/t检验）、分类关联（卡方）、数值关系（相关性）
- 关注：利润驱动、折扣影响、品类差异、区域对比、客群特征
"""

        prompt = f"""{self.persona}

请根据以下数据画像和用户需求，提出8-12个有业务价值的统计分析问题。

【数据画像】
{json.dumps(data_profile, ensure_ascii=False, indent=2)}

【用户需求】
{user_requirement}

{domain_guidance}

{self._build_common_constraints()}

【统计方法约束】
- 方法只能从：t检验、配对t检验、ANOVA、卡方检验、相关性分析、分布检验 中选择
- 变量名必须与数据画像中的column字段完全一致
- 输出必须严格符合JSON格式
"""
        messages = [{"role": "user", "content": prompt}]
        response = self._call_with_retry(messages, response_format=CandidateQuestionsResponse)
        return response.questions

    # ==================================================================
    # Round 2: 发现值得深入的问题（problem_discovery）
    # ==================================================================

    def discover_problems(
        self,
        stats_results: Dict,
        data_profile: Dict,
        evidence_table=None,
        field_registry: Optional[Dict] = None,
        granularity: Optional[Dict] = None,
    ) -> List[DiscoveredProblem]:
        """Round 2: 发现有特点、值得深入研究的问题。"""
        if self.offline_mode:
            return self._offline_discover_problems(stats_results)

        evidence_block = self._build_evidence_block(evidence_table)

        # 粒度提醒
        granularity_note = ""
        if granularity:
            gran = granularity
            granularity_note = f"""
【数据粒度提醒】
- 行级实体: {gran.get('entity_description', '未知')}
- 总行数: {gran.get('row_count', '?')}
- 唯一订单数: {gran.get('unique_order_ids', '?')}
- 唯一客户数: {gran.get('unique_customer_ids', '?')}
- 唯一产品数: {gran.get('unique_product_ids', '?')}
- 重要: {gran.get('important_note', '所有比率必须明确分母')}
"""

        prompt = f"""{self.persona}

你是问题发现专家。请基于统计结果和证据表，发现最有特点、最值得深入研究的分析问题。

【统计结果摘要】
- 执行任务数: {len(stats_results.get('tasks_executed', []))}
- ANOVA 结果数: {len(stats_results.get('anova', {}).get('tests', {}))}
- 假设检验结果数: {len(stats_results.get('hypothesis_tests', {}).get('tests', {}))}

{granularity_note}

{evidence_block}

{self._build_common_constraints()}

【要求】
1. 发现3-8个值得深入研究的问题
2. 每个问题必须有明确的初步证据支撑
3. 优先发现：异常模式、反直觉现象、结构性矛盾、高价值但被忽略的维度
4. 不要重复统计结果中已经显而易见的结论——要寻找"下一层"的问题
5. 输出必须严格符合JSON格式
"""
        messages = [{"role": "user", "content": prompt}]
        response = self._call_with_retry(messages, response_format=DiscoveredProblemsResponse)
        return response.problems

    # ==================================================================
    # Round 3: 生成发现和建议（findings_suggestions）
    # ==================================================================

    def generate_findings_and_suggestions(
        self,
        stats_results: Dict,
        data_profile: Dict,
        valid_tasks: List[Dict],
        evidence_table=None,
        problems: Optional[List[DiscoveredProblem]] = None,
    ) -> tuple:
        """Round 3: 基于统计证据生成发现和建议。"""
        if self.offline_mode:
            return self._load_offline_findings_suggestions(stats_results)

        sig_count = self._count_significant_results(stats_results)
        evidence_block = self._build_evidence_block(evidence_table)

        # 问题上下文
        problems_context = ""
        if problems:
            problems_context = "\n".join(
                f"- {p.problem}（建议角度: {p.suggested_angle}）"
                for p in problems[:5]
            )
            problems_context = f"\n【Round 2 发现的问题】\n{problems_context}\n"

        # 域特定的建议方向
        if self.is_education:
            suggestion_guidance = """
【建议要求】
1. 每条建议对应一条数据发现
2. 建议具体可落地：目标群体、改进措施、预期效果
3. 示例: "针对每周学习时间不足3小时的15名学生（38.5%），建议增加每周1次答疑时段"
"""
        else:
            suggestion_guidance = """
【建议要求】
1. 每条建议对应一条数据发现，必须引用证据表中的数据
2. 建议必须具体可落地，包含：目标、措施、预期效果
3. 维度覆盖：定价策略、产品组合、区域管理、客户经营、成本控制
4. 每条发现必须包含：结论、规模、比较基准、原因线索、业务含义
"""

        prompt = f"""{self.persona}

请根据统计结果和证据表，生成核心数据发现和改进建议。

【数据画像】
{json.dumps(data_profile, ensure_ascii=False, indent=2)[:2000]}

【已执行任务数】{len(valid_tasks)}

【统计结果】
预扫描发现 {sig_count} 个统计显著（p<0.05）的结果。

{problems_context}

{evidence_block}

{suggestion_guidance}

{self._build_common_constraints()}

【数据发现要求】
1. 每条发现必须引用具体统计量（来自证据表或stats_results）
2. 每条发现包含：明确结论、规模数据、比较基准、原因线索、业务含义
3. 重要性评分: 5=对业务决策至关重要, 1=仅描述性观察
4. 优先筛选有实质性内容的发现（5-8条），按重要性排序
"""
        messages = [{"role": "user", "content": prompt}]
        response = self._call_with_retry(messages, response_format=FindingsAndSuggestionsResponse)
        return response.findings, response.suggestions

    # ==================================================================
    # Round 4: 正式报告写作（report_writing）
    # ==================================================================

    def generate_report(
        self,
        data_profile: Dict,
        stats_results: Dict,
        findings: List[DataFinding],
        suggestions: List[Suggestion],
        evidence_table=None,
        business_results: Optional[Dict] = None,
        user_requirement: str = "",
        valid_tasks: Optional[List[Dict]] = None,
    ) -> str:
        """Round 4: 生成正式的、语言润色后的分析报告。"""
        if self.offline_mode:
            return self._offline_generate_report(findings, suggestions, data_profile)

        evidence_block = self._build_evidence_block(evidence_table)

        # 业务分析结果摘要
        biz_summary = ""
        if business_results:
            biz_parts = []
            for module, result in business_results.items():
                if isinstance(result, dict) and "error" not in result:
                    summary_key = None
                    if module == "loss_driver":
                        summary_key = "top_loss_contributors"
                        if summary_key in result:
                            top_items = result[summary_key][:3]
                            biz_parts.append("亏损驱动: " + "; ".join(
                                f"{i.get('dimension_display','')}/{i.get('name','')} 亏损贡献{i.get('loss_contribution_pct',0):.1f}%"
                                for i in top_items
                            ))
                    elif module == "discount_response":
                        tp = result.get("profit_tipping_point", {})
                        if tp.get("tipping_bin"):
                            biz_parts.append(f"折扣阈值: {tp['description']}")
                    elif module == "pareto":
                        pc = result.get("product_concentration", {})
                        if pc.get("concentration_metrics"):
                            m = pc["concentration_metrics"]
                            biz_parts.append(f"集中度: 前5商品贡献{m.get('top5_pct',0):.1f}%销售")
                    elif module == "cross_dimension":
                        biz_parts.append(f"交叉维度: {result.get('summary', {}).get('successful', 0)}个有效组合")
            if biz_parts:
                biz_summary = "\n".join(f"- {p}" for p in biz_parts)
                biz_summary = f"\n【业务分析摘要】\n{biz_summary}\n"

        # 发现和建议摘要
        findings_text = "\n".join(
            f"- [{f.importance}★] {f.conclusion}（{f.evidence[:100]}）"
            for f in sorted(findings, key=lambda x: x.importance, reverse=True)[:8]
        )
        suggestions_text = "\n".join(
            f"- {s.suggestion}（{s.evidence[:80]}）"
            for s in suggestions[:5]
        )

        if self.is_education:
            report_guidance = """
【报告风格】
- 面向教师和教学管理者
- 语言专业但易懂
- 重点围绕教学改进方向
"""
        else:
            report_guidance = """
【报告风格】
- 面向业务管理者和分析师
- 语言专业、简洁、直接
- 每个重要发现必须包含：结论、规模、比较基准、原因线索、经营含义
- 使用表格呈现排名和对比数据
- 不重复执行摘要和优先结论
- 不包含"生成了多少发现、验证得分多少"等过程信息
- 不要通过重复文字或空页来制造"内容充分"
"""

        prompt = f"""{self.persona}

你是报告写作专家。请基于以下所有分析结果，撰写一份正式的数据分析报告。

【用户需求】{user_requirement}

【数据概况】
- 行数: {data_profile.get('meta', {}).get('n_rows', '?')}
- 列数: {data_profile.get('meta', {}).get('n_columns', '?')}

{biz_summary}

【证据表】
{evidence_block[:3000]}

【核心发现】
{findings_text}

【改进建议】
{suggestions_text}

{report_guidance}

{self._build_common_constraints()}

【报告结构要求】
1. 执行摘要（关键结论3-5条，每条≤2句话）
2. 数据概况（粒度说明、实体识别、关键数字）
3. 核心分析发现（按重要性排列，每项含结论+规模+基准+原因线索+业务含义）
4. 优先建议（排序、含预期影响和实施难度）
5. 局限性说明

【格式】
- 使用 Markdown
- 重要数据使用表格呈现
- 不使用 "可能/大概/也许" 等模糊词汇
- 统计显著标注为（p<0.05）或（p<0.01），不标注为（显著）
"""
        messages = [{"role": "user", "content": prompt}]
        response = self._call_with_retry(messages)
        return response.choices[0].message.content

    # ==================================================================
    # 工具方法
    # ==================================================================

    @staticmethod
    def _count_significant_results(stats_results: Dict) -> int:
        """统计 p<0.05 的显著结果数量。"""
        count = 0
        alpha = 0.05
        for section in ["hypothesis_tests", "anova", "chi_square_goodness_of_fit"]:
            tests = stats_results.get(section, {}).get("tests", {})
            for item in tests.values():
                if isinstance(item, dict):
                    if "p_value" in item:
                        p = item["p_value"]
                        if isinstance(p, (int, float)) and p < alpha:
                            count += 1
                    for val in item.values():
                        if isinstance(val, dict) and "p_value" in val:
                            p = val["p_value"]
                            if isinstance(p, (int, float)) and p < alpha:
                                count += 1
        return count

    # ==================================================================
    # 离线模式支持
    # ==================================================================

    def _load_offline_questions(self) -> List[CandidateQuestion]:
        """加载预生成的候选问题。"""
        logger.info("离线模式：生成通用候选问题")
        return [
            CandidateQuestion(
                question="不同类别在数值指标上是否存在显著差异？",
                variables=["category", "value"],
                method="ANOVA",
                value="了解组间差异",
            ),
            CandidateQuestion(
                question="两个数值变量之间是否存在显著相关性？",
                variables=["var1", "var2"],
                method="相关性分析",
                value="探索变量关系",
            ),
        ]

    def _offline_discover_problems(self, stats_results: Dict) -> List[DiscoveredProblem]:
        """离线模式下生成通用问题。"""
        return [
            DiscoveredProblem(
                problem="数据中的异常模式和结构性矛盾",
                rationale="从描述性统计中发现偏离预期的模式",
                evidence_preview="基于统计结果中的离群值和分布特征",
                suggested_angle="关注偏离整体趋势2个标准差以上的子群体",
            ),
            DiscoveredProblem(
                problem="关键维度的交互效应",
                rationale="单因素分析可能掩盖重要的交互作用",
                evidence_preview="检查不同维度交叉后是否出现反转",
                suggested_angle="对比双因素交互与单因素主效应的差异",
            ),
        ]

    def _load_offline_findings_suggestions(
        self, stats_results: Dict
    ) -> tuple:
        """从统计结果自动生成发现和建议。"""
        logger.info("离线模式：基于统计结果自动生成发现和建议")
        return self._generate_offline_findings_suggestions(stats_results)

    def _generate_offline_findings_suggestions(
        self, stats_results: Dict
    ) -> tuple:
        """自动提取显著结果生成发现。"""
        from config import clean_field_name

        findings: List[DataFinding] = []
        suggestions: List[Suggestion] = []
        alpha = 0.05

        # 扫描 ANOVA
        anova = stats_results.get("anova", {}).get("tests", {})
        for name, test in anova.items():
            if not isinstance(test, dict) or "error" in str(test):
                continue
            p = test.get("p_value")
            if isinstance(p, (int, float)) and p < alpha:
                factor = clean_field_name(str(test.get("factor", "")))
                dep = clean_field_name(str(test.get("dependent", "")))
                findings.append(DataFinding(
                    conclusion=f"{factor}在{dep}上存在显著组间差异",
                    evidence=f"F={test.get('F_statistic', 0):.2f}, p={p:.4f}",
                    method="ANOVA",
                    importance=5 if p < 0.01 else 4,
                    evidence_ref=f"anova.{name}",
                    magnitude=f"涉及{test.get('n_groups', '?')}个组",
                ))

        # 扫描假设检验
        ht = stats_results.get("hypothesis_tests", {}).get("tests", {})
        for name, test in ht.items():
            if isinstance(test, dict) and "p_value" in test and "error" not in str(test):
                p = test["p_value"]
                if isinstance(p, (int, float)) and p < alpha:
                    var_info = test.get("variables", test.get("column", ""))
                    stat_val = test.get("t_statistic") or test.get("statistic")
                    findings.append(DataFinding(
                        conclusion=f"检测到统计显著的组间差异",
                        evidence=f"{test.get('method','?')}: p={p:.4f}",
                        method=test.get("method", "假设检验"),
                        importance=4 if p < 0.01 else 3,
                    ))

        # 补足至最少5条
        if len(findings) < 5:
            pe = stats_results.get("point_estimation", {}).get("fields", {})
            added = 0
            for col, info in pe.items():
                if len(findings) >= 8:
                    break
                if isinstance(info, dict) and "cv_pct" in info:
                    col_display = clean_field_name(str(col))
                    cv = info.get("cv_pct", 0)
                    cv_desc = "低" if cv < 20 else ("中等" if cv < 50 else "高")
                    findings.append(DataFinding(
                        conclusion=f"{col_display}的平均值为{info.get('mean',0):.2f}，变异程度{cv_desc}（CV={cv:.1f}%）",
                        evidence=f"均值={info.get('mean',0):.2f}, 标准差={info.get('std',0):.2f}",
                        method="描述性统计",
                        importance=2,
                    ))
                    added += 1
                    if added >= 5:
                        break

        findings.sort(key=lambda x: x.importance, reverse=True)
        findings = findings[:8]

        # 生成建议
        for i, f in enumerate(findings[:5]):
            suggestions.append(Suggestion(
                suggestion=f"针对「{f.conclusion[:30]}...」制定专项改进措施",
                evidence=f.evidence,
                direction="基于数据特征，制定针对性的改进方案并追踪效果",
                priority_score=max(3, f.importance),
            ))

        return findings, suggestions[:5]

    def _offline_generate_report(
        self,
        findings: List[DataFinding],
        suggestions: List[Suggestion],
        data_profile: Dict,
    ) -> str:
        """离线模式生成简单报告。"""
        meta = data_profile.get("meta", {})
        lines = [
            f"# 数据分析报告（离线模式）",
            "",
            f"数据规模: {meta.get('n_rows', '?')} 行 × {meta.get('n_columns', '?')} 列",
            "",
            "## 主要发现",
        ]
        for f in findings[:8]:
            lines.append(f"- [{f.importance}★] {f.conclusion}")
            lines.append(f"  证据: {f.evidence}")
        lines.extend(["", "## 改进建议"])
        for s in suggestions[:5]:
            lines.append(f"- {s.suggestion}")
        return "\n".join(lines)
