"""
Glossary review engine.
Handles batch processing, character identification, and priority-tier logic.
"""
import openai
import json
import re


class GlossaryReviewer:
    """
    Glossary reviewer that checks and refines term translations.
    """

    # Character keywords (used to identify character terms)
    CHARACTER_KEYWORDS = ["人名", "角色", "character", "人物", "姓名"]

    def __init__(self, api_key, base_url="https://api.deepseek.com", model="deepseek-chat"):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.config = {
            "connect_timeout": 120.0
        }

    def review_glossary_batch(self, glossary, novel_background="", custom_prompt="", callback=None):
        """
        Review the glossary in batches.

        Args:
            glossary: List of glossary terms [{src, dst, info, frequency}]
            novel_background: Novel background/setting
            custom_prompt: Custom prompt text
            callback: Progress callback

        Returns:
            List[dict]: Reviewed glossary list
        """
        batch_size = 20  # 20 terms per batch
        reviewed_glossary = []
        total = len(glossary)

        for i in range(0, total, batch_size):
            batch = glossary[i:i + batch_size]

            if callback:
                callback({
                    'current': i,
                    'total': total,
                    'percent': int((i / total) * 100),
                    'message': f'校對中... ({i}/{total})'
                })

            try:
                reviewed_batch = self._process_batch(batch, novel_background, custom_prompt)
                reviewed_glossary.extend(reviewed_batch)

            except Exception as e:
                print(f"Batch {i//batch_size} review failed: {e}")
                # Keep the original terms if the review fails
                reviewed_glossary.extend(batch)

        return reviewed_glossary

    def _process_batch(self, batch, novel_background, custom_prompt=""):
        """
        Process a single batch of terms.
        """
        # Build the batch list (including priority tier)
        batch_list = []

        for term in batch:
            korean_term = term['src'].strip()
            freq = term.get('frequency', 1)
            info = term.get('info', '')

            # Determine whether this is a core lore term
            is_lore = korean_term in novel_background

            # Assign a priority tier
            tier = "S" if is_lore else ("A" if freq >= 5 else "C")
            instruction = "【核心設定】" if is_lore else ("【高頻詞】" if freq >= 5 else "【低頻詞】")

            # Determine whether this is a character term
            is_character = any(k in info for k in self.CHARACTER_KEYWORDS)

            # Extract source-text context (up to 3 entries from the term's contexts, to keep the prompt from getting too long)
            contexts = term.get('contexts', [])
            context = "\n".join(contexts[:3]) if contexts else ""

            batch_list.append({
                "korean_term": korean_term,
                "chinese_translation": term.get('dst', '').strip(),
                "tier": tier,
                "instruction": instruction,
                "is_character": is_character,
                "current_info": info,
                "context": context  # Source-text context (used for consistency/gender inference)
            })

        # Build the prompt
        prompt = self._get_batch_prompt(novel_background, batch_list, custom_prompt)

        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=8192,
            timeout=self.config['connect_timeout']
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON
        reviewed = self._parse_json_response(content)

        # Build an index of the original terms (to retain fields like frequency and contexts)
        original_map = {t['src']: t for t in batch}

        # Convert back to the original format
        result = []
        for item in reviewed:
            korean_term = item.get('korean_term', '')
            original = original_map.get(korean_term, {})

            result.append({
                'src': korean_term,
                'dst': item.get('recommended_translation', item.get('chinese_translation', '')),
                'info': item.get('current_info', ''),
                'frequency': original.get('frequency', 1),
                'contexts': original.get('contexts', []),  # Keep source-text context for later review/viewing
                'should_delete': item.get('should_delete', False),
                'justification': item.get('justification', ''),
                'gender': item.get('gender'),
                'sibling': item.get('sibling')
            })

        return result

    def _get_batch_prompt(self, novel_background, batch_list, custom_prompt=""):
        """
        Build the prompt for a batch review request.
        """
        # Base prompt
        base_prompt = custom_prompt if custom_prompt else """你是專業的韓文小說翻譯審校專家。請審查以下術語翻譯的準確性和一致性。

審校標準：
1. **人名翻譯**：
   - 常見韓國姓氏（金、樸、李、崔等）使用標準音譯
   - 不常見姓氏根據發音準確音譯
   - 名字部分使用雅緻的漢字對應或音譯

2. **地名翻譯**：
   - 真實地名使用標準譯名
   - 虛構地名音譯或意譯，保持風格一致

3. **專有名詞**：
   - 技能、物品、稱號等根據含義意譯
   - 保持譯名的文學性和易讀性

4. **一致性原則**：
   - 相同術語必須使用相同翻譯
   - 類似術語保持風格一致

5. **刪除建議**：
   - 普通名詞（書、桌子）應刪除
   - 重複術語（已有更完整版本）應刪除
"""

        # If there are character terms, add character-identification guidance
        if any(item.get("is_character") for item in batch_list):
            char_guidance = """
【角色性別和手足關係判斷】
對於角色（is_character 為 true），請額外判斷：
1. **gender（性別）**：根據原文線索判斷，**必須**在「男性」/「女性」之間二選一，不得為空或 unknown
   - 線索包括：稱謂（哥哥/姐姐/先生/小姐）、代詞（他/她）、名字特徵、對話語氣
   - 即使線索較弱，也要選出最可能的性別

2. **sibling（手足關係）**：該角色是否有更年幼的手足
   - 如果原文明確提到弟弟/妹妹，填寫「弟弟」/「妹妹」/「弟弟妹妹」
   - 否則填 null（不得猜測）

對於非角色術語，gender 和 sibling 一律填 null。
"""
            base_prompt += "\n" + char_guidance

        # Fixed formatting requirements
        fixed_suffix = f"""
請根據「小說背景設定」、「權重等級」與「術語參考」，判斷下列術語：

小說背景設定:
{novel_background if novel_background else "（無）"}

待處理術語列表:
{json.dumps(batch_list, ensure_ascii=False, indent=2)}

請嚴格按 JSON 格式返回列表。每個物件必須包含：
- korean_term: 原韓文術語
- original_translation: 原翻譯
- recommended_translation: 建議翻譯（修正後的）
- should_delete: 是否應刪除（true/false）
- deletion_reason: 刪除理由（如果 should_delete 為 true）
- judgment_emoji: 判斷表情（✅ 正確 / ⚠️ 需修正 / ❌ 應刪除）
- justification: 判斷理由

【角色附加判斷】對於 is_character 為 true 的術語，額外加入：
- gender: 性別（"男性" / "女性"，必須二選一）
- sibling: 手足關係（"弟弟" / "妹妹" / "弟弟妹妹" / null）

對於 is_character 為 false 的術語，gender 與 sibling 一律填 null。
"""

        return base_prompt + "\n" + fixed_suffix

    def _parse_json_response(self, response_text):
        """Parse JSON (with three-layer fallback parsing)."""
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
                # Find the last complete object
                last_complete = clean_text.rfind('}')
                if last_complete > 0:
                    truncated = clean_text[:last_complete + 1] + ']'
                    data = json.loads(truncated)
                    return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                pass

        return []


