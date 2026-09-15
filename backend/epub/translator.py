"""
EPUB translation engine - streaming version (uses the enhanced parser)
Uses full DOM node traversal to avoid missing any text during translation.
"""
import openai
import zipfile
import os
import json
import time
import threading
from collections import defaultdict
from enhanced_epub_parser import EnhancedEPUBParser


def translate_epub_streaming(epub_path, glossary, api_key, callback=None,
                             base_url="https://api.deepseek.com",
                             model="deepseek-chat",
                             max_workers=3,
                             batch_size=10,
                             delay=0.5,
                             custom_prompt=""):
    """
    Translate an EPUB file in a streaming fashion (uses full node traversal to avoid missing text).

    Args:
        epub_path: Path to the source EPUB
        glossary: Glossary List[dict]
        api_key: API key
        callback: Progress callback function callback(progress_dict)
        base_url: API endpoint URL
        model: Model name
        max_workers: Number of concurrent workers (2-3 recommended for mobile)
        batch_size: Number of segments per batch (5-10 recommended for mobile)
        delay: Delay between requests in seconds (to avoid rate limiting)
        custom_prompt: Custom translation prompt

    Returns:
        str: Path to the translated EPUB
    """
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    output_path = epub_path.replace('.epub', '_translated.epub')

    # Use the enhanced parser
    parser = EnhancedEPUBParser()

    try:
        # Step 1: extract all text nodes
        if callback:
            callback({
                'current': 0,
                'total': 100,
                'percent': 5,
                'message': '正在解析 EPUB...'
            })

        text_nodes = parser.extract_text_from_epub(epub_path)
        total_nodes = len(text_nodes)

        if total_nodes == 0:
            raise Exception("EPUB 中沒有找到可翻譯的文本")

        # Build a glossary dict (for fast lookup)
        glossary_dict = {term['src']: term['dst'] for term in glossary if term.get('dst')}

        # Step 2: translate in batches
        if callback:
            callback({
                'current': 0,
                'total': total_nodes,
                'percent': 10,
                'message': f'開始翻譯 {total_nodes} 個文本節點...'
            })

        # Group nodes by file
        file_groups = defaultdict(list)
        for node in text_nodes:
            file_groups[node['file']].append(node)

        # Translate each file concurrently (progress updates per batch rather than per file, so large files don't stall progress display)
        from concurrent.futures import ThreadPoolExecutor, as_completed

        translated_nodes = {}  # {file: [translated_nodes]}
        progress_lock = threading.Lock()
        processed_counter = {'count': 0}

        def on_batch_done(batch_len):
            if delay > 0:
                time.sleep(delay)
            with progress_lock:
                processed_counter['count'] += batch_len
                processed = processed_counter['count']
                if callback:
                    callback({
                        'current': processed,
                        'total': total_nodes,
                        'percent': 10 + int((processed / total_nodes) * 80),
                        'message': f'翻譯中... ({processed}/{total_nodes})'
                    })

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    translate_file_nodes,
                    nodes, client, model, glossary_dict, batch_size, custom_prompt, on_batch_done
                ): filename
                for filename, nodes in file_groups.items()
            }

            for future in as_completed(futures):
                filename = futures[future]
                try:
                    translated_nodes[filename] = future.result()
                except Exception as e:
                    print(f"Failed to translate {filename}: {e}")
                    # Keep the original text if translation fails
                    translated_nodes[filename] = file_groups[filename]

        # Step 3: write back into the EPUB
        if callback:
            callback({
                'current': total_nodes,
                'total': total_nodes,
                'percent': 95,
                'message': '正在生成翻譯後的 EPUB...'
            })

        parser.translate_epub(epub_path, translated_nodes, output_path)

        if callback:
            callback({
                'current': total_nodes,
                'total': total_nodes,
                'percent': 100,
                'message': '翻譯完成！'
            })

        return output_path

    except Exception as e:
        print(f"Translation failed: {e}")
        raise


def translate_file_nodes(nodes, client, model, glossary_dict, batch_size=10, custom_prompt="", on_batch_done=None):
    """
    Translate all text nodes of a single file

    Args:
        nodes: List of text nodes [{text, file, index, type}]
        client: OpenAI client
        model: Model name
        glossary_dict: Glossary dict
        batch_size: Batch size
        custom_prompt: Custom prompt
        on_batch_done: Called once per completed batch as on_batch_done(batch_len), used for real-time progress reporting

    Returns:
        List[dict]: List of translated nodes (includes an 'original' field for verification)
    """
    translated_nodes = []

    # Process in batches
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i + batch_size]
        texts = [node['text'] for node in batch]

        # Translate this batch
        translated_texts = translate_batch(client, model, texts, glossary_dict, custom_prompt)

        # Build the translation result (keep the original text for verification)
        for node, translated in zip(batch, translated_texts):
            translated_nodes.append({
                'index': node['index'],
                'text': translated,  # Translated text
                'original': node['text'],  # Original text (used to verify before replacing)
                'file': node['file'],
                'type': node['type']
            })

        if on_batch_done:
            on_batch_done(len(batch))

    return translated_nodes


def translate_batch(client, model, texts, glossary_dict, custom_prompt=""):
    """
    Translate a batch of text

    Args:
        client: OpenAI client
        model: Model name
        texts: List of texts to translate
        glossary_dict: Glossary
        custom_prompt: Custom prompt prefix

    Returns:
        List[str]: Translation results
    """
    if not texts:
        return []

    # Build the prompt
    glossary_str = ""
    if glossary_dict:
        glossary_items = [f"{k} -> {v}" for k, v in list(glossary_dict.items())[:50]]
        glossary_str = "\n術語表：\n" + "\n".join(glossary_items)

    texts_json = json.dumps(texts, ensure_ascii=False)

    # Base prompt
    base_prompt = f"""請將以下韓文文本翻譯成繁體中文。

{glossary_str}

翻譯要求：
1. 保持原文的語氣和風格
2. 優先使用術語表中的翻譯
3. 保留段落結構
4. 自然流暢的中文表達"""

    # If a custom prompt is provided, prepend it
    if custom_prompt:
        full_prompt = f"{custom_prompt}\n\n{base_prompt}"
    else:
        full_prompt = base_prompt

    full_prompt += f"""

待翻譯文本（JSON 格式）：
{texts_json}

請嚴格返回 JSON 格式的翻譯結果（與輸入順序一致）：
["翻譯1", "翻譯2", ...]"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.3,
            max_tokens=8192
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        content = content.strip()

        translated = json.loads(content)

        # Verify the length
        if len(translated) != len(texts):
            print(f"Warning: translation count mismatch ({len(translated)} != {len(texts)})")
            # Pad or truncate to match
            while len(translated) < len(texts):
                translated.append(texts[len(translated)])
            translated = translated[:len(texts)]

        return translated

    except Exception as e:
        print(f"Translation batch failed: {e}")
        # Return the original text on failure
        return texts


if __name__ == '__main__':
    # Test
    import sys
    if len(sys.argv) > 1:
        epub_path = sys.argv[1]
        api_key = os.getenv('DEEPSEEK_API_KEY', '')

        if not api_key:
            print("請設置 DEEPSEEK_API_KEY 環境變量")
            sys.exit(1)

        def progress_callback(prog):
            print(f"{prog['message']} - {prog['percent']}%")

        result = translate_epub_streaming(epub_path, [], api_key, callback=progress_callback)
        print(f"翻譯完成：{result}")
