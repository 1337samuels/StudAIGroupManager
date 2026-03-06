#!/usr/bin/env python3
"""AI Service - Multiple AI provider backends gated behind feature flags."""

import os
import json
import logging
import time
from datetime import datetime

from config.feature_flags import (
    USE_OPENAI_DIRECT, AB_AI_MODEL_GPT4, ENABLE_LOCAL_LLM_FALLBACK,
    ENABLE_AI_STUDY_RECOMMENDATIONS, ENABLE_AI_CONFLICT_RESOLUTION,
    ENABLE_ASSIGNMENT_PRIORITY_SCORING, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)


# ==================== AI PROVIDER ABSTRACTION ====================

class AIProvider:
    """Base class for AI providers"""
    def query(self, messages, stream=False):
        raise NotImplementedError

    def get_model_name(self):
        raise NotImplementedError


class AzureOpenAIProvider(AIProvider):
    """Azure OpenAI provider (default). Used when USE_OPENAI_DIRECT is False."""

    def __init__(self):
        self.client = None
        self.deployment_name = ''
        try:
            with open('AI_API_KEYS.json', 'r') as f:
                config = json.load(f)
            self.deployment_name = config.get('deployment_name', '')
            from openai import AzureOpenAI
            self.client = AzureOpenAI(api_key=config.get('api_key', ''),
                                       api_version=config.get('api_version', '2024-02-01'),
                                       azure_endpoint=config.get('endpoint', ''))
        except Exception as e:
            logger.warning(f"Azure OpenAI init failed: {e}")

    def query(self, messages, stream=False):
        if not self.client:
            raise RuntimeError("Azure OpenAI client not initialized")
        model = self.deployment_name + ("-gpt4o" if AB_AI_MODEL_GPT4 else "")
        if AB_AI_MODEL_GPT4:
            logger.info("A/B test: Using GPT-4o model")
        response = self.client.chat.completions.create(model=model, messages=messages, stream=stream)
        return response if stream else response.choices[0].message.content

    def get_model_name(self):
        return f"{self.deployment_name}-gpt4o (A/B test)" if AB_AI_MODEL_GPT4 else self.deployment_name


class DirectOpenAIProvider(AIProvider):
    """Direct OpenAI API. Used when USE_OPENAI_DIRECT is True."""

    def __init__(self):
        if not USE_OPENAI_DIRECT:
            raise RuntimeError("Direct OpenAI is not enabled")
        self.client = None
        api_key = os.environ.get('OPENAI_API_KEY', '')
        if api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            except Exception as e:
                logger.error(f"OpenAI init failed: {e}")

    def query(self, messages, stream=False):
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        model = "gpt-4o" if AB_AI_MODEL_GPT4 else "gpt-3.5-turbo"
        response = self.client.chat.completions.create(model=model, messages=messages, stream=stream)
        return response if stream else response.choices[0].message.content

    def get_model_name(self):
        return "gpt-4o" if AB_AI_MODEL_GPT4 else "gpt-3.5-turbo"


class LocalLLMProvider(AIProvider):
    """Local LLM via Ollama. Fallback when ENABLE_LOCAL_LLM_FALLBACK is True."""

    def __init__(self):
        if not ENABLE_LOCAL_LLM_FALLBACK:
            raise RuntimeError("Local LLM fallback is not enabled")
        self.model = os.environ.get('LOCAL_LLM_MODEL', 'llama3.2')
        logger.info(f"Local LLM provider: {self.model}")

    def query(self, messages, stream=False):
        logger.info(f"Local LLM query with {self.model}")
        return "[Local LLM response - Ollama not available in demo]"

    def get_model_name(self):
        return f"ollama/{self.model}"


# ==================== AI SERVICE ====================

