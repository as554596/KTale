"""
TXT file translation support
Supports translation of plain text novels
"""
import os
import re


class TxtTranslator:
    """TXT file translator"""

    def __init__(self):
        self.paragraphs = []

    def extract_paragraphs(self, txt_path, encoding='utf-8'):
        """
        Extract paragraphs from a TXT file

        Args:
            txt_path: TXT file path
            encoding: File encoding (default utf-8)

        Returns:
            List[dict]: List of paragraphs
        """
        paragraphs = []

        try:
            # Try different encodings
            encodings = [encoding, 'utf-8', 'utf-8-sig', 'gbk', 'big5']
            content = None

            for enc in encodings:
                try:
                    with open(txt_path, 'r', encoding=enc) as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if content is None:
                raise Exception("無法解碼文件，請檢查編碼")

            # Split into paragraphs (separated by blank lines)
            raw_paragraphs = re.split(r'\n\s*\n', content)

            for index, para in enumerate(raw_paragraphs):
                para = para.strip()
                if not para:
                    continue

                # Filter out lines that are pure symbols
                if re.match(r'^[=\-*#\s]+$', para):
                    continue

                paragraphs.append({
                    'text': para,
                    'index': index,
                    'original': para  # Keep original text for verification
                })

            self.paragraphs = paragraphs
            return paragraphs

        except Exception as e:
            raise Exception(f"讀取 TXT 失敗: {e}")

    def write_translated(self, paragraphs, output_path, encoding='utf-8'):
        """
        Write translated paragraphs back to a TXT file

        Args:
            paragraphs: List of translated paragraphs [{index, text, original}]
            output_path: Output file path
            encoding: File encoding
        """
        # Sort by index
        sorted_paragraphs = sorted(paragraphs, key=lambda x: x['index'])

        # Join into text (paragraphs separated by double newline)
        content = '\n\n'.join(p['text'] for p in sorted_paragraphs)

        # Write to file
        with open(output_path, 'w', encoding=encoding) as f:
            f.write(content)

    def translate_txt(self, txt_path, client, model, glossary_dict, batch_size=10, custom_prompt="", callback=None):
        """
        Translate an entire TXT file

        Args:
            txt_path: Source TXT path
            client: OpenAI client
            model: Model name
            glossary_dict: Glossary dictionary
            batch_size: Batch size
            custom_prompt: Custom prompt
            callback: Progress callback function

        Returns:
            str: Path to the translated TXT
        """
        from translator import translate_batch
        import time

        # Extract paragraphs
        paragraphs = self.extract_paragraphs(txt_path)
        total = len(paragraphs)

        if total == 0:
            raise Exception("TXT 文件中沒有找到有效段落")

        # Translate in batches
        translated_paragraphs = []

        for i in range(0, total, batch_size):
            batch = paragraphs[i:i + batch_size]
            texts = [p['text'] for p in batch]

            # Translate this batch
            try:
                translated_texts = translate_batch(client, model, texts, glossary_dict, custom_prompt)

                # Build translation results
                for para, trans_text in zip(batch, translated_texts):
                    translated_paragraphs.append({
                        'index': para['index'],
                        'text': trans_text,
                        'original': para['original']
                    })

                # Update progress
                if callback:
                    callback({
                        'current': len(translated_paragraphs),
                        'total': total,
                        'percent': int((len(translated_paragraphs) / total) * 100),
                        'message': f'翻譯中... ({len(translated_paragraphs)}/{total})'
                    })

                # Avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                print(f"Batch translation failed: {e}")
                # Keep original text on failure
                for para in batch:
                    translated_paragraphs.append({
                        'index': para['index'],
                        'text': para['text'],
                        'original': para['original']
                    })

        # Generate output file name
        output_path = txt_path.replace('.txt', '_translated.txt')

        # Write back to file
        self.write_translated(translated_paragraphs, output_path)

        return output_path


def translate_txt_streaming(txt_path, glossary, api_key, callback=None,
                            base_url="https://api.deepseek.com",
                            model="deepseek-chat",
                            batch_size=10,
                            custom_prompt=""):
    """
    Stream-translate a TXT file (compatible with the EPUB translation interface)

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
        str: Path to the translated TXT
    """
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    # Build glossary dictionary
    glossary_dict = {term['src']: term['dst'] for term in glossary if term.get('dst')}

    # Use TxtTranslator
    translator = TxtTranslator()
    output_path = translator.translate_txt(
        txt_path,
        client,
        model,
        glossary_dict,
        batch_size=batch_size,
        custom_prompt=custom_prompt,
        callback=callback
    )

    return output_path


if __name__ == '__main__':
    # Test code
    import sys
    import os

    if len(sys.argv) > 1:
        txt_path = sys.argv[1]
        api_key = os.getenv('DEEPSEEK_API_KEY', '')

        if not api_key:
            print("請設置 DEEPSEEK_API_KEY 環境變量")
            sys.exit(1)

        def progress_callback(prog):
            print(f"{prog['message']} - {prog['percent']}%")

        print(f"開始翻譯: {txt_path}")
        result = translate_txt_streaming(txt_path, [], api_key, callback=progress_callback)
        print(f"翻譯完成: {result}")
