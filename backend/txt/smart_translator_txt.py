# -*- coding: utf-8 -*-
"""
TXT Smart Translator - Wrapper function with integrated quality detection
"""

from txt_translator import TxtTranslator
from smart_translator import SmartTranslator
import openai


def translate_txt_smart(txt_path, glossary, api_key, callback=None,
                       base_url="https://api.deepseek.com",
                       model="deepseek-chat",
                       batch_size=20,
                       custom_prompt=""):
    """
    Translate TXT using the smart translator (with quality detection and automatic retry)

    Args:
        txt_path: Source TXT path
        glossary: Glossary List[dict]
        api_key: API key
        callback: Progress callback function
        base_url: API endpoint URL
        model: Model name
        batch_size: Batch size
        custom_prompt: Custom translation prompt

    Returns:
        (output_path, stats)
    """
    # Create client
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    # Build glossary dictionary
    glossary_dict = {term['src']: term['dst'] for term in glossary if term.get('dst')}

    # Extract paragraphs
    txt_translator = TxtTranslator()
    paragraphs = txt_translator.extract_paragraphs(txt_path)

    if len(paragraphs) == 0:
        raise Exception("TXT 文件中沒有找到有效段落")

    # Use the smart translator
    smart_translator = SmartTranslator(
        client=client,
        model=model,
        glossary_dict=glossary_dict,
        chunk_size=batch_size,
        context_lines=3,
        source_lang="ko",  # Assume Korean
        target_lang="zh",
        custom_prompt=custom_prompt
    )

    # Translate
    translated_paragraphs = smart_translator.translate_paragraphs(paragraphs, callback)

    # Get statistics
    stats = smart_translator.get_stats()

    # Generate output file name
    output_path = txt_path.replace('.txt', '_translated_smart.txt')

    # Write back to file
    txt_translator.write_translated(translated_paragraphs, output_path)

    # Save quality report (for missed-translation review)
    quality_report_path = txt_path.replace('.txt', '_quality_report.json')
    save_quality_report(translated_paragraphs, quality_report_path, stats)

    return output_path, stats


def save_quality_report(translated_paragraphs, report_path, stats):
    """
    Save quality report JSON (contains quality info for all paragraphs)

    Args:
        translated_paragraphs: List of translation results
        report_path: Report save path
        stats: Statistics
    """
    import json

    # Find low-quality paragraphs
    low_quality = []
    high_quality = []

    for para in translated_paragraphs:
        confidence = para.get('confidence', 1.0)

        item = {
            'index': para['index'],
            'original': para.get('original', ''),
            'translation': para['text'],
            'confidence': confidence
        }

        if confidence < 0.7:
            low_quality.append(item)
        else:
            high_quality.append(item)

    report = {
        'stats': stats,
        'summary': {
            'total': len(translated_paragraphs),
            'low_quality_count': len(low_quality),
            'high_quality_count': len(high_quality),
            'low_quality_percent': round(len(low_quality) / max(len(translated_paragraphs), 1) * 100, 2)
        },
        'low_quality_paragraphs': sorted(low_quality, key=lambda x: x['confidence']),
        'all_paragraphs': translated_paragraphs
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✅ 質量報告已保存: {report_path}")
    print(f"   低質量段落: {len(low_quality)} / {len(translated_paragraphs)}")

    return report_path


if __name__ == "__main__":
    print("✅ SmartTranslator for TXT 已就緒")