class AIService:
    """Routes AI requests to the appropriate provider based on feature flags."""

    def __init__(self):
        self.provider = self._get_provider()

    def _get_provider(self):
        if USE_OPENAI_DIRECT:
            try:
                return DirectOpenAIProvider()
            except Exception:
                if ENABLE_LOCAL_LLM_FALLBACK:
                    return LocalLLMProvider()
        try:
            return AzureOpenAIProvider()
        except Exception:
            if ENABLE_LOCAL_LLM_FALLBACK:
                return LocalLLMProvider()
        return None

    def query(self, messages, stream=False):
        if not self.provider:
            raise RuntimeError("No AI provider available")
        try:
            return self.provider.query(messages, stream)
        except Exception as e:
            if ENABLE_LOCAL_LLM_FALLBACK and not isinstance(self.provider, LocalLLMProvider):
                return LocalLLMProvider().query(messages, stream)
            raise

    def get_model_info(self):
        if not self.provider:
            return {"model": "none", "provider": "none"}
        return {"model": self.provider.get_model_name(), "provider": type(self.provider).__name__,
                "ab_test_gpt4": AB_AI_MODEL_GPT4, "local_fallback": ENABLE_LOCAL_LLM_FALLBACK}


# ==================== AI FEATURES ====================

class StudyRecommendationEngine:
    """AI study recommendations. Gated behind ENABLE_AI_STUDY_RECOMMENDATIONS."""

    def __init__(self, ai_service=None):
        if not ENABLE_AI_STUDY_RECOMMENDATIONS:
            return
        self.ai = ai_service or AIService()

    @feature_flag('ENABLE_AI_STUDY_RECOMMENDATIONS')
    def get_pairing_recommendations(self, members, assignments):
        return self.ai.query([{"role": "system", "content": "Match study partners by complementary skills."},
                              {"role": "user", "content": f"Members: {json.dumps(members)}\nAssignments: {json.dumps(assignments)}"}])

    @feature_flag('ENABLE_AI_STUDY_RECOMMENDATIONS')
    def get_study_plan(self, member, assignments, schedule):
        return self.ai.query([{"role": "system", "content": "Create a personalized study plan."},
                              {"role": "user", "content": f"Member: {json.dumps(member)}\nAssignments: {json.dumps(assignments)}"}])


class ConflictResolutionEngine:
    """AI scheduling conflict resolution. Gated behind ENABLE_AI_CONFLICT_RESOLUTION."""

    def __init__(self, ai_service=None):
        if not ENABLE_AI_CONFLICT_RESOLUTION:
            return
        self.ai = ai_service or AIService()

    @feature_flag('ENABLE_AI_CONFLICT_RESOLUTION')
    def detect_conflicts(self, schedules):
        conflicts = []
        for i, a in enumerate(schedules):
            for b in schedules[i+1:]:
                if a.get('start', 0) < b.get('end', 0) and b.get('start', 0) < a.get('end', 0):
                    conflicts.append({'member_a': a.get('member'), 'member_b': b.get('member')})
        return conflicts

    @feature_flag('ENABLE_AI_CONFLICT_RESOLUTION')
    def suggest_resolution(self, conflicts, available_slots):
        if not conflicts:
            return []
        return self.ai.query([{"role": "system", "content": "Suggest optimal scheduling conflict resolutions."},
                              {"role": "user", "content": f"Conflicts: {json.dumps(conflicts)}"}])


class AssignmentPriorityScorer:
    """AI assignment priority scoring. Gated behind ENABLE_ASSIGNMENT_PRIORITY_SCORING."""

    PRIORITY_WEIGHTS = {'deadline_urgency': 0.35, 'difficulty_level': 0.25,
                        'expertise_match': 0.20, 'group_impact': 0.20}

    def __init__(self, ai_service=None):
        if not ENABLE_ASSIGNMENT_PRIORITY_SCORING:
            return
        self.ai = ai_service or AIService()

    @feature_flag('ENABLE_ASSIGNMENT_PRIORITY_SCORING')
    def score_assignments(self, assignments, members):
        scored = []
        for a in assignments:
            score = 0.5  # Simplified scoring
            label = "CRITICAL" if score >= 0.8 else "HIGH" if score >= 0.6 else "MEDIUM" if score >= 0.4 else "LOW"
            scored.append({**a, 'priority_score': score, 'priority_label': label})
        scored.sort(key=lambda x: x['priority_score'], reverse=True)
        return scored

    @feature_flag('ENABLE_ASSIGNMENT_PRIORITY_SCORING')
    def get_ai_priority_analysis(self, assignments, members):
        return self.ai.query([{"role": "system", "content": "Analyze assignment priorities."},
                              {"role": "user", "content": f"Assignments: {json.dumps(assignments, default=str)}"}])
