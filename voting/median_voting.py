"""Алгоритмы голосования с использованием библиотеки statistics"""

from typing import List, Dict, Any, Optional
from statistics import median, mean, stdev
from collections import Counter


class VotingResult:
    """Результат голосования"""

    def __init__(self,
                 voted_value: float,
                 values_count: int,
                 all_values: List[float],
                 voting_type: str = 'median',
                 is_correct: Optional[bool] = None,
                 correct_answer: Optional[float] = None,
                 deviation: Optional[float] = None,
                 additional_info: Optional[Dict[str, Any]] = None):
        self.voted_value = voted_value
        self.values_count = values_count
        self.all_values = sorted(all_values)
        self.voting_type = voting_type
        self.is_correct = is_correct
        self.correct_answer = correct_answer
        self.deviation = deviation
        self.additional_info = additional_info or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'voted_value': self.voted_value,
            'values_count': self.values_count,
            'all_values': self.all_values,
            'voting_type': self.voting_type,
            'is_correct': self.is_correct,
            'correct_answer': self.correct_answer,
            'deviation': self.deviation,
            **self.additional_info
        }


class VotingAlgorithm:
    """Алгоритмы голосования"""

    def __init__(self, epsilon: float = 0.01):
        self.epsilon = epsilon

    def _check_correctness(self, voted_value: float, correct_answer: Optional[float]):
        if correct_answer is None:
            return None, None

        deviation = abs(voted_value - correct_answer)

        if correct_answer != 0:
            is_correct = deviation <= self.epsilon * abs(correct_answer)
        else:
            is_correct = deviation <= self.epsilon

        return is_correct, deviation

    def _get_reference_value(self, values: List[float], method: str = 'median') -> Optional[float]:
        """
        Получение опорного (правильного) значения из списка

        Args:
            values: Список значений (correct_answer)
            method: 'median' - медиана, 'majority' - самое частое значение
        """
        if not values:
            return None

        if method == 'median':
            return median(values)
        elif method == 'majority':
            counter = Counter(values)
            return counter.most_common(1)[0][0]
        else:
            raise ValueError(f"Неизвестный метод: {method}")

    def vote_median(self, values: List[float],
                    correct_answers: Optional[List[float]] = None) -> VotingResult:
        """
        Вычисление медианы по ВСЕМ значениям сразу

        Правильный ответ вычисляется как МЕДИАНА всех correct_answer

        Args:
            values: Список всех значений (version_answer)
            correct_answers: Список всех правильных ответов (correct_answer)
        """
        if not values:
            raise ValueError("Список значений пуст")

        if len(values) < 2:
            raise ValueError("Нужно минимум 2 значения")

        # Вычисляем медиану
        voted_value = median(values)

        # Правильный ответ = медиана всех correct_answer
        correct_answer = self._get_reference_value(correct_answers, 'median') if correct_answers else None

        is_correct, deviation = self._check_correctness(voted_value, correct_answer)

        # Статистика
        counter = Counter(values)
        most_common = counter.most_common(1)[0]

        additional_info = {
            'mean_value': mean(values),
            'stdev_value': stdev(values) if len(values) > 1 else 0.0,
            'min_value': min(values),
            'max_value': max(values),
            'mode_value': most_common[0],
            'mode_count': most_common[1]
        }

        return VotingResult(
            voted_value=voted_value,
            values_count=len(values),
            all_values=values,
            voting_type='median',
            is_correct=is_correct,
            correct_answer=correct_answer,
            deviation=deviation,
            additional_info=additional_info
        )

    def vote_absolute_majority(self, values: List[float],
                                correct_answers: Optional[List[float]] = None) -> VotingResult:
        """
        Голосование абсолютным большинством

        Правильный ответ = самое частое значение среди correct_answer (мода)

        Алгоритм:
        1. Подсчитываем частоту каждого УНИКАЛЬНОГО значения
        2. Находим значение с максимальной частотой
        3. Возвращаем самое частое значение (моду)

        Args:
            values: Список всех значений
            correct_answers: Список всех правильных ответов
        """
        if not values:
            raise ValueError("Список значений пуст")

        if len(values) < 2:
            raise ValueError("Нужно минимум 2 значения")

        # Подсчитываем частоту каждого значения
        counter = Counter(values)

        # Находим самое частое значение
        most_common_value, most_common_count = counter.most_common(1)[0]

        # Проверяем, есть ли абсолютное большинство (>50%)
        majority_threshold = len(values) / 2.0
        has_absolute_majority = most_common_count > majority_threshold

        # Возвращаем самое частое значение
        voted_value = most_common_value

        # Правильный ответ = самое частое значение среди correct_answer
        correct_answer = self._get_reference_value(correct_answers, 'majority') if correct_answers else None

        is_correct, deviation = self._check_correctness(voted_value, correct_answer)

        # Топ-5 самых частых значений
        top_5 = counter.most_common(5)
        frequency_info = {
            f"value_{i+1}": val for i, (val, count) in enumerate(top_5)
        }
        frequency_info.update({
            f"count_{i+1}": count for i, (val, count) in enumerate(top_5)
        })

        additional_info = {
            'has_absolute_majority': has_absolute_majority,
            'most_common_value': most_common_value,
            'most_common_count': most_common_count,
            'majority_threshold': majority_threshold,
            'total_unique_values': len(counter),
            'mean_value': mean(values),
            'stdev_value': stdev(values) if len(values) > 1 else 0.0,
            'min_value': min(values),
            'max_value': max(values),
            **frequency_info
        }

        return VotingResult(
            voted_value=voted_value,
            values_count=len(values),
            all_values=values,
            voting_type='absolute_majority',
            is_correct=is_correct,
            correct_answer=correct_answer,
            deviation=deviation,
            additional_info=additional_info
        )