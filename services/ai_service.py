#!/usr/bin/env python3
"""
AI Service
Handles AI-powered features with multiple provider backends.
Feature flags control which AI provider is used and which AI features are active.
"""

import os
import json
import hashlib
import logging
import time
from datetime import datetime

from config.feature_flags import (
    USE_OPENAI_DIRECT,
    AB_AI_MODEL_GPT4,
    ENABLE_LOCAL_LLM_FALLBACK,
    ENABLE_AI_STUDY_RECOMMENDATIONS,
    ENABLE_AI_CONFLICT_RESOLUTION,
    ENABLE_ASSIGNMENT_PRIORITY_SCORING,
    is_flag_enabled,
    feature_flag,
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
    """
    Azure OpenAI provider (default).
    Used when USE_OPENAI_DIRECT is False.
    """

    def __init__(self):
        self.api_key = None
        self.endpoint = None
        self.deployment_name = None
        self.api_version = None
        self.client = None
        self._load_config()

    def _load_config(self):
        """Load Azure OpenAI configuration"""
        try:
            with open('AI_API_KEYS.json', 'r') as f:
                config = json.load(f)
            self.api_key = config.get('api_key', '')
            self.endpoint = config.get('endpoint', '')
            self.deployment_name = config.get('deployment_name', '')
            self.api_version = config.get('api_version', '2024-02-01')

            # Import only when needed
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
            )
            logger.info("Azure OpenAI provider initialized")
        except FileNotFoundError:
            logger.warning("AI_API_KEYS.json not found - Azure OpenAI disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI: {e}")

    def query(self, messages, stream=False):
        """Query Azure OpenAI"""
        if not self.client:
            raise RuntimeError("Azure OpenAI client not initialized")

        if AB_AI_MODEL_GPT4:
            # A/B test: use GPT-4o model
            model = self.deployment_name + "-gpt4o"
            logger.info("A/B test: Using GPT-4o model")
        else:
            model = self.deployment_name

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
        )

        if stream:
            return response
        return response.choices[0].message.content

    def get_model_name(self):
        if AB_AI_MODEL_GPT4:
            return f"{self.deployment_name}-gpt4o (A/B test)"
        return self.deployment_name


class DirectOpenAIProvider(AIProvider):
    """
    Direct OpenAI API provider.
    Used when USE_OPENAI_DIRECT is True.
    """

    def __init__(self):
        if not USE_OPENAI_DIRECT:
            raise RuntimeError("Direct OpenAI is not enabled")

        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info("Direct OpenAI provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")

    def query(self, messages, stream=False):
        """Query OpenAI directly"""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")

        if AB_AI_MODEL_GPT4:
            model = "gpt-4o"
        else:
            model = "gpt-3.5-turbo"

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
        )

        if stream:
            return response
        return response.choices[0].message.content

    def get_model_name(self):
        if AB_AI_MODEL_GPT4:
            return "gpt-4o"
        return "gpt-3.5-turbo"


class LocalLLMProvider(AIProvider):
    """
    Local LLM provider using Ollama.
    Used as fallback when ENABLE_LOCAL_LLM_FALLBACK is True.
    """

    DEFAULT_MODEL = "llama3.2"
    OLLAMA_URL = "http://localhost:11434"

    def __init__(self):
        if not ENABLE_LOCAL_LLM_FALLBACK:
            raise RuntimeError("Local LLM fallback is not enabled")

        self.model = os.environ.get('LOCAL_LLM_MODEL', self.DEFAULT_MODEL)
        self.base_url = os.environ.get('OLLAMA_URL', self.OLLAMA_URL)
        logger.info(f"Local LLM provider initialized: {self.model} at {self.base_url}")

    def query(self, messages, stream=False):
        """Query local Ollama LLM"""
        # In production: use requests to call Ollama API
        # import requests
        # response = requests.post(f"{self.base_url}/api/chat", json={
        #     "model": self.model,
        #     "messages": messages,
        #     "stream": stream,
        # })
        logger.info(f"Local LLM query with {self.model}")
        return "[Local LLM response - Ollama not available in demo]"

    def get_model_name(self):
        return f"ollama/{self.model}"


