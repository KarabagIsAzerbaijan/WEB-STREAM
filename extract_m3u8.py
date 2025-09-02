import os
import shutil
import requests
import re

# Canlı yayım URL-ləri siyahısı
source_urls = {
    "showtv": "https://www.showtv.com.tr/canli-yayin",
    "nowtv": "https://www.nowtv.com.tr/canli-yayin",
    "tv4": "https://www.tv4.com.tr/canli-yayin",
    "kanal7": "https://www.kanal7.com/canli-izle",
    "showturk": "https://www.showturk.com.tr/canli-yayin/showturk",
    "Quran": "https://aloula.sba.sa/live/qurantvsa",
    "beyaztv": "https://beyaztv.com.tr/canli-yayin",
    "azeri": "https://sepehrtv.ir/live/sahar1",
}

stream_folder = "stream"

if os.path.exists(stream_folder):
    shutil.rmtree(stream_folder)

os.makedirs(stream_folder)

def get_azeri_m3u8():
    """
    Sahar Azeri TV üçün xüsusi olaraq hazırlanmış funksiya.
    M3u8 linkini JavaScript faylının içindən çıxarır.
    """
    html_url = "https://sepehrtv.ir/live/sahar1"
    
    # Canlı yayın linkini ehtiva edən JavaScript faylının URL-i
    js_url_template = "https://lb-cdn.sepehrtv.ir/_next/static/chunks/pages/_app-{}.js"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        "Referer": "https://sepehrtv.ir/"
    }
    
    try:
        html_response = requests.get(html_url, headers=headers, timeout=10)
        html_response.raise_for_status()
        html_content = html_response.text
        
        # HTML-dən JavaScript faylının adını axtarırıq
        js_match = re.search(r'/_next/static/chunks/pages/_app-([a-f0-9]+)\.js', html_content)
        
        if not js_match:
            return "JS faylı tapılmadı."
            
        js_file_hash = js_match.group(1)
        js_url = js_url_template.format(js_file_hash)
        
        js_response = requests.get(js_url, headers=headers, timeout=10)
        js_response.raise_for_status()
        js_content = js_response.text
        
        # M3U8 linkini JavaScript faylında axtarırıq
        match = re.search(r'src:"(https:\/\/.*?-cdn\.sepehrtv\.(?:org|ir)\/securelive3\/saharazarsd\/saharazarsd\.m3u8\?s=[^&]+&t=\d+)"', js_content)
        
        if match:
            m3u8_url = match.group(1)
            # URL-dəki '\u0026' kodunu '&' simvolu ilə əvəz edir
            m3u8_url = m3u8_url.replace('\\u0026', '&')
            return m3u8_url
        else:
            return "M3U8 linki tapılmadı."
            
    except requests.exceptions.RequestException as e:
        return f"İstək xətası: {e}"

def extract_m3u8(url):
    """
    Digər kanallar üçün m3u8 linkini çıxarmaq
    """
    # ...
    # Əvvəlki kodunuz burada qalır
    # ...

def write_multi_variant_m3u8(filename, url):
    """
    multi-variant m3u8 üçün minimal nümunə yaratmaq:
    """
    content = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        f"#EXT-X-STREAM-INF:BANDWIDTH=1500000,RESOLUTION=1280x720\n"
        f"{url}\n"
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    for name, page_url in source_urls.items():
        if name == "azeri":
            m3u8_link = get_azeri_m3u8()
        else:
            m3u8_link = extract_m3u8(page_url)
        
        if m3u8_link and "Xəta" not in m3u8_link:
            file_path = os.path.join(stream_folder, f"{name}.m3u8")
            write_multi_variant_m3u8(file_path, m3u8_link)
            print(f"{file_path} faylı yaradıldı.")
        else:
            print(f"{name} üçün link tapılmadı. Xəta: {m3u8_link}")
