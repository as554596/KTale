# -*- coding: utf-8 -*-
"""
Adaptive chunker - dynamically adjusts batch size based on paragraph length.
Optimizes token usage while balancing speed and quality.
"""

from typing import List, Dict


class AdaptiveChunker:
    """
    Adaptive chunker

    Features:
    1. Dynamically adjusts batch size based on paragraph length
    2. Dynamically filters the glossary (only passes relevant terms)
    3. Intelligently trims context (stays within the token budget)
    """

    def __init__(self,
                 base_chunk_size=25,
                 min_chunk_size=15,
                 max_chunk_size=40,
                 max_context_lines=3,
                 max_glossary_terms=30):
        """
        Initialize the chunker

        Args:
            base_chunk_size: base batch size (default 25)
            min_chunk_size: minimum batch size (default 15, for long paragraphs)
            max_chunk_size: maximum batch size (default 40, for short paragraphs)
            max_context_lines: maximum number of context lines
            max_glossary_terms: maximum number of glossary terms to pass along
        """
        self.base_chunk_size = base_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.max_context_lines = max_context_lines
        self.max_glossary_terms = max_glossary_terms

    def calculate_optimal_chunk_size(self, paragraphs: List[Dict]) -> int:
        """
        Calculate the optimal batch size

        Args:
            paragraphs: list of paragraphs

        Returns:
            the optimal chunk_size
        """
        if not paragraphs:
            return self.base_chunk_size

        # Calculate the average paragraph length
        avg_length = sum(len(p.get('text', '')) for p in paragraphs) / len(paragraphs)

        # Dynamically adjust based on the average length
        if avg_length < 50:
            # Short paragraphs (mostly dialogue) -> large batch
            return self.max_chunk_size
        elif avg_length < 150:
            # Medium paragraphs (balanced) -> base batch
            return self.base_chunk_size
        else:
            # Long paragraphs (mostly narration) -> small batch
            return self.min_chunk_size

    def create_chunks(self, paragraphs: List[Dict]) -> List[Dict]:
        """
        Create adaptive chunks

        Args:
            paragraphs: list of paragraphs [{text, index}, ...]

        Returns:
            list of chunks [{paragraphs, context, start, end}, ...]
        """
        if not paragraphs:
            return []

        # Calculate the optimal batch size
        chunk_size = self.calculate_optimal_chunk_size(paragraphs)
        print(f"📦 自適應分塊: 批次大小 = {chunk_size} 行")

        chunks = []
        total = len(paragraphs)

        for i in range(0, total, chunk_size):
            chunk_paras = paragraphs[i:i + chunk_size]

            # Get the context (preceding paragraphs)
            context_start = max(0, i - self.max_context_lines)
            context_paras = paragraphs[context_start:i] if i > 0 else []

            chunks.append({
                'paragraphs': chunk_paras,
                'context': context_paras,
                'start': i,
                'end': min(i + chunk_size, total)
            })

        print(f"   總段落: {total}, 分成 {len(chunks)} 個批次")
        return chunks

    def filter_relevant_glossary(self, chunk_text: str, glossary: List[Dict]) -> List[Dict]:
        """
        Filter to relevant terms (dynamic glossary)

        Args:
            chunk_text: the text of the current chunk (all paragraphs combined)
            glossary: the full glossary

        Returns:
            list of relevant terms (at most max_glossary_terms)
        """
        if not glossary:
            return []

        relevant = []

        for term in glossary:
            src = term.get('src', '')
            if src and src in chunk_text:
                relevant.append(term)

        # Sorted by frequency (assumes the glossary is already frequency-sorted)
        # Limit the count
        return relevant[:self.max_glossary_terms]

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the token count (simplified)

        Args:
            text: the text

        Returns:
            the estimated token count
        """
        # Simplified estimate:
        # - Chinese: 1 character ≈ 1.5 tokens
        # - English: 1 word ≈ 1.3 tokens
        # - Korean: 1 character ≈ 2 tokens

        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        korean_chars = sum(1 for c in text if '가' <= c <= '힯')
        other_chars = len(text) - chinese_chars - korean_chars

        tokens = (
            chinese_chars * 1.5 +
            korean_chars * 2.0 +
            other_chars * 0.5  # spaces, punctuation, etc.
        )

        return int(tokens)

    def get_chunking_stats(self, paragraphs: List[Dict]) -> Dict:
        """
        Get chunking statistics

        Args:
            paragraphs: list of paragraphs

        Returns:
            a dict of statistics
        """
        if not paragraphs:
            return {}

        lengths = [len(p.get('text', '')) for p in paragraphs]
        chunk_size = self.calculate_optimal_chunk_size(paragraphs)
        num_chunks = (len(paragraphs) + chunk_size - 1) // chunk_size

        return {
            'total_paragraphs': len(paragraphs),
            'avg_length': sum(lengths) / len(lengths),
            'min_length': min(lengths),
            'max_length': max(lengths),
            'optimal_chunk_size': chunk_size,
            'num_chunks': num_chunks,
            'estimated_api_calls': num_chunks
        }


# Convenience function
def create_adaptive_chunks(paragraphs: List[Dict],
                          base_size=25,
                          min_size=15,
                          max_size=40) -> List[Dict]:
    """
    Create adaptive chunks (convenience function)

    Args:
        paragraphs: list of paragraphs
        base_size: base batch size
        min_size: minimum batch size
        max_size: maximum batch size

    Returns:
        list of chunks
    """
    chunker = AdaptiveChunker(
        base_chunk_size=base_size,
        min_chunk_size=min_size,
        max_chunk_size=max_size
    )

    return chunker.create_chunks(paragraphs)


if __name__ == "__main__":
    # Test
    print("✅ AdaptiveChunker 模塊已就緒")

    # Simulate different types of paragraphs
    short_paras = [{'text': '你好' * 10, 'index': i} for i in range(100)]
    medium_paras = [{'text': '這是一段中等長度的文本' * 5, 'index': i} for i in range(100)]
    long_paras = [{'text': '這是一段很長的描述性文本，包含了大量的細節和情節' * 10, 'index': i} for i in range(100)]

    chunker = AdaptiveChunker()

    print("\n📊 短段落（對話）:")
    stats = chunker.get_chunking_stats(short_paras)
    print(f"   平均長度: {stats['avg_length']:.0f} 字")
    print(f"   最優批次: {stats['optimal_chunk_size']} 行")
    print(f"   API 調用: {stats['estimated_api_calls']} 次")

    print("\n📊 中等段落（平衡）:")
    stats = chunker.get_chunking_stats(medium_paras)
    print(f"   平均長度: {stats['avg_length']:.0f} 字")
    print(f"   最優批次: {stats['optimal_chunk_size']} 行")
    print(f"   API 調用: {stats['estimated_api_calls']} 次")

    print("\n📊 長段落（描述）:")
    stats = chunker.get_chunking_stats(long_paras)
    print(f"   平均長度: {stats['avg_length']:.0f} 字")
    print(f"   最優批次: {stats['optimal_chunk_size']} 行")
    print(f"   API 調用: {stats['estimated_api_calls']} 次")