# ==================== AI SERVICE ====================


class AIService:
    """
    Main AI service that routes requests to the appropriate provider.
    """

    def __init__(self):
        self.provider = self._get_provider()

    def _get_provider(self):
        """Get the appropriate AI provider based on feature flags"""
        if USE_OPENAI_DIRECT:
            try:
                return DirectOpenAIProvider()
            except Exception as e:
                logger.warning(f"Failed to init Direct OpenAI: {e}")
                if ENABLE_LOCAL_LLM_FALLBACK:
                    logger.info("Falling back to local LLM")
                    return LocalLLMProvider()

        # Default: Azure OpenAI
        try:
            return AzureOpenAIProvider()
        except Exception as e:
            logger.warning(f"Failed to init Azure OpenAI: {e}")
            if ENABLE_LOCAL_LLM_FALLBACK:
                logger.info("Falling back to local LLM")
                return LocalLLMProvider()

        return None

    def query(self, messages, stream=False):
        """Query the AI provider"""
        if not self.provider:
            raise RuntimeError("No AI provider available")

        try:
            return self.provider.query(messages, stream)
        except Exception as e:
            if ENABLE_LOCAL_LLM_FALLBACK and not isinstance(self.provider, LocalLLMProvider):
                logger.warning(f"Primary AI provider failed ({e}), falling back to local LLM")
                fallback = LocalLLMProvider()
                return fallback.query(messages, stream)
            raise

    def get_model_info(self):
        """Get information about the current AI model"""
        if not self.provider:
            return {"model": "none", "provider": "none"}
        return {
            "model": self.provider.get_model_name(),
            "provider": type(self.provider).__name__,
            "ab_test_gpt4": AB_AI_MODEL_GPT4,
            "local_fallback": ENABLE_LOCAL_LLM_FALLBACK,
        }


# ==================== AI FEATURES ====================


class StudyRecommendationEngine:
    """
    AI-powered study recommendations based on member backgrounds.
    Gated behind ENABLE_AI_STUDY_RECOMMENDATIONS flag.
    """

    def __init__(self, ai_service=None):
        if not ENABLE_AI_STUDY_RECOMMENDATIONS:
            logger.debug("AI study recommendations are disabled")
            return
        self.ai = ai_service or AIService()
        logger.info("StudyRecommendationEngine initialized")

    @feature_flag('ENABLE_AI_STUDY_RECOMMENDATIONS')
    def get_pairing_recommendations(self, members, assignments):
        """Generate optimal study pair recommendations"""
        messages = [
            {
                "role": "system",
                "content": "You are an expert at matching study partners based on complementary skills."
            },
            {
                "role": "user",
                "content": f"Given these members: {json.dumps(members)}\n"
                           f"And these assignments: {json.dumps(assignments)}\n"
                           f"Suggest optimal study pairs with rationale."
            }
        ]

        return self.ai.query(messages)

    @feature_flag('ENABLE_AI_STUDY_RECOMMENDATIONS')
    def get_study_plan(self, member, assignments, schedule):
        """Generate personalized study plan for a member"""
        messages = [
            {
                "role": "system",
                "content": "Create a personalized study plan considering the member's background and schedule."
            },
            {
                "role": "user",
                "content": f"Member: {json.dumps(member)}\n"
                           f"Assignments: {json.dumps(assignments)}\n"
                           f"Schedule: {json.dumps(schedule)}"
            }
        ]

        return self.ai.query(messages)


