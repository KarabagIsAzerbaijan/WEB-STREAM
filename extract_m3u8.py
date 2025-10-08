import os
import shutil
import requests
import re

# Canlı yayım URL-ləri siyahısı (məsələn Show TV, digər kanallar)
source_urls = {
    "showtv": "https://www.showtv.com.tr/canli-yayin",
    "nowtv": "https://www.nowtv.com.tr/canli-yayin",
    "tv4": "https://www.tv4.com.tr/canli-yayin",
    "kanal7": "https://www.kanal7.com/canli-izle",
    "showturk": "https://www.showturk.com.tr/canli-yayin/showturk",
    "Quran": "https://aloula.sba.sa/live/qurantvsa",
    "beyaztv": "https://beyaztv.com.tr/canli-yayin",
    "azeri": "https://sepehrtv.ir/live/sahar1",
     "kpz": "http://www.kepeztv.az/",
    # Digər kanallar əlavə edə bilərsən
}

stream_folder = "stream"

# Əgər stream qovluğu varsa, tam sil
if os.path.exists(stream_folder):
    shutil.rmtree(stream_folder)

# Yenidən stream qovluğunu yarat
os.makedirs(stream_folder)

def extract_m3u8(url):
    """
    yt-dlp istifadə etmədən, birbaşa URL-dən m3u8 linkini çıxarmaq üçün requests istifadə edirik.
    Amma daha mürəkkəb saytlar üçün yt-dlp tövsiyə olunur.
    """
    try:
        # Xətanın qarşısını almaq üçün başlıqları əlavə edirik
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
            "Referer": "https://sepehrtv.ir/"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        text = response.text
        
        # Sadə regex və ya axtarışla .m3u8 linki tapılır
        m3u8_matches = re.findall(r'https?://[^\s\'"]+\.m3u8[^\s\'"]*', text)
        if m3u8_matches:
            # URL-dəki '\u0026' kodunu '&' simvolu ilə əvəz edirik
            m3u8_url = m3u8_matches[0]
            m3u8_url = m3u8_url.replace('\\u0026', '&')
            return m3u8_url
        else:
            print(f"{url} saytında m3u8 tapılmadı.")
            return None
    except Exception as e:
        print(f"Xəta: {e}")
        return None

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
        m3u8_link = extract_m3u8(page_url)
        if m3u8_link:
            file_path = os.path.join(stream_folder, f"{name}.m3u8")
            write_multi_variant_m3u8(file_path, m3u8_link)
            print(f"{file_path} faylı yaradıldı.")
        else:
            print(f"{name} üçün link tapılmadı.")
