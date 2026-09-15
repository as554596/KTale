# -*- coding: utf-8 -*-
"""
Smart translator - combines missed-translation detection with automatic retries.
Optimizes token usage and translation quality.
v2.0: added adaptive chunking and a dynamic glossary.
"""

import json
import time
from typing import List, Dict, Tuple, Callable
from quality_checker import QualityChecker
from adaptive_chunker import AdaptiveChunker


class SmartTranslator:
    """
    Smart translator - applies quality-focused translation best practices

    Features:
    1. Automatic missed-translation detection
    2. Smart retries (partial retries + micro-batch retries)
    3. Token optimization (JSONLINE format + context control)
    4. Adaptive chunking (new in v2.0)
    5. Dynamic glossary (new in v2.0)
    6. Incremental saving (mobile-friendly)
    """

    def __init__(self, client, model, glossary_dict,
                 chunk_size=25,
                 context_lines=3,
                 source_lang="ko", target_lang="zh",
                 custom_prompt="",
                 use_adaptive_chunking=True,
                 use_dynamic_glossary=True):
        """
        Initialize the translator

        Args:
            client: the OpenAI client
            model: the model name
            glossary_dict: the glossary {source: translation}
            chunk_size: base batch size (a reference value in adaptive mode)
            context_lines: number of context lines (default 3)
            source_lang: source language code
            target_lang: target language code
            custom_prompt: custom prompt text
            use_adaptive_chunking: whether to use adaptive chunking
            use_dynamic_glossary: whether to use dynamic glossary filtering
        """
        self.client = client
        self.model = model
        self.glossary_dict = glossary_dict
        self.chunk_size = chunk_size
        self.context_lines = context_lines
        self.custom_prompt = custom_prompt
        self.use_adaptive_chunking = use_adaptive_chunking
        self.use_dynamic_glossary = use_dynamic_glossary

        # Quality checker
        self.quality_checker = QualityChecker(source_lang, target_lang)

        # Adaptive chunker
        if use_adaptive_chunking:
            self.chunker = AdaptiveChunker(
                base_chunk_size=chunk_size,
                min_chunk_size=max(10, chunk_size - 10),
                max_chunk_size=min(50, chunk_size + 15),
                max_context_lines=context_lines,
                max_glossary_terms=30
            )
            print(f"✅ 使用自適應分塊（基礎大小: {chunk_size}）")
        else:
            self.chunker = None
            print(f"⚠️ 使用固定分塊（大小: {chunk_size}）")

        # Stats
        self.stats = {
            "total_paragraphs": 0,
            "translated": 0,
            "retried": 0,
            "failed": 0,
            "total_tokens": 0,
            "glossary_filtered_count": 0  # New: number of glossary filter passes
        }

    def translate_paragraphs(self, paragraphs: List[Dict],
                            callback: Callable = None) -> List[Dict]:
        """
        Translate a list of paragraphs (with quality checks and automatic retries)

        Args:
            paragraphs: [{text, index}, ...]
            callback: progress callback

        Returns:
            List[Dict]: the translated paragraphs [{text, index, original, confidence}, ...]
        """
        self.stats["total_paragraphs"] = len(paragraphs)
        results = []

        # Use adaptive chunking or fixed chunking
        if self.use_adaptive_chunking and self.chunker:
            chunks = self.chunker.create_chunks(paragraphs)
            print(f"📦 自適應分塊: {len(chunks)} 個批次")
        else:
            # Fixed chunking (original logic)
            chunks = []
            for i in range(0, len(paragraphs), self.chunk_size):
                chunk_paras = paragraphs[i:i + self.chunk_size]
                context_start = max(0, i - self.context_lines)
                context_paras = paragraphs[context_start:i] if i > 0 else []

                chunks.append({
                    'paragraphs': chunk_paras,
                    'context': context_paras,
                    'start': i,
                    'end': min(i + self.chunk_size, len(paragraphs))
                })

        # Translate each chunk
        for chunk_info in chunks:
            chunk = chunk_info['paragraphs']
            context = chunk_info['context']

            # Translate this chunk
            translated_chunk = self._translate_chunk_with_retry(chunk, context)
            results.extend(translated_chunk)

            # Update progress
            self.stats["translated"] = len(results)
            if callback:
                callback({
                    "current": len(results),
                    "total": len(paragraphs),
                    "percent": int((len(results) / len(paragraphs)) * 100),
                    "message": f"翻譯中 {len(results)}/{len(paragraphs)}",
                    "stats": self.stats.copy()
                })

            # Rate limiting
            time.sleep(0.3)

        return results

    def _translate_chunk_with_retry(self, chunk: List[Dict],
                                    context: List[Dict],
                                    max_retries=2) -> List[Dict]:
        """
        Translate a chunk (with retries)

        Args:
            chunk: the paragraphs in the current chunk
            context: the preceding context
            max_retries: maximum number of retries

        Returns:
            the list of translated paragraphs
        """
        # First translation pass
        translated = self._translate_chunk(chunk, context)

        # Quality check
        issues = self._check_quality(chunk, translated)

        # Retry if there are issues
        retry_count = 0
        while issues and retry_count < max_retries:
            self.stats["retried"] += len(issues)

            # Strategy 1: if over 50% have issues, retranslate the whole chunk
            if len(issues) >= len(chunk) * 0.5:
                print(f"  ⚠️ {len(issues)}/{len(chunk)} 段有問題，整體重譯")
                translated = self._translate_chunk(chunk, context,
                                                  retry_hint="SOURCE_RESIDUE")

            # Strategy 2: otherwise only retranslate the problem paragraphs (micro-batch)
            else:
                print(f"  🔄 重譯 {len(issues)} 個問題段")
                translated = self._retry_failed_items(chunk, translated, issues, context)

            # Check again
            issues = self._check_quality(chunk, translated)
            retry_count += 1

        # If issues remain, flag them but stop retrying
        if issues:
            self.stats["failed"] += len(issues)
            print(f"  ❌ {len(issues)} 段質量仍不理想")

        return translated

    def _translate_chunk(self, chunk: List[Dict], context: List[Dict],
                        retry_hint: str = None) -> List[Dict]:
        """
        Translate a chunk (single API call)

        Args:
            chunk: the paragraphs to translate
            context: the preceding context
            retry_hint: retry hint (SOURCE_RESIDUE, LOW_CONFIDENCE, etc.)

        Returns:
            the translated paragraphs
        """
        # Build the prompt (uses JSONLINE format to save tokens)
        prompt = self._build_prompt(chunk, context, retry_hint)

        # Call the API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional translator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            # Track token usage
            if hasattr(response, 'usage'):
                self.stats["total_tokens"] += response.usage.total_tokens

            # Parse the result
            output = response.choices[0].message.content
            translated = self._parse_jsonline_output(output, chunk)

            return translated

        except Exception as e:
            print(f"  ❌ API 錯誤: {e}")
            # Fall back to the source text on failure
            return [{"text": p["text"], "index": p["index"],
                    "original": p["text"], "confidence": 0.0} for p in chunk]

    def _build_prompt(self, chunk: List[Dict], context: List[Dict],
                     retry_hint: str = None) -> str:
        """Build the translation prompt (optimized for token usage)"""
        prompt_parts = []

        # 1. Glossary (dynamically filtered or count-limited)
        if self.glossary_dict:
            if self.use_dynamic_glossary and self.chunker:
                # Dynamic filtering: only pass terms that appear in the current chunk
                chunk_text = " ".join([p['text'] for p in chunk])
                glossary_list = [{"src": k, "dst": v} for k, v in self.glossary_dict.items()]
                filtered_glossary = self.chunker.filter_relevant_glossary(chunk_text, glossary_list)

                if filtered_glossary:
                    glossary_text = "\n".join([
                        f"- {term['src']} -> {term['dst']}"
                        for term in filtered_glossary
                    ])
                    prompt_parts.append(f"[Glossary]\n{glossary_text}\n")
                    self.stats["glossary_filtered_count"] += 1
                    print(f"   📝 術語表過濾: {len(filtered_glossary)}/{len(self.glossary_dict)} 個相關術語")
            else:
                # Fixed mode: limit to the first 50
                glossary_text = "\n".join([
                    f"- {src} -> {dst}"
                    for src, dst in list(self.glossary_dict.items())[:50]
                ])
                prompt_parts.append(f"[Glossary]\n{glossary_text}\n")

        # 2. Context (read-only, not translated)
        if context:
            context_text = "\n".join([f"{p['text']}" for p in context])
            prompt_parts.append(
                f"[Context - for reference only, do not translate]\n{context_text}\n"
            )

        # 3. Custom prompt text
        if self.custom_prompt:
            prompt_parts.append(f"{self.custom_prompt}\n")

        # 4. Retry hint
        if retry_hint == "SOURCE_RESIDUE":
            prompt_parts.append(
                "⚠️ SOURCE-RESIDUE RETRY: Previous translation kept source language text. "
                "Please translate ALL text to target language.\n"
            )
        elif retry_hint == "LOW_CONFIDENCE":
            prompt_parts.append(
                "⚠️ QUALITY RETRY: Previous translation had quality issues. "
                "Please ensure complete and accurate translation.\n"
            )

        # 5. Translation task (JSONLINE format - condensed system prompt)
        jsonline_input = "\n".join([
            json.dumps({"index": p["index"], "text": p["text"]}, ensure_ascii=False)
            for p in chunk
        ])

        prompt_parts.append(
            f"[Translate to Chinese]\n"
            f"Output: JSONLINE format\n"
            f"{jsonline_input}\n"
        )

        return "\n".join(prompt_parts)

    def _parse_jsonline_output(self, output: str, chunk: List[Dict]) -> List[Dict]:
        """
        Parse the JSONLINE output

        Args:
            output: the text returned by the API
            chunk: the original paragraphs (for cross-referencing)

        Returns:
            the parsed translation results
        """
        results = []
        index_map = {p["index"]: p for p in chunk}

        # Parse line by line
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('[') or line.startswith('{'):
                try:
                    obj = json.loads(line)
                    if "index" in obj and "text" in obj:
                        index = obj["index"]
                        text = obj["text"]

                        results.append({
                            "index": index,
                            "text": text,
                            "original": index_map.get(index, {}).get("text", ""),
                            "confidence": 1.0  # will be updated by the quality check later
                        })
                except:
                    continue

        # If parsing failed, try parsing as a whole block (fallback)
        if not results:
            try:
                # Try treating it as a JSON array
                objs = json.loads("[" + output.replace("}\n{", "},{") + "]")
                for obj in objs:
                    if "index" in obj and "text" in obj:
                        results.append({
                            "index": obj["index"],
                            "text": obj["text"],
                            "original": index_map.get(obj["index"], {}).get("text", ""),
                            "confidence": 1.0
                        })
            except:
                pass

        # If it still failed, fall back to the source text
        if not results:
            results = [
                {"index": p["index"], "text": p["text"],
                 "original": p["text"], "confidence": 0.0}
                for p in chunk
            ]

        return results

    def _check_quality(self, original_chunk: List[Dict],
                       translated_chunk: List[Dict]) -> List[int]:
        """
        Check translation quality and return the list of problematic indices

        Args:
            original_chunk: the source paragraphs
            translated_chunk: the translated paragraphs

        Returns:
            List[int]: indices that need to be retranslated
        """
        issues = []
        original_map = {p["index"]: p["text"] for p in original_chunk}

        for trans in translated_chunk:
            index = trans["index"]
            src = original_map.get(index, "")
            dst = trans["text"]

            # Quality check
            result = self.quality_checker.check_translation(src, dst)
            trans["confidence"] = result["confidence"]

            # Record the index if it doesn't pass
            if not result["is_valid"] or result["confidence"] < 0.7:
                issues.append(index)
                print(f"    ⚠️ 段落 {index} 質量問題: {', '.join(result['issues'])}")

        return issues

    def _retry_failed_items(self, original_chunk: List[Dict],
                           translated_chunk: List[Dict],
                           failed_indices: List[int],
                           context: List[Dict]) -> List[Dict]:
        """
        Retranslate only the failed paragraphs (micro-batch strategy)

        Args:
            original_chunk: the source chunk
            translated_chunk: the current translated chunk
            failed_indices: the failed indices
            context: the context

        Returns:
            the updated translated chunk
        """
        # Build the sub-chunk of failed items
        failed_items = [p for p in original_chunk if p["index"] in failed_indices]

        # Retranslate in small batches (5 per batch)
        micro_batch_size = 5
        for i in range(0, len(failed_items), micro_batch_size):
            micro_batch = failed_items[i:i + micro_batch_size]

            # Retranslate
            retried = self._translate_chunk(micro_batch, context,
                                           retry_hint="LOW_CONFIDENCE")

            # Replace the original results
            for retry_item in retried:
                for j, trans in enumerate(translated_chunk):
                    if trans["index"] == retry_item["index"]:
                        translated_chunk[j] = retry_item
                        break

        return translated_chunk

    def get_stats(self) -> Dict:
        """Get statistics"""
        return self.stats.copy()


# Convenience function
def translate_with_quality_check(paragraphs: List[Dict],
                                 client, model, glossary_dict,
                                 callback=None,
                                 chunk_size=20,
                                 custom_prompt="") -> Tuple[List[Dict], Dict]:
    """
    Translate paragraphs (with quality checks)

    Returns:
        (translated_paragraphs, stats)
    """
    translator = SmartTranslator(
        client=client,
        model=model,
        glossary_dict=glossary_dict,
        chunk_size=chunk_size,
        custom_prompt=custom_prompt
    )

    results = translator.translate_paragraphs(paragraphs, callback)
    stats = translator.get_stats()

    return results, stats


if __name__ == "__main__":
    # Test
    print("✅ SmartTranslator 模塊已就緒")
    print("   - 自動漏翻檢測")
    print("   - 智能重試機制")
    print("   - Token 優化")
