"""
Glossary extraction engine.
Uses an LLM API to extract terms (not simple frequency counting).
"""
import openai
import json
import re
from collections import Counter


class GlossaryExtractor:
    """
    Glossary extractor that uses an LLM to identify terms requiring translation.
    """

    def __init__(self, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def extract_from_text_chunks(self, text_chunks, source_lang="韓文", target_lang="繁體中文",
                                 chunk_char_limit=3000, callback=None):
        """
        Extract glossary terms from text chunks.

        Args:
            text_chunks: List of text chunks
            source_lang: Source language
            target_lang: Target language
            chunk_char_limit: Character limit per chunk
            callback: Progress callback

        Returns:
            List[dict]: Extracted glossary list [{src, dst, info, frequency}]
        """
        all_candidates = []
        total_chunks = len(text_chunks)

        for i, chunk in enumerate(text_chunks):
            if callback:
                callback({
                    'current': i,
                    'total': total_chunks,
                    'percent': int((i / total_chunks) * 100),
                    'message': f'提取術語中... ({i}/{total_chunks})'
                })

            try:
                # Use the LLM to extract terms from this chunk
                candidates = self._extract_chunk(chunk, source_lang, target_lang)
                all_candidates.extend(candidates)

            except Exception as e:
                print(f"Chunk {i} extraction failed: {e}")
                continue

        # Merge and normalize
        normalized = self._normalize_candidates(all_candidates)

        # Count frequencies
        glossary = self._count_frequencies(normalized, text_chunks)

        return glossary

    def _extract_chunk(self, text_chunk, source_lang, target_lang):
        """
        Use an LLM to extract and translate terms from a single text chunk,
        including automatic translation and gender inference.
        """
        prompt = f"""請從以下{source_lang}文本中提取需要翻譯的術語，並提供{target_lang}翻譯。

提取規則：
1. **人名**：所有角色名字（請判斷性別：男性人名/女性人名/性別不明）
2. **地名**：所有地點名稱
3. **專有名詞**：組織、物品、技能、稱號等
4. **核心設定**：世界觀相關的重要詞彙
5. **高頻詞**：反復出現的關鍵詞

不需要提取：
- 普通名詞（書、桌子、房間等）
- 動詞（去、看、說等）
- 形容詞（大、小、美麗等）
- 代詞（我、你、他等）

文本：
{text_chunk}

請返回 JSON 格式的術語列表，每個術語包含：
- src: 原文術語
- dst: {target_lang}翻譯（人名保持音譯，地名/專有名詞提供恰當翻譯）
- info: 分類（**對於人名，必須標註性別：男性人名/女性人名/性別不明**；其他為：地名/專有名詞等）

格式範例：
[
  {{"src": "노아", "dst": "諾亞", "info": "男性人名"}},
  {{"src": "소피아", "dst": "索菲亞", "info": "女性人名"}},
  {{"src": "갤러리", "dst": "畫廊", "info": "地名/場所"}},
  {{"src": "드래곤 길드", "dst": "龍之公會", "info": "組織"}},
  ...
]

重要：
- 人名必須判斷性別（根據文本中的代詞、描述、互動推斷）
- 如果完全無法判斷性別，標註為「性別不明」
- 只返回 JSON，不要其他說明
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4096
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON
            return self._parse_json_response(content)

        except Exception as e:
            print(f"API call failed: {e}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise Exception(f"術語提取失敗: {str(e)}")

    def _parse_json_response(self, response_text):
        """Parse the JSON returned by the AI (three-layer fallback parsing)."""
        if not response_text:
            return []

        clean_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()

        # Layer 1: direct parse
        try:
            data = json.loads(clean_text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            pass

        # Layer 2: extract JSON array
        match = re.search(r'\[.*\]', clean_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                pass

        # Layer 3: repair truncated array
        if clean_text.startswith('[') and not clean_text.rstrip().endswith(']'):
            try:
                data = json.loads(clean_text + ']')
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                pass

        return []

    def _normalize_candidates(self, candidates):
        """
        Normalize candidate terms (deduplicate and clean up).
        """
        seen = {}

        for item in candidates:
            src = item.get('src', '').strip()
            if not src:
                continue

            # Strip leading/trailing whitespace and punctuation
            src = src.strip('.,;:!?。，；：！？「」『』""')

            if src not in seen:
                seen[src] = {
                    'src': src,
                    'dst': item.get('dst', ''),
                    'info': item.get('info', '')
                }

        return list(seen.values())

    def _count_frequencies(self, normalized, text_chunks):
        """
        Count how often each term appears and extract source-text context.
        """
        import re

        # Merge all text
        full_text = '\n'.join(text_chunks)

        # Split the text into sentences (used for context extraction)
        sentences = re.split(r'[。！？\n]+', full_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        glossary = []
        for term in normalized:
            src = term['src']
            # Count occurrences
            frequency = full_text.count(src)

            if frequency > 0:
                # Extract sentences containing this term as source-text context (up to 5, preferring longer sentences)
                contexts = []
                for sentence in sentences:
                    if src in sentence:
                        contexts.append(sentence)

                # Sort by length and keep the 5 longest sentences as context
                contexts.sort(key=len, reverse=True)
                contexts = contexts[:5]

                glossary.append({
                    'src': src,
                    'dst': term.get('dst', ''),
                    'info': term.get('info', ''),
                    'frequency': frequency,
                    'contexts': contexts  # Source-text context (up to 5 of the longer sentences)
                })

        # Sort by frequency
        glossary.sort(key=lambda x: x['frequency'], reverse=True)

        return glossary


def extract_glossary_with_llm(file_paths, api_key, base_url, model, callback=None):
    """
    Extract a glossary from files using an LLM.

    Args:
        file_paths: List of file paths
        api_key: API key
        base_url: API endpoint
        model: Model name
        callback: Progress callback

    Returns:
        List[dict]: List of glossary terms
    """
    print(f"=== Extract Glossary With LLM ===")
    print(f"File paths: {file_paths}")
    print(f"API key exists: {bool(api_key)}")

    extractor = GlossaryExtractor(api_key, base_url, model)

    # Collect all text
    all_text_chunks = []

    for filepath in file_paths:
        print(f"\nProcessing file: {filepath}")

        if filepath.endswith('.epub'):
            try:
                from enhanced_epub_parser import EnhancedEPUBParser
                print(f"Using EnhancedEPUBParser for EPUB")
                parser = EnhancedEPUBParser()
                nodes = parser.extract_text_from_epub(filepath)
                print(f"Extracted {len(nodes)} nodes from EPUB")

                chunks = [node['text'] for node in nodes if node['text'].strip()]
                print(f"Got {len(chunks)} text chunks from nodes")

                total_chars = sum(len(c) for c in chunks)
                print(f"Total characters: {total_chars}")

                all_text_chunks.extend(chunks)
            except Exception as e:
                print(f"ERROR processing EPUB: {e}")
                import traceback
                traceback.print_exc()

        elif filepath.endswith('.txt'):
            try:
                from txt_translator import TxtTranslator
                print(f"Using TxtTranslator for TXT")
                translator = TxtTranslator()
                paragraphs = translator.extract_paragraphs(filepath)
                print(f"Extracted {len(paragraphs)} paragraphs from TXT")

                chunks = [p['text'] for p in paragraphs if p['text'].strip()]
                print(f"Got {len(chunks)} text chunks")

                all_text_chunks.extend(chunks)
            except Exception as e:
                print(f"ERROR processing TXT: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n=== Total text chunks collected: {len(all_text_chunks)} ===")

    if not all_text_chunks:
        print("WARNING: No text chunks found!")
        return []

    # Extract in chunks (3000 characters per chunk)
    chunk_limit = 3000
    batched_chunks = []
    current_batch = ""

    for chunk in all_text_chunks:
        if len(current_batch) + len(chunk) > chunk_limit:
            if current_batch:
                batched_chunks.append(current_batch)
            current_batch = chunk
        else:
            current_batch += "\n" + chunk

    if current_batch:
        batched_chunks.append(current_batch)

    print(f"Created {len(batched_chunks)} batches for extraction")

    # Extract terms
    glossary = extractor.extract_from_text_chunks(
        batched_chunks,
        callback=callback
    )

    print(f"Extracted {len(glossary)} terms")
    return glossary


if __name__ == '__main__':
    # Test
    import sys
    import os

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        api_key = os.getenv('DEEPSEEK_API_KEY', '')

        if not api_key:
            print("請設置 DEEPSEEK_API_KEY 環境變量")
            sys.exit(1)

        def progress_callback(prog):
            print(f"{prog['message']} - {prog['percent']}%")

        print(f"開始提取術語: {file_path}")
        glossary = extract_glossary_with_llm(
            [file_path],
            api_key,
            "https://api.deepseek.com",
            "deepseek-chat",
            callback=progress_callback
        )
        print(f"\n提取到 {len(glossary)} 個術語")
        for i, term in enumerate(glossary[:10], 1):
            print(f"{i}. {term['src']} - {term['frequency']}次 - {term['info']}")
