# -*- coding: utf-8 -*-
"""
Traditional/Simplified Chinese unification tool
Resolves the issue of mixed traditional/simplified characters in AI output
"""

# Common traditional/simplified mix-up mapping table (characters AI often gets wrong)
COMMON_MIXED_CHARS = {
    # Simplified -> Traditional
    '为': '為',
    '么': '麼',
    '们': '們',
    '这': '這',
    '那': '那',
    '说': '說',
    '话': '話',
    '时': '時',
    '间': '間',
    '来': '來',
    '还': '還',
    '过': '過',
    '没': '沒',
    '应': '應',
    '该': '該',
    '会': '會',
    '关': '關',
    '门': '門',
    '头': '頭',
    '发': '發',
    '长': '長',
    '种': '種',
    '样': '樣',
    '经': '經',
    '历': '歷',
    '学': '學',
    '气': '氣',
    '电': '電',
    '台': '臺',
    '国': '國',
    '东': '東',
    '西': '西',
    '南': '南',
    '北': '北',
    '风': '風',
    '觉': '覺',
    '认': '認',
    '记': '記',
    '让': '讓',
    '听': '聽',
    '见': '見',
    '与': '與',
    '给': '給',
    '从': '從',
    '书': '書',
    '开': '開',
    '当': '當',
    '变': '變',
    '业': '業',
    '运': '運',
    '动': '動',
    '声': '聲',
    '备': '備',
    '准': '準',
    '实': '實',
    '虚': '虛',
    '处': '處',
    '节': '節',
    '龙': '龍',
    '凤': '鳳',
    '马': '馬',
    '鸟': '鳥',
    '鱼': '魚',
    '车': '車',
    '张': '張',
    '刘': '劉',
    '陈': '陳',
    '黄': '黃',
    '周': '週',
    '吴': '吳',
    '郑': '鄭',
    '亚': '亞',
    '画': '畫',
    '廊': '廊',
    '诺': '諾',
    '索': '索',
    '菲': '菲',
    '专': '專',
    '词': '詞',
    '术': '術',
    '语': '語',
    '义': '義',
    '名': '名',
    '性': '性',
    '地': '地',
    '有': '有',
    '里': '裡',
    '后': '後',
    '前': '前',
    '面': '面',
    '个': '個',
    '对': '對',
    '于': '於',
    '在': '在',
    '她': '她',
    '他': '他',
    '它': '它',
}


def detect_text_type(text):
    """
    Detect whether the text is predominantly traditional or simplified Chinese

    Args:
        text: input text

    Returns:
        'traditional' or 'simplified'
    """
    if not text:
        return 'traditional'

    traditional_count = 0
    simplified_count = 0

    # Detect characteristic characters
    for char in text:
        if char in COMMON_MIXED_CHARS.values():  # Traditional characteristic
            traditional_count += 1
        elif char in COMMON_MIXED_CHARS.keys():  # Simplified characteristic
            simplified_count += 1

    # Determine the predominant type
    if simplified_count > traditional_count:
        return 'simplified'
    else:
        return 'traditional'


def unified_to_traditional(text):
    """
    Uniformly convert to traditional Chinese

    Args:
        text: input text (may be mixed)

    Returns:
        unified traditional Chinese text
    """
    if not text:
        return text

    result = text

    # Replace simplified characters with traditional ones one by one
    for simp, trad in COMMON_MIXED_CHARS.items():
        result = result.replace(simp, trad)

    return result


def unified_to_simplified(text):
    """
    Uniformly convert to simplified Chinese

    Args:
        text: input text (may be mixed)

    Returns:
        unified simplified Chinese text
    """
    if not text:
        return text

    result = text

    # Replace traditional characters with simplified ones one by one
    for simp, trad in COMMON_MIXED_CHARS.items():
        result = result.replace(trad, simp)

    return result


def batch_unified_to_traditional(texts):
    """
    Batch convert to traditional Chinese

    Args:
        texts: list of texts

    Returns:
        list of converted texts
    """
    return [unified_to_traditional(text) for text in texts]


def unified_glossary(glossary):
    """
    Unify the traditional/simplified characters in the glossary

    Args:
        glossary: glossary list [{src, dst, info, ...}, ...]

    Returns:
        the unified glossary
    """
    unified = []

    for term in glossary:
        unified_term = term.copy()

        # Unify the translation
        if 'dst' in unified_term and unified_term['dst']:
            unified_term['dst'] = unified_to_traditional(unified_term['dst'])

        # Unify the category info
        if 'info' in unified_term and unified_term['info']:
            unified_term['info'] = unified_to_traditional(unified_term['info'])

        unified.append(unified_term)

    return unified


