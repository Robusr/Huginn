# -*- coding: utf-8 -*-
"""
@File    : llm_client.py
@Author  : Robusr
@Date    : 2026/6/10 15:59
@Description: DeepSeek API 封装
@Software: PyCharm
"""

"""
DeepSeek API 客户端封装
结构化输出候选问题、数据发现和课程建议
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

# 加载环境变量
load_dotenv()

# ------------------------------
# 结构化输出模型定义（Pydantic v2）
# ------------------------------
class CandidateQuestion(BaseModel):
    """单个候选分析问题的结构化格式"""
    question: str = Field(description="自然语言描述的分析问题，必须围绕课程教学改进")
    variables: List[str] = Field(description="涉及的变量名，必须与数据画像中的column字段完全一致")
    method: str = Field(
        description="建议使用的统计方法，只能从以下选择：t检验、配对t检验、ANOVA、卡方检验、相关性分析、分布检验"
    )
    value: str = Field(description="该问题的业务分析价值，说明为什么值得研究")

class CandidateQuestionsResponse(BaseModel):
    """候选问题列表的输出格式"""
    questions: List[CandidateQuestion] = Field(description="8-12个候选分析问题，必须覆盖至少2个ANOVA、2个卡方、3个t检验")

class DataFinding(BaseModel):
    """单个数据发现的结构化格式"""
    conclusion: str = Field(description="基于统计结果的明确结论，不能模糊")
    evidence: str = Field(description="数据依据，必须引用具体的统计量和p值，例如：'F=4.23, p=0.023'")
    method: str = Field(description="使用的统计方法")
    importance: int = Field(description="重要性评分，1-5分，5分最高")

class CourseSuggestion(BaseModel):
    """单个课程建议的结构化格式"""
    suggestion: str = Field(description="具体可落地的改进建议，不能泛泛而谈")
    evidence: str = Field(description="支撑该建议的数据发现，引用具体结论")
    direction: str = Field(description="具体的改进方向和预期效果")

class FindingsAndSuggestionsResponse(BaseModel):
    """发现和建议的统一输出格式"""
    findings: List[DataFinding] = Field(description="5-8条核心数据发现，按重要性从高到低排序")
    suggestions: List[CourseSuggestion] = Field(description="3-5条针对性课程建议，与发现一一对应")

# ------------------------------
# DeepSeek API 客户端核心
# ------------------------------
class LLMClient:
    def __init__(self, offline_mode: bool = False):
        """
        初始化LLM客户端
        :param offline_mode: 离线模式，仅加载预生成的结果，不调用API
        """
        self.offline_mode = offline_mode
        if not offline_mode:
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", Config.LLM_BASE_URL),
            )
            self.model = Config.LLM_MODEL
            self.max_retries = Config.LLM_MAX_RETRIES
            self.retry_delay = Config.LLM_RETRY_DELAY

    def _call_with_retry(self, messages: List[Dict], response_format: Optional[BaseModel] = None) -> Any:
        """带重试机制的API调用，处理速率限制和超时

        DeepSeek API 不支持 beta.chat.completions.parse 结构化输出，
        因此使用 json_object 模式 + 手动 Pydantic 解析。
        """
        if self.offline_mode:
            raise Exception("离线模式下无法调用API")

        # 如果需要结构化输出，预先构造带 JSON Schema 的消息（避免重试时重复拼接）
        if response_format:
            schema_json = response_format.model_json_schema()
            schema_str = json.dumps(schema_json, ensure_ascii=False)
            augmented_messages = [
                *messages[:-1],
                {
                    "role": messages[-1]["role"],
                    "content": messages[-1]["content"] + (
                        f"\n\n【输出格式要求 - 必须严格遵守的JSON Schema】\n{schema_str}"
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
                    # 手动解析 JSON 响应为 Pydantic 模型
                    content = response.choices[0].message.content
                    parsed_dict = json.loads(content)
                    return response_format.model_validate(parsed_dict)

                return response
            except RateLimitError:
                if attempt == self.max_retries - 1:
                    raise Exception("DeepSeek API 速率限制超限，请等待1分钟后重试")
                wait_time = self.retry_delay * (attempt + 1)
                logger.warning("速率限制触发，等待 %d 秒后重试...", wait_time)
                time.sleep(wait_time)
            except APITimeoutError:
                if attempt == self.max_retries - 1:
                    raise Exception("DeepSeek API 超时，请检查网络连接")
                time.sleep(self.retry_delay)
            except APIError as e:
                raise Exception(f"DeepSeek API 调用失败: {str(e)}")

    def generate_candidate_questions(self, data_profile: Dict, user_requirement: str) -> List[CandidateQuestion]:
        """
        基于数据画像和用户需求生成候选分析问题
        :param data_profile: data_profiler.py生成的数据画像JSON
        :param user_requirement: 用户输入的分析需求
        :return: 候选问题列表
        """
        if self.offline_mode:
            return self._load_offline_questions()

        prompt = f"""
