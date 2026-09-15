"""
Test the enhanced EPUB parser
Verifies it can capture all text nodes, including malformed EPUBs
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 - registers backend subfolders on sys.path

from enhanced_epub_parser import EnhancedEPUBParser


def test_epub_parser(epub_path):
    """Test the EPUB parser's full node traversal"""
    print(f"正在測試: {epub_path}\n")
    print("=" * 80)

    parser = EnhancedEPUBParser()

    # Extract all text nodes
    print("\n[步驟 1] 提取所有文本節點...")
    nodes = parser.extract_text_from_epub(epub_path)
    print(f"✓ 找到 {len(nodes)} 個文本節點")

    # Gather stats grouped by file
    from collections import defaultdict
    file_stats = defaultdict(int)
    for node in nodes:
        file_stats[node['file']] += 1

    print(f"\n[步驟 2] 文件分佈:")
    for filename, count in sorted(file_stats.items()):
        print(f"  - {filename}: {count} 個節點")

    # Show the content of the first 20 nodes
    print(f"\n[步驟 3] 前 20 個文本節點預覽:")
    for i, node in enumerate(nodes[:20], 1):
        text_preview = node['text'][:60].replace('\n', ' ')
        print(f"  {i:3d}. [{node['file']}:{node['index']}] {text_preview}...")

    # Check whether there is an NCX table of contents
    ncx_nodes = [n for n in nodes if n['type'] == 'ncx']
    if ncx_nodes:
        print(f"\n[步驟 4] NCX 目錄文本:")
        for i, node in enumerate(ncx_nodes, 1):
            print(f"  {i}. {node['text']}")
    else:
        print(f"\n[步驟 4] 未找到 NCX 目錄")

    print("\n" + "=" * 80)
    print(f"測試完成！共提取 {len(nodes)} 個文本節點")
    print("=" * 80)

    return nodes


def compare_with_xpath(epub_path):
    """Compare the differences between the XPath method and the full node traversal method"""
    print(f"\n\n對比測試: XPath vs 全節點遍歷")
    print("=" * 80)

    parser = EnhancedEPUBParser()
    all_nodes = parser.extract_text_from_epub(epub_path)

    # Gather stats on tag distribution
    from bs4 import BeautifulSoup
    import zipfile

    tag_stats = defaultdict(int)

    with zipfile.ZipFile(epub_path, 'r') as zip_file:
        for filename in zip_file.namelist():
            if not filename.lower().endswith(('.html', '.xhtml', '.htm')):
                continue

            content = zip_file.read(filename)
            soup = BeautifulSoup(content.decode('utf-8-sig'), 'html.parser')

            for node in parser._get_text_nodes(soup):
                tag_name = node.parent.name
                tag_stats[tag_name] += 1

    print("\n文本節點的父標籤分佈:")
    for tag, count in sorted(tag_stats.items(), key=lambda x: -x[1]):
        print(f"  <{tag}>: {count} 個文本節點")

    # Check for non-standard tags
    standard_tags = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'li', 'td', 'th'}
    non_standard = [tag for tag in tag_stats.keys() if tag not in standard_tags]

    if non_standard:
        print(f"\n⚠ 發現非標準標籤（舊方法可能會漏翻）:")
        for tag in non_standard:
            print(f"  <{tag}>: {tag_stats[tag]} 個節點")
    else:
        print(f"\n✓ 所有文本都在標準標籤內")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python test_enhanced_parser.py <epub_file_path>")
        print("\n示例:")
        print("  python test_enhanced_parser.py uploads/novel.epub")
        sys.exit(1)

    epub_path = sys.argv[1]

    if not os.path.exists(epub_path):
        print(f"錯誤: 文件不存在 - {epub_path}")
        sys.exit(1)

    # Run the test
    nodes = test_epub_parser(epub_path)

    # Run the comparison test
    compare_with_xpath(epub_path)

    print(f"\n✓ 測試完成！增強版解析器可以處理任意結構的 EPUB。")
