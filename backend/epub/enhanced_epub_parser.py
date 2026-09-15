"""
Enhanced EPUB parser using full DOM node traversal.
Ensures no text is missed, no matter how complex the EPUB structure is.
"""
import os
import zipfile
import re
import tempfile
import shutil
from bs4 import BeautifulSoup, NavigableString, Comment
from collections import defaultdict


class EnhancedEPUBParser:
    """
    Enhanced EPUB parser
    - Traverses all text nodes (including malformed EPUBs)
    - Handles NCX table-of-contents files
    - Preserves the original HTML structure
    - Supports automatic glossary substitution
    """

    # Tags that don't need translation
    SKIP_TAGS = {'script', 'style', 'pre', 'code', 'meta', 'link', 'head'}

    def __init__(self):
        self.text_nodes = []  # Stores all text nodes
        self.file_map = defaultdict(list)  # Map of file -> text nodes

    def extract_text_from_epub(self, epub_path):
        """
        Extract all text nodes from an EPUB

        Args:
            epub_path: Path to the EPUB file

        Returns:
            List[dict]: [
                {
                    'text': 'original text',
                    'file': 'chapter1.html',
                    'index': 0,
                    'type': 'html' or 'ncx'
                }
            ]
        """
        text_nodes = []

        try:
            with zipfile.ZipFile(epub_path, 'r') as zip_file:
                for filename in zip_file.namelist():
                    # Only process content files
                    if not filename.lower().endswith(('.html', '.xhtml', '.htm', '.ncx')):
                        continue

                    try:
                        content = zip_file.read(filename)

                        if filename.lower().endswith('.ncx'):
                            # Extract NCX table-of-contents files with regex
                            nodes = self._extract_ncx_text(content, filename)
                        else:
                            # Traverse HTML files with BeautifulSoup
                            nodes = self._extract_html_text(content, filename)

                        text_nodes.extend(nodes)

                    except Exception as e:
                        print(f"Warning: Failed to parse {filename}: {e}")
                        continue

        except Exception as e:
            raise Exception(f"Failed to open EPUB: {e}")

        return text_nodes

    def _extract_html_text(self, content_bytes, filename):
        """Extract all text nodes from an HTML file"""
        nodes = []

        try:
            # Try several encodings
            content_str = None
            for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb18030', 'big5']:
                try:
                    content_str = content_bytes.decode(encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if content_str is None:
                # Last resort: decode while ignoring errors
                content_str = content_bytes.decode('utf-8', errors='ignore')

            soup = BeautifulSoup(content_str, 'html.parser')

            # Traverse all text nodes (using the exact same logic to keep ordering consistent)
            for index, node in enumerate(self._get_text_nodes(soup)):
                text = str(node).strip()
                if not text:
                    continue

                nodes.append({
                    'text': text,  # Original text
                    'file': filename,
                    'index': index,
                    'type': 'html',
                    'node_ref': node  # Keep a reference for later replacement
                })

        except Exception as e:
            print(f"HTML parse error in {filename}: {e}")
            import traceback
            traceback.print_exc()

        return nodes

    def _extract_ncx_text(self, content_bytes, filename):
        """Extract text from an NCX file (used for the table of contents)"""
        nodes = []

        try:
            content_str = content_bytes.decode('utf-8-sig')
            # Extract the content inside <text>...</text> tags
            texts = re.findall(r'<text>(.*?)</text>', content_str, flags=re.DOTALL)

            for index, text in enumerate(texts):
                text = text.strip()
                if not text:
                    continue

                nodes.append({
                    'text': text,
                    'file': filename,
                    'index': index,
                    'type': 'ncx'
                })

        except Exception as e:
            print(f"NCX parse error in {filename}: {e}")

        return nodes

    def _get_text_nodes(self, soup):
        """
        Traverse the BeautifulSoup tree and return all text nodes that need translation

        Filter rules:
        1. Skip comments
        2. Skip script/style and other tags
        3. Skip whitespace-only text
        """
        for node in soup.find_all(text=True):
            # Skip comments
            if isinstance(node, Comment):
                continue

            # Skip tags that don't need translation
            if node.parent.name in self.SKIP_TAGS:
                continue

            # Skip pure whitespace
            if not node.strip():
                continue

            yield node

    def translate_epub(self, epub_path, translations, output_path):
        """
        Write the translated text back into the EPUB

        Args:
            epub_path: Path to the source EPUB
            translations: dict - {file: [{index: 0, text: 'translation'}]}
            output_path: Path to the output EPUB
        """
        temp_dir = tempfile.mkdtemp()

        try:
            # Unpack the EPUB
            with zipfile.ZipFile(epub_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Process each file
            for filename, trans_list in translations.items():
                file_path = os.path.join(temp_dir, filename)
                if not os.path.exists(file_path):
                    continue

                with open(file_path, 'rb') as f:
                    content = f.read()

                try:
                    if filename.lower().endswith('.ncx'):
                        # Replace text in NCX files with regex
                        new_content = self._replace_ncx_text(content, trans_list)
                    else:
                        # Replace text in HTML files with BeautifulSoup
                        new_content = self._replace_html_text(content, trans_list)

                    # Write the file back
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)

                except Exception as e:
                    print(f"Failed to translate {filename}: {e}")

            # Repackage the EPUB
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zip_out.write(file_path, arcname)

        finally:
            # Clean up the temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _replace_html_text(self, content_bytes, translations):
        """Replace text in an HTML file"""
        content_str = content_bytes.decode('utf-8-sig')
        soup = BeautifulSoup(content_str, 'html.parser')

        # Build an index map (also keeping the original text for verification)
        trans_map = {}
        for t in translations:
            trans_map[t['index']] = {
                'original': t.get('original', ''),  # Original text (used for verification)
                'translated': t['text']  # Translated text
            }

        # Traverse nodes using the exact same logic as extraction, to keep ordering consistent
        replaced_count = 0
        mismatched_count = 0

        for index, node in enumerate(self._get_text_nodes(soup)):
            if index >= len(translations):
                # More nodes than translations, stop to avoid misalignment
                break

            if index in trans_map:
                current_text = str(node).strip()
                trans_info = trans_map[index]
                translated = trans_info['translated']
                original = trans_info.get('original', '')

                # Safety check: if the original text is provided, make sure it matches the current node
                if original:
                    # Compare the first 50 characters (to tolerate whitespace differences)
                    current_prefix = current_text[:50].strip()
                    original_prefix = original[:50].strip()

                    if current_prefix != original_prefix:
                        mismatched_count += 1
                        print(f"Warning: Text mismatch at index {index}")
                        print(f"  Expected: {original_prefix}")
                        print(f"  Got: {current_prefix}")
                        # Skip on mismatch to avoid misaligned translation
                        continue

                # Perform the replacement (only when there's a translation and it differs from the original)
                if translated and translated != current_text:
                    node.replace_with(translated)
                    replaced_count += 1

        if mismatched_count > 0:
            print(f"Warning: {mismatched_count} text nodes mismatched during replacement")

        return str(soup)

    def _replace_ncx_text(self, content_bytes, translations):
        """Replace text in an NCX file"""
        content_str = content_bytes.decode('utf-8-sig')

        # Build an index map
        trans_map = {t['index']: t['text'] for t in translations}
        current_index = 0

        def ncx_replacer(match):
            nonlocal current_index
            original_text = match.group(1).strip()

            if not original_text:
                return match.group(0)

            replacement = trans_map.get(current_index, original_text)
            current_index += 1

            return f'<text>{replacement}</text>'

        new_content = re.sub(
            r'<text>(.*?)</text>',
            ncx_replacer,
            content_str,
            flags=re.DOTALL
        )

        return new_content

    def extract_text_for_glossary(self, epub_path, min_frequency=2):
        """
        Extract a glossary (Korean vocabulary)

        Args:
            epub_path: Path to the EPUB
            min_frequency: Minimum occurrence count

        Returns:
            List[dict]: [{'src': 'Korean term', 'frequency': count}]
        """
        from collections import Counter

        korean_pattern = re.compile(r'[가-힣]{2,}')
        term_counter = Counter()

        # Extract all text nodes
        text_nodes = self.extract_text_from_epub(epub_path)

        # Count Korean vocabulary occurrences
        for node in text_nodes:
            text = node['text']
            matches = korean_pattern.findall(text)
            term_counter.update(matches)

        # Filter out low-frequency terms
        filtered_terms = [
            {'src': term, 'dst': '', 'frequency': count}
            for term, count in term_counter.items()
            if count >= min_frequency
        ]

        # Sort by frequency
        filtered_terms.sort(key=lambda x: x['frequency'], reverse=True)

        return filtered_terms


# Wrapper kept for backward compatibility with the original interface
def extract_terms_from_epub(epub_path, batch_size=10):
    """Wrapper for backward compatibility with the original interface"""
    parser = EnhancedEPUBParser()
    return parser.extract_text_for_glossary(epub_path, min_frequency=2)


def extract_context_from_epub(epub_path, term, max_contexts=3):
    """Extract context around a term"""
    parser = EnhancedEPUBParser()
    text_nodes = parser.extract_text_from_epub(epub_path)

    contexts = []
    context_pattern = re.compile(
        f'.{{0,30}}{re.escape(term)}.{{0,30}}',
        re.UNICODE
    )

    for node in text_nodes:
        if len(contexts) >= max_contexts:
            break

        text = node['text']
        matches = context_pattern.findall(text)
        contexts.extend(matches[:max_contexts - len(contexts)])

    return contexts


if __name__ == '__main__':
    # Test code
    import sys

    if len(sys.argv) > 1:
        epub_path = sys.argv[1]
        parser = EnhancedEPUBParser()

        print("提取所有文本節點...")
        nodes = parser.extract_text_from_epub(epub_path)
        print(f"找到 {len(nodes)} 個文本節點")

        print("\n前 10 個節點:")
        for i, node in enumerate(nodes[:10], 1):
            print(f"{i}. [{node['file']}] {node['text'][:50]}...")

        print("\n提取術語表...")
        terms = parser.extract_text_for_glossary(epub_path)
        print(f"找到 {len(terms)} 個高頻術語")

        print("\n前 10 個高頻術語:")
        for i, term in enumerate(terms[:10], 1):
            print(f"{i}. {term['src']} - {term['frequency']}次")
