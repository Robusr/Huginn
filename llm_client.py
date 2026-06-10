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
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
            )
            self.model = os.getenv("LLM_MODEL", "deepseek-chat")
            self.max_retries = 3
            self.retry_delay = 3  # DeepSeek免费用户速率限制较严格

    def _call_with_retry(self, messages: List[Dict], response_format: Optional[BaseModel] = None) -> Any:
        """带重试机制的API调用，处理速率限制和超时"""
        if self.offline_mode:
            raise Exception("离线模式下无法调用API")

        for attempt in range(self.max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.05,  # 极低温度保证结果稳定、无幻觉
                    "top_p": 0.95,
                    "max_tokens": 4096
                }
                if response_format:
                    kwargs["response_format"] = response_format
                return self.client.beta.chat.completions.parse(**kwargs)
            except RateLimitError:
                if attempt == self.max_retries - 1:
                    raise Exception("DeepSeek API 速率限制超限，请等待1分钟后重试")
                wait_time = self.retry_delay * (attempt + 1)
                print(f"⚠️  速率限制触发，等待 {wait_time} 秒后重试...")
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
        return response.choices[0].message.parsed.questions

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

        prompt = f"""
你是一位严谨的教育数据分析专家。请根据以下统计结果和数据画像，生成主要数据发现和课程改进建议。

【数据画像】
{json.dumps(data_profile, ensure_ascii=False, indent=2)}

【已执行的统计任务】
{json.dumps(executed_tasks, ensure_ascii=False, indent=2)}

【统计结果】
{json.dumps(stats_results, ensure_ascii=False, indent=2)}

【绝对禁止】
1. 禁止编造任何数据，所有结论必须严格基于提供的统计结果
2. 禁止将相关性表述为因果关系，必须使用"相关"而非"导致"
3. 禁止引用p≥0.05的结果作为显著发现
4. 禁止添加任何没有数据支撑的主观臆断
5. 禁止使用"可能"、"大概"等模糊词汇

【要求】
1. 每个发现必须引用具体的统计量和p值，例如："模块A的平均难度显著高于其他模块（F=4.23, p=0.023）"
2. 主要发现筛选最有价值的5-8条，按重要性从高到低排序
3. 课程建议必须与数据发现一一对应，每条建议要有明确的数据依据和可落地的改进方向
4. 输出必须严格符合指定的JSON格式，不能有任何额外的解释或markdown标记
"""
        messages = [{"role": "user", "content": prompt}]
        response = self._call_with_retry(messages, response_format=FindingsAndSuggestionsResponse)
        parsed = response.choices[0].message.parsed
        return parsed.findings, parsed.suggestions

    # ------------------------------
    # 离线模式支持（用于演示）
    # ------------------------------
    def _load_offline_questions(self) -> List[CandidateQuestion]:
        """加载预生成的候选问题（离线演示用）"""
        print("⚠️  离线模式：加载预生成的候选问题")
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
        print("⚠️  离线模式：加载预生成的发现和建议")
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