你是一位专业的教育数据分析专家。请根据以下数据画像和用户需求，提出8-12个有业务价值的统计分析问题。

【数据画像】
{json.dumps(data_profile, ensure_ascii=False, indent=2)}

【用户需求】
{user_requirement}

【严格要求】
1. 所有问题必须围绕课程教学改进展开，具有实际指导意义
2. 每个问题必须明确标注涉及的变量，变量名必须与数据画像中的column字段完全一致，不能写错
3. 建议的统计方法只能从以下列表选择：t检验、配对t检验、ANOVA、卡方检验、相关性分析、分布检验
4. 优先选择能体现群体差异、模块难度、学习效果相关性的问题
5. 强制要求：至少包含2个ANOVA问题、2个卡方检验问题、3个t检验问题
6. 输出必须严格符合指定的JSON格式，不能有任何额外的解释、markdown标记或注释
"""
        messages = [{"role": "user", "content": prompt}]
        response = self._call_with_retry(messages, response_format=CandidateQuestionsResponse)
        return response.questions

    def generate_findings_and_suggestions(
        self,
        stats_results: Dict,
        data_profile: Dict,
        executed_tasks: List[Dict]
    ) -> tuple[List[DataFinding], List[CourseSuggestion]]:
        """
        基于统计结果生成主要发现和课程建议
        :param stats_results: analysis_engine.py生成的统计结果JSON
        :param data_profile: 数据画像JSON
        :param executed_tasks: 已执行的任务列表
        :return: (数据发现列表, 课程建议列表)
        """
        if self.offline_mode:
            return self._load_offline_findings_suggestions()

        # 预扫描：统计显著结果数量，帮助LLM判断数据质量
        sig_count = self._count_significant_results(stats_results)

        prompt = f"""
你是一位严谨的教育数据分析专家。请根据以下统计结果和数据画像，生成主要数据发现和课程改进建议。

【数据画像】
{json.dumps(data_profile, ensure_ascii=False, indent=2)}

【已执行的统计任务】
{json.dumps(executed_tasks, ensure_ascii=False, indent=2)}

【统计结果】
{json.dumps(stats_results, ensure_ascii=False, indent=2)}

【预扫描信息】
本次分析共发现 {sig_count} 个统计显著（p<0.05）的结果。

【绝对禁止】
1. 禁止编造任何数据或统计量，所有结论必须严格基于提供的统计结果
2. 禁止将相关性表述为因果关系——必须使用"相关"、"关联"而非"导致"、"影响"、"造成"
3. 严格禁止引用p≥0.05的结果作为"显著发现"——p≥0.05意味着"无统计显著差异/关联"
4. 禁止添加任何没有数据支撑的主观臆断
5. 禁止使用"可能"、"大概"、"也许"等模糊词汇
6. 禁止使用"维持现状"、"无需改变"、"保持现有策略"等消极表述作为建议

【p≥0.05 结果的正确处理方式】
- 如果某个分析的p≥0.05，说明该分析未能发现统计显著的差异或关联
- 你可以将其作为"探索性发现"提及，但必须在结论中明确指出"未发现统计显著证据"
- 重要性评分应为1-2分（因为统计证据不足）
- 不要将"无显著差异"包装成正面发现

