"""
Test EPUB glossary extraction
Used to diagnose the issue where EPUB extraction returns 0 terms on mobile
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 - registers backend subfolders on sys.path

def test_epub_parsing(epub_path):
    """Test EPUB parsing"""
    print("=" * 60)
    print(f"測試 EPUB 文件: {epub_path}")
    print("=" * 60)

    # 1. Check whether the file exists
    if not os.path.exists(epub_path):
        print(f"❌ 文件不存在: {epub_path}")
        return False

    file_size = os.path.getsize(epub_path)
    print(f"✓ 文件大小: {file_size} bytes")

    # 2. Test the EPUB parser
    try:
        from enhanced_epub_parser import EnhancedEPUBParser
        print("✓ EnhancedEPUBParser 導入成功")

        parser = EnhancedEPUBParser()
        nodes = parser.extract_text_from_epub(epub_path)

        print(f"✓ 提取到 {len(nodes)} 個節點")

        if nodes:
            print("\n前 3 個節點:")
            for i, node in enumerate(nodes[:3]):
                text_preview = node['text'][:50] + ('...' if len(node['text']) > 50 else '')
                print(f"  [{i}] {node['file']} - {text_preview}")

            total_chars = sum(len(n['text']) for n in nodes)
            print(f"\n總字符數: {total_chars}")
        else:
            print("⚠️  沒有提取到任何文本節點")
            return False

        return True

    except Exception as e:
        print(f"❌ EPUB 解析失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_glossary_extraction(epub_path, api_key):
    """Test glossary term extraction"""
    print("\n" + "=" * 60)
    print("測試術語提取")
    print("=" * 60)

    try:
        from glossary_extractor_llm import extract_glossary_with_llm

        print(f"API Key: {api_key[:10]}...{api_key[-5:]}")

        glossary = extract_glossary_with_llm(
            [epub_path],
            api_key,
            "https://api.deepseek.com",
            "deepseek-chat",
            callback=None
        )

        print(f"\n✓ 提取到 {len(glossary)} 個術語")

        if glossary:
            print("\n前 5 個術語:")
            for i, term in enumerate(glossary[:5]):
                print(f"  [{i+1}] {term['src']} → {term.get('dst', '')} ({term['frequency']}次)")
        else:
            print("⚠️  沒有提取到任何術語")

        return glossary

    except Exception as e:
        print(f"❌ 術語提取失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    # Get it from command-line arguments
    if len(sys.argv) < 2:
        print("用法: python test_epub_extract.py <epub_path> [api_key]")
        sys.exit(1)

    epub_path = sys.argv[1]
    api_key = sys.argv[2] if len(sys.argv) > 2 else None

    # Test EPUB parsing
    if test_epub_parsing(epub_path):
        print("\n✓ EPUB 解析正常")

        # If an API key was provided, test glossary extraction
        if api_key:
            glossary = test_glossary_extraction(epub_path, api_key)
            if glossary:
                print("\n✓ 術語提取正常")
            else:
                print("\n❌ 術語提取異常")
        else:
            print("\n未提供 API Key，跳過術語提取測試")
    else:
        print("\n❌ EPUB 解析異常")
