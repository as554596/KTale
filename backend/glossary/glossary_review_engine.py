# -*- coding: utf-8 -*-
"""
Glossary review engine v2.0.
Supports two review passes, manual edits, incremental display of changes,
and traditional/simplified Chinese unification.
"""

import json
import os
from typing import List, Dict, Tuple
from traditional_converter import unified_glossary, advanced_to_traditional, check_mixed_chars


class GlossaryReviewEngine:
    """
    Glossary review engine.

    Features:
    1. Two review passes (basic review + consistency review)
    2. Supports editing dst (translation) and info (gender/category)
    3. Only shows terms that were changed
    4. Download includes everything (for use in translation)
    """

    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.modification_history = []  # Records all modifications

    def first_round_review(self, glossary: List[Dict], novel_background: str,
                          callback=None) -> Tuple[List[Dict], List[Dict]]:
        """
        First review pass: basic review.

        Args:
            glossary: Original glossary [{src, dst, info, frequency, reference}, ...]
            novel_background: Novel background/setting
            callback: Progress callback

        Returns:
            (reviewed_glossary, modifications)
            - reviewed_glossary: The full glossary after review
            - modifications: Only the terms that were changed
        """
        print("\n=== 第一輪校對：基礎審查 ===")

        modifications = []
        reviewed_glossary = []

        total = len(glossary)
        batch_size = 10  # 10 terms per batch

        for i in range(0, total, batch_size):
            batch = glossary[i:i + batch_size]

            if callback:
                callback({
                    'current': i,
                    'total': total,
                    'percent': int((i / total) * 100),
                    'message': f'第一輪校對 {i}/{total}'
                })

            # Call the AI to review
            batch_results = self._review_batch(batch, novel_background, round_num=1)

            # Process the results
            for original_term, ai_result in zip(batch, batch_results):
                reviewed_term = self._merge_ai_result(original_term, ai_result)

                # Check whether anything changed
                if self._has_modification(original_term, reviewed_term):
                    modifications.append({
                        'src': original_term['src'],
                        'original_dst': original_term['dst'],
                        'reviewed_dst': reviewed_term['dst'],
                        'original_info': original_term.get('info', ''),
                        'reviewed_info': reviewed_term.get('info', ''),
                        'reason': ai_result.get('justification', ''),
                        'should_delete': ai_result.get('should_delete', False),
                        'round': 1
                    })

                reviewed_glossary.append(reviewed_term)

        print(f"✅ 第一輪完成：{len(modifications)} 個術語被修改")
        return reviewed_glossary, modifications

    def second_round_review(self, glossary: List[Dict], novel_background: str,
                           callback=None) -> Tuple[List[Dict], List[Dict]]:
        """
        Second review pass: consistency review.

        Mainly checks:
        1. Consistency of character gender
        2. Consistency of term translations
        3. Contextual relationships

        Args:
            glossary: The glossary after the first review pass
            novel_background: Novel background/setting
            callback: Progress callback

        Returns:
            (final_glossary, modifications)
        """
        print("\n=== 第二輪校對：一致性審查 ===")

        modifications = []
        final_glossary = []

        # Group by category (focus the check on character names)
        characters = [t for t in glossary if '人名' in t.get('info', '')]
        other_terms = [t for t in glossary if '人名' not in t.get('info', '')]

        print(f"   人名: {len(characters)} 個")
        print(f"   其他: {len(other_terms)} 個")

        # Mainly check consistency of character names
        if characters:
            batch_size = 20
            total = len(characters)

            for i in range(0, total, batch_size):
                batch = characters[i:i + batch_size]

                if callback:
                    callback({
                        'current': i,
                        'total': total,
                        'percent': int((i / total) * 100),
                        'message': f'第二輪校對（一致性） {i}/{total}'
                    })

                # AI consistency check
                batch_results = self._consistency_check_batch(batch, novel_background)

                for original_term, ai_result in zip(batch, batch_results):
                    reviewed_term = self._merge_ai_result(original_term, ai_result)

                    # Check whether anything changed
                    if self._has_modification(original_term, reviewed_term):
                        modifications.append({
                            'src': original_term['src'],
                            'original_dst': original_term['dst'],
                            'reviewed_dst': reviewed_term['dst'],
                            'original_info': original_term.get('info', ''),
                            'reviewed_info': reviewed_term.get('info', ''),
                            'reason': ai_result.get('justification', ''),
                            'round': 2
                        })

                    final_glossary.append(reviewed_term)

        # Keep other terms unchanged
        final_glossary.extend(other_terms)

        print(f"✅ 第二輪完成：{len(modifications)} 個術語被修改")
        return final_glossary, modifications

    def _review_batch(self, batch: List[Dict], novel_background: str,
                     round_num: int = 1) -> List[Dict]:
        """
        Call the AI to review a batch of terms.

        Args:
            batch: The batch of terms
            novel_background: Novel background/setting
            round_num: Review pass number (1 = basic, 2 = consistency)

        Returns:
            List of AI review results
        """
        prompt = self._build_review_prompt(batch, novel_background, round_num)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是專業的韓文翻譯術語審查員。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            output = response.choices[0].message.content
            return self._parse_ai_response(output)

        except Exception as e:
            print(f"  ❌ API 錯誤: {e}")
            # Return the terms unchanged
            return [{'korean_term': t['src'], 'recommended_translation': t['dst'],
                    'should_delete': False, 'justification': '跳過'} for t in batch]

    def _build_review_prompt(self, batch: List[Dict], novel_background: str,
                            round_num: int) -> str:
        """Build the review prompt."""

        if round_num == 1:
            # First pass: basic review
            prompt = f"""請審查以下韓文術語的中文翻譯，判斷是否需要修改。

小說背景：
{novel_background}

待審查術語：
{json.dumps([{
    'korean_term': t['src'],
    'chinese_translation': t['dst'],
    'info': t.get('info', ''),
    'frequency': t.get('frequency', 0),
    'context': t.get('reference', '')
} for t in batch], ensure_ascii=False, indent=2)}

審查規則：
1. **人名**：檢查音譯是否準確，判斷性別（男性人名/女性人名/性別不明）
2. **地名**：檢查翻譯是否恰當
3. **專有名詞**：檢查意譯或音譯的選擇
4. **高頻詞**：優先保證翻譯準確
5. **低頻詞**：可建議刪除（如果是普通詞彙）

返回 JSON 格式：
[
  {{
    "korean_term": "原文",
    "original_translation": "原譯文",
    "recommended_translation": "建議譯文（如無需修改則與原譯文相同）",
    "recommended_info": "建議分類（人名請標註性別：男性人名/女性人名）",
    "should_delete": false,
    "deletion_reason": "",
    "justification": "審查理由"
  }}
]"""

        else:
            # Second pass: consistency review
            prompt = f"""請審查以下人名術語的**性別和翻譯一致性**。

小說背景：
{novel_background}

人名列表：
{json.dumps([{
    'korean_term': t['src'],
    'chinese_translation': t['dst'],
    'info': t.get('info', ''),
    'context': t.get('reference', '')
} for t in batch], ensure_ascii=False, indent=2)}

一致性規則：
1. **性別判斷**：根據上下文、代詞、稱謂判斷性別（必須是：男性人名/女性人名）
2. **音譯一致性**：相似發音的人名應使用相似的中文字
3. **關係一致性**：家族成員、兄弟姐妹的翻譯風格應一致

返回 JSON 格式：
[
  {{
    "korean_term": "原文",
    "original_translation": "原譯文",
    "recommended_translation": "建議譯文（如無需修改則與原譯文相同）",
    "recommended_info": "建議分類（必須包含性別）",
    "justification": "一致性審查理由"
  }}
]"""

        return prompt

    def _consistency_check_batch(self, batch: List[Dict],
                                 novel_background: str) -> List[Dict]:
        """Consistency check (used only in the second review pass)."""
        return self._review_batch(batch, novel_background, round_num=2)

    def _parse_ai_response(self, response_text: str) -> List[Dict]:
        """Parse the JSON returned by the AI."""
        import re

        # Strip markdown code-fence markers
        clean_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()

        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            # Try to extract the JSON portion
            match = re.search(r'\[.*\]', clean_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass

        # Return an empty list on failure
        print("  ⚠️ JSON 解析失敗")
        return []

    def _merge_ai_result(self, original: Dict, ai_result: Dict) -> Dict:
        """Merge the AI result into the original term (unifying to traditional Chinese)."""
        merged = original.copy()

        # Update the translation (unify to traditional Chinese)
        if 'recommended_translation' in ai_result:
            dst = ai_result['recommended_translation']
            # Convert to traditional Chinese
            merged['dst'] = advanced_to_traditional(dst)

        # Update category/gender (unify to traditional Chinese)
        if 'recommended_info' in ai_result:
            info = ai_result['recommended_info']
            # Convert to traditional Chinese
            merged['info'] = advanced_to_traditional(info)

        # Mark whether this term should be deleted
        if ai_result.get('should_delete', False):
            merged['_should_delete'] = True
            merged['_deletion_reason'] = ai_result.get('deletion_reason', '')

        return merged

    def _has_modification(self, original: Dict, reviewed: Dict) -> bool:
        """Check whether anything changed."""
        dst_changed = original.get('dst', '') != reviewed.get('dst', '')
        info_changed = original.get('info', '') != reviewed.get('info', '')
        deleted = reviewed.get('_should_delete', False)

        return dst_changed or info_changed or deleted

    def apply_manual_edits(self, glossary: List[Dict],
                          edits: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Apply manual edits.

        Args:
            glossary: The current glossary
            edits: List of manual edits [{src, dst, info}, ...]

        Returns:
            (updated_glossary, manual_modifications)
        """
        print("\n=== 應用手動編輯 ===")

        edit_map = {e['src']: e for e in edits}
        manual_modifications = []
        updated_glossary = []

        for term in glossary:
            src = term['src']

            if src in edit_map:
                edit = edit_map[src]
                original_dst = term['dst']
                original_info = term.get('info', '')

                # Apply the edit
                term['dst'] = edit.get('dst', original_dst)
                term['info'] = edit.get('info', original_info)

                # Record the modification
                if original_dst != term['dst'] or original_info != term['info']:
                    manual_modifications.append({
                        'src': src,
                        'original_dst': original_dst,
                        'reviewed_dst': term['dst'],
                        'original_info': original_info,
                        'reviewed_info': term['info'],
                        'reason': '手動編輯',
                        'round': 'manual'
                    })

            updated_glossary.append(term)

        print(f"✅ 手動編輯完成：{len(manual_modifications)} 個術語被修改")
        return updated_glossary, manual_modifications

    def export_results(self, glossary: List[Dict], modifications: List[Dict],
                      output_dir: str) -> Dict:
        """
        Export the results (unifying to traditional/simplified Chinese).

        Generates two files:
        1. modified.json - only the changed terms (for the user to review)
        2. glossary_reviewed.json - the full glossary (for use in translation)

        Args:
            glossary: The final glossary
            modifications: All modification records
            output_dir: Output directory

        Returns:
            Dict of output file paths
        """
        os.makedirs(output_dir, exist_ok=True)

        # Unify traditional/simplified Chinese
        print("\n=== 統一繁簡體 ===")
        unified_glossary_list = unified_glossary(glossary)

        # Check for and report mixed traditional/simplified usage
        mixed_count = 0
        for term in unified_glossary_list:
            mixed_info = check_mixed_chars(term.get('dst', ''))
            if mixed_info['has_mixed']:
                mixed_count += 1
                print(f"  修正: {term['src']} - {mixed_info['simplified_chars']}")

        if mixed_count > 0:
            print(f"✅ 已修正 {mixed_count} 個繁簡混雜的術語")
        else:
            print("✅ 未發現繁簡混雜")

        # 1. Export only the changed terms
        modified_path = os.path.join(output_dir, 'modified.json')
        with open(modified_path, 'w', encoding='utf-8') as f:
            json.dump(modifications, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 修改記錄: {modified_path}")
        print(f"   共 {len(modifications)} 個修改")

        # 2. Export the full glossary (for translation use, already unified to traditional/simplified)
        reviewed_path = os.path.join(output_dir, 'glossary_reviewed.json')

        # Filter out terms marked for deletion
        final_glossary = [
            {'src': t['src'], 'dst': t['dst'], 'info': t.get('info', ''),
             'contexts': t.get('contexts', [])}  # Keep the full context
            for t in unified_glossary_list
            if not t.get('_should_delete', False)
        ]

        with open(reviewed_path, 'w', encoding='utf-8') as f:
            json.dump(final_glossary, f, ensure_ascii=False, indent=2)

        print(f"✅ 完整術語表: {reviewed_path}")
        print(f"   共 {len(final_glossary)} 個術語（已刪除 {len(glossary) - len(final_glossary)} 個）")
        print(f"   ✅ 已統一爲繁體中文")

        return {
            'modified': modified_path,
            'reviewed': reviewed_path,
            'stats': {
                'total': len(glossary),
                'modified': len(modifications),
                'deleted': len(glossary) - len(final_glossary),
                'final': len(final_glossary),
                'mixed_fixed': mixed_count
            }
        }


if __name__ == "__main__":
    print("✅ GlossaryReviewEngine v2.0 已就緒")
    print("   - 兩輪校對（基礎 + 一致性）")
    print("   - 支持編輯 dst 和 info")
    print("   - 只顯示修改內容")
    print("   - 完整導出用於翻譯")
