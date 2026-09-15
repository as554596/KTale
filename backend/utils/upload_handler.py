# -*- coding: utf-8 -*-
"""
Safe file upload handling - avoids Unicode encoding errors
"""
import re
import time
import sys
import io

# Set stdout to UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def safe_print(*args, **kwargs):
    """Safe print function that avoids encoding errors"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # If printing fails, fall back to repr
        safe_args = [repr(arg) if isinstance(arg, str) else arg for arg in args]
        print(*safe_args, **kwargs)


def handle_upload(file, upload_folder):
    """
    Handle file upload, supporting Unicode filenames

    Args:
        file: Flask request.files['file']
        upload_folder: Path object

    Returns:
        dict: {'status': 'success'/'error', 'filename': ..., 'filepath': ..., ...}
    """
    safe_print("=== Upload File Handler ===")

    try:
        original_filename = file.filename
        safe_print(f"Uploading file (length: {len(original_filename)})")

        # Extract the file extension
        if '.' in original_filename:
            name_part = original_filename.rsplit('.', 1)[0]
            ext = original_filename.rsplit('.', 1)[1].lower()
        else:
            name_part = original_filename
            ext = ''

        # Only remove dangerous characters, keep Unicode characters
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name_part)

        # If the filename is empty, use a timestamp
        if not safe_name.strip():
            safe_name = 'file'

        # Generate a unique filename
        timestamp = str(int(time.time() * 1000))
        unique_filename = f"{timestamp}_{safe_name}.{ext}" if ext else f"{timestamp}_{safe_name}"
        filepath = upload_folder / unique_filename

        safe_print(f"Saving with timestamp: {timestamp}")

        # Save the file
        file.save(str(filepath))

        # Verify
        if not filepath.exists():
            return {
                'status': 'error',
                'error': '文件保存失敗'
            }

        file_size = filepath.stat().st_size
        safe_print(f"Saved successfully: {file_size} bytes")

        file_type = 'epub' if ext == 'epub' else 'txt'

        return {
            'status': 'success',
            'filename': original_filename,
            'filepath': str(filepath),
            'file_type': file_type,
            'file_size': file_size
        }

    except Exception as e:
        safe_print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'error': f'上傳失敗: {str(e)}'
        }
