"""
Flask backend API - supports EPUB and TXT translation
Separate API configs: glossary extraction, review, and translation
"""
import _paths  # noqa: F401 - registers backend subfolders on sys.path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import json
import time
import tempfile
from werkzeug.utils import secure_filename
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Config
UPLOAD_FOLDER = Path(tempfile.gettempdir()) / 'novel_translator_uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER = Path(tempfile.gettempdir()) / 'novel_translator_outputs'
OUTPUT_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'epub', 'txt'}
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Global state
tasks = {}
glossary_cache = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== Health Check ====================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0'})


# ==================== File Upload ====================

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a file (EPUB or TXT)"""
    from upload_handler import handle_upload

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'error': '沒有文件'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'status': 'error', 'error': '文件名為空'}), 400

    if not allowed_file(file.filename):
        return jsonify({'status': 'error', 'error': '不支持的文件格式（僅支持 .epub 和 .txt）'}), 400

    # Use the safe upload handler
    result = handle_upload(file, UPLOAD_FOLDER)

    if result['status'] == 'error':
        return jsonify(result), 500

    return jsonify(result)


# ==================== Glossary Extraction ====================

@app.route('/api/extract_glossary', methods=['POST'])
def extract_glossary():
    """Start a glossary extraction task (async, with real per-batch progress callbacks)"""
    print("=== Extract Glossary API Called ===")

    data = request.json
    task_id = data.get('task_id') or f'extract_{int(time.time() * 1000)}'

    files = data.get('files', [])
    api_key = (data.get('api_key') or '').strip()
    base_url = (data.get('base_url') or 'https://api.deepseek.com').strip()
    model = (data.get('model') or 'deepseek-chat').strip()
    custom_prompt = (data.get('custom_prompt') or '').strip()

    if not files:
        return jsonify({'status': 'error', 'error': '沒有文件'}), 400

    if not api_key:
        return jsonify({'status': 'error', 'error': '需要 API Key 來提取術語'}), 400

    if not api_key.startswith('sk-'):
        return jsonify({'status': 'error', 'error': 'API Key 格式錯誤（應以 sk- 開頭）'}), 400

    if not base_url.startswith('http'):
        return jsonify({'status': 'error', 'error': 'API URL 格式錯誤（應以 http 開頭）'}), 400

    # Verify the files exist
    for filepath in files:
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'error': f'文件不存在: {os.path.basename(filepath)}'}), 400

        if os.path.getsize(filepath) == 0:
            return jsonify({'status': 'error', 'error': f'文件為空: {os.path.basename(filepath)}'}), 400

    # Create task
    tasks[task_id] = {
        'status': 'processing',
        'progress': {'current': 0, 'total': 100, 'percent': 0, 'message': '準備中...'},
        'result': None,
        'error': None
    }

    import threading

    def extract_task():
        try:
            from glossary_extractor_llm import extract_glossary_with_llm

            def progress_callback(prog):
                tasks[task_id]['progress'] = prog

            glossary = extract_glossary_with_llm(
                files,
                api_key,
                base_url,
                model,
                callback=progress_callback
            )

            print(f"Extraction completed. Found {len(glossary)} terms")

            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = glossary
            tasks[task_id]['progress'] = {
                'current': len(glossary),
                'total': len(glossary),
                'percent': 100,
                'message': f'提取完成，共 {len(glossary)} 個術語'
            }

        except Exception as e:
            print(f"Error during extraction: {str(e)}")
            import traceback
            traceback.print_exc()
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)

    thread = threading.Thread(target=extract_task)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'success', 'task_id': task_id})


# ==================== Glossary Review ====================

@app.route('/api/review_glossary', methods=['POST'])
def review_glossary():
    """Start a glossary review task (async, with real per-batch progress callbacks)"""
    data = request.json
    task_id = data.get('task_id') or f'review_{int(time.time() * 1000)}'

    glossary = data.get('glossary', [])
    api_key = data.get('api_key')
    base_url = data.get('base_url', 'https://api.deepseek.com')
    model = data.get('model', 'deepseek-chat')
    custom_prompt = data.get('custom_prompt', '')
    novel_background = data.get('novel_background', '')
    output_language = data.get('output_language', 'traditional')

    if not api_key:
        return jsonify({'status': 'error', 'error': '需要 API Key'}), 400

    if not glossary:
        return jsonify({'status': 'error', 'error': '術語表為空'}), 400

    # Create task
    tasks[task_id] = {
        'status': 'processing',
        'progress': {'current': 0, 'total': 100, 'percent': 0, 'message': '準備中...'},
        'result': None,
        'error': None
    }

    import threading

    def review_task():
        try:
            from glossary_reviewer import review_glossary_with_llm
            from traditional_converter import unified_glossary, s2t_glossary

            def progress_callback(prog):
                tasks[task_id]['progress'] = prog

            # Review terms in batches
            reviewed_glossary = review_glossary_with_llm(
                glossary,
                api_key,
                base_url,
                model,
                novel_background=novel_background,
                custom_prompt=custom_prompt,
                callback=progress_callback
            )

            # Filter out terms suggested for deletion
            filtered_glossary = [
                term for term in reviewed_glossary
                if not term.get('should_delete', False)
            ]

            # Unify traditional/simplified based on the user's choice
            if output_language == 'simplified':
                filtered_glossary = s2t_glossary(filtered_glossary, to_simplified=True)
            else:
                filtered_glossary = unified_glossary(filtered_glossary)

            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = {
                'glossary': filtered_glossary,
                'original_count': len(glossary),
                'reviewed_count': len(filtered_glossary),
                'deleted_count': len(glossary) - len(filtered_glossary)
            }
            tasks[task_id]['progress'] = {
                'current': len(glossary),
                'total': len(glossary),
                'percent': 100,
                'message': '校對完成！'
            }

        except Exception as e:
            print(f"Error during review: {str(e)}")
            import traceback
            traceback.print_exc()
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)

    thread = threading.Thread(target=review_task)
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'success', 'task_id': task_id})


# ==================== Translation ====================

@app.route('/api/translate', methods=['POST'])
def translate():
    """Start a translation task (EPUB or TXT) - with quality checking"""
    data = request.json
    task_id = data.get('task_id')
    file_path = data.get('file')
    file_type = data.get('file_type')
    glossary = data.get('glossary', [])
    api_key = data.get('api_key')
    base_url = data.get('base_url', 'https://api.deepseek.com')
    model = data.get('model', 'deepseek-chat')
    custom_prompt = data.get('custom_prompt', '')
    max_workers = data.get('max_workers', 10)  # Default: 10 concurrent
    batch_size = data.get('batch_size', 20)   # Default: batch size of 20
    delay = data.get('delay', 0.3)  # Default: 0.3 second interval
    use_smart_translator = data.get('use_smart_translator', True)  # Added: whether to use the smart translator

    # Cap the max concurrency (to avoid overload)
    max_workers = min(max_workers, 20)
    batch_size = min(batch_size, 50)

    if not api_key:
        return jsonify({'status': 'error', 'error': '需要 API Key'}), 400

    if not file_path:
        return jsonify({'status': 'error', 'error': '沒有文件'}), 400

    # Create task
    tasks[task_id] = {
        'status': 'processing',
        'progress': {'current': 0, 'total': 100, 'percent': 0, 'message': '準備中...'},
        'file_path': file_path,
        'file_type': file_type,
        'result_file': None,
        'error': None,
        'stats': {}  # Added: stats info
    }

    # Start background translation
    import threading

    def translate_task():
        try:
            def progress_callback(prog):
                tasks[task_id]['progress'] = prog
                # Update stats info too, if present
                if 'stats' in prog:
                    tasks[task_id]['stats'] = prog['stats']

            # Use the smart translator (with quality checking)
            if use_smart_translator and file_type == 'txt':
                from smart_translator_txt import translate_txt_smart

                output_path, stats = translate_txt_smart(
                    file_path,
                    glossary,
                    api_key,
                    callback=progress_callback,
                    base_url=base_url,
                    model=model,
                    batch_size=batch_size,
                    custom_prompt=custom_prompt
                )

                tasks[task_id]['stats'] = stats

            # Traditional translation (no quality checking)
            elif file_type == 'epub':
                from translator import translate_epub_streaming

                output_path = translate_epub_streaming(
                    file_path,
                    glossary,
                    api_key,
                    callback=progress_callback,
                    base_url=base_url,
                    model=model,
                    max_workers=max_workers,
                    batch_size=batch_size,
                    delay=delay,
                    custom_prompt=custom_prompt
                )

            elif file_type == 'txt':
                from txt_translator import translate_txt_streaming

                output_path = translate_txt_streaming(
                    file_path,
                    glossary,
                    api_key,
                    callback=progress_callback,
                    base_url=base_url,
                    model=model,
                    batch_size=batch_size,
                    custom_prompt=custom_prompt
                )

            else:
                raise Exception(f"不支持的文件類型: {file_type}")

            # Task completed
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result_file'] = output_path

        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)

    thread = threading.Thread(target=translate_task)
    thread.daemon = True
    thread.start()

    return jsonify({
        'status': 'success',
        'task_id': task_id,
        'message': '翻譯任務已啟動（智能模式）' if use_smart_translator else '翻譯任務已啟動'
    })


# ==================== Progress Query ====================

@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """Query task progress"""
    if task_id not in tasks:
        return jsonify({'status': 'error', 'error': '任務不存在'}), 404

    task = tasks[task_id]

    return jsonify({
        'status': task['status'],
        'progress': task.get('progress', {}),
        'result_file': task.get('result_file'),
        'result': task.get('result'),
        'error': task.get('error')
    })


# ==================== File Download ====================

@app.route('/api/download/<path:filepath>', methods=['GET'])
def download_file(filepath):
    """Download the translated file"""
    filepath = Path(filepath)

    if not filepath.exists():
        return jsonify({'status': 'error', 'error': '文件不存在'}), 404

    return send_file(
        str(filepath),
        as_attachment=True,
        download_name=filepath.name
    )


# ==================== Glossary Review v2.0 ====================

@app.route('/api/glossary-review-round1', methods=['POST'])
def glossary_review_round1():
    """Round 1 review: basic check"""
    data = request.json
    glossary = data.get('glossary', [])
    novel_background = data.get('novel_background', '')
    api_key = data.get('api_key')
    base_url = data.get('base_url', 'https://api.deepseek.com')
    model = data.get('model', 'deepseek-chat')
    output_language = data.get('output_language', 'traditional')  # Added: output language option

    if not glossary or not api_key:
        return jsonify({'status': 'error', 'error': '缺少必要參數'}), 400

    try:
        import openai
        from glossary_review_engine import GlossaryReviewEngine
        from traditional_converter import unified_glossary, s2t_glossary

        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        engine = GlossaryReviewEngine(client, model)

        # Progress callback
        def progress_callback(prog):
            pass  # Could implement real-time progress push here

        reviewed_glossary, modifications = engine.first_round_review(
            glossary, novel_background, callback=progress_callback
        )

        # Convert based on the user's language choice
        if output_language == 'traditional':
            reviewed_glossary = unified_glossary(reviewed_glossary)
        elif output_language == 'simplified':
            reviewed_glossary = s2t_glossary(reviewed_glossary, to_simplified=True)

        return jsonify({
            'status': 'success',
            'reviewed_glossary': reviewed_glossary,
            'modifications': modifications
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/glossary-review-round2', methods=['POST'])
def glossary_review_round2():
    """Round 2 review: consistency check"""
    data = request.json
    glossary = data.get('glossary', [])
    novel_background = data.get('novel_background', '')
    api_key = data.get('api_key')
    base_url = data.get('base_url', 'https://api.deepseek.com')
    model = data.get('model', 'deepseek-chat')
    output_language = data.get('output_language', 'traditional')  # Added: output language option

    if not glossary or not api_key:
        return jsonify({'status': 'error', 'error': '缺少必要參數'}), 400

    try:
        import openai
        from glossary_review_engine import GlossaryReviewEngine
        from traditional_converter import unified_glossary, s2t_glossary

        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        engine = GlossaryReviewEngine(client, model)

        def progress_callback(prog):
            pass

        final_glossary, modifications = engine.second_round_review(
            glossary, novel_background, callback=progress_callback
        )

        # Convert based on the user's language choice
        if output_language == 'traditional':
            final_glossary = unified_glossary(final_glossary)
        elif output_language == 'simplified':
            final_glossary = s2t_glossary(final_glossary, to_simplified=True)

        return jsonify({
            'status': 'success',
            'final_glossary': final_glossary,
            'modifications': modifications
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/glossary-apply-manual-edits', methods=['POST'])
def glossary_apply_manual_edits():
    """Apply manual edits"""
    data = request.json
    glossary = data.get('glossary', [])
    edits = data.get('edits', [])

    if not glossary or not edits:
        return jsonify({'status': 'error', 'error': '缺少必要參數'}), 400

    try:
        from glossary_review_engine import GlossaryReviewEngine
        import openai

        # Create a temporary engine (no API needed)
        engine = GlossaryReviewEngine(None, None)

        updated_glossary, manual_modifications = engine.apply_manual_edits(
            glossary, edits
        )

        return jsonify({
            'status': 'success',
            'updated_glossary': updated_glossary,
            'manual_modifications': manual_modifications
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/glossary-unify-traditional', methods=['POST'])
def glossary_unify_traditional():
    """Unify the glossary to Traditional Chinese"""
    data = request.json
    glossary = data.get('glossary', [])

    if not glossary:
        return jsonify({'status': 'error', 'error': '缺少術語表'}), 400

    try:
        from traditional_converter import unified_glossary, check_mixed_chars

        # Unify conversion
        unified = unified_glossary(glossary)

        # Check what was fixed
        fixed_terms = []
        for orig, unif in zip(glossary, unified):
            if orig.get('dst') != unif.get('dst') or orig.get('info') != unif.get('info'):
                mixed_info = check_mixed_chars(orig.get('dst', ''))
                fixed_terms.append({
                    'src': orig['src'],
                    'original_dst': orig.get('dst', ''),
                    'unified_dst': unif.get('dst', ''),
                    'simplified_chars': mixed_info.get('simplified_chars', [])
                })

        return jsonify({
            'status': 'success',
            'unified_glossary': unified,
            'fixed_count': len(fixed_terms),
            'fixed_terms': fixed_terms
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ==================== Missed-Translation Review ====================

@app.route('/api/quality-report/<task_id>', methods=['GET'])
def get_quality_report(task_id):
    """Get the translation quality report"""
    if task_id not in tasks:
        return jsonify({'status': 'error', 'error': '任務不存在'}), 404

    task = tasks[task_id]
    if task['status'] != 'completed':
        return jsonify({'status': 'error', 'error': '任務尚未完成'}), 400

    # Locate the quality report file
    file_path = task.get('file_path', '')
    if not file_path:
        return jsonify({'status': 'error', 'error': '找不到源文件'}), 404

    report_path = file_path.replace('.txt', '_quality_report.json')

    if not os.path.exists(report_path):
        return jsonify({'status': 'error', 'error': '質量報告不存在'}), 404

    # Read the report
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    return jsonify({
        'status': 'success',
        'report': report
    })


@app.route('/api/retry-paragraph', methods=['POST'])
def retry_paragraph():
    """Retranslate a single paragraph"""
    data = request.json
    original_text = data.get('original')
    context = data.get('context', [])  # Preceding/following context
    glossary = data.get('glossary', [])
    api_key = data.get('api_key')
    base_url = data.get('base_url', 'https://api.deepseek.com')
    model = data.get('model', 'deepseek-chat')
    custom_prompt = data.get('custom_prompt', '')

    if not api_key or not original_text:
        return jsonify({'status': 'error', 'error': '缺少必要參數'}), 400

    try:
        import openai
        from smart_translator import SmartTranslator

        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        glossary_dict = {term['src']: term['dst'] for term in glossary if term.get('dst')}

        translator = SmartTranslator(
            client=client,
            model=model,
            glossary_dict=glossary_dict,
            chunk_size=1,
            context_lines=len(context),
            custom_prompt=custom_prompt
        )

        # Build the paragraph
        para = {'text': original_text, 'index': 0}
        context_paras = [{'text': c, 'index': -i-1} for i, c in enumerate(context)]

        # Translate
        result = translator._translate_chunk([para], context_paras)

        if result:
            return jsonify({
                'status': 'success',
                'translation': result[0]['text'],
                'confidence': result[0].get('confidence', 1.0)
            })
        else:
            return jsonify({'status': 'error', 'error': '翻譯失敗'}), 500

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/batch-retry', methods=['POST'])
def batch_retry():
    """Batch-retranslate multiple paragraphs"""
    data = request.json
    paragraphs = data.get('paragraphs', [])  # [{ index, original, context }]
    glossary = data.get('glossary', [])
    api_key = data.get('api_key')
    base_url = data.get('base_url', 'https://api.deepseek.com')
    model = data.get('model', 'deepseek-chat')
    custom_prompt = data.get('custom_prompt', '')

    if not api_key or not paragraphs:
        return jsonify({'status': 'error', 'error': '缺少必要參數'}), 400

    try:
        import openai
        from smart_translator import SmartTranslator

        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        glossary_dict = {term['src']: term['dst'] for term in glossary if term.get('dst')}

        translator = SmartTranslator(
            client=client,
            model=model,
            glossary_dict=glossary_dict,
            chunk_size=len(paragraphs),
            context_lines=0,
            custom_prompt=custom_prompt
        )

        # Build the paragraph list
        paras = [{'text': p['original'], 'index': p['index']} for p in paragraphs]

        # Translate
        results = translator.translate_paragraphs(paras)

        return jsonify({
            'status': 'success',
            'translations': [
                {
                    'index': r['index'],
                    'translation': r['text'],
                    'confidence': r.get('confidence', 1.0)
                }
                for r in results
            ]
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/update-translation', methods=['POST'])
def update_translation():
    """Update the translation result (after a manual edit)"""
    data = request.json
    task_id = data.get('task_id')
    updated_paragraphs = data.get('paragraphs', [])  # [{ index, text }]

    if task_id not in tasks:
        return jsonify({'status': 'error', 'error': '任務不存在'}), 404

    task = tasks[task_id]
    result_file = task.get('result_file')

    if not result_file or not os.path.exists(result_file):
        return jsonify({'status': 'error', 'error': '找不到翻譯文件'}), 404

    try:
        # Read the quality report
        report_path = task['file_path'].replace('.txt', '_quality_report.json')
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)

        # Update paragraphs
        all_paras = report['all_paragraphs']
        update_map = {p['index']: p['text'] for p in updated_paragraphs}

        for para in all_paras:
            if para['index'] in update_map:
                para['text'] = update_map[para['index']]
                para['confidence'] = 1.0  # Treat manual edits as high quality

        # Write the file back
        from txt_translator import TxtTranslator
        translator = TxtTranslator()
        translator.write_translated(all_paras, result_file)

        # Update the report
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return jsonify({'status': 'success', 'message': '更新成功'})

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ==================== Start Server ====================

# Serve frontend static files
@app.route('/')
def index():
    """Serve the frontend homepage"""
    return send_from_directory('../frontend', 'index_final.html')

# Explicit static file routes
@app.route('/app_final.js')
def serve_js():
    return send_from_directory('../frontend', 'app_final.js')

@app.route('/default_prompts.js')
def serve_default_prompts():
    return send_from_directory('../frontend', 'default_prompts.js')

@app.route('/default_prompts.local.js')
def serve_local_prompts():
    """Serve the uncommitted local prompt override, if present (git-ignored)"""
    local_path = os.path.join(os.path.dirname(__file__), '../frontend/default_prompts.local.js')
    if os.path.exists(local_path):
        return send_from_directory('../frontend', 'default_prompts.local.js')
    return '', 204

@app.route('/quality_checker.html')
def serve_quality_checker():
    return send_from_directory('../frontend', 'quality_checker.html')

@app.route('/quality_checker.js')
def serve_quality_checker_js():
    return send_from_directory('../frontend', 'quality_checker.js')

@app.route('/favicon.ico')
def serve_favicon():
    return send_from_directory('../frontend', 'favicon.ico')

# Don't use a catch_all route - let Flask return 404 for unknown paths

if __name__ == '__main__':
    import socket

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = '<run ipconfig / ifconfig to find your LAN IP>'

    print("=" * 60)
    print("KTale - Backend Server")
    print("=" * 60)
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print("=" * 60)
    print("Server starting...")
    print("Access at: http://localhost:5000")
    print(f"Mobile access (same WiFi): http://{local_ip}:5000")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
