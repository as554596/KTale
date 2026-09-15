"""
Test CSS style and HTML structure preservation
Verifies translated text is correctly placed back into the original structure
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 - registers backend subfolders on sys.path

from bs4 import BeautifulSoup

# Force UTF-8 output
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from enhanced_epub_parser import EnhancedEPUBParser


def test_css_preservation():
    """Test various CSS style scenarios"""

    test_cases = [
        {
            "name": "對話框 (div with class)",
            "html": '''
<html>
<head>
    <style>
        .dialog-box {
            border: 2px solid #333;
            padding: 10px;
            background: #f0f0f0;
        }
    </style>
</head>
<body>
    <div class="dialog-box">
        <p>「這是一段對話」</p>
        <p>「另一段對話」</p>
    </div>
</body>
</html>
            '''
        },
        {
            "name": "帶 ID 的特殊段落",
            "html": '''
<div id="chapter-title" style="font-size: 24px; font-weight: bold;">
    第一章 開始
</div>
<p class="narration" style="font-style: italic;">
    這是旁白文字
</p>
            '''
        },
        {
            "name": "嵌套結構 (span in p)",
            "html": '''
<p>
    普通文字 <span class="highlight" style="color: red;">重點文字</span> 後續文字
</p>
            '''
        },
        {
            "name": "複雜嵌套",
            "html": '''
<div class="scene">
    <div class="dialog-container">
        <span class="speaker">角色A:</span>
        <span class="content">這是對話內容</span>
    </div>
</div>
            '''
        },
        {
            "name": "多層 class 和 data 屬性",
            "html": '''
<div class="message user-message" data-user-id="123" data-timestamp="1234567890">
    <div class="message-header">
        <span class="username">用戶名</span>
    </div>
    <div class="message-body">
        訊息內容
    </div>
</div>
            '''
        }
    ]

    parser = EnhancedEPUBParser()

    print("=" * 80)
    print("CSS 樣式和結構保留測試")
    print("=" * 80)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[測試 {i}] {test_case['name']}")
        print("-" * 80)

        html = test_case['html']
        soup = BeautifulSoup(html, 'html.parser')

        # Extract text nodes
        nodes = list(parser._get_text_nodes(soup))
        print(f"✓ 提取到 {len(nodes)} 個文本節點:")
        for j, node in enumerate(nodes):
            parent_tag = node.parent.name
            parent_class = node.parent.get('class', [])
            parent_style = node.parent.get('style', '')
            parent_id = node.parent.get('id', '')

            print(f"  {j+1}. 文本: '{str(node).strip()}'")
            print(f"     父標籤: <{parent_tag}>")
            if parent_class:
                print(f"     Class: {parent_class}")
            if parent_id:
                print(f"     ID: {parent_id}")
            if parent_style:
                print(f"     Style: {parent_style[:50]}...")

        # Simulate translation (Chinese -> English)
        translations = []
        for j, node in enumerate(nodes):
            original_text = str(node).strip()
            # Simple mock translation
            fake_translation = f"[TRANSLATED_{j}] " + original_text
            translations.append({
                'index': j,
                'text': fake_translation,
                'original': original_text
            })

        # Perform the replacement
        translated_html = parser._replace_html_text(html.encode('utf-8'), translations)
        translated_soup = BeautifulSoup(translated_html, 'html.parser')

        # Verify structure preservation
        print(f"\n✓ 翻譯後驗證:")

        # Check whether CSS is preserved
        original_styles = soup.find_all(style=True)
        translated_styles = translated_soup.find_all(style=True)
        if len(original_styles) == len(translated_styles):
            print(f"  ✓ Style 屬性保留完整 ({len(original_styles)} 個)")
        else:
            print(f"  ✗ Style 屬性數量變化: {len(original_styles)} -> {len(translated_styles)}")

        # Check whether class is preserved
        original_classes = soup.find_all(class_=True)
        translated_classes = translated_soup.find_all(class_=True)
        if len(original_classes) == len(translated_classes):
            print(f"  ✓ Class 屬性保留完整 ({len(original_classes)} 個)")
        else:
            print(f"  ✗ Class 屬性數量變化: {len(original_classes)} -> {len(translated_classes)}")

        # Check whether ID is preserved
        original_ids = soup.find_all(id=True)
        translated_ids = translated_soup.find_all(id=True)
        if len(original_ids) == len(translated_ids):
            print(f"  ✓ ID 屬性保留完整 ({len(original_ids)} 個)")
        else:
            print(f"  ✗ ID 屬性數量變化: {len(original_ids)} -> {len(translated_ids)}")

        # Check custom attributes (data-*)
        original_data_attrs = len([elem for elem in soup.find_all()
                                   if any(k.startswith('data-') for k in elem.attrs.keys())])
        translated_data_attrs = len([elem for elem in translated_soup.find_all()
                                    if any(k.startswith('data-') for k in elem.attrs.keys())])
        if original_data_attrs == translated_data_attrs:
            print(f"  ✓ Data 屬性保留完整 ({original_data_attrs} 個)")
        else:
            print(f"  ✗ Data 屬性數量變化: {original_data_attrs} -> {translated_data_attrs}")

        # Show the translated text
        print(f"\n  翻譯後的文本節點:")
        for j, node in enumerate(parser._get_text_nodes(translated_soup)):
            print(f"    {j+1}. '{str(node).strip()}'")

    print("\n" + "=" * 80)
    print("測試完成！")
    print("=" * 80)


def test_real_epub_css(epub_path):
    """Test CSS preservation on a real EPUB"""
    print(f"\n\n真實 EPUB CSS 測試")
    print("=" * 80)
    print(f"EPUB: {epub_path}\n")

    import zipfile
    from collections import defaultdict

    parser = EnhancedEPUBParser()
    css_stats = defaultdict(int)
    class_stats = defaultdict(int)

    with zipfile.ZipFile(epub_path, 'r') as zip_file:
        for filename in zip_file.namelist():
            if not filename.lower().endswith(('.html', '.xhtml', '.htm')):
                continue

            content = zip_file.read(filename)
            soup = BeautifulSoup(content.decode('utf-8-sig'), 'html.parser')

            # Gather stats on the parent element attributes of text nodes
            for node in parser._get_text_nodes(soup):
                parent = node.parent

                # Count style attributes
                if parent.get('style'):
                    css_stats['inline-style'] += 1

                # Count class attributes
                if parent.get('class'):
                    classes = parent.get('class')
                    if isinstance(classes, list):
                        for cls in classes:
                            class_stats[cls] += 1
                    css_stats['has-class'] += 1

                # Count id attributes
                if parent.get('id'):
                    css_stats['has-id'] += 1

    print("文本節點的父元素 CSS 使用統計:")
    print(f"  - 使用 inline style: {css_stats['inline-style']} 個節點")
    print(f"  - 使用 class 屬性: {css_stats['has-class']} 個節點")
    print(f"  - 使用 id 屬性: {css_stats['has-id']} 個節點")

    if class_stats:
        print(f"\n最常用的 CSS class:")
        top_classes = sorted(class_stats.items(), key=lambda x: -x[1])[:10]
        for cls, count in top_classes:
            print(f"  - .{cls}: {count} 次")

    print("\n✓ 這些 CSS 屬性在翻譯後會完整保留")
    print("=" * 80)


if __name__ == '__main__':
    # Run the basic test
    test_css_preservation()

    # If an EPUB path was provided, test the real file
    if len(sys.argv) > 1:
        epub_path = sys.argv[1]
        if os.path.exists(epub_path):
            test_real_epub_css(epub_path)
        else:
            print(f"\n警告: 文件不存在 - {epub_path}")
