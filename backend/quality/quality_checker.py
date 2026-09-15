# -*- coding: utf-8 -*-
"""
Translation quality checker - detects missed translations, mistranslations,
and leftover source-language text.
"""

import re
from typing import List, Dict, Tuple

class QualityChecker:
    """Translation quality checker"""

    # English function words (should not appear in Chinese translations)
    ENGLISH_FUNCTION_WORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "should",
        "could", "may", "might", "can", "must", "shall", "of", "in", "on",
        "at", "to", "for", "with", "by", "from", "as", "and", "or", "but",
        "if", "then", "than", "that", "this", "these", "those", "it", "its"
    }

    # AI filler/boilerplate patterns
    AI_NONSENSE_PATTERNS = [
        r"^\s*(?:translation|translated text)\s*[:：]",
        r"^\s*(?:譯文|翻譯結果|翻譯)\s*[:：]",
        r"^\s*(?:as an ai|i'm sorry|i cannot)",
        r"^\s*(?:作爲|作爲一個)(?:AI|人工智能)",
        r"^\s*(?:對不起|抱歉|很抱歉)",
    ]

    def __init__(self, source_lang="ko", target_lang="zh"):
        self.source_lang = source_lang
        self.target_lang = target_lang

    def check_translation(self, source: str, translation: str) -> Dict:
        """
        Check translation quality

        Returns: {
            "is_valid": bool,
            "confidence": float (0-1),
            "issues": List[str],
            "scores": Dict
        }
        """
        if not source or not translation:
            return {
                "is_valid": False,
                "confidence": 0.0,
                "issues": ["空文本"],
                "scores": {}
            }

        issues = []
        scores = {}

        # 1. Length ratio check
        length_score, length_issue = self._check_length_ratio(source, translation)
        scores["length_ratio"] = length_score
        if length_issue:
            issues.append(length_issue)

        # 2. Punctuation check
        punct_score, punct_issue = self._check_punctuation(source, translation)
        scores["punctuation"] = punct_score
        if punct_issue:
            issues.append(punct_issue)

        # 3. Truncation detection
        truncation_issue = self._check_truncation(source, translation)
        if truncation_issue:
            issues.append(truncation_issue)
            scores["truncation"] = 0.0
        else:
            scores["truncation"] = 1.0

        # 4. Source-language residue detection
        residue_score, residue_issue = self._check_source_residue(source, translation)
        scores["source_residue"] = residue_score
        if residue_issue:
            issues.append(residue_issue)

        # 5. English function word leakage (Chinese target only)
        if self.target_lang == "zh":
            function_score, function_issue = self._check_function_words(translation)
            scores["function_words"] = function_score
            if function_issue:
                issues.append(function_issue)

        # 6. AI filler/boilerplate detection
        nonsense_issue = self._check_ai_nonsense(translation)
        if nonsense_issue:
            issues.append(nonsense_issue)
            scores["nonsense"] = 0.0
        else:
            scores["nonsense"] = 1.0

        # Calculate overall confidence
        confidence = sum(scores.values()) / len(scores)
        is_valid = confidence >= 0.7 and len(issues) == 0

        return {
            "is_valid": is_valid,
            "confidence": confidence,
            "issues": issues,
            "scores": scores
        }

    def _check_length_ratio(self, source: str, translation: str) -> Tuple[float, str]:
        """Check the length ratio"""
        src_len = len(source.strip())
        dst_len = len(translation.strip())

        if src_len == 0:
            return 0.0, "源文本爲空"

        ratio = dst_len / src_len

        # Korean->Chinese: typically 0.5-1.5x
        # Japanese->Chinese: typically 0.6-1.2x
        if ratio < 0.3:
            return 0.0, f"譯文過短 (比率: {ratio:.2f})"
        elif ratio > 2.5:
            return 0.5, f"譯文過長 (比率: {ratio:.2f})"
        elif ratio < 0.4 or ratio > 2.0:
            return 0.7, f"長度可疑 (比率: {ratio:.2f})"
        else:
            return 1.0, None

    def _check_punctuation(self, source: str, translation: str) -> Tuple[float, str]:
        """Check the punctuation count"""
        src_punct = self._count_punctuation(source)
        dst_punct = self._count_punctuation(translation)

        delta = abs(dst_punct - src_punct)

        if delta > 12:
            return 0.3, f"標點差異過大 ({src_punct} -> {dst_punct})"
        elif delta > 8:
            return 0.6, f"標點差異較大 ({src_punct} -> {dst_punct})"
        elif delta > 5:
            return 0.8, None
        else:
            return 1.0, None

    def _count_punctuation(self, text: str) -> int:
        """Count punctuation marks"""
        punct = r'[.!?。！？;；:：,，、]'
        return len(re.findall(punct, text))

    def _check_truncation(self, source: str, translation: str) -> str:
        """Check whether the translation was truncated"""
        src_sentences = re.split(r'[.!?。！？]', source.strip())
        dst_sentences = re.split(r'[.!?。！？]', translation.strip())

        # If the source has multiple sentences but the translation only has one
        if len(src_sentences) > 2 and len(dst_sentences) <= 1:
            return "可能只翻譯了第一句"

        # If the translation ends mid-word/mid-character (no punctuation)
        if source.rstrip()[-1] in '.!?。！？' and translation.rstrip()[-1] not in '.!?。！？':
            if len(translation) < len(source) * 0.6:
                return "譯文可能被截斷"

        return None

    def _check_source_residue(self, source: str, translation: str) -> Tuple[float, str]:
        """Check for leftover source-language text"""
        issues = []
        score = 1.0

        if self.source_lang == "ko":
            # Hangul characters (U+AC00 - U+D7AF)
            hangul_count = len(re.findall(r'[가-힯]', translation))
            if hangul_count > 0:
                issues.append(f"{hangul_count}個韓文字符")
                score = 0.0

        elif self.source_lang == "ja":
            # Japanese kana (U+3040 - U+30FF)
            kana_count = len(re.findall(r'[぀-ヿ]', translation))
            if kana_count > 5:  # a small amount of kana may just be onomatopoeia
                issues.append(f"{kana_count}個日文假名")
                score = 0.2

        # Check for long runs of Latin characters (could be names/places, be cautious)
        latin_words = re.findall(r'\b[a-zA-Z]{4,}\b', translation)
        if len(latin_words) > 10:
            issues.append(f"{len(latin_words)}個英文詞")
            score = min(score, 0.5)

        if issues:
            return score, "源語言殘留: " + ", ".join(issues)
        return 1.0, None

    def _check_function_words(self, translation: str) -> Tuple[float, str]:
        """Check for English function word leakage (a Chinese translation should not contain many English function words)"""
        words = re.findall(r'\b[a-z]+\b', translation.lower())
        if not words:
            return 1.0, None

        function_word_count = sum(1 for w in words if w in self.ENGLISH_FUNCTION_WORDS)
        ratio = function_word_count / len(words)

        if ratio > 0.4:
            return 0.0, f"大量英文功能詞 ({function_word_count}/{len(words)})"
        elif ratio > 0.2:
            return 0.5, f"較多英文功能詞 ({function_word_count}/{len(words)})"
        else:
            return 1.0, None

    def _check_ai_nonsense(self, translation: str) -> str:
        """Check for AI filler/boilerplate text"""
        for pattern in self.AI_NONSENSE_PATTERNS:
            if re.search(pattern, translation, re.IGNORECASE):
                return "包含AI廢話或格式標記"
        return None

    def batch_check(self, pairs: List[Tuple[str, str]]) -> List[Dict]:
        """Batch check"""
        return [self.check_translation(src, dst) for src, dst in pairs]

    def get_failed_indices(self, pairs: List[Tuple[str, str]], confidence_threshold=0.7) -> List[int]:
        """Return the indices of paragraphs that need to be retried"""
        results = self.batch_check(pairs)
        return [
            i for i, result in enumerate(results)
            if not result["is_valid"] or result["confidence"] < confidence_threshold
        ]


if __name__ == "__main__":
    # Test
    checker = QualityChecker(source_lang="ko", target_lang="zh")

    # Test cases
    test_cases = [
        ("안녕하세요. 저는 학생입니다.", "你好。我是學生。"),  # normal
        ("안녕하세요. 저는 학생입니다.", "你好"),  # too short
        ("안녕하세요.", "안녕하세요."),  # Korean residue
        ("こんにちは。", "こんにちは。"),  # Japanese residue
        ("Hello, how are you?", "譯文：你好，你好嗎？"),  # AI filler
        ("This is a test.", "This is a test."),  # English function words
    ]

    for src, dst in test_cases:
        result = checker.check_translation(src, dst)
        print(f"\n源文: {src}")
        print(f"譯文: {dst}")
        print(f"有效: {result['is_valid']}, 置信度: {result['confidence']:.2f}")
        if result['issues']:
            print(f"問題: {', '.join(result['issues'])}")