class ConflictResolutionEngine:
    """
    AI-powered scheduling conflict detection and resolution.
    Gated behind ENABLE_AI_CONFLICT_RESOLUTION flag.
    """

    def __init__(self, ai_service=None):
        if not ENABLE_AI_CONFLICT_RESOLUTION:
            logger.debug("AI conflict resolution is disabled")
            return
        self.ai = ai_service or AIService()
        logger.info("ConflictResolutionEngine initialized")

    @feature_flag('ENABLE_AI_CONFLICT_RESOLUTION')
    def detect_conflicts(self, schedules):
        """Detect scheduling conflicts across study group members"""
        conflicts = []
        for i, sched_a in enumerate(schedules):
            for sched_b in schedules[i+1:]:
                if self._times_overlap(sched_a, sched_b):
                    conflicts.append({
                        'member_a': sched_a.get('member'),
                        'member_b': sched_b.get('member'),
                        'time_a': sched_a.get('time'),
                        'time_b': sched_b.get('time'),
                    })
        return conflicts

    def _times_overlap(self, a, b):
        """Check if two time slots overlap"""
        return (a.get('start', 0) < b.get('end', 0) and
                b.get('start', 0) < a.get('end', 0))

    @feature_flag('ENABLE_AI_CONFLICT_RESOLUTION')
    def suggest_resolution(self, conflicts, available_slots):
        """Use AI to suggest conflict resolutions"""
        if not conflicts:
            return []

        messages = [
            {
                "role": "system",
                "content": "You are a scheduling expert. Suggest optimal resolutions for scheduling conflicts."
            },
            {
                "role": "user",
                "content": f"Conflicts: {json.dumps(conflicts)}\n"
                           f"Available slots: {json.dumps(available_slots)}"
            }
        ]

        return self.ai.query(messages)


class AssignmentPriorityScorer:
    """
    AI-based assignment priority scoring using member expertise matching.
    Gated behind ENABLE_ASSIGNMENT_PRIORITY_SCORING flag.
    """

    PRIORITY_WEIGHTS = {
        'deadline_urgency': 0.35,
        'difficulty_level': 0.25,
        'expertise_match': 0.20,
        'group_impact': 0.20,
    }

    def __init__(self, ai_service=None):
        if not ENABLE_ASSIGNMENT_PRIORITY_SCORING:
            logger.debug("Assignment priority scoring is disabled")
            return
        self.ai = ai_service or AIService()
        logger.info("AssignmentPriorityScorer initialized")

    @feature_flag('ENABLE_ASSIGNMENT_PRIORITY_SCORING')
    def score_assignments(self, assignments, members):
        """Score assignments by priority considering member expertise"""
        scored = []
        for assignment in assignments:
            score = self._calculate_priority_score(assignment, members)
            scored.append({
                **assignment,
                'priority_score': score,
                'priority_label': self._score_to_label(score),
            })

        scored.sort(key=lambda x: x['priority_score'], reverse=True)
        return scored

    def _calculate_priority_score(self, assignment, members):
        """Calculate priority score for an assignment"""
        score = 0.0

        # Deadline urgency (0-1)
        due_date = assignment.get('due_datetime')
        if due_date:
            days_until_due = max(0, (due_date - datetime.now()).days)
            urgency = max(0, 1 - (days_until_due / 14))  # 14 days scale
            score += urgency * self.PRIORITY_WEIGHTS['deadline_urgency']

        # Difficulty estimation (simplified)
        title = assignment.get('title', '').lower()
        difficulty_keywords = {'exam': 0.9, 'midterm': 0.9, 'final': 1.0, 'project': 0.7, 'quiz': 0.4, 'homework': 0.3}
        difficulty = 0.5
        for keyword, diff_score in difficulty_keywords.items():
            if keyword in title:
                difficulty = diff_score
                break
        score += difficulty * self.PRIORITY_WEIGHTS['difficulty_level']

        # Expertise match (simplified)
        score += 0.5 * self.PRIORITY_WEIGHTS['expertise_match']

        # Group impact
        score += 0.5 * self.PRIORITY_WEIGHTS['group_impact']

        return round(score, 3)

    def _score_to_label(self, score):
        """Convert numeric score to human-readable label"""
        if score >= 0.8:
            return "CRITICAL"
        elif score >= 0.6:
            return "HIGH"
        elif score >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"

    @feature_flag('ENABLE_ASSIGNMENT_PRIORITY_SCORING')
    def get_ai_priority_analysis(self, assignments, members):
        """Get AI-powered detailed priority analysis"""
        messages = [
            {
                "role": "system",
                "content": "Analyze assignment priorities considering team member expertise and deadlines."
            },
            {
                "role": "user",
                "content": f"Assignments: {json.dumps(assignments, default=str)}\n"
                           f"Members: {json.dumps(members)}\n"
                           f"Provide priority ranking with rationale."
            }
        ]

        return self.ai.query(messages)
