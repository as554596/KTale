# -*- coding: utf-8 -*-
"""
Test Traditional/Simplified Chinese selection
"""
import sys
import io
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: F401 - registers backend subfolders on sys.path

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from traditional_converter import (
    unified_to_traditional,
    unified_to_simplified,
    unified_glossary,
    s2t_glossary
)

print("=" * 60)
print("繁簡體選擇功能測試")
print("=" * 60)

# Test glossary
test_glossary = [
    {"src": "노아", "dst": "诺亚", "info": "男性人名"},
    {"src": "소피아", "dst": "索菲亞", "info": "女性人名"},
    {"src": "갤러리", "dst": "畫廊", "info": "地名"},
    {"src": "드래곤", "dst": "龍", "info": "專有名詞"},
]

print("\n原始術語表（混合）:")
for term in test_glossary:
    print(f"  {term['src']} -> {term['dst']} ({term['info']})")

print("\n" + "=" * 60)
print("測試1: 統一爲繁體（unified_glossary）")
print("=" * 60)

traditional = unified_glossary(test_glossary)
print("\n繁體結果:")
for term in traditional:
    print(f"  {term['src']} -> {term['dst']} ({term['info']})")

print("\n" + "=" * 60)
print("測試2: 轉換爲簡體（s2t_glossary to_simplified=True）")
print("=" * 60)

simplified = s2t_glossary(test_glossary, to_simplified=True)
print("\n簡體結果:")
for term in simplified:
    print(f"  {term['src']} -> {term['dst']} ({term['info']})")

print("\n" + "=" * 60)
print("測試3: 轉換爲繁體（s2t_glossary to_simplified=False）")
print("=" * 60)

traditional2 = s2t_glossary(test_glossary, to_simplified=False)
print("\n繁體結果:")
for term in traditional2:
    print(f"  {term['src']} -> {term['dst']} ({term['info']})")

print("\n" + "=" * 60)
print("✅ 測試完成")
print("=" * 60)