def review_glossary_with_llm(glossary, api_key, base_url, model,
                             novel_background="", custom_prompt="", callback=None):
    """
    Review a glossary using an LLM.

    Args:
        glossary: List of glossary terms
        api_key: API key
        base_url: API endpoint
        model: Model name
        novel_background: Novel background/setting
        custom_prompt: Custom prompt text
        callback: Progress callback

    Returns:
        List[dict]: Reviewed glossary list
    """
    reviewer = GlossaryReviewer(api_key, base_url, model)
    return reviewer.review_glossary_batch(
        glossary,
        novel_background=novel_background,
        custom_prompt=custom_prompt,
        callback=callback
    )


if __name__ == '__main__':
    # Test
    import sys
    import os

    if len(sys.argv) > 1:
        import json

        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            glossary = json.load(f)

        api_key = os.getenv('DEEPSEEK_API_KEY', '')

        if not api_key:
            print("請設置 DEEPSEEK_API_KEY 環境變量")
            sys.exit(1)

        def progress_callback(prog):
            print(f"{prog['message']} - {prog['percent']}%")

        print(f"開始校對 {len(glossary)} 個術語")
        reviewed = review_glossary_with_llm(
            glossary,
            api_key,
            "https://api.deepseek.com",
            "deepseek-chat",
            callback=progress_callback
        )
        print(f"\n校對完成")
        for i, term in enumerate(reviewed[:10], 1):
            print(f"{i}. {term['src']} → {term['dst']} ({term.get('justification', '')})")