def s2t_glossary(glossary, to_simplified=False):
    """
    Convert the glossary between traditional and simplified

    Args:
        glossary: glossary list [{src, dst, info, ...}, ...]
        to_simplified: True=convert to simplified, False=convert to traditional

    Returns:
        the converted glossary
    """
    converted = []

    for term in glossary:
        converted_term = term.copy()

        if to_simplified:
            # Convert to simplified
            if 'dst' in converted_term and converted_term['dst']:
                converted_term['dst'] = unified_to_simplified(converted_term['dst'])
            if 'info' in converted_term and converted_term['info']:
                converted_term['info'] = unified_to_simplified(converted_term['info'])
        else:
            # Convert to traditional
            if 'dst' in converted_term and converted_term['dst']:
                converted_term['dst'] = unified_to_traditional(converted_term['dst'])
            if 'info' in converted_term and converted_term['info']:
                converted_term['info'] = unified_to_traditional(converted_term['info'])

        converted.append(converted_term)

    return converted


def check_mixed_chars(text):
    """
    Check for mixed traditional/simplified characters in the text

    Args:
        text: input text

    Returns:
        {
            'has_mixed': bool,
            'simplified_chars': List[str],
            'examples': List[dict]
        }
    """
    if not text:
        return {'has_mixed': False, 'simplified_chars': [], 'examples': []}

    simplified_found = []
    examples = []

    for simp, trad in COMMON_MIXED_CHARS.items():
        if simp in text:
            simplified_found.append(simp)
            # Find the surrounding context
            index = text.find(simp)
            start = max(0, index - 10)
            end = min(len(text), index + 11)
            context = text[start:end]
            examples.append({
                'char': simp,
                'should_be': trad,
                'context': context
            })

    return {
        'has_mixed': len(simplified_found) > 0,
        'simplified_chars': simplified_found,
        'examples': examples[:5]  # Only return the first 5 examples
    }


# Use opencc for more precise conversion (optional)
try:
    import opencc
    converter = opencc.OpenCC('s2twp.json')  # Simplified to Traditional (Taiwan)

    def advanced_to_traditional(text):
        """Advanced conversion using OpenCC"""
        if not text:
            return text
        try:
            return converter.convert(text)
        except:
            # Fall back to basic conversion
            return unified_to_traditional(text)

    print("[OK] OpenCC available (advanced conversion)")
    HAS_OPENCC = True

except ImportError:
    print("[WARNING] OpenCC not installed, using basic conversion")
    HAS_OPENCC = False

    def advanced_to_traditional(text):
        """Fallback to basic conversion"""
        return unified_to_traditional(text)


if __name__ == "__main__":
    # Test
    print("=" * 60)
    print("繁簡體統一轉換測試")
    print("=" * 60)

    test_cases = [
        "这是一个测试。",  # pure simplified
        "這是一個測試。",  # pure traditional
        "这是一个测试，包含繁体：測試",  # mixed
        "爲什麼會這樣？應該怎麼辦？",  # mixed
        "他說話的時候很認真。",  # mixed
    ]

    for i, text in enumerate(test_cases, 1):
        print(f"\n測試 {i}: {text}")

        # Detect the type
        text_type = detect_text_type(text)
        print(f"  檢測類型: {text_type}")

        # Check for mixing
        mixed_info = check_mixed_chars(text)
        if mixed_info['has_mixed']:
            print(f"  ⚠️ 發現簡體字符: {', '.join(mixed_info['simplified_chars'])}")
            for ex in mixed_info['examples']:
                print(f"     '{ex['char']}' 應爲 '{ex['should_be']}' (上下文: {ex['context']})")

        # Unify conversion
        unified = unified_to_traditional(text)
        print(f"  統一後: {unified}")

        # Advanced conversion (if available)
        if HAS_OPENCC:
            advanced = advanced_to_traditional(text)
            print(f"  高級轉換: {advanced}")

    print("\n" + "=" * 60)
    print("測試術語表統一")
    print("=" * 60)

    test_glossary = [
        {"src": "노아", "dst": "諾亞", "info": "男性人名"},
        {"src": "소피아", "dst": "索菲亚", "info": "女性人名"},  # simplified "亞"
        {"src": "갤러리", "dst": "画廊", "info": "地名"},  # simplified "畫"
        {"src": "드래곤", "dst": "龍", "info": "專有名詞"},  # traditional
    ]

    print("\n原始術語表:")
    for term in test_glossary:
        print(f"  {term['src']} -> {term['dst']} ({term['info']})")

    unified = unified_glossary(test_glossary)

    print("\n統一後:")
    for term in unified:
        print(f"  {term['src']} -> {term['dst']} ({term['info']})")

    print("\n✅ 測試完成")
