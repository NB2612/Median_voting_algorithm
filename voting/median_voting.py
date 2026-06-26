"""Алгоритм медианного голосования"""

from typing import List, Dict, Any, Optional
from statistics import median, median_low, median_high


class MedianVotingResult:
    """Результат голосования"""

    def __init__(self,
                 voted_value: float,
                 versions_count: int,
                 versions_answers: List[float],
                 median_type: str = 'median',
                 is_correct: Optional[bool] = None,
                 correct_answer: Optional[float] = None,
                 deviation: Optional[float] = None):
        self.voted_value = voted_value
        self.versions_count = versions_count
        self.versions_answers = sorted(versions_answers)
        self.median_type = median_type
        self.is_correct = is_correct
        self.correct_answer = correct_answer
        self.deviation = deviation

    def to_dict(self) -> Dict[str, Any]:
        return {
            'voted_value': self.voted_value,
            'versions_count': self.versions_count,
            'versions_answers': self.versions_answers,
            'median_type': self.median_type,
            'is_correct': self.is_correct,
            'correct_answer': self.correct_answer,
            'deviation': self.deviation
        }


class MedianVotingAlgorithm:
    """Алгоритм медианного голосования"""

    def __init__(self, epsilon: float = 0.01):
        self.epsilon = epsilon

    def vote(self, versions: List[Any], median_type: str = 'median') -> MedianVotingResult:
        """
        Обычное медианное голосование

        Args:
            versions: Список объектов ExperimentData
            median_type: Тип медианы
        """
        if not versions:
            raise ValueError("Список версий пуст")

        if len(versions) < 2:
            raise ValueError("Нужно минимум 2 версии")

        answers = [v.version_answer for v in versions]

        if median_type == 'median':
            voted_value = median(answers)
        elif median_type == 'median_low':
            voted_value = median_low(answers)
        elif median_type == 'median_high':
            voted_value = median_high(answers)
        else:
            raise ValueError(f"Неизвестный тип: {median_type}")

        correct_answer = versions[0].correct_answer if versions else None
        deviation = abs(voted_value - correct_answer) if correct_answer is not None else None
        is_correct = None

        if deviation is not None and correct_answer is not None:
            if correct_answer != 0:
                is_correct = deviation <= self.epsilon * abs(correct_answer)
            else:
                is_correct = deviation <= self.epsilon

        return MedianVotingResult(
            voted_value=voted_value,
            versions_count=len(versions),
            versions_answers=answers,
            median_type=median_type,
            is_correct=is_correct,
            correct_answer=correct_answer,
            deviation=deviation
        )

    def vote_weighted(self, versions: List[Any]) -> MedianVotingResult:
        """
        Взвешенное медианное голосование

        Args:
            versions: Список объектов ExperimentData с version_reliability
        """
        if not versions:
            raise ValueError("Список версий пуст")

        versions_with_weights = [
            (v.version_answer, v.version_reliability or 1.0)
            for v in versions
        ]
        versions_with_weights.sort(key=lambda x: x[0])

        total_weight = sum(w for _, w in versions_with_weights)
        cumulative_weight = 0
        median_value = versions_with_weights[-1][0]

        for value, weight in versions_with_weights:
            cumulative_weight += weight
            if cumulative_weight >= total_weight / 2:
                median_value = value
                break

        correct_answer = versions[0].correct_answer if versions else None
        deviation = abs(median_value - correct_answer) if correct_answer is not None else None
        is_correct = None

        if deviation is not None and correct_answer is not None:
            if correct_answer != 0:
                is_correct = deviation <= self.epsilon * abs(correct_answer)
            else:
                is_correct = deviation <= self.epsilon

        return MedianVotingResult(
            voted_value=median_value,
            versions_count=len(versions),
            versions_answers=[v.version_answer for v in versions],
            median_type='weighted_median',
            is_correct=is_correct,
            correct_answer=correct_answer,
            deviation=deviation
        )