import os
import sys
import requests
from requests.exceptions import RequestException

def download_file(url, filename):
    try:
        print(f'正在下载 {url}...')
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        print(f'下载完成: {filename} ({len(response.content)} 字节)')
        return True
    except RequestException as e:
        print(f'下载失败: {url}')
        print(f'错误: {e}')
        return False
    except Exception as e:
        print(f'发生错误: {e}')
        return False

def main():
    # JavaScript 库文件列表
    js_files = [
        'https://code.jquery.com/jquery-1.8.3.min.js',
        'https://code.jquery.com/ui/1.8.24/jquery-ui.min.js',
        'https://cdnjs.cloudflare.com/ajax/libs/jquery-cookie/1.4.1/jquery.cookie.min.js',
        'https://cdnjs.cloudflare.com/ajax/libs/dynatree/1.2.4/jquery.dynatree.min.js',
        'https://cdnjs.cloudflare.com/ajax/libs/jquery.tablesorter/2.31.3/js/jquery.tablesorter.min.js'
    ]

    # 确保目录存在
    js_dir = 'templates/js'
    try:
        print(f'创建目录: {js_dir}')
        os.makedirs(js_dir, exist_ok=True)
    except Exception as e:
        print(f'创建目录失败: {e}')
        return

    # 下载文件
    success_count = 0
    for url in js_files:
        filename = os.path.join(js_dir, url.split('/')[-1])
        if download_file(url, filename):
            success_count += 1

    print(f'\n下载完成: {success_count}/{len(js_files)} 个文件成功')

if __name__ == '__main__':
    main() 