【数据发现要求】
1. 每个发现必须引用具体的统计量和p值，例如："模块A的平均难度显著高于其他模块（F=4.23, p=0.023）"
2. 优先筛选p<0.05的显著结果作为主要发现（重要性4-5分）
3. 如果显著结果不足5个，可以用p<0.15的"边际显著"结果补充（重要性2-3分），并明确标注"边际显著"
4. 如果几乎无显著结果，诚实说明"本次数据未发现统计显著的模式"，并从描述性统计中提炼有价值的观察
5. 主要发现筛选5-8条，按重要性从高到低排序

【课程建议要求】
1. 每条建议必须对应一条数据发现，引用具体证据
2. 即使数据中缺乏显著结果，也应基于描述性统计（如频数分布、均值对比）提出观察性建议
3. 建议必须具体可落地，包含：目标群体、改进措施、预期效果
4. 示例正确格式："针对每周学习时间不足3小时的15名学生（占比38.5%），建议增加每周1次答疑时段，预期将作业完成率提升20%"
5. 如果数据中揭示了学生行为模式（如时间分配、座位选择），即使无统计显著性也可作为观察性建议的依据
6. 输出3-5条课程建议
7. 输出必须严格符合指定的JSON格式，不能有任何额外的解释或markdown标记
"""
        messages = [{"role": "user", "content": prompt}]
        response = self._call_with_retry(messages, response_format=FindingsAndSuggestionsResponse)
        return response.findings, response.suggestions

    @staticmethod
    def _count_significant_results(stats_results: Dict) -> int:
        """预扫描统计结果，统计p<0.05的显著结果数量。"""
        count = 0
        alpha = 0.05

        # 扫描假设检验
        ht = stats_results.get("hypothesis_tests", {}).get("tests", {})
        for test_group in ht.values():
            if not isinstance(test_group, dict):
                continue
            if "p_value" in test_group:
                p = test_group["p_value"]
                if isinstance(p, (int, float)) and p < alpha:
                    count += 1
            for val in test_group.values():
                if isinstance(val, dict) and "p_value" in val:
                    p = val["p_value"]
                    if isinstance(p, (int, float)) and p < alpha:
                        count += 1

        # 扫描 ANOVA
        anova = stats_results.get("anova", {}).get("tests", {})
        for item in anova.values():
            if isinstance(item, dict) and "p_value" in item:
                p = item["p_value"]
                if isinstance(p, (int, float)) and p < alpha:
                    count += 1

        # 扫描卡方
        chi = stats_results.get("chi_square_goodness_of_fit", {}).get("tests", {})
        for item in chi.values():
            if isinstance(item, dict) and "p_value" in item:
                p = item["p_value"]
                if isinstance(p, (int, float)) and p < alpha:
                    count += 1

        return count

    # ------------------------------
    # 离线模式支持（用于演示）
    # ------------------------------
    def _load_offline_questions(self) -> List[CandidateQuestion]:
        """加载预生成的候选问题（离线演示用）"""
        logger.info("离线模式：加载预生成的候选问题")
        return [
            CandidateQuestion(
                question="不同专业的学生对课程整体满意度是否存在显著差异？",
                variables=["整体满意度", "专业"],
                method="ANOVA",
                value="了解不同专业学生的满意度差异，便于针对性调整教学内容"
            ),
            CandidateQuestion(
                question="是否及格的学生在模块3难度评分上是否存在显著差异？",
                variables=["模块3难度", "是否及格"],
                method="t检验",
                value="识别影响学生及格率的关键难点模块"
            )
        ]

    def _load_offline_findings_suggestions(self) -> tuple[List[DataFinding], List[CourseSuggestion]]:
        """加载预生成的发现和建议（离线演示用）"""
        logger.info("离线模式：加载预生成的发现和建议")
        findings = [
            DataFinding(
                conclusion="计算机专业学生的整体满意度显著低于其他专业",
                evidence="F=5.67, p=0.004",
                method="单因素方差分析",
                importance=5
            )
        ]
        suggestions = [
            CourseSuggestion(
                suggestion="针对计算机专业学生增加实践案例和编程练习",
                evidence="计算机专业学生整体满意度显著低于其他专业",
                direction="将理论课时与实践课时比例调整为1:1，预期满意度提升15%"
            )
        ]
        return findings, suggestions